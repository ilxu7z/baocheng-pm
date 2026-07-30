#!/bin/bash
# ══════════════════════════════════════════════════════════════
# 鲍澄项目管理体系 · 卸载/清理脚本 v2
# 三模式：clean / clean-all / clean-update / uninstall
# ══════════════════════════════════════════════════════════════
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OC_HOME="$HOME/.openclaw"
OC_CFG="$OC_HOME/openclaw.json"
MAIN_WS="$OC_HOME/workspace-main"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

banner() {
  echo ""
  echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║  🏛️  鲍澄 · 卸载/清理向导 v2                ║${NC}"
  echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
  echo ""
}

log()   { echo -e "${GREEN}✅ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
err()   { echo -e "${RED}❌ $1${NC}"; }
info()  { echo -e "${BLUE}ℹ️  $1${NC}"; }

# 从文件头部提取版本标记
extract_version() {
  local file="$1"
  if [ ! -f "$file" ] || [ ! -r "$file" ]; then
    echo ""
    return
  fi
  head -20 "$file" 2>/dev/null | sed -n 's/.*<!-- version:\([^ ]*\).*/\1/p' | head -1
}

# 从 registry.json 获取 Agent 列表
load_agents() {
  python3 -c "
import json
reg = json.load(open('$REPO_DIR/registry.json'))
print(' '.join(a['id'] for a in reg))
"
}

# 获取非 main 的子 Agent 列表
load_sub_agents() {
  python3 -c "
import json
reg = json.load(open('$REPO_DIR/registry.json'))
print(' '.join(a['id'] for a in reg if a['id'] != 'main'))
"
}

# ══════════════════════════════════════════════════════════════════
# 通用清理函数
# ══════════════════════════════════════════════════════════════════

# 确认交互
confirm_action() {
  local prompt="$1"

  if [ "$YES_MODE" = "true" ]; then
    return 0
  fi

  echo ""
  echo -e "${YELLOW}$prompt${NC}"
  read -p "(y/N) " -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    return 1
  fi
  return 0
}

# 停止正在运行的服务
stop_services() {
  info "尝试停止相关进程..."

  if pgrep -f "scripts/run_loop.sh" > /dev/null 2>&1; then
    pkill -f "scripts/run_loop.sh" || warn "无法自动停止 run_loop.sh"
    log "已尝试停止 run_loop.sh"
  fi

  if pgrep -f "python.*dashboard/server.py" > /dev/null 2>&1; then
    pkill -f "python.*dashboard/server.py" || warn "无法自动停止 dashboard/server.py"
    log "已尝试停止 dashboard/server.py"
  fi
}

# ══════════════════════════════════════════════════════════════════
# --mode clean: 清理子 Agent workspace（保留 main）
# ══════════════════════════════════════════════════════════════════

clean_mode() {
  info "========== 清理子 Agent Workspace =========="

  stop_services

  if ! confirm_action "确定要清理所有子 Agent 的 workspace 吗？（main 将保留）"; then
    info "已取消清理"
    return
  fi

  local sub_agents
  sub_agents=$(load_sub_agents)
  local removed=0

  for agent in $sub_agents; do
    local ws="$OC_HOME/workspace-$agent"
    if [ -d "$ws" ]; then
      rm -rf "$ws"
      removed=$((removed + 1))
      log "已清理: $ws"
    else
      info "  [跳过] $ws（不存在）"
    fi
  done

  log "成功清理了 $removed 个子 Agent workspace"
}

# ══════════════════════════════════════════════════════════════════
# --mode clean-all: 清理所有 Agent workspace（含 main）
# ══════════════════════════════════════════════════════════════════

clean_all_mode() {
  info "========== 清理所有 Agent Workspace =========="

  stop_services

  if ! confirm_action "⚠️  确定要清理所有 Agent 的 workspace 吗？（含 main）\n此操作将删除 MEMORY.md 等用户数据，不可恢复！"; then
    info "已取消清理"
    return
  fi

  local agents
  agents=$(load_agents)
  local removed=0

  for agent in $agents; do
    local ws="$OC_HOME/workspace-$agent"
    if [ -d "$ws" ]; then
      rm -rf "$ws"
      removed=$((removed + 1))
      log "已清理: $ws"
    fi
  done

  log "成功清理了 $removed 个 Agent workspace"
}

# ══════════════════════════════════════════════════════════════════
# --mode clean-update: 清理 deprecated 标记段落
# ══════════════════════════════════════════════════════════════════

clean_update_mode() {
  info "========== 清理 deprecated 标记段落 =========="

  # 扫描所有 workspace 中的 .md 文件
  local deprecated_files=()
  local total_lines=0
  local preview_lines=""

  # 扫描所有 workspace
  for ws_dir in "$OC_HOME"/workspace-*/; do
    [ ! -d "$ws_dir" ] && continue
    for f in "$ws_dir"/*.md; do
      [ ! -f "$f" ] && continue

      # 查找 <!-- version:*deprecated* --> 标记
      local deprecated_lines
      deprecated_lines=$(grep -n '<!-- version:.*deprecated' "$f" 2>/dev/null || true)

      if [ -n "$deprecated_lines" ]; then
        deprecated_files+=("$f")
        while IFS= read -r line; do
          local line_num
          line_num=$(echo "$line" | cut -d: -f1)
          total_lines=$((total_lines + 1))
          preview_lines+="  📄 $f:$line_num"$'\n'
        done <<< "$deprecated_lines"
      fi
    done
  done

  if [ ${#deprecated_files[@]} -eq 0 ]; then
    log "未发现 deprecated 标记，无需清理"
    return
  fi

  echo ""
  echo -e "${YELLOW}发现 ${#deprecated_files[@]} 个文件中的 deprecated 段落，涉及 ${total_lines} 个标记行：${NC}"
  echo "$preview_lines"

  if ! confirm_action "确认执行清理？将删除以上 deprecated 段落（备份保留）"; then
    info "已取消清理"
    return
  fi

  # 执行清理：删除 deprecated 标记行及其后续段落直到下一个版本标记
  local cleaned=0
  for f in "${deprecated_files[@]}"; do
    cp "$f" "${f}.bak.clean-$(date +%Y%m%d-%H%M%S)"

    # macOS 用 sed -i ''，Linux 用 sed -i
    #   deprecated-range: 从 deprecated 标记行到下一个 version 标记行
    #   1) 先删除 deprecated 标记行本身
    #   2) 再删除 deprecated 标记之后的段落内容（直到下一个 version 标记前）
    local sed_cmd='/<!-- version:.*deprecated -->/,/^<!-- version:/{'
'  /<!-- version:.*deprecated -->/d'
'  /^<!-- version:/!d'
'}'
    if sed -i '' "$sed_cmd" "$f" 2>/dev/null; then
      cleaned=$((cleaned + 1))
    elif sed -i "$sed_cmd" "$f" 2>/dev/null; then
      cleaned=$((cleaned + 1))
    else
      # sed 不支持该语法 → 回退到 Python 实现
      python3 -c "
import re, sys
with open('$f', 'r') as fh:
    content = fh.read()
# 删除 deprecated 标记行及其后续段落
result = re.sub(r'<!-- version:.*deprecated -->.*?(?=<!-- version:|\Z)', '', content, flags=re.DOTALL)
with open('$f', 'w') as fh:
    fh.write(result)
" 2>/dev/null && cleaned=$((cleaned + 1)) || warn "清理失败: $f"
    fi
  done

  log "已完成清理: $cleaned 个文件"
  log "备份保存到: *.bak.clean-*"
}

# ══════════════════════════════════════════════════════════════════
# --mode uninstall: 完全卸载（原 uninstall.sh 全部功能）
# ══════════════════════════════════════════════════════════════════

uninstall_mode() {
  info "========== 完全卸载 =========="

  stop_services

  if ! confirm_action "确定要完全卸载「三省六部」系统并清理相关 Agent 数据吗？"; then
    info "已取消卸载"
    return
  fi

  # 从 OpenClaw 移除注册信息
  info "从 OpenClaw 移除三省六部 Agents 注册信息..."

  if [ ! -f "$OC_CFG" ]; then
    warn "未找到 openclaw.json，跳过配置清理"
  else
    cp "$OC_CFG" "$OC_CFG.bak.pre-uninstall-$(date +%Y%m%d-%H%M%S)"
    log "已备份当前配置"

    export EDICT_HOME="$REPO_DIR"
    python3 << 'PYEOF'
import json, os, pathlib

cfg_path = pathlib.Path.home() / '.openclaw' / 'openclaw.json'
if not cfg_path.exists():
    print("  openclaw.json 不存在。")
    exit(0)

try:
    cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
except Exception as e:
    print(f"  解析 openclaw.json 失败: {e}")
    exit(1)

repo_dir = os.environ.get('EDICT_HOME', str(pathlib.Path.cwd()))
AGENTS_TO_REMOVE = {
    a["id"] for a in json.load(open(pathlib.Path(repo_dir) / 'registry.json'))
    if a["id"] != "main"
}

agents_list = cfg.get('agents', {}).get('list', [])
new_list = [a for a in agents_list if a.get('id') not in AGENTS_TO_REMOVE]
removed_count = len(agents_list) - len(new_list)

if 'agents' in cfg:
    cfg['agents']['list'] = new_list
    cfg_path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"  成功移除了 {removed_count} 个 Agent 的注册信息")
PYEOF
  fi

  # 清除 Workspace 目录
  info "清除 Agent Workspace 目录..."

  local sub_agents
  sub_agents=$(load_sub_agents)
  local removed=0
  for agent in $sub_agents; do
    local ws="$OC_HOME/workspace-$agent"
    if [ -d "$ws" ]; then
      rm -rf "$ws"
      removed=$((removed + 1))
    fi
  done
  log "成功清理了 $removed 个 Workspace 目录"

  # 清除本地数据缓存
  if confirm_action "是否需要删除项目内的 data 目录及已生成的数据？"; then
    if [ -d "$REPO_DIR/data" ]; then
      rm -rf "$REPO_DIR/data"
      log "已删除 $REPO_DIR/data"
    else
      warn "$REPO_DIR/data 不存在"
    fi
  else
    info "保留原有 data 目录"
  fi

  # 重启 Gateway
  restart_gateway
}

# 重启 Gateway
restart_gateway() {
  info "重启 OpenClaw Gateway 以应用配置..."
  if command -v openclaw &>/dev/null; then
    if openclaw gateway restart 2>/dev/null; then
      log "Gateway 重启成功"
    else
      warn "Gateway 重启失败，请手动重启：openclaw gateway restart"
    fi
  else
    warn "未找到 openclaw 命令行工具，跳过重启 Gateway"
  fi
}

# ══════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════

main() {
  local mode="clean-update"
  YES_MODE="false"

  # 参数解析
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --mode)
        mode="$2"
        shift 2
        ;;
      --yes)
        YES_MODE="true"
        shift
        ;;
      clean|clean-all|clean-update|uninstall)
        mode="$1"
        shift
        ;;
      *)
        echo "用法: $0 [--mode clean|clean-all|clean-update|uninstall] [--yes]"
        echo ""
        echo "模式说明："
        echo "  --mode clean          清理子 Agent workspace（保留 main）"
        echo "  --mode clean-all      清理所有 Agent workspace（含 main）"
        echo "  --mode clean-update   清理 deprecated 标记段落（默认）"
        echo "  --mode uninstall      完全卸载"
        echo "  --yes                 跳过所有交互确认"
        exit 1
        ;;
    esac
  done

  banner

  case "$mode" in
    clean)
      clean_mode
      ;;
    clean-all)
      clean_all_mode
      ;;
    clean-update)
      clean_update_mode
      ;;
    uninstall)
      uninstall_mode
      ;;
    *)
      err "未知模式: $mode"
      exit 1
      ;;
  esac

  echo ""
  echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║  ✅  操作完成！                                 ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
  echo ""
}

main "$@"