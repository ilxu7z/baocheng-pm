# 审议部审查报告 · JJC-20260807-001

## 结论：驳回（有条件，逐条指出，不打回重写）

核心 bug 诊断全部经源码验证成立，技术方向正确；但 AC 有 2 处硬伤 + P1-3 DoD/核对表口径矛盾，修正后即可通过。

## 技术正确性核验（4 bug 全成立 ✅）
1. limit 50 硬上限 ✅（但修复不完整，见驳回点5）
2. spawnedBy 死代码 ✅（实测 spawnedBy="agent:main:dashboard:..."，parentSessionKey="agent:main:main"，与裸 id 恒不等）
3. org 未归一化 ✅（三省-军师/三省-研发主管 均不在 ORG_LEGACY_MAP 与 migrate VALUE_MAP）
4. TTL 实际 2.0s ✅（L1167）
额外：openclaw sessions list 返回 totalCount:224、hasMore:True，证实 limit 50 截断。

## 驳回点
1. **AC1 事实错误**：JJC-20260807-001 的 org 是「审议部」非「规划部」，应关联 shenyi 而非 guihua。改 AC1。
2. **P1-3 grep AC 不可测**：「人力路由处」含子串「路由处」，朴素 grep 误命中。改精确模式 grep -nE "（路由处）|（交付处）|\| 路由处 \||\| 交付处 \||退回路由处"（实测命中 5 行 L29/31/57/69/74）。
3. **P1-3 DoD「11 行全对」不符**：错误行仅 5 行，非 11。改「5 行错误全改」或明确 11 指部门数。
4. **核对表「≥5 文档」但表内仅 4 个**：补第 5 个文档或改 AC 为 ≥4。
5. **Bug1 修复不完整**：200 仍 < 224。用 hasMore 分页循环拉取，或 limit ≥ totalCount 并处理 hasMore。AC3 补「totalSessions 应等于真实总数（分页后）」。
6. **agents/main/AGENTS.md 位置存疑**：main 的 AGENTS.md 实际在 workspace 根（workspace-shenyi/AGENTS.md），非 agents/main/。确认放哪；ld-r 缺失确认无误。

## 完整性核验
三线覆盖充分 ✅；分工 7 层防线合理，无跨 Agent 文件重叠 ✅；风险清单基本完备，但「改宪法文档」仅靠军师复核偏薄，建议改前备份 + 军师+审计官双复核。

## 通过后品控官验收要点
1. AC1：JJC-20260807-001(org=审议部) 关联 shenyi session
2. AC2：两个怪值 AUTO 任务经 _modern 归一命中
3. AC3：returnedSessions≤totalSessions，totalSessions 分页后=真实总数(≥224)
4. AC4：单测覆盖怪值/spawnedBy/截断，100%
5. P1-2：_modern 11 部门+2 怪值全对；11 agent 全有 AGENTS.md（main/ld-r 位置正确）；registry↔ORG_MODERN 0 差异
6. P1-3：精确 grep 5 行错误全改；核对表≥5 文档；改名方案标注已落地
7. 回归：改映射后看板正常；迁移经 --dry-run+备份
