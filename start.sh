#!/bin/bash
# ══════════════════════════════════════════════════════════════
# 鲍澄项目管理体系 · 一键启动
# 同时启动看板服务器 + 数据刷新循环
# ══════════════════════════════════════════════════════════════

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

# ── 找到 Python 3.10+ ──
resolve_python() {
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    command -v "$candidate" &>/dev/null || continue
    version=$("$candidate" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")' 2>/dev/null) || continue
    major=${version%%.*}
    minor=${version#*.}
    if [ "$major" -gt 3 ] || { [ "$major" -eq 3 ] && [ "$minor" -ge 10 ]; }; then
      echo "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN=$(resolve_python) || {
  echo -e "${RED}❌ 未找到 Python 3.10+${NC}"
  exit 1
}

# ── 确保 data 目录存在 ──
mkdir -p "$REPO_DIR/data"
for f in live_status.json agent_config.json model_change_log.json sync_status.json; do
  [ ! -f "$REPO_DIR/data/$f" ] && echo '{}' > "$REPO_DIR/data/$f"
done
[ ! -f "$REPO_DIR/data/pending_model_changes.json" ] && echo '[]' > "$REPO_DIR/data/pending_model_changes.json"
[ ! -f "$REPO_DIR/data/tasks_source.json" ] && echo '[]' > "$REPO_DIR/data/tasks_source.json"
[ ! -f "$REPO_DIR/data/tasks.json" ] && echo '[]' > "$REPO_DIR/data/tasks.json"

# ── 自动注册 Agent（每启动时检查，缺失即补） ──
ensure_agents_registered() {
  "$PYTHON_BIN" -c '
import json, pathlib

oc_home = pathlib.Path.home() / ".openclaw"
cfg_path = oc_home / "openclaw.json"
cfg = json.loads(cfg_path.read_text())

reg_path = pathlib.Path("'"$REPO_DIR"'") / "registry.json"
reg = json.loads(reg_path.read_text())

agents_cfg = cfg.setdefault("agents", {})
agents_list = agents_cfg.get("list", [])
existing_ids = {a["id"] for a in agents_list}

added = 0
for ag in reg:
    ag_id = ag["id"]
    ws = str(oc_home / f"workspace-{ag_id}")
    if ag_id not in existing_ids:
        agents_list.append({
            "default": False,
            "id": ag_id,
            "name": ag.get("name", ag_id),
            "identity": {"emoji": ag.get("emoji", "🤖"), "name": ag.get("name", ag_id)},
            "workspace": ws
        })
        added += 1

if added:
    agents_cfg["list"] = agents_list
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    print(f"✅ 已注册 {added} 个新 Agent 到 OpenClaw")
else:
    print("✅ 所有 Agent 已注册，跳过")
' 2>&1
}

ensure_agents_registered

# ── 优雅退出 ──
cleanup() {
  echo ""
  echo -e "${YELLOW}正在关闭服务...${NC}"
  kill $SERVER_PID $LOOP_PID 2>/dev/null
  wait $SERVER_PID $LOOP_PID 2>/dev/null
  echo -e "${GREEN}✅ 已关闭${NC}"
  exit 0
}
trap cleanup SIGINT SIGTERM

echo ""
echo -e "${BLUE}╔══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  🏛️  鲍澄项目管理体系 · 启动中           ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════╝${NC}"
echo ""

# 启动数据刷新循环（后台）
echo -e "${GREEN}▶ 启动数据刷新循环...${NC}"
export EDICT_HOME="$REPO_DIR"
export EDICT_PYTHON="$PYTHON_BIN"
bash scripts/run_loop.sh &
LOOP_PID=$!

# 启动看板服务器
echo -e "${GREEN}▶ 启动看板服务器 (port 7891)...${NC}"
# 传递 API Token 环境变量（Agent 自动化调用用）
if [ -n "$EDICT_API_TOKEN" ]; then
  export EDICT_API_TOKEN
elif [ -f "$REPO_DIR/.env" ]; then
  source <(grep -E '^EDICT_API_TOKEN=' "$REPO_DIR/.env" 2>/dev/null)
fi
"$PYTHON_BIN" dashboard/server.py &
SERVER_PID=$!

sleep 1
echo ""
echo -e "${GREEN}✅ 服务已启动！${NC}"
echo -e "   看板地址: ${BLUE}http://127.0.0.1:7891${NC}"
echo -e "   按 ${YELLOW}Ctrl+C${NC} 关闭所有服务"
echo ""

# 尝试打开浏览器
if command -v open &>/dev/null; then
  open http://127.0.0.1:7891
fi

wait $SERVER_PID $LOOP_PID 2>/dev/null
