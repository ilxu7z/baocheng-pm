#!/usr/bin/env bash
# <!-- version:v2.0.0-system -->
# upgrade.sh — OCR 融合系统升级脚本
# 版本: v2.0.0-system
# <!-- version:v2.0.0-system -->
set -euo pipefail
B="$(cd "$(dirname "$0")/.." && pwd)"
source "$B/lib/core.sh" 2>/dev/null || { echo "[错误] 无法加载 core.sh"; exit 1; }
R='\033[0;31m'; G='\033[0;32m'; Y='\033[1;33m'; N='\033[0m'
log_info() { echo -e "${G}[INFO]${N} $1"; }
log_warn() { echo -e "${Y}[WARN]${N} $1"; }
log_error() { echo -e "${R}[ERROR]${N} $1"; }
scan_versions() {
  local sd="${1:-$B/agents}" dd="${2:-}"
  log_info "扫描源版本..."
  echo "| 文件 | 源版本 | 目标版本 | 操作 |" > /tmp/upgrade_rpt.md
  echo "|------|--------|---------|------|" >> /tmp/upgrade_rpt.md
  local o=0 a=0 s=0 c=0
  while IFS= read -r -d '' f; do
    local r="${f#$sd/}" d="${dd}/$r" sv dv ac
    sv=$(extract_version "$f") || sv="0.0.0"
    dv=$(extract_version "$d") || dv=""
    case $(version_compare "$sv" "$dv") in 0) ac="跳过";((s++));;1) ac="覆盖";((o++));;2) ac="增量追加";((a++));;3) ac="创建";((c++));;esac
    echo "| $r | $sv | ${dv:--} | $ac |" >> /tmp/upgrade_rpt.md
  done < <(find "$sd" -name '*.md' -type f -print0)
  echo -e "\n### 统计\n- 创建: $c | 覆盖: $o | 增量追加: $a | 跳过: $s" >> /tmp/upgrade_rpt.md
  cat /tmp/upgrade_rpt.md
}
do_upgrade() {
  local sd="${1:-$B/agents}" dd="${2:-}"
  [ -n "$dd" ] || { log_error "目标目录未指定"; exit 1; }
  log_info "升级: $sd → $dd"
  local e=0
  while IFS= read -r -d '' f; do
    local r="${f#$sd/}" d="${dd}/$r" sv
    sv=$(extract_version "$f") || sv="0.0.0"
    case $(version_compare "$sv" "$(extract_version "$d" || echo "")") in
      0) log_info "跳过: $r" ;;
      1) handle_bootstrap_file "$f" "$d" 1 && log_info "覆盖: $r" ;;
      2) append_incremental "$f" "$d" ;;
      3) write_with_version "$f" "$d" create ;;
    esac || { log_error "失败: $r"; ((e++)); }
  done < <(find "$sd" -name '*.md' -type f -print0)
  [ $e -eq 0 ] && log_info "✅ 升级完成" || log_warn "升级完成，$e 个错误"
}
main() {
  case "${1:-scan}" in
    scan) scan_versions "${2:-$B/agents}" "${3:-}" ;;
    upgrade) do_upgrade "${2:-$B/agents}" "${3:-}" ;;
    *) echo "用法: $0 [scan|upgrade] [src] [dst]" ;;
  esac
}
main "$@"
