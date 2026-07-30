#!/usr/bin/env bash
# <!-- version:v2.0.0-system -->
# uninstall.sh — OCR 融合系统清理脚本
# 版本: v2.0.0-system
# 功能: --mode clean / clean-all / clean-update
# <!-- version:v2.0.0-system -->
set -euo pipefail
B="$(cd "$(dirname "$0")/.." && pwd)"
source "$B/lib/core.sh" 2>/dev/null || { echo "[错误] 无法加载 core.sh"; exit 1; }
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; N='\033[0m'
log_info() { echo -e "${G}[INFO]${N} $1"; }
log_warn() { echo -e "${Y}[WARN]${N} $1"; }
log_error() { echo -e "${R}[ERROR]${N} $1"; }
clean_deprecated() {
  local t="${1:-.}"; log_info "clean: 扫描 $t 废弃段落..."; local f=0
  while IFS= read -r -d '' ff; do scan_deprecated "$ff" || f=$((f+$?)); done < <(find "$t" -name '*.md' -print0 2>/dev/null)
  [ $f -eq 0 ] && log_info "✅ 无废弃段落" || log_warn "发现 $f 个废弃段落"
}
clean_all() {
  local t="${1:-.}"; log_info "clean-all: 删除 $t 中带版本标记的文件..."; local c=0
  while IFS= read -r -d '' f; do
    if head -1 "$f" | grep -q '<!-- version:'; then rm "$f"; log_info "删除: $f"; ((c++)); fi
  done < <(find "$t" -name '*.md' -print0 2>/dev/null)
  log_info "✅ 删除 $c 个文件（备份在 .bak.* 中）"
}
clean_update() {
  local t="${1:-.}"; log_info "clean-update: 清理备份和沉余..."; local c=0
  while IFS= read -r -d '' f; do rm "$f"; ((c++)); done < <(find "$t" -name '*.bak.*' -print0 2>/dev/null)
  log_info "删除 $c 个备份"; clean_deprecated "$t"
}
main() {
  case "${1:-clean}" in
    clean|--mode\ clean) clean_deprecated "${2:-$B}" ;;
    clean-all|--mode\ clean-all) clean_all "${2:-$B}" ;;
    clean-update|--mode\ clean-update) clean_update "${2:-$B}" ;;
    *) echo "用法: $0 [--mode clean|clean-all|clean-update] [dir]" ;;
  esac
}
main "$@"
