# 执行方案 · JJC-20260807-001「岗位部门Agent编排全面落地与文档纠正」（修订版 v2）

> 修订依据：审议部审查报告（audit-review.md）6 个驳回点 + 1 项额外要求，逐条修订。本版为完整方案全文。

## 产出摘要
「全面落地」定义为**三线并进**：① 修复会话映射核心逻辑（P1-1）；② 补齐岗位→Agent→文档编排缺口（P1-2）；③ 全量文档纠正对齐（P1-3）。每线含独立子任务、涉及文件、DoD、可量化 AC。

> ⚠️ [NEEDS CLARIFICATION] 若老板本意仅指「修复会话映射」，则 P1-1 单独交付即可，P1-2/P1-3 降级为 P2。建议三线并进（共享同一真源 registry.json，分开做反复返工）。

## 编排链路（现状）
```
registry.json ──→ get_sessions_mapping() ──→ 任务派发 ──→ Agent 执行 ──→ 验收 ──→ 看板展示
     ↑ 权威真源          ↑ 会话映射(有bug)        ↑ 派发(正常)      ↑ 防线(正常)    ↑ 展示(依赖映射)
```

---

## P1-1 会话映射逻辑修复（开发部 daima）

**范围**：`dashboard/server.py` `get_sessions_mapping()`（L1199-1326）+ 缓存函数（L1166-1177）

**4 个 bug**：
| # | Bug | 证据 | 修复 |
|---|-----|------|------|
| 1 | `--limit 50` 硬上限 | L1212；实测 `openclaw sessions list` 返回 totalCount:224、hasMore:True | **hasMore 分页循环拉取**（见下），返回 returnedSessions |
| 2 | spawnedBy 死代码 | L1290-1292，spawnedBy 实为 `agent:main:main` 完整 key，恒 false | split(':')[1] 取裸 id 或删分支 |
| 3 | org 未归一化 | L1285 未过 `_modern()`；有 `三省-军师`/`三省-研发主管` | L1285 前加 `_modern(task_org)` + ORG_LEGACY_MAP 扩展 |
| 4 | 缓存 TTL 不符 | 实际 `_SESSIONS_CACHE_TTL=2.0`（L1167） | 提到 10-15s；纠正「30 秒」表述 |

**Bug1 分页修复方案（驳回点5）**：
- 不用固定 `--limit 200`（200 < 224 仍截断）。
- 改为 **hasMore 分页循环**：`while hasMore: 拉取下一页（limit=100/页）`，直至 hasMore=False，聚合全部 session。
- 兜底：若分页循环不可行，则 `limit ≥ totalCount`（如 300）**且**仍处理 hasMore 标志，避免静默截断。
- 返回 `returnedSessions`（实际拉取数）与 `totalSessions`（分页后真实总数）。

**DoD**：org 过 `_modern()`；分页循环拉全量（hasMore 处理）；limit 可配置+returnedSessions；无恒 false 分支；TTL 10-15s；单元测试覆盖怪值/spawnedBy/截断。

**AC**：
- **AC1**：JJC-20260807-001（org=**审议部**）关联 **shenyi** session（非 guihua）。⚠️ 若要验证规划部链路，需另选 org=规划部的任务——当前任务池无此类任务，需在验收时说明「规划部链路未覆盖，待有规划部任务时补验」。
- **AC2**：两个怪值 AUTO 任务（`三省-军师`/`三省-研发主管`）经 `_modern()` 归一命中。
- **AC3**：`returnedSessions ≤ totalSessions`；**totalSessions 分页后 = 真实总数（≥224，与 `openclaw sessions list` 全量一致）**。
- **AC4**：单测覆盖怪值/spawnedBy/截断，100% 通过。

---

## P1-2 编排缺口补齐（daima + rongcui）

**2a org 怪值归一化**：ORG_LEGACY_MAP + migrate_org_names.py VALUE_MAP 增 `'三省-军师':'规划部'`、`'三省-研发主管':'开发部'`；--dry-run→迁移→重启。

**2b 缺 AGENTS.md（驳回点6，位置确认）**：
- **位置确认**：main 与 ld-r 的 AGENTS.md **实际在 workspace 根**（`~/.openclaw/workspace-main/AGENTS.md`、`~/.openclaw/workspace-ld-r/AGENTS.md`），**非** `agents/main/AGENTS.md`。
- 实测：repo `agents/` 目录仅含 9 个执行 agent 子目录（daima/guihua/huizong/paifa/rongcui/sheji/shencha/shenyi/wenan），**无 main、无 ld-r**；而 11 个 agent 的 workspace 根均有 AGENTS.md。
- **结论**：main/ld-r 的 AGENTS.md 以 **workspace 根**为准（已存在，无需新建）。repo `agents/` 是模板源，main/ld-r 不在其中属正常（总控/调度长不参与执行派发模板）。
- **ld-r 缺失确认**：repo `agents/` 无 `ld-r` 子目录，确认无误；但 workspace-ld-r/AGENTS.md 已存在，故**不新建**，仅核对内容与 guihua 模板一致。
- **修正动作**：将「新建 agents/main/AGENTS.md、agents/ld-r/AGENTS.md」改为「**核对** workspace-main/AGENTS.md 与 workspace-ld-r/AGENTS.md 内容完整（参照 guihua 模板），缺失字段补齐；不新建 repo 侧文件」。

**2c registry 真源校验**：比对 registry courtTitle 与 ORG_MODERN.values()。

**AC**：`_modern()` 全部门+怪值正确；11 个 agent 全有 AGENTS.md（workspace 根，main/ld-r 位置正确）；registry↔ORG_MODERN 校验 0 差异。

---

## P1-3 文档纠正对齐（wenan + guihua 复核）

**目标文件**：`~/.openclaw/workspace-guihua/WORKFLOW.md`（实测含错误，5 行）。repo `agents/WORKFLOW.md` 已用「人力路由处」正确（L62），仅抽查。

| 文档 | 现状 | 真源 | 需改 |
|------|------|------|------|
| workspace-guihua/WORKFLOW.md | 路由处/交付处（5 行错误） | 人力路由处/交付汇总处 | 改 |
| README.md | 已一致 | 一致 | 抽查 |
| agents/WORKFLOW.md | 已现代化 | 一致 | 抽查 |
| docs/现代化改名方案.md | 历史方案 | — | 标注已落地 |
| specs/现代化改名/spec.md + 验证报告-JJC-20260801-005.md | 历史方案/验证 | — | 标注已落地（第 5 个核对文档） |

**精确 grep 模式（驳回点2，防「路由处」子串误命中）**：
```
grep -nE "（路由处）|（交付处）|\| 路由处 \||\| 交付处 \||退回路由处" ~/.openclaw/workspace-guihua/WORKFLOW.md
```
实测命中 **5 行**：L29 / L31 / L57 / L69 / L74。

**DoD（驳回点3，口径修正）**：
- **5 行错误全改**（L29/31/57/69/74，非 11 行）。
- 「11」指 **11 个部门/agent 核对口径**：改后对 11 个 agent 的 WORKFLOW.md 逐一核对「人力路由处/交付汇总处」用词一致，非指错误行数。
- README/agents 抽查；改名方案标注落地；交付一致性核对表。

**AC**：
- 精确 grep 无「路由处/交付处」残留（5 行错误全改）。
- 核对表覆盖 **≥5 文档**（含 specs/现代化改名/spec.md + 验证报告-JJC-20260801-005.md）。
- 改名方案（docs/现代化改名方案.md + specs/现代化改名/）标注已落地。

---

## P2 增强（不阻塞）
P2-1 前端截断提示；P2-2 命中率监控 matchRate；P2-3 selfcheck 加一致性检查。

---

## 风险（含额外要求加强）
- 改映射影响看板展示：中，先单测再改。
- 迁移误伤历史：中，--dry-run+备份。
- **改宪法文档（WORKFLOW.md 等）：高。对策加强为「改前备份 + 军师+审计官双复核」**（原仅军师复核，现升级：① 改前 `cp` 备份原文件；② 军师复核改后内容；③ 审计官独立复核改后内容，双签通过后才算完成）。
- TTL 影响性能：低。

---

## 分工（7 层防线）
guihua(方案)→shenyi(审议)→main(拍板)→paifa(派发)→daima(P1-1/2a/2c)+rongcui(2b)+wenan(P1-3)→shencha(验收)→huizong(交付)

## 文件清单
dashboard/server.py、scripts/migrate_org_names.py、data/tasks_source.json、workspace-main/AGENTS.md(核对)、workspace-ld-r/AGENTS.md(核对)、workspace-guihua/WORKFLOW.md、docs/现代化改名方案.md、specs/现代化改名/spec.md、specs/现代化改名/验证报告-JJC-20260801-005.md、tests/(新增)

---

## 驳回点修订对照表（供审计官复核）
| # | 驳回点 | 修订 |
|---|--------|------|
| 1 | AC1 org 错误 | AC1 改「JJC-20260807-001(org=审议部) 关联 shenyi」；规划部链路另选任务（当前无，验收时说明） |
| 2 | grep 不可测 | 改精确模式 `grep -nE "（路由处）|（交付处）|\| 路由处 \||\| 交付处 \||退回路由处"`，实测 5 行 L29/31/57/69/74 |
| 3 | DoD「11 行」不符 | 改「5 行错误全改」；「11」明确为 11 个部门/agent 核对口径 |
| 4 | 核对表仅 4 文档 | 补第 5 个：specs/现代化改名/spec.md + 验证报告-JJC-20260801-005.md；AC 改 ≥5 |
| 5 | Bug1 修复不完整 | 改 hasMore 分页循环拉全量；AC3 补「totalSessions 分页后=真实总数(≥224)」 |
| 6 | agents/main/AGENTS.md 位置 | 确认 main/ld-r 的 AGENTS.md 在 workspace 根（已存在），非 agents/main/；repo agents/ 无 main/ld-r 属正常；ld-r 缺失确认无误，改为「核对」非「新建」 |
| 额外 | 改宪法风险对策 | 加强为「改前备份 + 军师+审计官双复核」 |
