#!/usr/bin/env python3
"""ocr_auto_trigger.py — 锋铸完成 → 自动 OCR 审查 → 缺陷创建任务

审查在 state 推进到 Review 时自动触发。

依赖:
  - ocr_bridge.py (同目录)
  - data/ocr_dedup_cache.json (自动创建)
  - file_lock.py (原子读写)
  - kanban_update.py (看板更新)
"""

import json
import os
import sys
import time
import pathlib

sys.path.insert(0, os.path.dirname(__file__))

from ocr_bridge import ocr_review, OcrReviewResult, save_ocr_result

# ── 路径 ──────────────────────────────────────────────

_SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
CACHE_FILE = _PROJECT_ROOT / "data" / "ocr_dedup_cache.json"
DEFECTS_DIR = _PROJECT_ROOT / "data" / "ocr_results"

# ── 去重缓存（使用 file_lock.py 原子读写）───────────────

from file_lock import atomic_json_read, atomic_json_write  # noqa: E402


def load_dedup_cache():
    """加载去重缓存 {task_id: commit_hash}（原子读）"""
    data = atomic_json_read(CACHE_FILE, {})
    return data if isinstance(data, dict) else {}


def save_dedup_cache(cache):
    """写入去重缓存（原子写）"""
    atomic_json_write(CACHE_FILE, cache)


def clear_dedup_cache(task_id=None):
    """清除去重缓存。task_id 指定则只清除单个，否则全部清除。"""
    if task_id:
        def modifier(cache):
            if cache is None:
                cache = {}
            cache.pop(task_id, None)
            return cache
        # 用 atomic_json_update 精确修改
        from file_lock import atomic_json_update
        atomic_json_update(CACHE_FILE, modifier, {})
    else:
        atomic_json_write(CACHE_FILE, {})


# ── Git 辅助 ──────────────────────────────────────────


def get_current_commit(repo_dir):
    """获取当前 HEAD commit"""
    import subprocess

    r = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    return r.stdout.strip() if r.returncode == 0 else ""


# ── 去重检查 ──────────────────────────────────────────


def should_review(task_id, repo_dir):
    """同 task + 同 commit 只审一次（原子读写）"""
    commit = get_current_commit(repo_dir)
    cache = load_dedup_cache()
    if cache.get(task_id) == commit:
        return False
    # 原子更新
    def modifier(cache):
        if cache is None:
            cache = {}
        cache[task_id] = commit
        return cache
    from file_lock import atomic_json_update
    atomic_json_update(CACHE_FILE, modifier, {})
    return True


# ── 看板回写辅助 ──────────────────────────────────────


def _run_kanban_command(args):
    """运行 kanban_update.py 命令（独立子进程，不阻塞）"""
    import subprocess
    kanban_script = str(_SCRIPT_DIR / "kanban_update.py")
    cmd = [sys.executable, kanban_script] + list(args)
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        cwd=str(_PROJECT_ROOT),
    )


def _save_defects_json(task_id, result, created_tasks):
    """将缺陷信息写入 data/ocr_results/{task_id}.defects.json"""
    DEFECTS_DIR.mkdir(parents=True, exist_ok=True)
    defects_file = DEFECTS_DIR / f"{task_id}.defects.json"
    data = {
        "task_id": task_id,
        "session_id": result.session_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "critical_count": len(created_tasks),
        "defects": created_tasks,
        "usage": {
            "total_tokens": result.summary.total_tokens,
            "input_tokens": result.summary.input_tokens,
            "output_tokens": result.summary.output_tokens,
            "elapsed": result.summary.elapsed,
        },
    }
    tmp = defects_file.with_suffix(".defects.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.rename(defects_file)
    return str(defects_file)


# ── 自动审查 + 创建缺陷任务 ────────────────────────────


def auto_review_and_create_tasks(task_id, repo_dir, rule_path=None, update_kanban=True):
    """自动审查 + 创建缺陷 todo 任务 + 看板回写

    Args:
        task_id: 看板任务 ID
        repo_dir: Git 仓库目录
        rule_path: 可选的审查规则路径
        update_kanban: 是否回写看板（默认 True）

    Returns:
        dict:
            - {"skipped": True, "reason": "dedup"}  → 同一 commit 已审过
            - {"error": "..."}                      → 审查失败
            - {"reviewed": True, ...}                → 审查成功，含 tasks_created
    """
    start_time = time.time()

    # 1. 去重检查
    if not should_review(task_id, repo_dir):
        return {"skipped": True, "reason": "dedup"}

    # 2. 执行审查
    result = ocr_review(repo_dir, rule_path)
    elapsed = round(time.time() - start_time, 1)

    # 3. 处理审查失败（含超时）
    if not result.success:
        error_msg = result.error
        if "超时" in error_msg:
            if update_kanban:
                _run_kanban_command([
                    "progress", task_id,
                    f"OCR 审查超时（>{300}秒），建议手动重试",
                    "--elapsed", str(elapsed),
                ])
        return {
            "error": error_msg,
            "elapsed": elapsed,
        }

    # 4. 收集 critical/high 缺陷
    created_tasks = []
    for c in result.critical_comments():  # severity=critical|high
        title = (
            f"[OCR审查] {c.severity}: {c.path}:{c.start_line}"
            f" - {c.content[:50]}"
        )
        desc = (
            f"OCR 代码审查发现 {c.severity} 级别缺陷\n\n"
            f"**文件**: `{c.path}`:{c.start_line}-{c.end_line}\n"
            f"**类别**: {c.category}\n"
            f"**问题**: {c.content}\n\n"
            f"**现有代码**:\n```\n{c.existing_code}\n```\n\n"
            f"**建议修改**:\n```\n{c.suggestion_code}\n```\n\n"
            f"**审查会话**: {result.session_id}\n"
        )
        created_tasks.append({
            "title": title,
            "description": desc,
            "severity": c.severity,
            "path": c.path,
            "start_line": c.start_line,
            "end_line": c.end_line,
        })

    # 5. 保存 OCR 结果文件
    result_file = save_ocr_result(task_id, result)

    # 6. 保存缺陷 JSON（供总办手动创建 todo 时参考）
    defects_file = _save_defects_json(task_id, result, created_tasks)

    # 7. 回写看板
    if update_kanban:
        # 7a. 回写进展摘要
        summary_text = (
            f"OCR 审查完成: {result.summary.files_reviewed} 文件, "
            f"{result.summary.comments} 评论, "
            f"耗时 {result.summary.elapsed}, "
            f"critical/high={len(created_tasks)}"
        )
        _run_kanban_command([
            "progress", task_id, summary_text,
            "--elapsed", str(elapsed),
            "--tokens", str(result.summary.total_tokens),
        ])

        # 7b. 为每个 critical/high 缺陷创建 todo 子任务
        # todo_id 从 1 开始递增（由总办手动执行时决定 seq，此处自动创建供参考）
        for seq, defect in enumerate(created_tasks, start=1):
            todo_title = (
                f"{defect['severity']}: {defect['path']}:{defect['start_line']}"
            )
            _run_kanban_command([
                "todo", task_id, str(seq), todo_title, "not-started",
                "--detail", defect['description'],
            ])

    return {
        "reviewed": True,
        "session_id": result.session_id,
        "comments_total": result.summary.comments,
        "files_reviewed": result.summary.files_reviewed,
        "critical_count": len(created_tasks),
        "elapsed": elapsed,
        "result_file": result_file,
        "defects_file": defects_file,
        "tasks_created": created_tasks,
    }


# ── CLI 入口 ──────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OCR 自动审查触发器")
    parser.add_argument("task_id", nargs="?", default=None, help="任务 ID")
    parser.add_argument("--repo", default=os.getcwd(), help="仓库目录")
    parser.add_argument("--rule", default=None, help="审查规则路径")
    parser.add_argument(
        "--update-kanban", action="store_true", default=False,
        help="审查完成后回写看板（进度+缺陷todo）",
    )
    parser.add_argument(
        "--clear-cache", nargs="?", const="__all__", default=None,
        help="清除去重缓存。指定 task_id 只清除单个，否则全部清除",
    )
    args = parser.parse_args()

    # 清除缓存模式（不需要 task_id）
    if args.clear_cache:
        if args.clear_cache == "__all__":
            clear_dedup_cache()
            print(f"✅ 去重缓存已全部清除")
        else:
            clear_dedup_cache(args.clear_cache)
            print(f"✅ 去重缓存已清除: {args.clear_cache}")
        sys.exit(0)

    if not args.task_id:
        parser.print_help()
        sys.exit(1)

    result = auto_review_and_create_tasks(
        args.task_id, args.repo, args.rule,
        update_kanban=args.update_kanban,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))