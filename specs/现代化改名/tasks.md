# Tasks: 三省六部 → 现代化组织改名

**Branch**: `feat/rename-modern` | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

> 每任务带 [S]/[M]/[L] 工作量标记。每阶段 Checkpoint 可独立验证（对齐七维分解门禁 D1-D7）。

---

## Phase 1: 常量层与后端契约（Foundation）⚠️

- [ ] T001 [Setup] 在 `dashboard/server.py` 顶部新增唯一真源常量表 `ORG_MODERN`（古ID→现代名）、`ORG_LEGACY_MAP`（历史古名→现代名）、`STATE_TEXT`（状态文案现代语）。[S]
  - **Test**: python import 后打印常量，断言 12 个部门 + 状态映射齐全。

- [ ] T002 [Core] 改 `_AGENT_DEPTS`（L984-994）label/role/rank 为现代名。[M]
  - **Test**: GET 看板官员数据，label 全为现代名。

- [ ] T003 [Core] 改 `_STATE_FLOW` + `_STATE_LABELS`（L2854-2865）from/to/now 文案现代化（含"回奏太子转报皇上"→"汇总至总办，报老板确认"）。[M]
  - **Test**: 走一遍状态机，flow 文案无古名。

- [ ] T004 [Core] 改 `handle_create_task`（L826-897）默认 `org='中书省'`→`'规划部'`、`official='中书令'`→现代职称、`initial_org='太子'`→`'总办'`、`from:'皇上'`→`'老板'`、now/remark 现代化。[M]
  - **Test**: 创建任务，返回 message/now 无古名。

- [ ] T005 [Core] 改 `handle_review_action`（L908-957）"准奏/封驳/御批/门下省/中书省/尚书省/皇上"→"通过/驳回/审批/审议部/规划部/执行办/老板"，`_MIN_TITLE_LEN` 相关"旨意"措辞同步。[M]
  - **Test**: 推进到审议驳回，提示"驳回"且状态正确回退。

- [ ] T006 [Core] 改任务叫停/取消/归档（L265/270/284/292/335）+ L1528-1536 映射 + L2067-2092 历史修复逻辑的古名。[M]
  - **Test**: 叫停/归档任务，now/remark 无古名。

- [ ] T007 [Core] 改 `dashboard/court_discuss.py`（L28-85 OFFICIALS 数组 name/role/duty、L93-104 剧本、L550-560 发言规则、L623-669 例句）——皇帝→老板、储君→项目总控、各尚书→负责人/专员。[L]
  - **Test**: 触发群聊模块，发言角色全部现代名。

**Checkpoint: A — 后端零古名**（grep server.py+court_discuss.py 古名 0 命中，服务可启动）

---

## Phase 2: 前端展示（dashboard.html）⚠️

### 子阶段 2a: 文案与 class
- [ ] T008 [UI] L6 title、L48 注释、L677/L688/L689/L695 logo 与副标题、L703/L704 标签——「军机处·三省六部总控台」→「任务协同总控台」、"皇上视角·实时旨意追踪"→"管理视角·实时任务追踪"、"旨意看板"→"任务看板"。[S]
  - **Test**: 打开首页，页头/标题无古名。

- [ ] T009 [UI] CSS L91-98 八个 `.dt-中书省` 等类名→`.dt-规划部`等现代名。[S]
  - **Test**: 渲染任务卡片，8 个部门色块样式正常（对应 org 显示新名）。

- [ ] T010 [UI] 筛选 chip L773-782 data-sf（保留）显示名"中书省"→"规划部"等 10 个。[S]
  - **Test**: 点击筛选 chip，按现代名过滤正常。

### 子阶段 2b: JS 数据结构（key=中文，高风险）
- [ ] T011 [Core] L981-987 状态→dept 对象、L993 `DEPT_COLOR`、L1679 `phaseColors` 的中文 key→现代名。[M]
  - **Test**: 渲染后 phase 颜色正确（用 t.org 现代名命中的映射）。

- [ ] T012 [Core] L1263-1273 `DEPT_MONITOR` 数组 label/role/rank 现代化，且 L1297 `t.org===d.label` 匹配逻辑确认同步。[M]
  - **Test**: 部门监控卡片按现代 label 匹配渲染。

- [ ] T013 [UI] L1001 `STATE_LABEL` + L1003-1008 `stateLabel(t)` 文案（"门下审议（第N轮）/中书修订（第N轮）"→"审议部审议/规划部修订"）+ L2889 `_NEXT_LABELS`。[S]
  - **Test**: 多轮驳回时文案显示现代名。

- [ ] T014 [Core] L1744 `_agentLabels`、L2194/2237 `AGENT_LABEL_MAP[agent]||t.org||agent` 相关 label→现代名。[M]
  - **Test**: agent 标签渲染现代名，org 兜底正常。

### 子阶段 2c: JS 逻辑（高风险正则/血缘/创建）
- [ ] T015 [Core] **L2302 正则** `(t.org||'').replace(/省|部/g,'').toLowerCase()` → 改用映射归一函数 `orgToId(org)`，摆脱"省/部后缀"依赖。[M]
  - **Test**: 传 `规划部/执行办/开发部` 等，归一结果正确映射 ID。

- [ ] T016 [Core] L3186/3210/3215-3217 血缘分析按中文过滤（`fl.from==='皇上'`、`t.to==='中书省'`）→ 现代名。[M]
  - **Test**: 血缘/参与分析展示现代名，过滤正确。

- [ ] T017 [Core] L3563 创建默认 `org:'中书省'`→`'规划部'`、L3468"将发送给中书省的旨意"、L1603 `escalation===1?'门下省':'尚书省'`、L3310-3384 模板 depts、L1400-1401 准奏/封驳按钮、L1093/L1405/L2958/L3013/L3256 太子/六部文案。[M]
  - **Test**: 创建/升级/模板/巡检路径无古名。

**Checkpoint: B — 前端零古名 + 关键正则/血缘/创建逻辑回归通过**

---

## Phase 3: 数据迁移（方案2核心）⚠️

- [ ] T018 [Core] 编写 `scripts/migrate_org_names.py`：支持 `--dry-run` 预演、自动备份 `tasks_source.json.bak-renamed-*`、扫描 org/from/to/now/remark/comment 字段按 `ORG_LEGACY_MAP` 替换。[M]
  - **Test**: `--dry-run` 输出改动数量不写盘；真实运行后生成备份。

- [ ] T019 [Data] 执行迁移 `data/tasks_source.json`。[S]
  - **Test**: python 扫描 tasks_source.json 古名 0 命中，原数据完整（git diff 复核）。

**Checkpoint: C — 历史数据零古名，备份存在，可回滚**

---

## Phase 4: 同步/测试脚本 + 门禁微调

- [ ] T020 [Core] `scripts/sync_from_openclaw_runtime.py` L94-119 `detect_official` 返回古名（储君/太子/尚书令/尚书省/钦天监）→ 现代名，default 分支同步。[M]
  - **Test**: 运行后 officials 数据无古名。

- [ ] T021 [Core] `scripts/sync_officials_stats.py` L66-76 OFFICIALS label/role/rank 现代化（生成 officials_stats.json 数据源）。[M]
  - **Test**: 重新生成 officials_stats.json 无古名。

- [ ] T022 [Core] `scripts/kanban_update.py` L94-96 ORG_TO_ID、L100-103、L316 flow from:"皇上"、L473-518 执行回报"to:尚书省"、L77-80 STATE_LABEL。[M]
  - **Test**: kanban update 流程写入 modern org。

- [ ] T023 [Test] `scripts/test_final.py` L254/260 断言'准奏'、`toctou_test_runner.py` L385 'to:尚书省'、`test_taizi_scan_agent_working.py` L478 'Next','尚书省' + 标题。[M]
  - **Test**: 三个测试文件改名后全部通过。

- [ ] T024 [Tune] `scripts/six_unity.py` L94/L153/L181/190 措辞核实（已多用新名），"封驳"措辞→"驳回"（若出现）。[S]
  - **Test**: 门禁拦截/放行提示用现代语，decomp 评分 ≥98。

**Checkpoint: D — 同步/测试脚本零古名，三测试通过，门禁正常**

---

## Phase 5: Agent 提示词 + README

- [ ] T025 [Doc] `agents/WORKFLOW.md`（最密集 30 处）——L12/L14/L22-25/L31-47 工作流、L53-63 角色映射表→现代名。[L]
  - **Test**: grep WORKFLOW.md 古名 0 命中，角色映射表完整。

- [ ] T026 [Doc] `agents/GLOBAL.md`（L9/L24/L32/L53）、`DISPATCH.md`(L4/L7)、`EVOLUTION.md`、`IDENTITY.md`、`MEMORY.md` 古名→现代名。[S]
  - **Test**: grep agents/ 古名 0 命中。

- [ ] T027 [Doc] `README.md` 全部古名现代化（六部/太子/中书省/封驳/准奏等）。[M]
  - **Test**: grep README.md 古名 0 命中。

**Checkpoint: E — 提示词/文档零古名，角色映射表一致**

---

## Phase 6: 回归验证与收尾

- [ ] T028 [Verify] 重启看板（`env SIX_UNITY=1` 方式），走全状态流转回归：创建→规划→审议(驳回1次)→执行→审查→完成。[M]
  - **Test**: 全流程无古名、无报错、门禁正常。

- [ ] T029 [Verify] 全仓 grep 清零：`grep -rlE "皇上|太子|中书省|门下省|尚书省|六部|准奏|封驳|御批|旨意|军机处" dashboard/ scripts/ agents/ README.md` 断言 0 命中（剔除暂缓目录）。[S]
  - **Test**: SC-001/SC-002 达成。

- [ ] T030 [Verify] `/api/six-unity` 复核 `sdd_enforce=true`、七维分解评分 ≥98、无短板维度。[S]
  - **Test**: SC-004 达成。

- [ ] T031 [Ship] git 提交（含数据备份不进仓库，只提交代码+specs），push 分支。[S]
  - **Test**: git status 干净，push 成功。

**Checkpoint: F — 全部 SC 达成，可交付**
