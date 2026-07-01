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

# ── 检查系统 ──
case "$(uname)" in
  Darwin) install_macos ;;
  Linux)  install_linux ;;
  *)      err "不支持的操作系统: $(uname)"; exit 1 ;;
esac

# ════════════════════════════════════════════════════════════
# macOS LaunchAgent
# ════════════════════════════════════════════════════════════
install_macos() {
  mkdir -p "$HOME/Library/LaunchAgents"

  echo -e "${GREEN}▶ 生成 LaunchAgent 配置...${NC}"
  sed "s|{{REPO_DIR}}|${REPO_DIR}|g" "$PLIST_SRC" > "$PLIST_DST"
  chmod 644 "$PLIST_DST"

  echo -e "${GREEN}▶ 加载 LaunchAgent...${NC}"
  launchctl bootout "gui/$(id -u)" "$PLIST_DST" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$PLIST_DST"

  sleep 1

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
}

# ════════════════════════════════════════════════════════════
# Linux systemd
# ════════════════════════════════════════════════════════════
install_linux() {
  SYSTEMD_SERVICE="oc-macs"
  SERVICE_FILE="/etc/systemd/system/${SYSTEMD_SERVICE}.service"

  if [ "$EUID" -ne 0 ]; then
    warn "安装 systemd 服务需要 root 权限，尝试 sudo..."
  fi

  echo -e "${GREEN}▶ 生成 systemd service 配置...${NC}"
  cat > /tmp/oc-macs.service << SYSTEMD_EOF
[Unit]
Description=鲍澄项目管理体系 · 三省六部看板服务
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${REPO_DIR}
ExecStart=${REPO_DIR}/edict.sh start
ExecStop=${REPO_DIR}/edict.sh stop
ExecReload=${REPO_DIR}/edict.sh restart
Restart=on-failure
RestartSec=10
Environment=EDICT_HOME=${REPO_DIR}
Environment=EDICT_DASHBOARD_PORT=7891

[Install]
WantedBy=multi-user.target
SYSTEMD_EOF

  if sudo mv /tmp/oc-macs.service "$SERVICE_FILE" 2>/dev/null; then
    sudo chmod 644 "$SERVICE_FILE"
    log "systemd service 文件已创建: $SERVICE_FILE"
  else
    err "写入 $SERVICE_FILE 失败，请手动执行:"
    echo "  sudo cp /tmp/oc-macs.service $SERVICE_FILE"
    exit 1
  fi

  echo -e "${GREEN}▶ 加载 systemd 服务...${NC}"
  sudo systemctl daemon-reload
  sudo systemctl enable "${SYSTEMD_SERVICE}.service"
  sudo systemctl restart "${SYSTEMD_SERVICE}.service"

  sleep 2

  if sudo systemctl is-active --quiet "${SYSTEMD_SERVICE}.service"; then
    log "服务已安装并启动"
    echo "   服务名: ${SYSTEMD_SERVICE}.service"
    echo "   地址:   ${BLUE}http://127.0.0.1:7891${NC}"
    echo "   日志:   journalctl -u ${SYSTEMD_SERVICE}.service -f"
    echo ""
    echo -e "${YELLOW}提示: 服务将在开机时自动启动${NC}"
    echo -e "${YELLOW}      手动控制: systemctl {start|stop|restart|status} ${SYSTEMD_SERVICE}${NC}"
  else
    err "服务启动失败，请检查日志:"
    echo "  journalctl -u ${SYSTEMD_SERVICE}.service -n 50 --no-pager"
    exit 1
  fi
}
