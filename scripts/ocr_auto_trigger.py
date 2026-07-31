#!/usr/bin/env python3
"""ocr_auto_trigger.py — 锋铸完成 → 自动 OCR 审查 → 缺陷创建任务

审查在 state 推进到 Review 时自动触发。
同步版，后续可改线程池。

依赖:
  - ocr_bridge.py (同目录)
  - data/ocr_dedup_cache.json (自动创建)
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from ocr_bridge import ocr_review, OcrReviewResult

DEDUP_CACHE = {}
CACHE_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "ocr_dedup_cache.json"
)


# ── 去重缓存 ──────────────────────────────────────────


def load_dedup_cache():
    """加载去重缓存 {task_id: commit_hash}"""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_dedup_cache(cache):
    """原子写入去重缓存"""
    tmp = CACHE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cache, f)
    os.rename(tmp, CACHE_FILE)


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
    """同 task + 同 commit 只审一次"""
    commit = get_current_commit(repo_dir)
    cache = load_dedup_cache()
    if cache.get(task_id) == commit:
        return False
    cache[task_id] = commit
    save_dedup_cache(cache)
    return True


# ── 自动审查 + 创建缺陷任务 ────────────────────────────


def auto_review_and_create_tasks(task_id, repo_dir, rule_path=None):
    """自动审查 + 收集需要创建任务的缺陷

    Returns:
        dict:
            - {"skipped": True, "reason": "dedup"}  → 同一 commit 已审过
            - {"error": "..."}                      → 审查失败
            - {"reviewed": True, ...}                → 审查成功，含 tasks_created
    """
    if not should_review(task_id, repo_dir):
        return {"skipped": True, "reason": "dedup"}

    result = ocr_review(repo_dir, rule_path)
    if not result.success:
        return {"error": result.error}

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
        })

    return {
        "reviewed": True,
        "session_id": result.session_id,
        "comments_total": result.summary.comments,
        "critical_count": len(created_tasks),
        "tasks_created": created_tasks,
    }


# ── CLI 测试入口 ──────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OCR 自动审查触发器")
    parser.add_argument("task_id", help="任务 ID")
    parser.add_argument("--repo", default=os.getcwd(), help="仓库目录")
    parser.add_argument("--rule", default=None, help="审查规则路径")
    args = parser.parse_args()

    result = auto_review_and_create_tasks(args.task_id, args.repo, args.rule)
    print(json.dumps(result, indent=2, ensure_ascii=False))