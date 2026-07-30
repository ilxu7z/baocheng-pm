#!/usr/bin/env bash
# <!-- version:v2.0.0-system -->
# install_ocr.sh — OCR 融合系统安装脚本
# 版本: v2.0.0-system
# <!-- version:v2.0.0-system -->
set -e
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; N='\033[0m'
log_info() { echo -e "${G}[INFO]${N} $1"; }
log_warn() { echo -e "${Y}[WARN]${N} $1"; }
log_error() { echo -e "${R}[ERROR]${N} $1"; }
install_ocr() {
  local pkg="${1:-@baocheng/ocr-fusion}" ver="${2:-latest}"
  log_info "安装 OCR 融合系统: $pkg@$ver"
  command -v npm &>/dev/null || { log_error "npm 未安装"; return 1; }
  # Level 1: auto
  if npm install -g "${pkg}@${ver}" --no-audit --no-fund 2>/dev/null; then log_info "✅ 自动安装成功"; return 0; fi
  log_warn "自动安装失败，降级到用户级..."
  # Level 2: user-level
  local u="$HOME/.npm-global"; mkdir -p "$u"
  if npm config set prefix "$u" 2>/dev/null; then
    export PATH="$u/bin:$PATH"
    if npm install -g "${pkg}@${ver}" --no-audit --no-fund 2>/dev/null; then
      log_info "✅ 用户级安装成功 ($u/bin)"; echo "请将以下加入 ~/.zshrc: export PATH=\"$u/bin:\$PATH\""; return 0
    fi
  fi
  log_warn "用户级安装失败，尝试 sudo..."
  # Level 3: sudo
  if sudo npm install -g "${pkg}@${ver}" --no-audit --no-fund 2>/dev/null; then log_info "✅ sudo 安装成功"; return 0; fi
  log_error "❌ 安装失败，请手动执行: sudo npm install -g ${pkg}@${ver}"
  return 1
}
install_ocr_rules() {
  local d="${1:-.github}"; mkdir -p "$d"
  if [ -f ".github/ocr-rules.md" ]; then cp ".github/ocr-rules.md" "$d/ocr-rules.md"; log_info "✅ 规则已写入"; fi
}
main() { install_ocr "$@" && install_ocr_rules; }
[[ "${BASH_SOURCE[0]}" == "${0}" ]] && main "$@"
