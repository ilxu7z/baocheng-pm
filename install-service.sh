#!/bin/bash
# ══════════════════════════════════════════════════════════════
# 鲍澄项目管理体系 · 安装系统自启服务
# macOS: LaunchAgent
# ══════════════════════════════════════════════════════════════
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.oc-macs.server"
PLIST_SRC="$REPO_DIR/$PLIST_NAME.plist"
PLIST_DST="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

banner() {
  echo ""
  echo -e "${BLUE}╔══════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║  🏛️  鲍澄 · 系统自启服务安装                 ║${NC}"
  echo -e "${BLUE}╚══════════════════════════════════════════════╝${NC}"
  echo ""
}
log()   { echo -e "${GREEN}✅ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
err()   { echo -e "${RED}❌ $1${NC}"; }

banner

# 检查系统
case "$(uname)" in
  Darwin) ;;
  Linux)  warn "Linux 暂不支持自动安装，请手动配置 systemd"; exit 0 ;;
  *)      err "不支持的操作系统: $(uname)"; exit 1 ;;
esac

# 确保目标目录存在
mkdir -p "$HOME/Library/LaunchAgents"

# 写入 plist（替换占位符）
echo -e "${GREEN}▶ 生成 LaunchAgent 配置...${NC}"
sed "s|{{REPO_DIR}}|${REPO_DIR}|g" "$PLIST_SRC" > "$PLIST_DST"
chmod 644 "$PLIST_DST"

# 加载服务
echo -e "${GREEN}▶ 加载 LaunchAgent...${NC}"
launchctl bootout "gui/$(id -u)" "$PLIST_DST" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"

sleep 1

# 验证
if launchctl print "gui/$(id -u)/$PLIST_NAME" &>/dev/null; then
  log "服务已安装并启动"
  echo "   服务名: $PLIST_NAME"
  echo "   地址:   ${BLUE}http://127.0.0.1:7891${NC}"
  echo "   日志:   $REPO_DIR/logs/"
  echo ""
  echo -e "${YELLOW}提示: 服务将在下次开机时自动启动${NC}"
  echo -e "${YELLOW}      手动控制: launchctl kickstart gui/\$(id -u)/$PLIST_NAME${NC}"
else
  err "服务加载失败，请检查日志"
  launchctl print "gui/$(id -u)/$PLIST_NAME" 2>&1 || true
  exit 1
fi
