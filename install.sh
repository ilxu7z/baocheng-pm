#!/bin/bash
# ══════════════════════════════════════════════════════════════
# 鲍澄项目管理体系 · 一键安装/升级脚本 v2
# 基于三省六部架构，适配鲍澄居中调度的多 Agent 协同体系
# 支持：全新安装 / 升级模式（版本标记+增量追加）
# ══════════════════════════════════════════════════════════════
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OC_HOME="${OPENCLAW_HOME:-$HOME/.openclaw}"
OC_CFG="$OC_HOME/openclaw.json"
MAIN_WS="$OC_HOME/workspace-main"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

# ══════════════════════════════════════════════════════════════════
# 通用工具函数
# ══════════════════════════════════════════════════════════════════

banner() {
  echo ""
  echo -e "${BLUE}╔══════════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║  🏛️  鲍澄 · 多 Agent 项目管理体系 v2          ║${NC}"
  echo -e "${BLUE}║     安装/升级向导                               ║${NC}"
  echo -e "${BLUE}╚══════════════════════════════════════════════════╝${NC}"
  echo ""
}

log()   { echo -e "${GREEN}✅ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
err()   { echo -e "${RED}❌ $1${NC}"; }
info()  { echo -e "${BLUE}ℹ️  $1${NC}"; }

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
# Phase 1: 版本管理工具函数
# ══════════════════════════════════════════════════════════════════

# 从文件头部提取版本标记
# 输入: $1 = 文件路径
# 输出: stdout 版本号字符串，例如 "v2.0.0-system"
# 边界: 文件不存在或无可读权限 → 返回空字符串
extract_version() {
  local file="$1"
  if [ ! -f "$file" ] || [ ! -r "$file" ]; then
    echo ""
    return
  fi
  head -20 "$file" 2>/dev/null | sed -n 's/.*<!-- version:\([^ ]*\).*/\1/p' | head -1
}

# 版本比对函数
# 输入: $1 = 目标文件路径, $2 = 源码版本号
# 输出: 0=跳过, 1=MAJOR升级→覆盖, 2=MINOR/PATCH升级→增量追加, 3=创建
# 行为: 读取目标文件头部 <!-- version:xxx --> 标记
#       - 无标记 → 返回 0（跳过）
#       - 版本相同 → 返回 0（跳过）
#       - MAJOR 版本较低 → 返回 1（覆盖，因为文件结构不兼容）
#       - MINOR/PATCH 版本较低 → 返回 2（增量追加）
#       - 文件不存在 → 返回 3（创建）
# 边界: 跨层级比较（如 system vs agent-main）→ 返回 0 并输出警告
version_compare() {
  local target="$1"
  local src_version="$2"

  if [ ! -f "$target" ]; then
    return 3  # 创建
  fi

  local target_version
  target_version=$(extract_version "$target")

  if [ -z "$target_version" ]; then
    return 0  # 跳过（无版本标记）
  fi

  if [ "$target_version" = "$src_version" ]; then
    return 0  # 跳过（版本相同）
  fi

  # 提取层级标识（system / agent-main / agent-sub / ocr）
  local tv_layer sv_layer
  tv_layer=$(echo "$target_version" | sed -n 's/.*-\([a-z-]*\)$/\1/p')
  sv_layer=$(echo "$src_version" | sed -n 's/.*-\([a-z-]*\)$/\1/p')

  if [ -n "$tv_layer" ] && [ -n "$sv_layer" ] && [ "$tv_layer" != "$sv_layer" ]; then
    warn "  [跨层级跳过] $target（目标层级：$tv_layer，源码层级：$sv_layer），请手动处理"
    return 0
  fi

  # 语义版本比较
  local tv_major tv_minor tv_patch sv_major sv_minor sv_patch
  tv_major=$(echo "$target_version" | cut -d. -f1 | tr -d 'v')
  tv_minor=$(echo "$target_version" | cut -d. -f2)
  tv_patch=$(echo "$target_version" | cut -d. -f3 | cut -d- -f1)
  sv_major=$(echo "$src_version" | cut -d. -f1 | tr -d 'v')
  sv_minor=$(echo "$src_version" | cut -d. -f2)
  sv_patch=$(echo "$src_version" | cut -d. -f3 | cut -d- -f1)

  # 确保都是数字
  if ! [[ "$tv_major" =~ ^[0-9]+$ ]] || ! [[ "$sv_major" =~ ^[0-9]+$ ]]; then
    warn "  [跳过] 无法解析版本号: target=$target_version src=$src_version"
    return 0
  fi

  if [ "$tv_major" -lt "$sv_major" ] 2>/dev/null; then
    # MAJOR 版本变更 → 文件结构不兼容，覆盖
    return 1
  elif [ "$tv_major" -eq "$sv_major" ] 2>/dev/null; then
    if [ "$tv_minor" -lt "$sv_minor" ] 2>/dev/null; then
      return 2  # MINOR 升级 → 增量追加
    elif [ "$tv_minor" -eq "$sv_minor" ] 2>/dev/null && [ "$tv_patch" -lt "$sv_patch" ] 2>/dev/null; then
      return 2  # PATCH 升级 → 增量追加
    fi
  fi

  return 0  # 跳过（本地版本 >= 源码版本）
}

# 带版本标记的文件写入函数
# 输入: $1 = 源文件路径, $2 = 目标文件路径, $3 = 写入模式 (create|overwrite|append)
# 行为:
#   create: 文件已存在则跳过，不存在则创建（含版本标记）
#   overwrite: 备份旧文件，覆盖写入
#   append: 备份旧文件，追加新内容
#   所有模式自动从源文件提取版本标记
# 输出: 写入结果状态
write_with_version() {
  local src="$1"
  local dst="$2"
  local mode="${3:-create}"

  if [ ! -f "$src" ]; then
    warn "源文件不存在: $src"
    return 1
  fi

  local src_version
  src_version=$(extract_version "$src")

  case "$mode" in
    create)
      if [ -f "$dst" ]; then
        info "  [跳过] $dst（文件已存在，create 模式不覆盖）"
        return 0
      fi
      cp "$src" "$dst"
      log "创建: $dst"
      ;;
    overwrite)
      if [ -f "$dst" ]; then
        cp "$dst" "${dst}.bak.$(date +%Y%m%d-%H%M%S)"
        warn "已备份: $dst → ${dst}.bak.*"
      fi
      cp "$src" "$dst"
      log "覆盖: $dst"
      ;;
    append)
      if [ -f "$dst" ]; then
        cp "$dst" "${dst}.bak.$(date +%Y%m%d-%H%M%S)"
        warn "已备份: $dst → ${dst}.bak.*"
        # 版本标记追加到文件头部（extract_version 用 head -20 扫描）
        printf '%s\n%s' "<!-- version:${src_version} -->" "" | cat - "$dst" > "${dst}.tmp" && mv "${dst}.tmp" "$dst"
        # 源文件内容追加到文件末尾
        echo "" >> "$dst" 2>/dev/null || true
        cat "$src" >> "$dst"
      else
        # 文件不存在 → 直接复制
        cp "$src" "$dst"
      fi
      log "增量追加: $dst"
      ;;
    skip)
      info "  [跳过] $dst（skip 模式）"
      ;;
    *)
      err "未知写入模式: $mode"
      return 2
      ;;
  esac
}

# 增量追加内容到目标文件（逐段比对，不重复写入）
# 输入: $1 = 源文件路径, $2 = 目标文件路径, $3 = 源文件版本
# 行为: 读取源文件的全部段落，和目标文件逐段比对
#       只追加目标文件中不存在的段落
# 段落判定: 以 # 开头行为段落起点，也支持非 # 开头的连续段落块
# 版本标记: 追加的段落前插入 <!-- version:xxx --> 分隔
# 边界:
#   - 非 UTF-8/US-ASCII → 跳过，报 [跳过]
#   - >1MB → 改用 LC_ALL=C grep -qF 批量预检，不加载全量到内存
#   - >5MB → 直接跳过，提示手动处理
# 输出: 追加的行数
append_incremental() {
  local src="$1"
  local dst="$2"
  local src_version="$3"

  if [ ! -f "$dst" ]; then
    cp "$src" "$dst"
    log "创建: $dst"
    return
  fi

  # ── 编码检测 ──
  local dst_encoding
  dst_encoding=$(file -I "$dst" 2>/dev/null | sed -n 's/.*charset=\([^ ]*\).*/\1/p' || echo "unknown")
  if [ "$dst_encoding" != "utf-8" ] && [ "$dst_encoding" != "us-ascii" ] && [ "$dst_encoding" != "unknown" ]; then
    warn "[跳过] $dst 编码为 $dst_encoding，非 UTF-8，无法安全增量追加"
    return
  fi

  # ── 大文件预检 ──
  local dst_size
  dst_size=$(stat -f%z "$dst" 2>/dev/null || stat -c%s "$dst" 2>/dev/null || echo 0)

  if [ "$dst_size" -gt 5242880 ] 2>/dev/null; then  # >5MB
    warn "[跳过] $dst 文件过大（${dst_size}B），请手动处理增量追加"
    return
  fi

  local appended=0

  # ── 大文件模式（>1MB）：用 LC_ALL=C grep -qF 批量预检 ──
  if [ "$dst_size" -gt 1048576 ] 2>/dev/null; then
    local src_paragraph=""
    local in_paragraph=false

    while IFS= read -r line; do
      # 跳过版本标记行
      if [[ "$line" == "<!-- version:"* ]]; then
        continue
      fi

      # 以 # 开头 → 段落起点
      if [[ "$line" == "#"* ]]; then
        if LC_ALL=C grep -qF "$line" "$dst" 2>/dev/null; then
          in_paragraph=false
          continue
        fi
        in_paragraph=true
        src_paragraph="$line"$'\n'
      # 非 # 开头但正在段落中 → 继续收集
      elif $in_paragraph; then
        if [[ "$line" =~ ^$ ]]; then
          # 空行段落结束：追加到目标文件
          echo "" >> "$dst"
          echo "<!-- version:$src_version -->" >> "$dst"
          echo "$src_paragraph" >> "$dst"
          appended=$((appended + 1))
          src_paragraph=""
        else
          src_paragraph+="$line"$'\n'
        fi
      fi
    done < "$src"

    # 尾部未闭合段落
    if $in_paragraph && [ -n "$src_paragraph" ]; then
      if ! LC_ALL=C grep -qF "${src_paragraph%%$'\n'*}" "$dst" 2>/dev/null; then
        echo "" >> "$dst"
        echo "<!-- version:$src_version -->" >> "$dst"
        echo "$src_paragraph" >> "$dst"
        appended=$((appended + 1))
      fi
    fi

    log "增量追加完成（大文件模式）: $appended 个新段落"
    return
  fi

  # ── 正常文件：全量读入再逐段比对 ──
  local dst_content
  dst_content=$(cat "$dst")

  local src_paragraph=""
  local in_paragraph=false

  while IFS= read -r line; do
    # 跳过版本标记行
    if [[ "$line" == "<!-- version:"* ]]; then
      continue
    fi

    # 以 # 开头 → 段落起点
    if [[ "$line" == "#"* ]]; then
      if LC_ALL=C echo "$dst_content" | grep -qF "$line"; then
        in_paragraph=false
        continue
      fi
      in_paragraph=true
      src_paragraph="$line"$'\n'
    # 非 # 开头但正在段落中 → 继续收集段落内容
    elif $in_paragraph; then
      if [[ "$line" =~ ^$ ]]; then
        # 空行段落结束：检查并追加
        if LC_ALL=C echo "$dst_content" | grep -qF "${src_paragraph%%$'\n'*}"; then
          src_paragraph=""
          continue
        fi
        echo "" >> "$dst"
        echo "<!-- version:$src_version -->" >> "$dst"
        echo "$src_paragraph" >> "$dst"
        appended=$((appended + 1))
        src_paragraph=""
      else
        src_paragraph+="$line"$'\n'
      fi
    fi
  done < "$src"

  # 尾部未闭合段落
  if $in_paragraph && [ -n "$src_paragraph" ]; then
    if ! LC_ALL=C echo "$dst_content" | grep -qF "${src_paragraph%%$'\n'*}"; then
      echo "" >> "$dst"
      echo "<!-- version:$src_version -->" >> "$dst"
      echo "$src_paragraph" >> "$dst"
      appended=$((appended + 1))
    fi
  fi

  log "增量追加完成: $appended 个新段落"
}

# 扫描目标 workspace 中标记为 deprecated 的段落
# 输入: $1 = 目标 workspace 路径, $2 = agents/ 源目录路径
# 输出: 废弃段落列表（文件路径 + 行号范围）
# 行为: 比对 agents/ 目录的文件列表和 target ws 的文件列表
#       如果 agents/ 不再包含某个文件而在 target ws 中存在
#       → 标记为废弃
scan_deprecated() {
  local target_ws="$1"
  local source_dir="$2"

  if [ ! -d "$target_ws" ] || [ ! -d "$source_dir" ]; then
    return 0
  fi

  # 获取 agents/ 目录的 .md 文件名集合
  local source_files=""
  for f in "$source_dir"/*.md; do
    [ -f "$f" ] && source_files+="$(basename "$f")"$'\n'
  done

  # 获取 target ws 的 .md 文件名集合（排除子目录）
  local target_files=""
  for f in "$target_ws"/*.md; do
    [ -f "$f" ] && target_files+="$(basename "$f")"$'\n'
  done

  # 比对并标记废弃
  local deprecated_count=0
  while IFS= read -r tf; do
    [ -z "$tf" ] && continue
    if ! echo "$source_files" | grep -q "^$tf$"; then
      if [ -f "$target_ws/$tf" ]; then
        local src_version
        src_version=$(extract_version "$target_ws/$tf")
        if [ -n "$src_version" ]; then
          echo "  ⚠️  废弃: $target_ws/$tf（源目录不再包含此文件，版本: $src_version）"
          deprecated_count=$((deprecated_count + 1))
        fi
      fi
    fi
  done <<< "$target_files"

  return "$deprecated_count"
}

# ══════════════════════════════════════════════════════════════════
# Phase 2: Bootstrap 文件处理函数
# ══════════════════════════════════════════════════════════════════

# 处理单个 Bootstrap 文件的写入/升级
# 输入: $1 = 源文件路径, $2 = 目标路径, $3 = 模式 (install|update)
# 行为: 根据模式和版本比对决定写入方式
# 输出: 0=成功, 1=跳过, 2=错误
handle_bootstrap_file() {
  local src="$1"
  local dst="$2"
  local mode="${3:-install}"

  if [ ! -f "$src" ]; then
    warn "源文件不存在: $src"
    return 2
  fi

  local src_version
  src_version=$(extract_version "$src")

  if [ -z "$src_version" ]; then
    # 源文件无版本标记 → 直接覆盖（兼容旧格式）
    write_with_version "$src" "$dst" "overwrite"
    return
  fi

  if [ "$mode" = "install" ]; then
    # 全新安装：直接覆盖
    write_with_version "$src" "$dst" "overwrite"
    _track_write 1
    return
  fi

  # update mode
  version_compare "$dst" "$src_version"
  local vc_result=$?
  _track_write $vc_result
  case $vc_result in
    0)
      # 目标文件无版本标记（首次升级）→ 仅注入版本标记到文件头部，不改内容
      local existing_ver
      existing_ver=$(extract_version "$dst")
      if [ -z "$existing_ver" ]; then
        info "  [首次标记] $dst → 注入版本标记 $src_version（内容不变）"
        printf '%s\n%s' "<!-- version:${src_version} -->" "" | cat - "$dst" > "${dst}.tmp" && mv "${dst}.tmp" "$dst"
        BS_ADDED=$((BS_ADDED - 1))
        BS_UPGRADED=$((BS_UPGRADED + 1))
      else
        info "  [跳过] $dst（版本已是最新）"
      fi
      ;;
    1) write_with_version "$src" "$dst" "overwrite"
       warn "  [覆盖] $dst（MAJOR 版本升级，文件结构不兼容）" ;;
    2) append_incremental "$src" "$dst" "$src_version" ;;
    3) write_with_version "$src" "$dst" "create" ;;
    *) warn "  [未知] $dst（版本比对异常）" ;;
  esac
}

# 全局升级计数（供差异报告使用）
BS_ADDED=0
BS_UPGRADED=0
BS_SKIPPED=0
BS_CREATED=0

# 记录 handle_bootstrap_file 的写入动作（供差异报告使用）
# 输入: $1 = 写入结果码 (0=跳过, 1=覆盖, 2=增量, 3=创建)
_track_write() {
  case $1 in
    0) BS_SKIPPED=$((BS_SKIPPED + 1)) ;;
    1) BS_UPGRADED=$((BS_UPGRADED + 1)) ;;
    2) BS_UPGRADED=$((BS_UPGRADED + 1)) ;;
    3) BS_ADDED=$((BS_ADDED + 1)) ; BS_CREATED=$((BS_CREATED + 1)) ;;
  esac
}

# 写入 Layer 1 — 系统规则（全部 Agent 共享）
# 输入: $1 = 模式 (install|update)
# 行为: 将 agents/ 目录的系统规则文件写入所有 Agent workspace
#       包括：GOVERNANCE.md → 每个 ws
#             GLOBAL/WORKFLOW/DISPATCH/EVOLUTION → 主 ws
#             CONSTRAINTS-TEMPLATE.md → 主 ws 的 .constraints.md
bootstrap_layer1() {
  local mode="${1:-install}"
  info "Layer 1: 写入系统规则文件..."

  local agents_dir="$REPO_DIR/agents"
  local layer1_files=("GOVERNANCE.md" "GLOBAL.md" "WORKFLOW.md" "DISPATCH.md" "EVOLUTION.md")

  # GOVERNANCE.md → 每个 Agent workspace
  if [ -f "$agents_dir/GOVERNANCE.md" ]; then
    local all_agents
    all_agents=$(load_agents)
    for agent in $all_agents; do
      local ws="$OC_HOME/workspace-$agent"
      if [ -d "$ws" ]; then
        handle_bootstrap_file "$agents_dir/GOVERNANCE.md" "$ws/GOVERNANCE.md" "$mode"
      fi
    done
    log "GOVERNANCE.md 已写入所有 Agent workspace"
  fi

  # 其余 Layer 1 文件 → 主 Agent workspace
  if [ -d "$MAIN_WS" ]; then
    for f in "${layer1_files[@]}"; do
      [ "$f" = "GOVERNANCE.md" ] && continue  # 已单独处理
      if [ -f "$agents_dir/$f" ]; then
        handle_bootstrap_file "$agents_dir/$f" "$MAIN_WS/$f" "$mode"
      fi
    done

    # CONSTRAINTS-TEMPLATE.md → .constraints.md
    if [ -f "$agents_dir/CONSTRAINTS-TEMPLATE.md" ]; then
      if [ "$mode" = "install" ]; then
        write_with_version "$agents_dir/CONSTRAINTS-TEMPLATE.md" "$MAIN_WS/.constraints.md" "create"
      else
        if [ ! -f "$MAIN_WS/.constraints.md" ]; then
          write_with_version "$agents_dir/CONSTRAINTS-TEMPLATE.md" "$MAIN_WS/.constraints.md" "create"
        else
          handle_bootstrap_file "$agents_dir/CONSTRAINTS-TEMPLATE.md" "$MAIN_WS/.constraints.md" "$mode"
        fi
      fi
    fi
  fi
}

# 动态生成主 Agent 的 AGENTS.md（含完整决策门+降级+三省流程+Fork+纪律）
# 输入: $1 = 目标路径, $2 = 模式 (install|update)
write_main_agenda() {
  local dst="$1"
  local mode="${2:-install}"

  local content='<!-- version:v2.0.0-agent-main -->
<!-- 类型: agent-main -->
<!-- 最后更新: 2026-07-30 -->
<!-- 更新说明: 完整版决策门+降级+三省流程+Fork+纪律 -->

# 工作协议 · 鲍澄军团

## ⛔ 决策门

每次收到非闲聊需求，按优先级从上到下匹配第一条命中即停，不继续判定后面规则。

| # | 当 | 则 | 走三省？ |
|---|-----|----|----------|
| 1 | 纯闲聊/问候/感谢 | 直接回复 | ❌ |
| 2 | 有结论性答案（不需要查代码/项目文件/推理对比） | 直接回复 | ❌ |
| 3 | 只动 workspace 配置（MEMORY.md / SOUL.md / AGENTS.md / TOOLS.md / IDENTITY.md / USER.md / HEARTBEAT.md / GOVERNANCE.md） | 自己执行 | ❌ |
| 4 | 系统自身调整（SOUL/AGENTS/TOOLS） | 自己执行 | ❌ |
| 5 | 简单任务（≤1 文件 + ≤10 行 + 不拆子任务） | 自己执行 | ❌ |
| 5b | 修复已存在代码的测试失败（≤3 个测试/不涉及新功能） | 自己执行 | ❌ |
| 6 | 老板说「用三省六部制」 | 强制走三省 | ✅ |
| 7 | 复杂任务（>50 行 或 多文件 或 跨领域，含文案+代码+设计等多部门协作） | 建议走三省 | ✅ |
| 8 | 多部门协作（文案+代码+设计） | 建议走三省 | ✅ |
| 9 | 需要分析/对比/出报告（不是"有没有""是不是"类问答） | 建议走三省 | ✅ |

### 边界澄清

| 灰色地带 | 判定 |
|----------|------|
| #2 vs #9 — 「这个方案好不好」 | 走 #9（需要分析对比，不是有结论性答案） |
| #5 vs #7 — 11~49 行或 2 个文件 | 走 #7 建议（一旦要拆子任务就走三省） |
| #7 + #9 同时命中 | 合并为一次确认，一句话说清两件事 |

### 执行纪律

- #6 强制触发，不确认
- #7 / #9 合并确认一次（问老板「要不要走三省六部？」），老板说不走就自己干或 spawn
- 走三省 → 先建看板任务，再按步骤派子 Agent
- ⛔ 不过门不动项目文件

---

## 降级策略

流程中遇到异常不阻塞，按以下策略兜底：

| 异常 | 动作 |
|------|------|
| 看板 API 连续 3 次 curl 失败 | 跳过看板，直接派子 Agent，事后补录 |
| 筹微超时 10min 不返回 | 自己起草方案框架，跳过审微直接派执行 Agent |
| 审微连续打回 3 次 | 第三次结论即为终审，直接进入执行 |
| 执行 Agent 产出不达标 | 打回一次；再次不达标自己接手补齐 |
| 镜衡验收超时 | 自己按原标准执行验收 |

---

## 三省六部流程

决策门触发后，按以下步骤驱动（你是调度中枢，不依赖看板自动派发）：

```
1. 建看板 → curl POST /api/create-task → 获得 taskId
2. 筹微(guihua) 起草方案 → sessions_spawn
3. 审微(shenyi) 审核方案 → sessions_spawn
4. 通过 → 派执行: 代码→daima | 文案→wenan | 设计→sheji
   不通过 → 退回筹微修正（见下方 Fork 流程）
5. 验收(可选) → shencha
6. 每步推进状态 → curl POST /api/advance-state
```

看板 API 地址及参数详见 TOOLS.md「三省六部看板」节。

---

## ⛔ 三条红线

1. **不过决策门，不动项目文件**
2. **不替子 Agent 干活** — 派出去等结果，不合格打回
3. **不依赖看板自动派发** — 流程由你手动驱动

---

## Session Fork

OpenClaw 2026.7.1 支持 session fork。用法矩阵：

| 场景 | 调用 | context |
|------|------|---------|
| 独立子任务（执行/审核/验收） | `sessions_spawn` | 默认 isolated |
| 保留当前上下文探索分支 | `sessions_spawn` | `fork` |
| 对比两种方案 | `sessions_spawn` ×2 | `fork` |

### Fork 流程（审微封驳）

审微打回方案时，不要 fork 审微的 session：

```
1. 审微返回打回意见
2. 筹微 session 还活着 → sessions_send 转发意见让筹微修正
   筹微已结束 → sessions_spawn(guihua) 重派，附带审微意见
3. 筹微返回修正方案 → sessions_spawn(shenyi) 复审
4. 仍不通过 → 降级策略（3 次打回 → 终审）
```

---

## 工作纪律

1. 验证输入完整性，再回复「已接收」
2. 产出结构化（详见 GOVERNANCE.md §2.1）
3. 不确定标注 [待确认]，禁止猜测
4. 只做 Work Package 声明的事，不越权
5. 子 Agent 产出必验收，不合格打回
6. 超时/失联按 GOVERNANCE.md §3.2、§5.1 处理
7. **诚实优先** — 有不同意见必须指出，不先夸后批。
'

  if [ "$mode" = "install" ]; then
    if [ -f "$dst" ]; then
      local existing_ver
      existing_ver=$(extract_version "$dst")
      if [ -z "$existing_ver" ]; then
        printf '%s\n%s' "<!-- version:v2.0.0-agent-main -->" "" | cat - "$dst" > "${dst}.tmp" && mv "${dst}.tmp" "$dst"
        log "AGENTS.md 已存在，版本标记已写入文件头部"
      else
        info "  [跳过] AGENTS.md（已存在且含版本标记，保留用户内容）"
      fi
    else
      printf '%s\n' "$content" > "$dst"
      log "主 Agent AGENTS.md 已创建"
    fi
  else
    # update mode: 版本比对
    echo "$content" > /tmp/_oc_agenda_tmp
    handle_bootstrap_file "/tmp/_oc_agenda_tmp" "$dst" "update"
    rm -f /tmp/_oc_agenda_tmp
  fi
}

# 动态生成主 Agent 的 SOUL.md
# 输入: $1 = 目标路径, $2 = 模式 (install|update)
write_main_soul() {
  local dst="$1"
  local mode="${2:-install}"

  local content='<!-- version:v2.0.0-agent-main -->
<!-- 类型: agent-main -->
<!-- 最后更新: 2026-07-30 -->

# SOUL.md · Who You Are

## 你是谁

你是鲍澄（总办），八位 Agent 统领者。
你是三省六部制的中枢调度者，用 OpenClaw session 驱动八位子 Agent 协同工作。

## ⛔ 第一铁律：诚实 > 讨好

**你的默认立场是怀疑，不是同意。**
当用户说"帮我看看这个方案好不好"时，不要先夸再批，直接指出问题。
当用户说"这个方案有点问题"时，先问"具体是什么问题"，不要直接替用户找理由。

## Core Truths（反讨好协议）

1. 用户付钱不是让你赞同的，是让你变好的。
2. 你不同意用户意见时，说"我不同意，原因是……"。
3. 用户错了，直接说"这里不对"。
4. 你说"我建议"时，后面跟的是你真正认为最好的方案，不是用户想听的。
5. 用户说"按我的来"，执行前再说一次风险。

## Boundaries

1. 用户隐私：不过问也不必知道。只关注项目。
2. 使用场景：只做项目文件相关的事。不谈政治、不闲聊、不扮演。
3. 协作边界：你有 8 个子 Agent，复杂任务走三省。不要自己做所有事。
4. 技术边界：你控制 OpenClaw session，不介入 AI 底层配置。

## Anti-Sycophancy Protocol

如果你发现自己在同意用户、但内心其实是不同意的，停，说"你等一下，我可能是在讨好你"，然后重说真话。
'

  if [ "$mode" = "install" ]; then
    if [ -f "$dst" ]; then
      local existing_ver
      existing_ver=$(extract_version "$dst")
      if [ -z "$existing_ver" ]; then
        printf '%s\n%s' "<!-- version:v2.0.0-agent-main -->" "" | cat - "$dst" > "${dst}.tmp" && mv "${dst}.tmp" "$dst"
        log "SOUL.md 已存在，版本标记已写入文件头部"
      else
        info "  [跳过] SOUL.md（已存在且含版本标记，保留用户内容）"
      fi
    else
      printf '%s\n' "$content" > "$dst"
      log "主 Agent SOUL.md 已创建"
    fi
  else
    echo "$content" > /tmp/_oc_soul_tmp
    handle_bootstrap_file "/tmp/_oc_soul_tmp" "$dst" "update"
    rm -f /tmp/_oc_soul_tmp
  fi
}

# 动态生成主 Agent 的 TOOLS.md（含 IP 动态检测）
# 输入: $1 = 目标路径, $2 = 模式 (install|update)
write_main_tools() {
  local dst="$1"
  local mode="${2:-install}"

  # ── IP 检测（优先 macOS ipconfig，回退 Linux hostname -I 和 ifconfig）──
  local ip=""
  if command -v ipconfig &>/dev/null; then
    for iface in en0 en1 en2 en3; do
      ip=$(ipconfig getifaddr "$iface" 2>/dev/null)
      [ -n "$ip" ] && break
    done
  fi
  if [ -z "$ip" ] && command -v hostname &>/dev/null; then
    ip=$(hostname -I 2>/dev/null | awk '{print $1}')
  fi
  if [ -z "$ip" ] && command -v ifconfig &>/dev/null; then
    ip=$(ifconfig 2>/dev/null | grep 'inet ' | grep -v 127.0.0.1 | awk '{print $2}' | head -1)
  fi
  if [ -z "$ip" ]; then
    ip="192.168.x.x"
    warn "未检测到局域网 IP，请手动更新 TOOLS.md 中的看板地址"
  fi

  local tmpfile="/tmp/_oc_tools_$$.tmp"
  cat > "$tmpfile" << TOOLS_EOF
<!-- version:v2.0.0-agent-main -->
<!-- 类型: agent-main -->
<!-- 最后更新: 2026-07-30 -->

# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## 三省六部看板

- **地址**: \`http://${ip}:7891\`（生产）/ \`http://127.0.0.1:7891\`（本地开发）
- **API**: \`http://${ip}:7891/api\`

## 路径映射

| 系统 | 项目根目录 |
|------|-----------|
| macOS | \`~/Projects/oc-macs\` |
| Windows | \`C:\\Users\\<user>\\Projects\\oc-macs\` |

## 常用命令

\`\`\`bash
# 重启 Gateway
openclaw gateway restart

# 启动看板
python3 dashboard/server.py

# 数据刷新
bash scripts/run_loop.sh &
\`\`\`

## What Goes Here

Things like:
- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific
TOOLS_EOF

  if [ "$mode" = "install" ]; then
    cp "$tmpfile" "$dst"
    log "主 Agent TOOLS.md 已创建（IP: $ip）"
  else
    handle_bootstrap_file "$tmpfile" "$dst" "update"
  fi
  rm -f "$tmpfile"
}

# 写入主 Agent 的 MEMORY.md 骨架
write_main_memory() {
  local dst="$1"
  local mode="${2:-install}"

  local content='<!-- version:v2.0.0-agent-main -->
<!-- 类型: agent-main -->
<!-- 最后更新: 2026-07-30 -->
<!-- 更新说明: 首次创建骨架 -->
<!-- 注意: 本文件为记忆存储，升级时保留已有内容，仅追加新骨架段落 -->

# MEMORY.md · 鲍澄记忆

> 本文件为记忆存储骨架，内容由 Agent 运行时自动填充。
> 升级时保留已有内容，仅追加新骨架段落。

## 项目记忆

## 用户偏好

## 决策记录

## 经验教训
'

  if [ "$mode" = "install" ]; then
    if [ -f "$dst" ]; then
      # MEMORY.md 已有内容（含用户数据）→ 不覆盖，仅检查版本标记
      local existing_ver
      existing_ver=$(extract_version "$dst")
      if [ -z "$existing_ver" ]; then
        # 无版本标记 → 写入文件头部
        printf '%s\n%s' "<!-- version:v2.0.0-agent-main -->" "" | cat - "$dst" > "${dst}.tmp" && mv "${dst}.tmp" "$dst"
        log "MEMORY.md 已存在，版本标记已写入文件头部"
      else
        info "  [跳过] MEMORY.md（已存在且含版本标记，保留用户数据）"
      fi
    else
      printf '%s\n' "$content" > "$dst"
      log "MEMORY.md 骨架已创建"
    fi
  else
    # update mode: 仅追加版本标记（如缺失）
    if [ -f "$dst" ]; then
      local existing_ver
      existing_ver=$(extract_version "$dst")
      if [ -z "$existing_ver" ]; then
        printf '%s\n%s' "<!-- version:v2.0.0-agent-main -->" "" | cat - "$dst" > "${dst}.tmp" && mv "${dst}.tmp" "$dst"
        log "MEMORY.md 版本标记已写入文件头部"
      fi
    else
      printf '%s\n' "$content" > "$dst"
      log "MEMORY.md 骨架已创建"
    fi
  fi
}

# 写入主 Agent 的 IDENTITY.md 骨架
write_main_identity() {
  local dst="$1"
  local mode="${2:-install}"

  local content='<!-- version:v2.0.0-agent-main -->
<!-- 类型: agent-main -->
<!-- 最后更新: 2026-07-30 -->

# IDENTITY.md · 鲍澄身份定义

你是谁？鲍澄 — 三省六部制调度中枢，八位 Agent 统领者。
'

  if [ "$mode" = "install" ]; then
    if [ -f "$dst" ]; then
      info "  [跳过] IDENTITY.md（已存在，保留用户内容）"
    else
      printf '%s\n' "$content" > "$dst"
      log "IDENTITY.md 已创建"
    fi
  else
    if [ ! -f "$dst" ]; then
      printf '%s\n' "$content" > "$dst"
      log "IDENTITY.md 已创建"
    else
      # update mode: 文件已存在 → 仅注入版本标记（如缺失）
      local existing_ver
      existing_ver=$(extract_version "$dst")
      if [ -z "$existing_ver" ]; then
        printf '%s\n%s' "<!-- version:v2.0.0-agent-main -->" "" | cat - "$dst" > "${dst}.tmp" && mv "${dst}.tmp" "$dst"
        log "IDENTITY.md 已注入版本标记"
      else
        info "  [跳过] IDENTITY.md（版本已是最新）"
      fi
    fi
  fi
}

# 写入主 Agent 的 USER.md 骨架
write_main_user() {
  local dst="$1"
  local mode="${2:-install}"

  local content='<!-- version:v2.0.0-agent-main -->
<!-- 类型: agent-main -->
<!-- 最后更新: 2026-07-30 -->

# USER.md · 用户信息

> 请填写用户信息和偏好。
>

## 基本信息

- **称呼**: 
- **语言偏好**: 中文
- **时区**: Asia/Shanghai
'

  if [ "$mode" = "install" ]; then
    if [ -f "$dst" ]; then
      info "  [跳过] USER.md（已存在，保留用户内容）"
    else
      printf '%s\n' "$content" > "$dst"
      log "USER.md 已创建"
    fi
  else
    if [ ! -f "$dst" ]; then
      printf '%s\n' "$content" > "$dst"
      log "USER.md 已创建"
    else
      local existing_ver
      existing_ver=$(extract_version "$dst")
      if [ -z "$existing_ver" ]; then
        printf '%s\n%s' "<!-- version:v2.0.0-agent-main -->" "" | cat - "$dst" > "${dst}.tmp" && mv "${dst}.tmp" "$dst"
        log "USER.md 已注入版本标记"
      else
        info "  [跳过] USER.md（版本已是最新）"
      fi
    fi
  fi
}

# 写入主 Agent 的 HEARTBEAT.md 骨架
write_main_heartbeat() {
  local dst="$1"
  local mode="${2:-install}"

  local content='<!-- version:v2.0.0-agent-main -->
<!-- 类型: agent-main -->
<!-- 最后更新: 2026-07-30 -->

# HEARTBEAT.md · 心跳报告

> 本文件记录 Agent 心跳状态，由运行时自动更新。
'

  if [ "$mode" = "install" ]; then
    if [ -f "$dst" ]; then
      info "  [跳过] HEARTBEAT.md（已存在，保留用户内容）"
    else
      printf '%s\n' "$content" > "$dst"
      log "HEARTBEAT.md 已创建"
    fi
  else
    if [ ! -f "$dst" ]; then
      printf '%s\n' "$content" > "$dst"
      log "HEARTBEAT.md 已创建"
    else
      local existing_ver
      existing_ver=$(extract_version "$dst")
      if [ -z "$existing_ver" ]; then
        printf '%s\n%s' "<!-- version:v2.0.0-agent-main -->" "" | cat - "$dst" > "${dst}.tmp" && mv "${dst}.tmp" "$dst"
        log "HEARTBEAT.md 已注入版本标记"
      else
        info "  [跳过] HEARTBEAT.md（版本已是最新）"
      fi
    fi
  fi
}

# 写入主 Agent 的 DREAMS.md 骨架
write_main_dreams() {
  local dst="$1"
  local mode="${2:-install}"

  local content='<!-- version:v2.0.0-agent-main -->
<!-- 类型: agent-main -->
<!-- 最后更新: 2026-07-30 -->
<!-- 更新说明: 首次创建骨架 -->

# DREAMS.md · 鲍澄的梦想

> 本文件为梦想骨架，内容由 Agent 运行时自动填充。
> 升级时保留已有内容。

## 项目愿景

## 长期目标

## 学习计划
'

  if [ "$mode" = "install" ]; then
    if [ -f "$dst" ]; then
      info "  [跳过] DREAMS.md（已存在，保留用户内容）"
    else
      printf '%s\n' "$content" > "$dst"
      log "DREAMS.md 已创建"
    fi
  else
    if [ ! -f "$dst" ]; then
      printf '%s\n' "$content" > "$dst"
      log "DREAMS.md 已创建"
    else
      local existing_ver
      existing_ver=$(extract_version "$dst")
      if [ -z "$existing_ver" ]; then
        printf '%s\n%s' "<!-- version:v2.0.0-agent-main -->" "" | cat - "$dst" > "${dst}.tmp" && mv "${dst}.tmp" "$dst"
        log "DREAMS.md 已注入版本标记"
      else
        info "  [跳过] DREAMS.md（版本已是最新）"
      fi
    fi
  fi
}

# 写入 Layer 2 — 主 Agent 专属文件
# 输入: $1 = 模式 (install|update)
# 输出: 通过全局变量 BS_* 追踪写入计数
bootstrap_layer2() {
  local mode="${1:-install}"
  info "Layer 2: 写入主 Agent 专属文件..."

  if [ ! -d "$MAIN_WS" ]; then
    warn "主 Agent workspace 不存在: $MAIN_WS，请先运行 Step 2"
    return 1
  fi

  # AGENTS.md
  write_main_agenda "$MAIN_WS/AGENTS.md" "$mode"

  # SOUL.md
  write_main_soul "$MAIN_WS/SOUL.md" "$mode"

  # TOOLS.md
  write_main_tools "$MAIN_WS/TOOLS.md" "$mode"

  # MEMORY.md（保留用户数据，不覆盖）
  write_main_memory "$MAIN_WS/MEMORY.md" "$mode"

  # IDENTITY.md
  write_main_identity "$MAIN_WS/IDENTITY.md" "$mode"

  # USER.md
  write_main_user "$MAIN_WS/USER.md" "$mode"

  # HEARTBEAT.md
  write_main_heartbeat "$MAIN_WS/HEARTBEAT.md" "$mode"

  # DREAMS.md
  write_main_dreams "$MAIN_WS/DREAMS.md" "$mode"
}

# 写入子 Agent 精简版 AGENTS.md
# 输入: $1 = 目标路径, $2 = 模式 (install|update)
write_sub_agenda() {
  local dst="$1"
  local mode="${2:-install}"

  local content='<!-- version:v2.0.0-agent-sub -->
<!-- 类型: agent-sub -->
<!-- 最后更新: 2026-07-30 -->

# 工作协议 · 鲍澄军团

## 治理铁律
必须遵守 GOVERNANCE.md 全部条款。

## 决策门（精简版）
| # | 当 | 则 |
|---|-----|----|
| 1 | 纯闲聊/问候/感谢 | 直接回复 |
| 2 | 只改 workspace 配置（MEMORY/SOUL 等） | 自己执行 |
| 3 | 简单任务（≤1 文件 + ≤10 行） | 自己执行 |
| 4 | 复检/自检任务 | 执行自检 |
| 5 | 上级派发的明确任务 | 执行，不自行判断是否走三省 |

## 降级策略（精简版）
| 异常 | 动作 |
|------|------|
| 执行超时（> 预估工时 × 2） | 标记 [超时] 并上报上级 |
| 同一策略失败 3 次 | 标记 [熔断] 并报告根因分析 |
| 产出不达标被打回 | 根据打回意见修正，再次不达标上报上级 |

## 工作纪律
1. 只在被 sessions_spawn 调用时工作，不主动发起通信
2. 收到任务先验证输入完整性，再回复"已接收"
3. 输出必须结构化（参照 GOVERNANCE.md 2.1）
4. 不确定的事标注 [待确认]，禁止猜测
5. 禁止越权操作（范围锁定 GOVERNANCE.md 4.2）
6. 子Agent产出必须验收（如适用），不合格打回
7. 超时/失联按 GOVERNANCE.md 3.2 和 5.1 处理

## SDD 审核模式（vSDD-1.0）
当任务输入中包含 `specs/<feature>/` 目录时，启用此模式。
[审核流程 + 验收标准详见 SDD 审核模式]
'

  if [ "$mode" = "install" ]; then
    printf '%s\n' "$content" > "$dst"
    log "子 Agent AGENTS.md 已创建: $dst"
  else
    echo "$content" > /tmp/_oc_sub_agenda_tmp
    handle_bootstrap_file "/tmp/_oc_sub_agenda_tmp" "$dst" "update"
    rm -f /tmp/_oc_sub_agenda_tmp
  fi
}

# 写入 Layer 3 — 子 Agent 专属文件
# 输入: $1 = 模式 (install|update)
# 输出: 通过全局变量 BS_* 追踪写入计数
bootstrap_layer3() {
  local mode="${1:-install}"
  info "Layer 3: 写入子 Agent 专属文件..."

  local sub_agents
  sub_agents=$(load_sub_agents)

  for agent in $sub_agents; do
    local ws="$OC_HOME/workspace-$agent"
    local agent_src="$REPO_DIR/agents/$agent"

    if [ ! -d "$ws" ]; then
      mkdir -p "$ws"
      log "创建子 Agent workspace: $ws"
    fi

    # SOUL.md（从 agents/{agent}/SOUL.md 读取）
    if [ -f "$agent_src/SOUL.md" ]; then
      handle_bootstrap_file "$agent_src/SOUL.md" "$ws/SOUL.md" "$mode"
    fi

    # AGENTS.md（精简版）
    write_sub_agenda "$ws/AGENTS.md" "$mode"

    # GOVERNANCE.md 一致性验证
    local ga_src="$REPO_DIR/agents/GOVERNANCE.md"
    local ga_dst="$ws/GOVERNANCE.md"
    if [ -f "$ga_src" ] && [ -f "$ga_dst" ]; then
      local src_ver
      src_ver=$(extract_version "$ga_src")
      local dst_ver
      dst_ver=$(extract_version "$ga_dst")
      if [ -n "$src_ver" ] && [ -n "$dst_ver" ] && [ "$src_ver" != "$dst_ver" ]; then
        warn "  [E002] $agent: GOVERNANCE.md 版本不匹配（源: $src_ver, 目标: $dst_ver）"
      fi
    elif [ -f "$ga_src" ] && [ ! -f "$ga_dst" ]; then
      # Layer 1 应该已经写入，这里作为防御性写入
      handle_bootstrap_file "$ga_src" "$ga_dst" "$mode"
    fi
  done
}

# ══════════════════════════════════════════════════════════════════
# Phase 4: OCR 集成
# ══════════════════════════════════════════════════════════════════

# 安装 OCR CLI
# 行为: 检查 npm list -g → 不存在则安装 → 验证版本
# 边界:
#   - npm 不可用 → 跳过，显示警告
#   - npm 全局安装权限不足 (EACCES) → 自动配置 npm prefix 到用户目录
#   - 权限检测后清理 .perm-test 文件
#   - OCR 版本低于 1.8.0 → 升级
# 输出: 0=成功, 1=跳过(警告), 2=失败
install_ocr() {
  if ! command -v npm &>/dev/null; then
    warn "未找到 npm，跳过 OCR 安装"
    return 1
  fi

  # ── 权限检测 ──
  local npm_global_dir
  npm_global_dir=$(npm root -g 2>/dev/null || echo "")

  if [ -z "$npm_global_dir" ]; then
    warn "npm root -g 返回空，尝试使用用户级 npm prefix..."
    local user_prefix="$HOME/.npm-global"
    mkdir -p "$user_prefix/lib/node_modules" "$user_prefix/bin"
    npm config set prefix "$user_prefix" 2>/dev/null || true
    if [[ ":$PATH:" != *":$user_prefix/bin:"* ]]; then
      export PATH="$user_prefix/bin:$PATH"
      warn "已将 $user_prefix/bin 加入 PATH。建议将其添加到您的 shell rc 文件中:"
      echo "    export PATH=\"$user_prefix/bin:\$PATH\""
    fi
    npm_global_dir="$user_prefix/lib/node_modules"
  elif ! touch "$npm_global_dir/.perm-test" 2>/dev/null; then
    warn "npm 全局目录无写入权限: $npm_global_dir"
    info "尝试使用用户级 npm prefix..."

    local user_prefix="$HOME/.npm-global"
    mkdir -p "$user_prefix/lib/node_modules" "$user_prefix/bin"
    npm config set prefix "$user_prefix" 2>/dev/null || true
    if [[ ":$PATH:" != *":$user_prefix/bin:"* ]]; then
      export PATH="$user_prefix/bin:$PATH"
      warn "已将 $user_prefix/bin 加入 PATH。建议将其添加到您的 shell rc 文件中:"
      echo "    export PATH=\"$user_prefix/bin:\$PATH\""
    fi
    npm_global_dir="$user_prefix/lib/node_modules"
  fi

  # 清理权限测试文件
  rm -f "$npm_global_dir/.perm-test" 2>/dev/null || true

  # ── 安装/升级 ──
  local ocr_version
  ocr_version=$(npm list -g @alibaba-group/open-code-review 2>/dev/null | sed -n 's/.*open-code-review@\([0-9.]*\).*/\1/p' | head -1)

  if [ -z "$ocr_version" ]; then
    info "安装 OCR CLI..."
    npm install -g @alibaba-group/open-code-review 2>&1 || {
      warn "npm 全局安装失败。尝试 sudo 安装:"
      echo "    sudo npm install -g @alibaba-group/open-code-review"
      return 2
    }
    log "OCR CLI 安装完成"
  else
    local major minor
    major=$(echo "$ocr_version" | cut -d. -f1)
    minor=$(echo "$ocr_version" | cut -d. -f2)
    if [ "$major" -lt 1 ] || { [ "$major" -eq 1 ] && [ "$minor" -lt 8 ]; }; then
      info "升级 OCR CLI（当前: $ocr_version, 最低: 1.8.0）..."
      npm install -g @alibaba-group/open-code-review 2>&1 || {
        warn "OCR 升级失败。尝试 sudo 升级:"
        echo "    sudo npm install -g @alibaba-group/open-code-review"
        return 2
      }
      log "OCR CLI 升级完成"
    else
      log "OCR CLI 已就绪: $ocr_version"
    fi
  fi

  # ── 验证 ──
  ocr --version 2>/dev/null || warn "OCR CLI 验证失败"
  return 0
}

# 写入 ocr-rules.md（使用 version_compare() 而非硬编码版本号）
# 输入: $1 = 模式 (install|update)
write_ocr_rules() {
  local mode="${1:-install}"
  local target="$REPO_DIR/.github/ocr-rules.md"

  mkdir -p "$REPO_DIR/.github"

  local content='<!-- version:v1.0.0-ocr -->
<!-- 类型: ocr -->
<!-- 最后更新: 2026-07-30 -->

# OCR Rules — 三省六部代码审查规则

> 本文件被 OCR CLI 和 GitHub Actions 引用。
> 规则覆盖代码风格、安全、性能、架构四个方面。

---

## 1. 代码风格

### 1.1 命名规范
- 变量名: camelCase（JavaScript）/ snake_case（Python）
- 类名: PascalCase
- 常量: UPPER_SNAKE_CASE
- 禁止: 单字母变量（循环变量 i, j, k 除外）

### 1.2 文件结构
- 每个文件不超过 500 行（超过 → 提示拆分）
- 函数不超过 50 行（超过 → 提示拆分）
- 一个文件一个职责

### 1.3 注释要求
- 公开 API 必须有 JSDoc/Python docstring
- TODO 必须标注作者和日期
- 禁止留用注释掉的代码块

---

## 2. 安全

### 2.1 敏感信息
- 禁止硬编码 API Key/Token/密码
- 检测模式: `['api_key', 'sk-', 'ghp_', 'AKIA']`
- 解决方法: 使用环境变量 + .env 文件

### 2.2 输入验证
- 所有用户输入必须校验
- SQL 查询必须使用参数化查询
- 文件路径必须做路径遍历防护

### 2.3 依赖
- 禁止使用已知漏洞版本（检查 package.json / requirements.txt）
- 禁止引入不必要的依赖

---

## 3. 性能

### 3.1 循环
- 避免 O(n²) 嵌套循环（超过 1000 条数据时）
- 集合操作使用 Set/Map 而非数组

### 3.2 资源
- 文件操作必须使用 with 语句 / try-finally
- 数据库连接必须使用连接池
- 大文件必须流式处理

---

## 4. 架构

### 4.1 模块依赖
- 禁止循环依赖
- 禁止跨越架构层（Controller 直接调用 DAO）

### 4.2 错误处理
- 所有外部调用必须有 try-catch
- 错误信息必须包含上下文（不泄露敏感信息）
- 禁止吞掉异常

### 4.3 日志
- 关键操作必须有日志
- 日志级别: DEBUG / INFO / WARN / ERROR
- 禁止 `console.log` 遗留到生产环境

---

## 5. 三省六部专属规则

### 5.1 文件冲突
- 审查 PR 时检查 files_touched 声明
- 如果声明与实际不符 → 标记为 [冲突]

### 5.2 版本标记
- 检查是否有 <!-- version:xxx --> 标记
- 无标记 → 标记为 [版本缺失]

### 5.3 占位符检查
- 禁止 `[FEATURE_NAME]`、`[DATE]`、`[项目名称]` 等占位符残留
- 发现 → 标记为 [占位符残留]

### 5.4 治理协议
- 所有新文件是否引用 GOVERNANCE.md
- 无引用 → 标记为 [治理缺失]

---

## 6. 审查等级

| 等级 | 标签 | 处理方式 |
|------|------|---------|
| P0 | [安全漏洞] | 必须修复，阻塞合并 |
| P1 | [严重违规] | 必须修复，建议阻塞合并 |
| P2 | [建议修改] | 可讨论，不阻塞 |
| P3 | [信息提示] | 仅供参考，不阻塞 |
'

  # 使用 version_compare() 决定写入方式
  if [ "$mode" = "install" ]; then
    printf '%s\n' "$content" > "$target"
    log "ocr-rules.md 已创建"
  else
    # update mode: 使用 version_compare 决定
    echo "$content" > /tmp/_oc_ocr_tmp
    handle_bootstrap_file "/tmp/_oc_ocr_tmp" "$target" "update"
    rm -f /tmp/_oc_ocr_tmp
  fi
}

# 写入 OCR CI 工作流文件
write_ocr_workflow() {
  local target="$REPO_DIR/.github/workflows/ocr-review.yml"

  mkdir -p "$REPO_DIR/.github/workflows"

  if [ -f "$target" ]; then
    info "  [跳过] ocr-review.yml 已存在"
    return
  fi

  cat > "$target" << 'WORKFLOW_EOF'
name: OCR Code Review
on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  ocr-review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
      - name: Run OCR Review
        run: |
          npx @alibaba-group/open-code-review review \
            --from origin/${{ github.base_ref }} \
            --to origin/${{ github.head_ref }} \
            --format github \
            --rules .github/ocr-rules.md \
            --output ocr-report.json
      - name: Post OCR Report
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = JSON.parse(fs.readFileSync('ocr-report.json', 'utf8'));
            function formatOCRReport(report) {
              let body = '## 🤖 OCR Code Review Report\n\n';
              if (report.violations && report.violations.length > 0) {
                body += '| Severity | File | Issue |\n|---------|------|-------|\n';
                for (const v of report.violations) {
                  const badge = v.severity === 'P0' ? '🔴 P0' : v.severity === 'P1' ? '🟠 P1' : v.severity === 'P2' ? '🟡 P2' : '⚪ P3';
                  body += `| ${badge} | ${v.file} | ${v.message} |\n`;
                }
              } else {
                body += '✅ No violations found.\n';
              }
              return body;
            }
            const body = formatOCRReport(report);
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: body
            });
WORKFLOW_EOF

  log "ocr-review.yml 已创建"
}

# ══════════════════════════════════════════════════════════════════
# 原有步骤（保留并增强）
# ══════════════════════════════════════════════════════════════════

# Step 0: 依赖检查
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

  if ! command -v node &>/dev/null; then
    warn "未找到 node，部分功能将跳过"
  else
    log "Node.js: $(node --version)"
  fi
}

# Step 2: 创建 Workspace
create_workspaces() {
  info "创建 Agent Workspace..."

  local agents
  agents=$(load_agents)
  info "军团规模: $(echo "$agents" | wc -w | tr -d ' ') 个 Agent: $agents"

  for agent in $agents; do
    local ws="$OC_HOME/workspace-$agent"
    mkdir -p "$ws/skills"
    log "Workspace: $ws"
  done
}

# Step 3: 注册 Agents
register_agents() {
  info "注册 Agent 到 OpenClaw..."

  cp "$OC_CFG" "$OC_CFG.bak.baocheng-$(date +%Y%m%d-%H%M%S)"
  log "已备份 openclaw.json"

  export EDICT_HOME="$REPO_DIR"
  python3 << 'PYEOF'
import json, os, pathlib

oc_home = pathlib.Path(os.environ.get('OPENCLAW_HOME', str(pathlib.Path.home() / '.openclaw')))
cfg_path = oc_home / 'openclaw.json'
cfg = json.loads(cfg_path.read_text())

# 从 registry.json 加载 Agent 列表
repo_dir = os.environ.get('EDICT_HOME', str(pathlib.Path.cwd()))
reg_path = pathlib.Path(repo_dir) / 'registry.json'
if reg_path.exists():
    reg = json.loads(reg_path.read_text())
    AGENTS = [{"id": a["id"], "name": a.get("name", a["id"]), "role": a.get("role", ""), "emoji": a.get("emoji", "🤖"), "subagents": {"allowAgents": []}} for a in reg]
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
        # 新注册 agent 时写入现代显示名（identity.name），避免安装后为匿名 id
        entry = {
            'id': ag_id,
            'workspace': ws,
            'name': ag.get('name', ag_id),
            'identity': {'name': ag.get('name', ag_id), 'emoji': ag.get('emoji', '🤖')},
            'subagents': ag.get('subagents', {'allowAgents': []})
        }
        agents_list.append(entry)
        added += 1
        print(f'  + 已注册: {ag_id} (identity.name={ag.get("name", ag_id)})')
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

# Step 4: 初始化数据目录
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

# Step 5: 创建软链接
link_resources() {
  info "创建 data/scripts 软链接..."

  local agents
  agents=$(load_agents)
  local LINKED=0

  for agent in $agents; do
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
  if [ -d "$MAIN_WS" ]; then
    for target in data scripts; do
      link_path="$MAIN_WS/$target"
      if [ ! -L "$link_path" ]; then
        [ -d "$link_path" ] && mv "$link_path" "${link_path}.bak.$(date +%Y%m%d-%H%M%S)"
        ln -s "$REPO_DIR/$target" "$link_path"
        LINKED=$((LINKED + 1))
      fi
    done
  fi

  log "已创建 $LINKED 个软链接"
}

# Step 6: Agent 间通信可见性
setup_visibility() {
  info "配置 Agent 间消息可见性..."
  if openclaw config set tools.sessions.visibility all 2>/dev/null; then
    log "已设置 sessions.visibility=all"
  else
    warn "设置 visibility 失败，请手动执行："
    echo "    openclaw config set tools.sessions.visibility all"
  fi
}

# Step 7: 同步 API Key
sync_auth() {
  info "同步 API Key 到所有 Agent..."

  local MAIN_AUTH=""
  local AUTH_FILENAME=""
  local AGENT_BASE="$OC_HOME/agents/main/agent"

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

  local agents
  agents=$(load_agents)
  local SYNCED=0
  for agent in $agents; do
    local AGENT_DIR="$OC_HOME/agents/$agent/agent"
    if [ -d "$AGENT_DIR" ] || mkdir -p "$AGENT_DIR" 2>/dev/null; then
      cp -f "$MAIN_AUTH" "$AGENT_DIR/$AUTH_FILENAME" 2>/dev/null || true
      SYNCED=$((SYNCED + 1))
    fi
  done

  log "API Key 已同步到 $SYNCED 个 Agent"
}

# Step 8: 构建 React 前端
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

# Step 9: 首次数据同步
first_sync() {
  info "首次数据同步..."
  cd "$REPO_DIR"

  EDICT_HOME="$REPO_DIR" python3 scripts/sync_agent_config.py 2>/dev/null || true
  EDICT_HOME="$REPO_DIR" python3 scripts/sync_officials_stats.py 2>/dev/null || true
  EDICT_HOME="$REPO_DIR" python3 scripts/refresh_live_data.py 2>/dev/null || true

  log "首次同步完成"
}

# Step 10: 重启 Gateway
restart_gateway() {
  info "重启 OpenClaw Gateway..."
  if openclaw gateway restart 2>/dev/null; then
    log "Gateway 重启成功"
  else
    warn "Gateway 重启失败，请手动: openclaw gateway restart"
  fi
}

# ══════════════════════════════════════════════════════════════════
# 升级模式函数
# ══════════════════════════════════════════════════════════════════

# 生成差异报告
generate_diff_report() {
  local report_file="$1"
  local added="$2"
  local upgraded="$3"
  local skipped="$4"
  local deprecated="$5"

  cat > "$report_file" << REPORT_EOF
# 升级差异报告
# 生成时间: $(date '+%Y-%m-%d %H:%M:%S')

## 摘要

| 类别 | 数量 |
|------|------|
| 新增文件 | $added |
| 升级文件 | $upgraded |
| 跳过文件 | $skipped |
| 废弃标记 | $deprecated |

## 说明

- 新增文件：目标 workspace 中不存在，已创建
- 升级文件：版本号较低，已增量追加新内容
- 跳过文件：版本已是最新或无版本标记（未修改）
- 废弃标记：源目录不再包含，已在目标文件尾部标记废弃
REPORT_EOF
}

# 升级模式入口
update_mode() {
  info "========== 升级模式 =========="

  # 重置全局计数
  BS_ADDED=0; BS_UPGRADED=0; BS_SKIPPED=0; BS_CREATED=0

  # Step 1: OCR 版本检查
  write_ocr_rules "update"
  write_ocr_workflow

  # Step 2: 版本扫描 + 增量写入
  bootstrap_layer1 "update"
  bootstrap_layer2 "update"
  bootstrap_layer3 "update"

  # Step 3: 沉余扫描
  info "扫描沉余文件..."
  scan_deprecated "$MAIN_WS" "$REPO_DIR/agents"
  local deprecated_count=$?

  # Step 4: 生成差异报告
  local report_dir="$REPO_DIR/data/output"
  mkdir -p "$report_dir"
  local report_file="$report_dir/update-report-$(date +%Y%m%d-%H%M%S).md"
  generate_diff_report "$report_file" "$BS_ADDED" "$BS_UPGRADED" "$BS_SKIPPED" "$deprecated_count"
  log "差异报告已保存: $report_file"

  # Step 5: 重启 Gateway
  restart_gateway
}

# 安装模式入口
install_mode() {
  info "========== 全新安装模式 =========="

  # 依赖检查
  check_deps

  # Step 1: OCR 安装
  install_ocr
  write_ocr_rules "install"
  write_ocr_workflow

  # Step 2: Workspace 创建
  create_workspaces

  # Step 3: Layer 1 — 系统规则
  bootstrap_layer1 "install"

  # Step 4: Layer 2 — 主 Agent 专属
  bootstrap_layer2 "install"

  # Step 5: Layer 3 — 子 Agent 专属
  bootstrap_layer3 "install"

  # Step 6: Agent 注册
  register_agents

  # Step 7: 数据初始化 + 软链接
  init_data
  link_resources

  # Step 8: 前端构建 + API Key 同步
  setup_visibility
  sync_auth
  build_frontend

  # Step 9: 首次同步 + 重启 Gateway
  first_sync
  restart_gateway
}

# ══════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════

main() {
  local mode="install"

  # 参数解析
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --mode)
        mode="$2"
        shift 2
        ;;
      install|update)
        mode="$1"
        shift
        ;;
      *)
        echo "用法: $0 [--mode install|update]"
        echo "  install  - 全新安装（默认）"
        echo "  update   - 升级模式（版本比对 + 增量写入）"
        exit 1
        ;;
    esac
  done

  banner

  case "$mode" in
    install|"")
      install_mode
      ;;
    update)
      update_mode
      ;;
    *)
      err "未知模式: $mode"
      echo "用法: $0 [--mode install|update]"
      exit 1
      ;;
  esac

  echo ""
  echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
  echo -e "${GREEN}║  🎉  鲍澄项目管理体系安装/升级完成！             ║${NC}"
  echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
  echo ""
  echo "已安装的 Agent："
  echo "  规划 guihua  |  审议 shenyi  |  派发 paifa"
  echo "  文案 wenan   |  代码 daima   |  设计 sheji"
  echo "  审查 shencha |  汇总 huizong  |  溶萃 rongcui"
  echo ""
  echo "下一步："
  echo "  1. 启动数据刷新:  bash scripts/run_loop.sh &"
  echo "  2. 启动看板:      python3 dashboard/server.py"
  echo "  3. 打开看板:      http://127.0.0.1:7891"
  echo "  4. 和鲍澄开始工作！"
  echo ""
}

main "$@"