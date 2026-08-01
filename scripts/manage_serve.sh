#!/bin/bash
# 三省六部 · 干净启停管理脚本（避免 pkill -f 自匹配陷阱）
# 用法:
#   bash scripts/manage_serve.sh start   # 后台启动 server + run_loop，PID记录到/tmp/sansheng_liubu.pids
#   bash scripts/manage_serve.sh stop    # 按PID文件精确停止
#   bash scripts/manage_serve.sh status  # 查看状态
set -u
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIDFILE=/tmp/sansheng_liubu.pids
LOGDIR=/tmp/sansheng_liubu

case "${1:-}" in
  start)
    mkdir -p "$LOGDIR"
    rm -f "$PIDFILE"
    cd "$REPO_DIR"
    # resolve python
    PYTHON_BIN=$(for c in python3.13 python3.12 python3.11 python3.10 python3; do
      command -v "$c" >/dev/null 2>&1 || continue
      v=$("$c" -c 'import sys;print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null) || continue
      major=${v%%.*}; minor=${v#*.}
      [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; } && { echo "$c"; break; }
    done)
    [ -n "$PYTHON_BIN" ] || PYTHON_BIN=python3
    export EDICT_HOME="$REPO_DIR" EDICT_PYTHON="$PYTHON_BIN"
    # run_loop 后台
    nohup bash scripts/run_loop.sh > "$LOGDIR/refresh.log" 2>&1 &
    echo $! >> "$PIDFILE"
    # server 后台（日志明确落盘）
    nohup "$PYTHON_BIN" dashboard/server.py > "$LOGDIR/server.log" 2>&1 &
    echo $! >> "$PIDFILE"
    sleep 2
    echo "✅ 已启动。日志: $LOGDIR/{server,refresh}.log"
    ;;
  stop)
    if [ -f "$PIDFILE" ]; then
      while read -r pid; do
        kill -9 "$pid" 2>/dev/null && echo "kill -9 $pid"
      done < "$PIDFILE"
      rm -f "$PIDFILE"
    fi
    # 兜底精确清理（不含会自匹配的模式）
    spid=$(ps aux | grep -E "dashboard/server\.py" | grep -v grep | awk '{print $2}')
    [ -n "$spid" ] && kill -9 $spid 2>/dev/null && echo "kill server $spid"
    rm -f /tmp/sansheng_liubu_refresh.pid
    echo "✅ 已停止"
    ;;
  status)
    echo "=== server ==="; ps aux | grep -E "dashboard/server\.py" | grep -v grep || echo "  未运行"
    echo "=== run_loop ==="; ps aux | grep -E "run_loop\.sh" | grep -v grep || echo "  未运行"
    echo "=== 端口7891 ==="; ss -tlnp 2>/dev/null | grep ":7891 " || echo "  未监听"
    ;;
  *) echo "用法: $0 start|stop|status"; exit 1;;
esac
