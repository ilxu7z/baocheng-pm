#!/usr/bin/env bash
# <!-- version:v2.0.0-system -->
# core.sh — OCR 融合系统核心函数库
# 版本: v2.0.0-system
# 功能: version_compare, write_with_version, append_incremental, extract_version, scan_deprecated, handle_bootstrap_file, formatOCRReport

set -o pipefail
set -e

# ============================================================
# 配置常量
# ============================================================
READ_SIZE_LARGE_THRESHOLD=$((1 * 1024 * 1024))   # 1MB
READ_SIZE_SKIP_THRESHOLD=$((5 * 1024 * 1024))    # 5MB
BACKUP_SUFFIX=".bak.$(date +%Y%m%d-%H%M%S)"
VERSION_REGEX='<!--[[:space:]]*version:([^[:space:]]+)[[:space:]]*-->'

# ============================================================
# extract_version — 从文件头部提取版本标记
# 参数: $1 = 文件路径
# 返回: 0=找到并输出版本号, 1=未找到或无文件
# ============================================================
extract_version() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        return 1
    fi
    local head
    head=$(head -20 "$file" 2>/dev/null) || return 1
    if [[ "$head" =~ $VERSION_REGEX ]]; then
        echo "${BASH_REMATCH[1]}"
        return 0
    fi
    return 1
}

# ============================================================
# version_compare — 版本比对
# 参数: $1 = source_version, $2 = target_version
# 返回: 0=跳过, 1=MAJOR覆盖, 2=MINOR/PATCH增量追加, 3=创建
# 版本格式: vMAJOR.MINOR.PATCH[-suffix]
# ============================================================
version_compare() {
    local src="$1" dst="$2"

    # 如果目标不存在，直接创建
    if [[ -z "$dst" ]]; then
        echo 3
        return 0
    fi

    # 去除 v 前缀和后缀
    local src_clean="${src#v}" dst_clean="${dst#v}"
    src_clean="${src_clean%%-*}" dst_clean="${dst_clean%%-*}"

    local src_major src_minor src_patch
    local dst_major dst_minor dst_patch

    IFS='.' read -r src_major src_minor src_patch <<< "$src_clean"
    IFS='.' read -r dst_major dst_minor dst_patch <<< "$dst_clean"

    src_major=${src_major:-0} src_minor=${src_minor:-0} src_patch=${src_patch:-0}
    dst_major=${dst_major:-0} dst_minor=${dst_minor:-0} dst_patch=${dst_patch:-0}

    # MAJOR 变更 → 覆盖 (1)
    if (( src_major > dst_major )); then
        echo 1
        return 0
    fi

    # MINOR 或 PATCH 变更 → 增量追加 (2)
    if (( src_minor > dst_minor )) || (( src_patch > dst_patch )); then
        echo 2
        return 0
    fi

    # 版本相同或更低 → 跳过 (0)
    echo 0
    return 0
}

# ============================================================
# write_with_version — 带版本标记的写入
# 参数: $1 = source_file, $2 = target_file, $3 = action (create|overwrite|append)
# 环境变量: FORCE=1 跳过确认
# 返回: 0=成功, 1=跳过, 2=错误
# 自动备份: 覆盖操作前创建 .bak 文件
# ============================================================
write_with_version() {
    local src="$1" dst="$2" action="${3:-create}"
    local src_ver dst_ver compare_result

    # 确保源文件存在
    if [[ ! -f "$src" ]]; then
        echo "[错误] 源文件不存在: $src" >&2
        return 2
    fi

    # 提取版本
    src_ver=$(extract_version "$src") || src_ver="0.0.0"
    dst_ver=$(extract_version "$dst") || dst_ver=""

    # 版本比对
    compare_result=$(version_compare "$src_ver" "$dst_ver")

    case "$compare_result" in
        3)  # 创建
            action="create"
            ;;
        1)  # MAJOR 覆盖
            action="overwrite"
            ;;
        2)  # MINOR/PATCH 增量追加
            action="append"
            ;;
        0)  # 跳过
            echo "[跳过] $dst 版本 $dst_ver >= 源版本 $src_ver"
            return 1
            ;;
    esac

    # 执行动作
    case "$action" in
        create)
            mkdir -p "$(dirname "$dst")"
            cp "$src" "$dst"
            echo "[创建] $dst ← $src (v$src_ver)"
            ;;
        overwrite)
            mkdir -p "$(dirname "$dst")"
            if [[ -f "$dst" ]]; then
                cp "$dst" "${dst}${BACKUP_SUFFIX}"
                echo "[备份] ${dst}${BACKUP_SUFFIX}"
            fi
            cp "$src" "$dst"
            echo "[覆盖] $dst ← $src (v$src_ver, 之前 v$dst_ver)"
            ;;
        append)
            append_incremental "$src" "$dst"
            ;;
    esac

    return 0
}

# ============================================================
# append_incremental — 逐段增量追加
# 参数: $1 = source_file, $2 = target_file
# 功能: 将源文件中目标文件不存在的内容追加到目标文件尾部
# 大文件处理: >5MB 跳过, >1MB 使用 grep 批量预检
# 编码检测: 非 UTF-8 跳过
# ============================================================
append_incremental() {
    local src="$1" dst="$2"
    local src_size dst_encoding

    # 确保目标文件存在
    if [[ ! -f "$dst" ]]; then
        mkdir -p "$(dirname "$dst")"
        cp "$src" "$dst"
        echo "[创建] $dst ← $src (文件不存在，直接复制)"
        return 0
    fi

    # 编码检测
    dst_encoding=$(file -I "$dst" 2>/dev/null | grep -o 'charset=[^;]*' | cut -d= -f2 || echo "unknown")
    if [[ "$dst_encoding" != "utf-8" && "$dst_encoding" != "us-ascii" && "$dst_encoding" != "unknown" ]]; then
        echo "[跳过] $dst 编码 $dst_encoding 非 UTF-8，跳过增量追加" >&2
        return 2
    fi

    # 获取文件大小
    if [[ "$(uname)" == "Darwin" ]]; then
        src_size=$(stat -f%z "$src" 2>/dev/null || echo 0)
    else
        src_size=$(stat -c%s "$src" 2>/dev/null || echo 0)
    fi

    # >5MB 跳过
    if (( src_size > READ_SIZE_SKIP_THRESHOLD )); then
        echo "[跳过] $src 大小 $(numfmt --to=iec $src_size 2>/dev/null || echo "${src_size}B") >5MB，跳过增量追加，请手动处理" >&2
        return 2
    fi

    # 创建临时目录
    local tmp_dir
    tmp_dir=$(mktemp -d) || { echo "[错误] 无法创建临时目录" >&2; return 2; }
    local added=false

    # >1MB 使用 grep 批量预检
    if (( src_size > READ_SIZE_LARGE_THRESHOLD )); then
        # 大文件模式：按段落处理
        local paragraph=""
        while IFS= read -r line || [[ -n "$line" ]]; do
            if [[ "$line" =~ ^# ]]; then
                # 段落起点，检查前一段是否需要追加
                if [[ -n "$paragraph" ]]; then
                    if ! grep -Fq "$paragraph" "$dst" 2>/dev/null; then
                        echo "$paragraph" >> "$tmp_dir/new_content"
                        added=true
                    fi
                fi
                paragraph="$line"
            else
                paragraph="$paragraph"$'\n'"$line"
            fi
        done < "$src"
        # 处理最后一段
        if [[ -n "$paragraph" ]]; then
            if ! grep -Fq "$paragraph" "$dst" 2>/dev/null; then
                echo "$paragraph" >> "$tmp_dir/new_content"
                added=true
            fi
        fi
    else
        # 小文件模式：逐段全量比对
        local paragraph=""
        while IFS= read -r line || [[ -n "$line" ]]; do
            if [[ "$line" =~ ^# ]] || [[ -z "$line" && -n "$paragraph" ]]; then
                if [[ -n "$paragraph" ]]; then
                    if ! grep -Fq "$paragraph" "$dst" 2>/dev/null; then
                        echo "$paragraph" >> "$tmp_dir/new_content"
                        added=true
                    fi
                fi
                paragraph="$line"
            else
                paragraph="$paragraph"$'\n'"$line"
            fi
        done < "$src"
        if [[ -n "$paragraph" ]]; then
            if ! grep -Fq "$paragraph" "$dst" 2>/dev/null; then
                echo "$paragraph" >> "$tmp_dir/new_content"
                added=true
            fi
        fi
    fi

    if [[ "$added" == "true" ]]; then
        # 备份目标文件
        cp "$dst" "${dst}${BACKUP_SUFFIX}"
        echo "[备份] ${dst}${BACKUP_SUFFIX}"

        # 追加新内容
        cat "$tmp_dir/new_content" >> "$dst"
        local new_lines
        new_lines=$(wc -l < "$tmp_dir/new_content")
        echo "[增量追加] $dst ← $src ($new_lines 段新内容)"
    else
        echo "[跳过] $dst 已包含全部内容，无需追加"
    fi

    rm -rf "$tmp_dir"
    return 0
}

# ============================================================
# scan_deprecated — 扫描废弃段落
# 参数: $1 = target_file, $2 = source_version (可选)
# 输出: 标记为废弃的段落列表
# 废弃标记: 文件头部版本低于源版本、或包含 "deprecated" 标记的段落
# ============================================================
scan_deprecated() {
    local file="$1" src_ver="${2:-}"
    local file_ver deprecated_count=0

    if [[ ! -f "$file" ]]; then
        echo "[跳过] 文件不存在: $file"
        return 0
    fi

    file_ver=$(extract_version "$file") || file_ver=""

    echo "--- 扫描: $file ---"
    echo "当前版本: ${file_ver:-未标记}"
    echo "目标版本: ${src_ver:-未指定}"

    # 按段落扫描废弃标记
    local line_num=0
    local in_deprecated=false
    local dep_start=0

    while IFS= read -r line || [[ -n "$line" ]]; do
        ((line_num++))
        # 检查废弃标记
        if echo "$line" | grep -qiE '(deprecated|废弃|已弃用|obsolete|不再使用)'; then
            if [[ "$in_deprecated" == false ]]; then
                in_deprecated=true
                dep_start=$line_num
            fi
        fi
        # 段落结束检查
        if [[ -z "$line" && "$in_deprecated" == true ]]; then
            in_deprecated=false
            echo "  [废弃段落] 行 $dep_start-$((line_num-1))"
            ((deprecated_count++))
        fi
    done < "$file"

    if [[ "$in_deprecated" == true ]]; then
        echo "  [废弃段落] 行 $dep_start-$line_num (文件末尾)"
        ((deprecated_count++))
    fi

    if (( deprecated_count == 0 )); then
        echo "  ✅ 未发现废弃段落"
    fi

    echo "--- 扫描完成: $deprecated_count 个废弃段落 ---"
    return $deprecated_count
}

# ============================================================
# handle_bootstrap_file — Bootstrap 文件处理
# 参数: $1 = source_file, $2 = target_file, $3 = force (可选, 1=强制覆盖)
# 功能: 处理 bootstrap 文件，确保文件存在且版本正确
# bootstrap 文件 = 高优先级，MAJOR 变更时覆盖，同版本跳过
# ============================================================
handle_bootstrap_file() {
    local src="$1" dst="$2" force="${3:-0}"
    local src_ver dst_ver compare_result

    if [[ ! -f "$src" ]]; then
        echo "[Bootstrap 错误] 源文件不存在: $src" >&2
        return 2
    fi

    src_ver=$(extract_version "$src") || src_ver="0.0.0"
    dst_ver=$(extract_version "$dst") || dst_ver=""

    # 强制覆盖
    if [[ "$force" == "1" ]]; then
        mkdir -p "$(dirname "$dst")"
        if [[ -f "$dst" ]]; then
            cp "$dst" "${dst}${BACKUP_SUFFIX}"
            echo "[Bootstrap 备份] ${dst}${BACKUP_SUFFIX}"
        fi
        cp "$src" "$dst"
        echo "[Bootstrap 强制覆盖] $dst ← $src (v$src_ver)"
        return 0
    fi

    compare_result=$(version_compare "$src_ver" "$dst_ver")

    case "$compare_result" in
        3)  # 目标不存在 → 创建
            mkdir -p "$(dirname "$dst")"
            cp "$src" "$dst"
            echo "[Bootstrap 创建] $dst ← $src (v$src_ver)"
            return 0
            ;;
        1)  # MAJOR → 覆盖
            mkdir -p "$(dirname "$dst")"
            cp "$dst" "${dst}${BACKUP_SUFFIX}"
            cp "$src" "$dst"
            echo "[Bootstrap 覆盖] $dst ← $src (v$src_ver, 之前 v$dst_ver)"
            return 0
            ;;
        2)  # MINOR/PATCH → 尝试增量追加，但 bootstrap 优先追加头部
            append_incremental "$src" "$dst"
            return $?
            ;;
        0)  # 同版本 → 跳过
            echo "[Bootstrap 跳过] $dst 版本 $dst_ver == 源版本 $src_ver"
            return 1
            ;;
    esac
}

# ============================================================
# formatOCRReport — 生成 OCR 审查报告
# 参数: 从标准输入或文件读取检查结果
# 输出: 格式化的 Markdown 审查报告
# 被 .github/workflows/ocr-review.yml 引用
# ============================================================
formatOCRReport() {
    local report_file="${1:-/dev/stdin}"
    local title="${2:-OCR 审查报告}"
    local date_str
    date_str=$(date '+%Y-%m-%d %H:%M:%S %Z')

    cat <<EOF
# ${title}

**生成时间**: ${date_str}
**系统**: OCR 融合系统 (OpenClaw + Crestodian + RAG)
**版本**: v2.0.0-system

---

## 检查结果摘要

EOF

    if [[ -f "$report_file" ]]; then
        cat "$report_file"
    else
        echo "（无输入数据，报告为空）"
    fi

    cat <<EOF

---

## 结论

- **状态**: $(grep -c '\[FAIL\]' "$report_file" 2>/dev/null || echo 0) 项失败 / $(grep -c '\[PASS\]' "$report_file" 2>/dev/null || echo 0) 项通过
- **系统完整性**: $( [[ $(grep -c '\[FAIL\]' "$report_file" 2>/dev/null) -eq 0 ]] && echo "✅ 通过" || echo "🔴 失败")

---
*OCR 融合系统自动生成 — 版本 v2.0.0-system*
EOF
}

# 如果直接执行，显示帮助
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "OCR 融合系统核心函数库 v2.0.0"
    echo "用法: source core.sh 或 bash core.sh <function> [args...]"
    echo ""
    echo "可用函数:"
    echo "  extract_version <file>         — 提取文件版本标记"
    echo "  version_compare <src> <dst>    — 版本比对 (0跳过/1覆盖/2追加/3创建)"
    echo "  write_with_version <src> <dst> — 带版本标记写入"
    echo "  append_incremental <src> <dst> — 增量追加"
    echo "  scan_deprecated <file>         — 扫描废弃段落"
    echo "  handle_bootstrap_file <src> <dst> — Bootstrap 处理"
    echo "  formatOCRReport [file] [title] — 生成 OCR 审查报告"
fi