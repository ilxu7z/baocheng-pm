#!/usr/bin/env python3
"""ocr_bridge.py — open-code-review CLI 的统一 Python 封装

为三省六部看板提供结构化调用接口。
不依赖 oc-macs 其他模块，可独立使用。
零依赖：仅 Python 标准库。
"""

import json
import os
import subprocess
import time
import threading
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# ── 配置 ────────────────────────────────────────────

OCR_BIN = "ocr"
OCR_RESULTS_DIR = Path(__file__).parent.parent / "data" / "ocr_results"
DEFAULT_TIMEOUT = 300
MAX_CONCURRENT = 2

# 并发控制
_review_semaphore = threading.Semaphore(MAX_CONCURRENT)

# ── 数据模型 ─────────────────────────────────────────

@dataclass
class OcrComment:
    """单条审查评论 — 对应 OCR JSON 的 LlmComment"""
    path: str
    content: str
    start_line: int
    end_line: int
    suggestion_code: str = ""
    existing_code: str = ""
    thinking: str = ""
    category: str = ""
    severity: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "OcrComment":
        return cls(
            path=d.get("path", ""),
            content=d.get("content", ""),
            start_line=d.get("start_line", 0),
            end_line=d.get("end_line", 0),
            suggestion_code=d.get("suggestion_code", ""),
            existing_code=d.get("existing_code", ""),
            thinking=d.get("thinking", ""),
            category=d.get("category", ""),
            severity=d.get("severity", ""),
        )


@dataclass
class OcrSummary:
    """审查摘要 — 对应 OCR JSON 的 summary 字段"""
    files_reviewed: int = 0
    comments: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    elapsed: str = ""
    budget_exceeded: bool = False


@dataclass
class OcrToolCalls:
    """工具调用统计"""
    total: int = 0
    by_tool: dict = field(default_factory=dict)


@dataclass
class OcrReviewResult:
    """完整的 OCR 审查结果"""
    success: bool
    session_id: str = ""
    trace_id: str = ""
    summary: OcrSummary = field(default_factory=OcrSummary)
    comments: list = field(default_factory=list)
    tool_calls: OcrToolCalls = field(default_factory=OcrToolCalls)
    project_summary: str = ""
    error: str = ""
    raw_json: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "summary": asdict(self.summary),
            "comments": [asdict(c) for c in self.comments] if self.comments else None,
            "tool_calls": asdict(self.tool_calls),
            "project_summary": self.project_summary,
            "error": self.error,
        }

    def has_critical(self) -> bool:
        """是否有 critical 或 high 级别的缺陷"""
        if not self.comments:
            return False
        return any(c.severity in ("critical", "high") for c in self.comments)

    def critical_comments(self) -> list:
        """返回 critical + high 级别的评论"""
        if not self.comments:
            return []
        return [c for c in self.comments if c.severity in ("critical", "high")]


# ── 核心函数 ─────────────────────────────────────────

def _find_json_line(stdout: str) -> str:
    """从 OCR 输出中提取 JSON 内容（支持多行格式化 JSON）"""
    start = stdout.find("{")
    if start < 0:
        return stdout
    # 从第一个 { 开始，找到匹配的 } 结束
    depth = 0
    for i in range(start, len(stdout)):
        if stdout[i] == "{":
            depth += 1
        elif stdout[i] == "}":
            depth -= 1
        if depth == 0:
            return stdout[start:i+1]
    return stdout[start:]


def _parse_json_output(stdout: str) -> dict:
    """解析 OCR JSON 输出（支持多行格式化 JSON）"""
    json_str = _find_json_line(stdout)
    if not json_str:
        raise ValueError("OCR 输出中未找到 JSON")
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # 如果 JSON 提取不完整，尝试直接解析整个 stdout
        start = stdout.find("{")
        if start >= 0:
            return json.loads(stdout[start:])
        raise


def _run_ocr(args: list, timeout: int = DEFAULT_TIMEOUT) -> OcrReviewResult:
    """执行 ocr CLI 并解析 JSON 输出"""
    cmd = [OCR_BIN] + args
    env = os.environ.copy()
    # 强制使用 OpenAI 协议（OCR 1.8.3 默认走 Anthropic 协议导致 URL 拼接错误）
    if "OCR_LLM_PROTOCOL" not in env:
        env["OCR_LLM_PROTOCOL"] = "openai"
    try:
        with _review_semaphore:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
                env=env,
            )
    except subprocess.TimeoutExpired:
        return OcrReviewResult(
            success=False,
            error=f"审查超时（>{timeout}秒）",
        )
    except FileNotFoundError:
        return OcrReviewResult(
            success=False,
            error="OCR CLI 未找到。请先安装: npm install -g --allow-scripts=@alibaba-group/open-code-review @alibaba-group/open-code-review",
        )

    # P0-2: OCR JSON 输出在 stderr 而不是 stdout，先试 stderr 再试 stdout
    raw = result.stderr.strip() or result.stdout.strip()
    stdout = raw

    try:
        data = _parse_json_output(stdout)
    except (json.JSONDecodeError, ValueError):
        return OcrReviewResult(
            success=False,
            error=f"无法解析 OCR 输出\nstderr: {result.stderr.strip()[:500]}\nstdout: {result.stdout.strip()[:500]}",
        )

    # 解析摘要
    s = data.get("summary", {})
    summary = OcrSummary(
        files_reviewed=s.get("files_reviewed", 0),
        comments=s.get("comments", 0),
        total_tokens=s.get("total_tokens", 0),
        input_tokens=s.get("input_tokens", 0),
        output_tokens=s.get("output_tokens", 0),
        cache_read_tokens=s.get("cache_read_tokens", 0),
        cache_write_tokens=s.get("cache_write_tokens", 0),
        elapsed=s.get("elapsed", ""),
        budget_exceeded=s.get("budget_exceeded", False),
    )

    # 解析评论列表 — 注意: comments 可能是 null
    raw_comments = data.get("comments")
    if raw_comments is None:
        comments = []
    elif isinstance(raw_comments, list):
        comments = [OcrComment.from_dict(c) for c in raw_comments]
    else:
        comments = []

    # 解析工具调用
    tc = data.get("tool_calls", {})
    tool_calls = OcrToolCalls(
        total=tc.get("total", 0),
        by_tool=tc.get("by_tool", {}),
    )

    is_success = data.get("status") != "error"

    return OcrReviewResult(
        success=is_success,
        session_id=data.get("session_id", ""),
        trace_id=data.get("trace_id", ""),
        summary=summary,
        comments=comments,
        tool_calls=tool_calls,
        project_summary=data.get("project_summary", ""),
        raw_json=data,
    )


def ocr_review(
    repo_dir: str,
    rule_path: Optional[str] = None,
    from_branch: Optional[str] = None,
    to_branch: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> OcrReviewResult:
    """基于 Git diff 的代码审查"""
    args = [
        "review",
        "--repo", repo_dir,
        "--format", "json",
        "--audience", "agent",
    ]
    if rule_path:
        args.extend(["--rule", rule_path])
    if from_branch:
        args.extend(["--from", from_branch])
    if to_branch:
        args.extend(["--to", to_branch])
    return _run_ocr(args, timeout=timeout)


def ocr_scan(
    repo_dir: str,
    rule_path: Optional[str] = None,
    paths: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> OcrReviewResult:
    """全量文件审查（不需要 diff）"""
    args = [
        "scan",
        "--repo", repo_dir,
        "--format", "json",
        "--audience", "agent",
    ]
    if rule_path:
        args.extend(["--rule", rule_path])
    if paths:
        args.extend(["--path", paths])
    return _run_ocr(args, timeout=timeout)


def ocr_resume(
    session_id: str,
    repo_dir: str,
    rule_path: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> OcrReviewResult:
    """恢复中断的审查"""
    args = [
        "review",
        "--repo", repo_dir,
        "--format", "json",
        "--audience", "agent",
        "--resume", session_id,
    ]
    if rule_path:
        args.extend(["--rule", rule_path])
    return _run_ocr(args, timeout=timeout)


def ocr_status() -> dict:
    """获取 OCR CLI 状态"""
    status = {
        "installed": False,
        "version": "",
        "llm_configured": False,
        "config_path": "~/.opencodereview/config.json",
    }

    try:
        result = subprocess.run(
            [OCR_BIN, "--version"],
            capture_output=True, text=True, timeout=5
        )
        status["installed"] = True
        status["version"] = result.stdout.strip().split("\n")[0]
    except Exception:
        return status

    # 检查 LLM 配置
    config_path = os.path.expanduser("~/.opencodereview/config.json")
    if os.path.exists(config_path):
        status["config_path"] = config_path
        try:
            with open(config_path) as f:
                config = json.load(f)
            status["llm_configured"] = bool(
                config.get("llm_url") or config.get("provider")
            )
        except Exception:
            pass

    if not status["llm_configured"]:
        env_vars = ["OCR_LLM_URL", "OCR_LLM_TOKEN", "OCR_LLM_MODEL"]
        status["llm_configured"] = all(
            os.environ.get(v) for v in env_vars
        )

    return status


def save_ocr_result(task_id: str, result: OcrReviewResult) -> str:
    """将审查结果保存到 JSON 文件（原子写入）"""
    OCR_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    session_tag = result.session_id[:8] if result.session_id else "unknown"
    filename = f"{task_id}_{session_tag}.json"
    filepath = OCR_RESULTS_DIR / filename

    data = result.to_dict()
    data["task_id"] = task_id
    data["saved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    tmp_path = filepath.with_suffix(".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.rename(filepath)

    return str(filepath)


# ── CLI 测试入口 ────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python ocr_bridge.py <command> [args...]")
        print("  status  - 检查 OCR 状态")
        print("  review <repo_dir> [rule_path] [from] [to]")
        print("  scan <repo_dir> [rule_path] [paths]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "status":
        print(json.dumps(ocr_status(), indent=2, ensure_ascii=False))
    elif cmd == "review":
        repo = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
        rule = sys.argv[3] if len(sys.argv) > 3 else None
        from_b = sys.argv[4] if len(sys.argv) > 4 else None
        to_b = sys.argv[5] if len(sys.argv) > 5 else None
        result = ocr_review(repo, rule, from_b, to_b)
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    elif cmd == "scan":
        repo = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()
        rule = sys.argv[3] if len(sys.argv) > 3 else None
        paths = sys.argv[4] if len(sys.argv) > 4 else None
        result = ocr_scan(repo, rule, paths)
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)