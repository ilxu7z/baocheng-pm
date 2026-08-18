# Feature Specification: 三省六部 → 现代化组织改名（方案2·彻底）
> 🏁 **状态: 已落地**（JJC-20260801-005 验证通过，本 spec 为历史契约留存）

**Branch**: `feat/six-unity`（实际实施分支）
**Created**: 2026-08-01
**Status**: ✅ Complete（2026-08-01 Phase 1/2/3 已实施并端到端验证）
**Language**: chinese

---

## CDD 契约边界（Contract-Driven 层 · 铁律，不可破坏）

> 契约是什么：**英文 ID / 状态机 key / API 路径 / OpenClaw Agent ID / CSS 动态拼 class 规则**。
> 这些是系统稳定运行的接口契约，改名**绝不动**。

### C-001 保留 ID 契约（MUST 不变）
| 类别 | 保留值 |
|------|--------|
| 部门 ID | `taizi / zhongshu / menxia / shangshu / libu_hr / libu / bingbu / gongbu / xingbu / hubu / zaochao` |
| 状态机 key | `Pending / Taizi / Zhongshu / Menxia / Assigned / Next / Doing / Review / Done / PendingConfirm` |
| API 路径/参数 | `/api/create-task / advance-state / task-action / archive-task / live-status / six-unity`，参数 `taskId / action / state / comment` |
| Agent ID | `main / ld-r / guihua / shenyi / paifa / wenan / daima / sheji / shencha / huizong / rongcui` |
| 部门数据 key | `org / from / to / now / remark / comment` 字段名 |
| CSS 规则 | `dt-<org字符串>` 动态拼 class（改 org 时同步改 CSS class 名） |

### C-002 CDD 契约改造点（MUST 改，但保持接口）
- `spec.purpose / outputs / acceptance_criteria / dependencies` 字段结构不变，仅内容用语现代化
- 各 API 的**返回结构**（`{ok, message, taskId}`）不变，仅 message/now/remark 文案现代化
- flow_log 结构不变，仅 from/to/now/remark 的值现代化

### CDD 验收挂钩
实现完成后，`/api/six-unity` 的 `sdd_enforce` 仍为 `true`，七维分解评分 ≥98，契约字段（purpose/outputs/acceptance_criteria/dependencies）全部存在。

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — 全链路无古名展示 (Priority: P1) 🎯 MVP
用户在任务看板首页、任务卡片、部门卡片、状态流转、群聊面板、官员统计中，**看不到任何古代化命名**（皇上/太子/中书省/门下省/尚书省/六部/准奏/封驳/御批/旨意/军机处/储君/中书令/侍中/尚书令/朝报官/六部尚书），全部显示现代化组织名。

**Why this priority**: 这是改名核心价值——用户可见层必须彻底现代化，否则方案2无意义。

**Independent Test**: 拉取 dashboard 首页 + officials_stats + live_status + agent_config，grep 古名关键词，断言 0 命中。

**Acceptance Scenarios**:
1. **Given** 看板服务运行中，**When** 打开首页，**Then** 页头 logo 显示「任务协同总控台」而非「军机处」
2. **Given** 有任一历史任务，**When** 渲染任务卡片和部门筛选 chip，**Then** 显示「总办/规划部/审议部/执行办/开发部/设计部/质控部/内容部/人力路由处/交付汇总处/运维组」而非古名
3. **Given** 任一任务有流转记录，**When** 查看 flow_log 与 phase 颜色，**Then** from/to/now/remark 全为现代名，且颜色映射正常

### User Story 2 — 历史数据已迁移 (Priority: P1) 🎯 MVP
`data/tasks_source.json` 中所有历史任务的 org/from/to/now/remark/comment 字段的古名已被迁移为现代名，且迁移可回滚。

**Why this priority**: 方案2要求数据零残留，否则代码改了但数据显示还是古名。

**Independent Test**: 运行迁移脚本前备份，运行后 python 扫描 tasks_source.json，断言古名 0 命中。

**Acceptance Scenarios**:
1. **Given** 迁移脚本未运行，**When** 执行 `python scripts/migrate_org_names.py`，**Then** 生成 `tasks_source.json.bak-renamed-*` 备份且不破坏原数据
2. **Given** 迁移后，**When** 扫描全部任务字段，**Then** 无任何古名残留
3. **Given** 迁移脚本，**When** 用 `--dry-run` 预演，**Then** 输出将改动数量且不实际写入

### User Story 3 — 运行时逻辑与测试不破 (Priority: P1) 🎯 MVP
改名后，状态流转、门禁拦截、筛选、血缘分析、agent 标签、派发逻辑全部正常；既有测试断言不因改名而失败。

**Why this priority**: 高风险点（正则/颜色key/血缘过滤/测试断言）必须在落地时同步处理，否则功能回归。

**Independent Test**: 走一遍全状态流转（创建→规划→审议→执行→审查→完成），跑 test_final.py / six_unity 门禁，断言通过。

**Acceptance Scenarios**:
1. **Given** 改名完成，**When** 创建任务推进到审议驳回，**Then** 提示「驳回」而非「封驳」，且状态正确回退
2. **Given** 前端渲染，**When** org 有值，**Then** L2302 的正则转换不再依赖「/省|部/」后缀而是用映射表
3. **Given** test_final.py，**When** 运行，**Then** 断言改用现代名后通过

### User Story 4 — Agent 提示词现代化 (Priority: P2)
`agents/*.md` 工作流/角色描述、README 中的古名全部现代化，各 subagent 的 AGENTS.md（已用新名）保持一致。

**Why this priority**: 提示词层是 Agent 行为基线，古代叙事会让子 agent 措辞不统一。

**Independent Test**: grep agents/ 与 README.md 古名，断言 0 命中（WORKFLOW.md 角色映射表现代化）。

### Edge Cases
- **CSS class 未同步**：若 org 改现代名但 `.dt-中书省` 未改，部门色块样式丢失 → 用 `dt-<org>` 动态拼 + 全部类名同步
- **历史数据 org 与代码 org 不一致**：迁移脚本覆盖数据，渲染时 `AGENT_LABEL_MAP[agent]||t.org||agent` 兜底到新名
- **未知 org 值**：前端遇到未映射 org 时，走 `ORG_LEGACY_MAP` fallback，不白屏
- **门禁措辞**：六合一「封驳」→「驳回」，回归时重测 sdd_gate 拦截正常
- **edict/backend 历史遗留**：不纳入本次（未运行），文档标注暂缓

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 在后端 `dashboard/server.py` 建立唯一真源常量表 `ORG_MODERN` / `ORG_LEGACY_MAP`，集中定义所有古名→现代名映射
- **FR-002**: 系统 MUST 将 `_AGENT_DEPTS` / `_STATE_FLOW` / `_STATE_LABELS` 的 label/role/文案全部改为现代名
- **FR-003**: 系统 MUST 将 `handle_create_task` / `handle_review_action` / `handle_task_action` / `handle_archive_task` 中的 now/remark/from/to 文案现代化，默认 org 改为「规划部」
- **FR-004**: 前端 `dashboard.html` MUST 移除「军机处/皇上视角/旨意/太子巡检」等文案，改为现代语（任务协同总控台/管理视角/任务/总控巡检）
- **FR-005**: 前端 MUST 同步 CSS `.dt-中书省` 等 8 个类名为现代名，`DEPT_COLOR`/`phaseColors`/`DEPT_MONITOR`/`STATE_LABEL`/`_agentLabels`/`AGENT_LABEL_MAP` 的 key 同步现代化
- **FR-006**: 前端 MUST 修复 L2302 正则，改用 `ORG_MODERN` 映射而非依赖「/省|部/」后缀
- **FR-007**: 前端 MUST 修复 L3186 等血缘分析的按中文 org 过滤，改现代名
- **FR-008**: 系统 MUST 提供 `scripts/migrate_org_names.py`，支持 `--dry-run` 与真实迁移，迁移前自动备份
- **FR-009**: 系统 MUST 同步 `sync_from_openclaw_runtime.py` / `sync_officials_stats.py` / `kanban_update.py` 的古名映射与 flow 写入
- **FR-010**: 系统 MUST 更新 `test_final.py` / `toctou_test_runner.py` / `test_taizi_scan_agent_working.py` 中依赖中文古名的断言和测试数据
- **FR-011**: 系统 MUST 更新 `agents/WORKFLOW.md` / `GLOBAL.md` / `DISPATCH.md` / README.md 的古名与角色映射表
- **FR-012**: 系统 MUST 保证 `/api/six-unity` 的 `sdd_enforce=true` 与七维分解评分 ≥98 在改名后仍成立

### Key Entities

- **org（部门）**: 任务当前所属部门，字符串，值由古名→现代名（如 `中书省`→`规划部`），用于卡片渲染/筛选/派发
- **flow_log（流转记录）**: 数组，每项含 `from/to/now/remark`，值现代化
- **spec（任务契约）**: dict，含 `purpose/outputs/acceptance_criteria/dependencies`，用语现代化但结构不变
- **OFFICIAL（官员画像）**: court_discuss.py 的 OFFICIALS 数组，name/role/duty 现代化
- **STATE_TRANSITIONS（状态机）**: from/to 中文，现代化

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 运行时目录（server.py / dashboard.html / court_discuss.py / scripts/*.py / agents/*.md / README.md）grep 古名词 0 命中
- **SC-002**: `data/tasks_source.json` 迁移后古名 0 命中，备份文件存在
- **SC-003**: 全状态流转回归通过（创建→规划→审议(含驳回)→执行→审查→完成），无古名、无报错
- **SC-004**: `/api/six-unity` `sdd_enforce=true`，七维分解评分 ≥98，无短板维度
- **SC-005**: `test_final.py` 等测试改名后全部通过
- **SC-006**: 前端 8 个部门色块样式正常（CSS class 与 org 动态拼对齐）

---

## Assumptions

- 仅改 `dashboard/` + `scripts/` + `agents/` + `README.md` 等**当前运行**部分；`edict/backend`（v2.0 FastAPI 未运行）、`edict/frontend/`、`docs/` 历史文档、`data/output/` 历史产出 **暂缓**，不纳入本次验收
- 「皇上」→「老板」已与老板确认（待最终拍板，可替换为「发起人/指挥」）
- 命名遵循映射表（总办/规划部/审议部/执行办/开发部/设计部/质控部/内容部/人力路由处/交付汇总处/运维组）
- 英文 ID 与状态机 key 绝不改动（契约边界 C-001）

---

## ✅ 实施验收记录（2026-08-01）

**三个 Phase 全部完成并端到端验证通过：**

| Phase | 范围 | 状态 |
|-------|------|------|
| Phase 1 | 后端 server.py + court_discuss.py（数据源/逻辑/文案） | ✅ 完成，语法通过，服务重启正常 |
| Phase 2 | 前端 dashboard.html（CSS/JS/文案/逻辑） | ✅ 完成，91处古名清零，全渲染验证 |
| Phase 3 | 数据迁移（5个JSON文件） | ✅ 完成，638→0 处，幂等，自动备份 |

**关键决策与发现：**
1. **唯一真源**：`ORG_MODERN` + `ORG_LEGACY_MAP` + `_modern()` 归一函数（兼容历史古名兜底）
2. **兼容契约 C-001 全保留**：部门ID/状态key/API路径/Agent ID/CSS规则未动
3. **历史数据迁移**：org/from/to/now/remark/flow_log 全字段现代化（长词优先避免「太子调度」误拆）
4. **过时 dist 遗留**：7月9日 React 旧构建劫持服务加载（vite已停用），重命名为 `index.html.react-legacy-20260709`，服务正确回退到当前维护的 dashboard.html

**端到端验证：** 创建任务 → 总办→规划部→审议部→执行办→执行中→审查→完成，全流程现代名，无古名残留。
**git 状态：** 19 文件改动 + 新增 migrate_org_names.py / docs/现代化改名方案.md / specs/。

**遗留（deferred，非验收范围）：** edict/backend(v2.0 FastAPI)、edict/frontend/、docs/ 历史文档、data/output/。
