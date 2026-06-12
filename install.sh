#!/bin/bash
# ══════════════════════════════════════════════════════════════
# 鲍澄项目管理体系 · 一键安装脚本
# 基于 edict (三省六部) 改造，适配鲍澄居中调度的多 Agent 协同架构
# ══════════════════════════════════════════════════════════════
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OC_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
OC_CFG="$OC_HOME/openclaw.json"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

banner() {
  echo ""
  echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║  🏛️  鲍澄 · 多 Agent 项目管理体系            ║${NC}"
  echo -e "${BLUE}║     安装向导                                  ║${NC}"
  echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
  echo ""
}

log()   { echo -e "${GREEN}✅ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
err()   { echo -e "${RED}❌ $1${NC}"; }
info()  { echo -e "${BLUE}ℹ️  $1${NC}"; }

# ── Step 0: 依赖检查 ──
check_deps() {
  info "检查依赖..."
  if ! command -v openclaw &>/dev/null; then
    err "未找到 openclaw CLI。请先安装 OpenClaw"
    exit 1
  fi
  log "OpenClaw CLI 可用"

  if ! command -v python3 &>/dev/null; then
    err "未找到 python3"
    exit 1
  fi
  log "Python3: $(python3 --version)"
}

# ── Step 1: 创建 Workspace ──
create_workspaces() {
  info "创建 Agent Workspace..."

  # 从 registry.json 动态加载所有 Agent
  AGENTS=($(python3 -c "
import json
reg = json.load(open('$REPO_DIR/registry.json'))
print(' '.join(a['id'] for a in reg))
"))
  info "军团规模: ${#AGENTS[@]} 个 Agent: ${AGENTS[*]}"

  for agent in "${AGENTS[@]}"; do
    ws="$OC_HOME/workspace-$agent"
    mkdir -p "$ws/skills"

    # 写入 SOUL.md
    if [ -f "$REPO_DIR/agents/$agent/SOUL.md" ]; then
      if [ -f "$ws/SOUL.md" ]; then
        cp "$ws/SOUL.md" "$ws/SOUL.md.bak.$(date +%Y%m%d-%H%M%S)"
        warn "已备份旧 SOUL.md → $ws/SOUL.md.bak.*"
      fi
      cp "$REPO_DIR/agents/$agent/SOUL.md" "$ws/SOUL.md"
    fi

    # 部署治理协议
    if [ -f "$REPO_DIR/agents/GOVERNANCE.md" ]; then
      cp "$REPO_DIR/agents/GOVERNANCE.md" "$ws/GOVERNANCE.md"
    fi

    # 写入 AGENTS.md（工作协议）
    cat > "$ws/AGENTS.md" << 'AGENTS_EOF'
# 工作协议 · 鲍澄军团

## 治理铁律
必须遵守 GOVERNANCE.md 全部条款。

## 工作纪律
1. 只在被 sessions_spawn 调用时工作，不主动发起通信
2. 收到任务先验证输入完整性，再回复"已接收"
3. 输出必须结构化（参照 GOVERNANCE.md 2.1）
4. 不确定的事标注 [待确认]，禁止猜测
5. 禁止越权操作（范围锁定 GOVERNANCE.md 4.2）
6. 子Agent产出必须验收，不合格打回
7. 超时/失联按 GOVERNANCE.md 3.2 和 5.1 处理
AGENTS_EOF

    log "Workspace: $ws"
  done
}

# ── Step 2: 注册 Agents ──
register_agents() {
  info "注册 Agent 到 OpenClaw..."

  cp "$OC_CFG" "$OC_CFG.bak.baocheng-$(date +%Y%m%d-%H%M%S)"
  log "已备份 openclaw.json"

  python3 << 'PYEOF'
import json, os, pathlib

oc_home = pathlib.Path(os.environ.get('OPENCLAW_HOME', str(pathlib.Path.home() / '.openclaw')))
cfg_path = oc_home / 'openclaw.json'
cfg = json.loads(cfg_path.read_text())

# 从 registry.json 加载 Agent 列表
repo_dir = os.environ.get('EDICT_HOME', str(pathlib.Path(os.environ.get('HOME', str(pathlib.Path.home())) + '/Projects/oc-macs')))
reg_path = pathlib.Path(repo_dir) / 'registry.json'
if reg_path.exists():
    reg = json.loads(reg_path.read_text())
    AGENTS = [{"id": a["id"], "subagents": {"allowAgents": []}} for a in reg]
else:
    AGENTS = []

agents_cfg = cfg.setdefault('agents', {})
agents_list = agents_cfg.get('list', [])
existing_ids = {a['id'] for a in agents_list}

added = 0
for ag in AGENTS:
    ag_id = ag['id']
    ws = str(oc_home / f'workspace-{ag_id}')
    if ag_id not in existing_ids:
        entry = {'id': ag_id, 'workspace': ws, 'subagents': ag.get('subagents', {'allowAgents': []})}
        agents_list.append(entry)
        added += 1
        print(f'  + 已注册: {ag_id} ({ag.get("label", ag_id)})')
    else:
        print(f'  ~ 已存在: {ag_id}（跳过）')

agents_cfg['list'] = agents_list

# 清理 bindings 中的非法字段
bindings = cfg.get('bindings', [])
cleaned = 0
for b in bindings:
    match = b.get('match', {})
    if isinstance(match, dict) and 'pattern' in match:
        del match['pattern']
        cleaned += 1
if cleaned:
    print(f'  🧹 清理了 {cleaned} 个非法 binding 字段')

cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
print(f'完成: {added} 个 Agent 已注册')
PYEOF

  log "Agent 注册完成"
}

# ── Step 3: 初始化数据目录 ──
init_data() {
  info "初始化数据目录..."
  mkdir -p "$REPO_DIR/data"

  for f in live_status.json agent_config.json model_change_log.json sync_status.json; do
    [ ! -f "$REPO_DIR/data/$f" ] && echo '{}' > "$REPO_DIR/data/$f"
  done
  [ ! -f "$REPO_DIR/data/pending_model_changes.json" ] && echo '[]' > "$REPO_DIR/data/pending_model_changes.json"
  [ ! -f "$REPO_DIR/data/tasks_source.json" ] && echo '[]' > "$REPO_DIR/data/tasks_source.json"
  [ ! -f "$REPO_DIR/data/tasks.json" ] && echo '[]' > "$REPO_DIR/data/tasks.json"
  [ ! -f "$REPO_DIR/data/officials.json" ] && echo '[]' > "$REPO_DIR/data/officials.json"
  [ ! -f "$REPO_DIR/data/officials_stats.json" ] && echo '{}' > "$REPO_DIR/data/officials_stats.json"

  log "数据目录初始化完成"
}

# ── Step 4: 创建 data/scripts 软链接 ──
link_resources() {
  info "创建 data/scripts 软链接..."

  AGENTS=($(python3 -c "
import json
reg = json.load(open('$REPO_DIR/registry.json'))
print(' '.join(a['id'] for a in reg))
"))
  LINKED=0
  for agent in "${AGENTS[@]}"; do
    ws="$OC_HOME/workspace-$agent"
    mkdir -p "$ws"

    # soft link data
    ws_data="$ws/data"
    if [ -L "$ws_data" ]; then
      ws_old_target=$(readlink "$ws_data")
      if [ "$ws_old_target" != "$REPO_DIR/data" ]; then
        rm "$ws_data"
        ln -s "$REPO_DIR/data" "$ws_data"
        LINKED=$((LINKED + 1))
        echo "    ↻ 更新: $ws -> $REPO_DIR/data"
      fi
    elif [ -d "$ws_data" ]; then
      mv "$ws_data" "${ws_data}.bak.$(date +%Y%m%d-%H%M%S)"
      ln -s "$REPO_DIR/data" "$ws_data"
      LINKED=$((LINKED + 1))
    else
      ln -s "$REPO_DIR/data" "$ws_data"
      LINKED=$((LINKED + 1))
    fi

    # soft link scripts
    ws_scripts="$ws/scripts"
    if [ -L "$ws_scripts" ]; then
      ws_old_target=$(readlink "$ws_scripts")
      if [ "$ws_old_target" != "$REPO_DIR/scripts" ]; then
        rm "$ws_scripts"
        ln -s "$REPO_DIR/scripts" "$ws_scripts"
        LINKED=$((LINKED + 1))
        echo "    ↻ 更新: $ws -> $REPO_DIR/scripts"
      fi
    elif [ -d "$ws_scripts" ]; then
      mv "$ws_scripts" "${ws_scripts}.bak.$(date +%Y%m%d-%H%M%S)"
      ln -s "$REPO_DIR/scripts" "$ws_scripts"
      LINKED=$((LINKED + 1))
    else
      ln -s "$REPO_DIR/scripts" "$ws_scripts"
      LINKED=$((LINKED + 1))
    fi
  done

  # 也链接到主 workspace
  ws_main="$OC_HOME/workspace-main"
  if [ -d "$ws_main" ]; then
    for target in data scripts; do
      link_path="$ws_main/$target"
      if [ ! -L "$link_path" ]; then
        [ -d "$link_path" ] && mv "$link_path" "${link_path}.bak.$(date +%Y%m%d-%H%M%S)"
        ln -s "$REPO_DIR/$target" "$link_path"
        LINKED=$((LINKED + 1))
      fi
    done
  fi

  log "已创建 $LINKED 个软链接"
}

# ── Step 5: Agent 间通信可见性 ──
setup_visibility() {
  info "配置 Agent 间消息可见性..."
  if openclaw config set tools.sessions.visibility all 2>/dev/null; then
    log "已设置 sessions.visibility=all"
  else
    warn "设置 visibility 失败，请手动执行："
    echo "    openclaw config set tools.sessions.visibility all"
  fi
}

# ── Step 6: 同步 API Key ──
sync_auth() {
  info "同步 API Key 到所有 Agent..."

  MAIN_AUTH=""
  AUTH_FILENAME=""
  AGENT_BASE="$OC_HOME/agents/main/agent"

  for candidate in models.json auth-profiles.json; do
    if [ -f "$AGENT_BASE/$candidate" ]; then
      MAIN_AUTH="$AGENT_BASE/$candidate"
      AUTH_FILENAME="$candidate"
      break
    fi
  done

  if [ -z "$MAIN_AUTH" ]; then
    for candidate in models.json auth-profiles.json; do
      MAIN_AUTH=$(find "$OC_HOME/agents" -name "$candidate" -maxdepth 3 2>/dev/null | head -1)
      if [ -n "$MAIN_AUTH" ] && [ -f "$MAIN_AUTH" ]; then
        AUTH_FILENAME="$candidate"
        break
      fi
      MAIN_AUTH=""
    done
  fi

  if [ -z "$MAIN_AUTH" ] || [ ! -f "$MAIN_AUTH" ]; then
    warn "未找到已有的 API Key 配置"
    warn "请先配置 API Key: openclaw agents add main"
    warn "然后重新运行: ./install.sh"
    return
  fi

  AGENTS=($(python3 -c "
import json
reg = json.load(open('$REPO_DIR/registry.json'))
print(' '.join(a['id'] for a in reg))
"))
  SYNCED=0
  for agent in "${AGENTS[@]}"; do
    AGENT_DIR="$OC_HOME/agents/$agent/agent"
    if [ -d "$AGENT_DIR" ] || mkdir -p "$AGENT_DIR" 2>/dev/null; then
      cp -f "$MAIN_AUTH" "$AGENT_DIR/$AUTH_FILENAME" 2>/dev/null || true
      SYNCED=$((SYNCED + 1))
    fi
  done

  log "API Key 已同步到 $SYNCED 个 Agent"
}

# ── Step 7: 构建 React 前端 ──
build_frontend() {
  info "构建前端看板..."

  if ! command -v node &>/dev/null; then
    warn "未找到 node，跳过前端构建（将使用预构建版本）"
    return
  fi

  if [ -f "$REPO_DIR/edict/frontend/package.json" ]; then
    cd "$REPO_DIR/edict/frontend"
    npm install --silent 2>/dev/null || npm install
    npm run build 2>/dev/null
    cd "$REPO_DIR"
    if [ -f "$REPO_DIR/dashboard/dist/index.html" ]; then
      log "前端构建完成"
    else
      warn "前端构建可能失败，请检查"
    fi
  else
    warn "未找到 frontend/package.json，跳过"
  fi
}

# ── Step 8: 首次数据同步 ──
first_sync() {
  info "首次数据同步..."
  cd "$REPO_DIR"

  EDICT_HOME="$REPO_DIR" python3 scripts/sync_agent_config.py 2>/dev/null || true
  EDICT_HOME="$REPO_DIR" python3 scripts/sync_officials_stats.py 2>/dev/null || true
  EDICT_HOME="$REPO_DIR" python3 scripts/refresh_live_data.py 2>/dev/null || true

  log "首次同步完成"
}

# ── Step 9: 重启 Gateway ──
restart_gateway() {
  info "重启 OpenClaw Gateway..."
  if openclaw gateway restart 2>/dev/null; then
    log "Gateway 重启成功"
  else
    warn "Gateway 重启失败，请手动: openclaw gateway restart"
  fi
}

# ── Main ──
banner
check_deps
create_workspaces
register_agents
init_data
link_resources
setup_visibility
sync_auth
build_frontend
first_sync
restart_gateway

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  🎉  鲍澄项目管理体系安装完成！                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
echo "已安装的 Agent："
echo "  规划 guihua  |  审议 shenyi  |  派发 paifa"
echo "  文案 wenan   |  代码 daima   |  设计 sheji"
echo "  审查 shencha |  汇总 huizong"
echo ""
echo "下一步："
echo "  1. 启动数据刷新:  bash scripts/run_loop.sh &"
echo "  2. 启动看板:      python3 dashboard/server.py"
echo "  3. 打开看板:      http://127.0.0.1:7891"
echo "  4. 和鲍澄开始工作！"
echo ""
