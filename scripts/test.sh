#!/usr/bin/env bash
# <!-- version:v2.0.0-system -->
# test.sh — OCR 融合系统集成测试
# 版本: v2.0.0-system
# <!-- version:v2.0.0-system -->
set -euo pipefail
B="$(cd "$(dirname "$0")/.." && pwd)"
source "$B/lib/core.sh" 2>/dev/null || { echo "[错误] 无法加载 core.sh"; exit 1; }
R='\033[0;31m'; G='\033[0;32m'; N='\033[0m'
PASS() { echo -e "${G}[PASS]${N} $1"; }
FAIL() { echo -e "${R}[FAIL]${N} $1"; e=$((e+1)); }
e=0
echo "=== OCR 融合系统集成测试 ==="
echo "--- F1: 文件存在性 ---"
for f in "$B/lib/core.sh" "$B/agents/GLOBAL.md" "$B/agents/WORKFLOW.md" "$B/agents/DISPATCH.md" "$B/agents/EVOLUTION.md" "$B/agents/CONSTRAINTS-TEMPLATE.md" "$B/agents/AGENTS.md" "$B/agents/SOUL.md" "$B/agents/TOOLS.md" "$B/agents/USER.md" "$B/agents/MEMORY.md" "$B/agents/IDENTITY.md" "$B/agents/HEARTBEAT.md" "$B/agents/DREAMS.md"; do
  [ -f "$f" ] && PASS "存在: $f" || FAIL "缺失: $f"
done
echo "--- F2: 版本标记 ---"
find "$B/agents" -name '*.md' -print0 | while IFS= read -r -d '' f; do
  head -2 "$f" | grep -q '<!-- version:' && PASS "版本: $f" || FAIL "缺少版本标记: $f"
done
head -2 "$B/lib/core.sh" | grep -q '<!-- version:' && PASS "版本: lib/core.sh" || FAIL "缺少版本: lib/core.sh"
echo "--- F3: 版本比对 ---"
[ "$(version_compare "v2.0.0" "")" = "3" ] && PASS "创建(3)" || FAIL "创建(3)"
[ "$(version_compare "v2.0.0" "v1.0.0")" = "1" ] && PASS "MAJOR覆盖(1)" || FAIL "MAJOR覆盖(1)"
[ "$(version_compare "v2.1.0" "v2.0.0")" = "2" ] && PASS "MINOR追加(2)" || FAIL "MINOR追加(2)"
[ "$(version_compare "v2.0.0" "v2.0.0")" = "0" ] && PASS "跳过(0)" || FAIL "跳过(0)"
echo "--- F6: OCR 安装 ---"
[ -f "$B/scripts/install_ocr.sh" ] && PASS "install_ocr.sh" || FAIL "install_ocr.sh 缺失"
[ -f "$B/.github/ocr-rules.md" ] && PASS "ocr-rules.md" || FAIL "ocr-rules.md 缺失"
[ -f "$B/.github/workflows/ocr-review.yml" ] && PASS "ocr-review.yml" || FAIL "ocr-review.yml 缺失"
echo "--- F8: AGENTS.md 段落 ---"
for s in "决策门" "降级策略" "三省六部" "Fork" "纪律"; do
  grep -q "$s" "$B/agents/AGENTS.md" && PASS "AGENTS.md 含: $s" || FAIL "AGENTS.md 缺: $s"
done
echo "--- F10: TOOLS.md IP ---"
grep -qE '192\.168\.' "$B/agents/TOOLS.md" && PASS "TOOLS.md 含内网IP" || FAIL "TOOLS.md 缺内网IP"
echo "--- S1: 备份 ---"
grep -q 'BACKUP_SUFFIX' "$B/lib/core.sh" && PASS "core.sh 含备份" || FAIL "core.sh 缺备份"
grep -q '\.bak' "$B/lib/core.sh" && PASS "core.sh 含 .bak" || FAIL "core.sh 缺 .bak"
echo "--- P1: 文件数 ---"
fc=$(find "$B/agents" -name '*.md' | wc -l); fc=${fc// /}
[ "$fc" -ge 22 ] && PASS "Agent 文件: $fc (≥22)" || FAIL "Agent 文件: $fc (<22)"
echo "=== 结果: $e 项失败 ==="
exit $e
