#!/bin/bash
# 三省六部 · 数据刷新循环
# 用法: ./run_loop.sh [间隔秒数 [巡检间隔秒数]]
#   间隔秒数：数据刷新频率，默认 15 秒
#   巡检间隔秒数：自动重试卡住任务的频率，默认 120 秒

# 不使用 set -e：safe_run 内部已有 || true 兜底，
# 避免单个脚本非零退出导致整个循环终止（macOS 上 timeout 不可用，
# 无法限制脚本执行时间，只能靠内部超时保护）
# set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export EDICT_HOME="${EDICT_HOME:-$(dirname "$SCRIPT_DIR")}"
PYTHON_BIN="${EDICT_PYTHON:-python3}"
INTERVAL="${1:-15}"
LOG="/tmp/sansheng_liubu_refresh.log"
PIDFILE="/tmp/sansheng_liubu_refresh.pid"
MAX_LOG_SIZE=$((10 * 1024 * 1024))  # 10MB

# ── 单实例保护 ──
if [[ -f "$PIDFILE" ]]; then
  OLD_PID=$(cat "$PIDFILE" 2>/dev/null)
  if kill -0 "$OLD_PID" 2>/dev/null; then
    echo "❌ 已有实例运行中 (PID=$OLD_PID)，退出"
    exit 1
  fi
  rm -f "$PIDFILE"
fi
echo $$ > "$PIDFILE"

# ── 优雅退出 ──
cleanup() {
  echo "$(date '+%H:%M:%S') [loop] 收到退出信号，清理中..." >> "$LOG"
  rm -f "$PIDFILE"
  exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# ── 日志轮转 ──
rotate_log() {
  if [[ -f "$LOG" ]] && (( $(stat -f%z "$LOG" 2>/dev/null || stat -c%s "$LOG" 2>/dev/null || echo 0) > MAX_LOG_SIZE )); then
    mv "$LOG" "${LOG}.1"
    echo "$(date '+%H:%M:%S') [loop] 日志已轮转" > "$LOG"
  fi
}

SCAN_INTERVAL="${2:-120}"  # 巡检间隔(秒), 默认 120
SCAN_COUNTER=0
SCRIPT_TIMEOUT=30  # 单个脚本最大执行时间(秒)
DASHBOARD_PORT="${EDICT_DASHBOARD_PORT:-7891}"  # 看板端口，可通过环境变量覆盖
CLEANUP_INTERVAL=$((4 * 3600))  # Session 清理间隔(秒), 默认 4 小时
CLEANUP_COUNTER=0

# ── 重定向所有输出到日志（launchd 模式下 stdout/stderr 已在 plist 中配置，
#    但手动运行时也需要确保日志不丢失）──
if [[ -t 1 ]]; then
  echo "🏛️  三省六部数据刷新循环启动 (PID=$$)"
else
  echo "$(date '+%H:%M:%S') [loop] 🏛️  三省六部数据刷新循环启动 (PID=$$)" >> "$LOG"
fi
if [[ -t 1 ]]; then
  echo "   脚本目录: $SCRIPT_DIR"
  echo "   间隔: ${INTERVAL}s"
  echo "   巡检间隔: ${SCAN_INTERVAL}s"
  echo "   清理间隔: ${CLEANUP_INTERVAL}s"
  echo "   脚本超时: ${SCRIPT_TIMEOUT}s"
  echo "   日志: $LOG"
  echo "   PID文件: $PIDFILE"
  echo "   按 Ctrl+C 停止"
fi

# ── 安全执行（带超时保护）──
safe_run() {
  local script="$1"
  if command -v timeout &>/dev/null; then
    timeout "$SCRIPT_TIMEOUT" "$PYTHON_BIN" "$script" >> "$LOG" 2>&1 || {
      local rc=$?
      if [[ $rc -eq 124 ]]; then
        echo "$(date '+%H:%M:%S') [loop] ⚠️ 脚本超时(${SCRIPT_TIMEOUT}s): $script" >> "$LOG"
      fi
    }
  else
    # macOS 无 timeout 命令，用 Python 自带 subprocess 超时
    "$PYTHON_BIN" -c "
import subprocess, sys
try:
    subprocess.run([sys.executable] + sys.argv[1:], timeout=$SCRIPT_TIMEOUT)
except subprocess.TimeoutExpired:
    import datetime
    print(f'{datetime.datetime.now().strftime(\"%H:%M:%S\")} [loop] ⚠️ 脚本超时(${SCRIPT_TIMEOUT}s): {sys.argv[1]}')
except Exception as e:
    print(f'[loop] 脚本异常: {e}')
" "$script" >> "$LOG" 2>&1 || true
  fi
}

while true; do
  rotate_log
  safe_run "$SCRIPT_DIR/sync_from_openclaw_runtime.py"
  safe_run "$SCRIPT_DIR/sync_agent_config.py"
  safe_run "$SCRIPT_DIR/apply_model_changes.py"
  safe_run "$SCRIPT_DIR/sync_officials_stats.py"
  safe_run "$SCRIPT_DIR/knowledge_bridge.py" sync
  safe_run "$SCRIPT_DIR/refresh_live_data.py"

  # 定期巡检：检测卡住的任务并自动重试
  SCAN_COUNTER=$((SCAN_COUNTER + INTERVAL))
  if (( SCAN_COUNTER >= SCAN_INTERVAL )); then
    SCAN_COUNTER=0
    curl -s -X POST "http://127.0.0.1:${DASHBOARD_PORT}/api/scheduler-scan" \
      -H 'Content-Type: application/json' -d '{"thresholdSec":180}' >> "$LOG" 2>&1 || true
  fi

  # 定期清理：清理过期 session 文件，防止膨胀
  CLEANUP_COUNTER=$((CLEANUP_COUNTER + INTERVAL))
  if (( CLEANUP_COUNTER >= CLEANUP_INTERVAL )); then
    CLEANUP_COUNTER=0
    echo "$(date '+%H:%M:%S') [loop] 🧹 开始 session 清理" >> "$LOG"
    "$PYTHON_BIN" "$SCRIPT_DIR/session_cleaner.py" >> "$LOG" 2>&1 || true
  fi

  sleep "$INTERVAL"
done
