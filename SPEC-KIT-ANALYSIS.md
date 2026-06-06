# Spec-Kit 深度代码分析 × OC-MACS 对比 × 借鉴方案

> 分析日期: 2026-06-06
> 来源: https://github.com/github/spec-kit
> 目标框架: OC-MACS (三省六部制 / https://github.com/ilxu7z/oc-macs)

---

## 一、Spec-Kit 概况

GitHub 官方出品的 **Spec-Driven Development（SDD）工具链**，核心理念：规格说明（Spec）是第一公民，代码是 Spec 的派生物。

**工作流**: `Constitution → Specify → Plan → Tasks → Implement`

通过 `specify init` 初始化项目，AI 编码助手获得 `/speckit.*` 斜杠命令，强制按规范流程走。模板强制标注 `[NEEDS CLARIFICATION]`、phase gate 检查、test-first 排序、反过度抽象门控等。

---

## 二、Spec-Kit 核心代码模块拆解（7 个子系统）

### 2.1 模板引擎系统 (`templates/`)

**文件**: `spec-template.md`、`plan-template.md`、`tasks-template.md`、`constitution-template.md`、`checklist-template.md`

**功能**: 通过 Markdown 模板 + 占位符控制 AI 输出结构。模板本身就是超长 prompt，内嵌执行流程、校验规则、输出格式约束。

**亮点**:
- `spec-template.md` 强制 User Story 按 P1/P2/P3 优先级排序，每个 Story 必须独立可测试（Given-When-Then）
- `plan-template.md` 有 Constitution Check 门控 — 不通过不能进入 Phase 0；内含 Complexity Tracking 表，任何过度抽象必须 justify
- `tasks-template.md` 强制 `- [ ] T001 [P] [US1] Description` 标准格式，含 Phase 分层（Setup→Foundational→User Stories→Polish）、并行标记 + Story 归属、依赖声明 + 并行机会枚举
- `constitution-template.md` 带语义版本化治理（MAJOR.MINOR.BUILD）、Governance 元规则（Constitution supersedes all other practices）

**与 OC-MACS 对比**:

| 维度 | Spec-Kit 模板 | OC-MACS | 差距 |
|------|-------------|---------|------|
| 需求结构化 | User Story + FR-001 + SC-001 + Acceptance Scenarios + Edge Cases | TASK.md（筹微产出，格式自由） | OC-MACS 的 TASK.md 格式完全由筹微自由发挥，质量不稳定 |
| 技术方案结构化 | research.md → data-model.md → contracts/ → quickstart.md | 无标准化产物 | OC-MACS 缺少 Plan 层的标准产物体系 |
| 任务拆解标准 | 强制 T001+P+US 格式 + Phase 分层 + 依赖声明 | 锋铸自行拆解 | OC-MACS 没有标准化的任务粒度和标记 |
| 宪章约束 | Constitution.md 语义版本化治理 | GOVERNANCE.md（无版本化） | Governorance 原则是文本协议，缺少版本迭代 |

---

### 2.2 命令系统 (`templates/commands/`)

**文件**: `specify.md`、`plan.md`、`tasks.md`、`implement.md`、`clarify.md`、`analyze.md`、`checklist.md`、`constitution.md`、`taskstoissues.md`

**功能**: 每个 `.md` 文件 = 一个超长结构化 prompt，定义了 hooks、handoffs、执行步骤、完成报告。

**亮点**:
- **Hooks 机制**: 每个命令前后有 `.specify/extensions.yml` 的 hook 检查（可选/必选），Git extension 定义 before_specify → 自动创建 branch、after_specify → 自动 commit
- **Handoffs 机制**: `specify → plan` 的衔接有明确 prompt 模板传递
- **Sequential Clarification**: clarify 命令每次只问 1 个问题（最多 5 个），逐个确认后立即写入 spec（而非一次性问完 5 个，避免信息过载）
- **Validate 循环**: specify 写完后自动跑 checklist，不通过则自动修复最多 3 轮
- **Cross-Artifact Analysis**: analyze 命令做 spec×plan×tasks 的一致性检查，只读不修改，6 维检测框架（重复/歧义/缺漏/宪章对齐/覆盖缺口/矛盾）+ CRITICAL/HIGH/MEDIUM/LOW 严重度

**clarify 命令的 11 维覆盖分类**:
1. 功能完整性（Functionality）
2. 数据/状态（Data/State）
3. UX/交互（UX/Interactions）
4. 非功能性需求（Non-Functional）
5. 集成/接口（Integration/APIs）
6. 边界/错误（Edge Cases/Errors）
7. 约束（Constraints）
8. 术语/语言（Terminology/Language）
9. 完成信号（Done Signals）
10. 占位符检测（Placeholder Detection）
11. 一致性/矛盾（Consistency/Contradictions）

**checklist 命令的 9 维质量维度**:
1. 完整性（Completeness）
2. 清晰度（Clarity）
3. 一致性（Consistency）
4. 可度量性（Measurability）
5. 覆盖（Coverage）
6. 边界/错误（Boundaries/Errors）
7. 非功能性需求（Non-Functional）
8. 依赖（Dependencies）
9. 冲突（Conflicts）

---

### 2.3 Extension 系统 (`extensions/`)

**文件**: `extension.yml`（manifest）+ `commands/*.md` + `hooks` 声明

**功能**: 模块化扩展能力，每个 Extension 提供新命令、配置文件、声明式 hook。

**亮点**:
- **extension.yml schema**: `requires`（版本依赖）、`provides`（能力注册）、`hooks`（before/after 各阶段的自动执行点）
- **Hook 系统**: Git extension 定义了 before_specify → 自动创建 branch、after_specify → 自动 commit、before_plan → 提示 commit
- **命令命名空间**: `speckit.{ext-id}.{cmd}` — 完全隔离不冲突
- **Bug Triage 三步流水线**: assess → fix → test，每个阶段独立产出文件
- **优先级栈**: Project Overrides > Presets > Extensions > Core

---

### 2.4 Preset 系统 (`presets/`)

**文件**: `preset.yml` + `commands/*.md` + `templates/*.md`

**功能**: 覆盖核心模板和命令格式，不增加新能力。`lean` preset 是精简版命令（去掉不必要的结构）。

**Stacking**: 多个 Preset 可以叠加，按优先级排序。

---

### 2.5 Workflow Engine (`workflows/`)

**文件**: `workflow.yml` + `engine.py` + `base.py` + `steps/*.py`

**功能**: 轻量级 YAML 声明式工作流引擎，支持 command / gate / if_then / switch / fan_out / fan_in / while_loop / do_while / prompt / shell 等多种步骤类型。

**亮点**:
- `speckit/workflow.yml` 定义了完整的 specify → review-gate → plan → review-gate → tasks → implement 流水线
- Gate 步骤是**硬性人工门控** — 不 approve 就 abort
- 状态持久化 + resume 能力
- 变量替换表达式 `{{ inputs.spec }}`

---

### 2.6 CLI 工具 (`src/specify_cli/`)

**文件**: `commands/init.py`、`integrations/`、`agents.py`、`extensions.py`、`presets.py`

**功能**: `specify init` 初始化项目 + Agent 集成检测（自动检测 Claude/Copilot/Gemini/Codex 等 30+ 工具）；Extension/Preset 安装/卸载/搜索。

---

### 2.7 质量控制子系统（分布在各命令中）

Spec-Kit 最有价值的部分。核心机制：

| 机制 | 作用 | 维数 |
|------|------|------|
| Clarify 疑问分类 | 需求质量前移，每次 1 个问题 | 11 维 |
| Analyze 一致性 | spec×plan×tasks 交叉检查 | 6 维 |
| Checklist 质量 | 产物验证 | 9 维 |
| Constitution Gate | Plan 阶段硬性门控 | N/A |
| Validate 循环 | 最多 3 轮自修复 | N/A |

---

## 三、OC-MACS 现状与差距分析

### 3.1 OC-MACS 现有能力（v2，基于 git HEAD）

```
registry.json    → 11 Agent 注册
GLOBAL.md        → 无条件决策门（9 条规则）
DISPATCH.md      → 派发前意图评估机制
WORKFLOW.md      → 三省六部 6 层防线协议
GOVERNANCE.md    → 8 章治理协议（输入校验/产出规范/故障保护/协作纪律/状态完整性/Token纪律/移交协议/防线分层）
EVOLUTION.md     → 系统自进化协议（Skill 生命周期管理）

Agent SOUL.md:
  guihua（筹微）   → TASK.md 模板 + 冲突检测矩阵
  shenyi（审微）   → 多模型交叉评审 + 三态审查结论
  daima（锋铸）    → 代码自检纪律
  shencha（镜衡）  → 审查清单 5 维 + 评分报告
```

### 3.2 核心差距矩阵

| 差距项 | Spec-Kit 有 | OC-MACS 无 | 严重度 |
|--------|------------|-----------|--------|
| 需求模板标准化 | User Story + FR-xxx + SC-xxx + GWT | TASK.md 自由格式 | 🔴 P0 |
| 任务模板标准化 | T001+P+US 格式 + Phase 分层 | 锋铸自由拆解 | 🔴 P0 |
| 一致性检查 | analyze 6 维自动化 | 镜衡靠经验 | 🔴 P0 |
| Constituion 项目宪章 | 版本化 + 门控 | 无 | 🟡 P1 |
| 疑问分类体系 | clarify 11 维 | 审微无结构化分类 | 🟡 P1 |
| 质量 checklist | checklist 9 维 | 无 | 🟡 P1 |
| 需求-任务追溯 | FR→Task 映射表 | 无系统化映射 | 🟡 P1 |
| 人工硬门控 | Gate 步骤 | 无硬门控机制 | 🟢 P2 |
| Handoff 透明度 | handoffs 机制 | 已有 handoff.json | ✅ 已覆盖 |
| 并行标记 | `[P]` 标注 | 无 | 🟢 P2 |

---

## 四、借鉴方案：融合到 OC-MACS

### 核心原则：不做插件，做标准产物体系

```
当前 OC-MACS:                        融合后:

TASK.md (自由格式)                    TASK.md → 遵循标准 Spec 模板
  ↓                                   ↓
筹微起草                              筹微起草 (按 spec-template 结构)
  ↓                                   ↓
审微审查 (靠经验)                      审微审查 + 11 维分类扫描
  ↓                                   ↓
直接派发执行                           PLAN.md (标准技术方案模板)
  ↓                                   ↓
锋铸自行拆任务                         TASKS.md (标准任务清单: T001 [P] [US1])
  ↓                                   ↓
镜衡验收 (靠经验)                      镜衡验收 + 6 维一致性分析
                                      + 需求-任务追溯映射
```

### 4.1 Level 1：SOUL.md 改写（零代码，高收益）

| 动作 | 来源 | 目标文件 |
|------|------|---------|
| 筹微加入 Spec 模板约束 | spec-template.md 核心结构 | `agents/guihua/SOUL.md` |
| 筹微产出标准要素 | FR-xxx + SC-xxx + P1/P2/P3 | `agents/guihua/SOUL.md` |
| 锋铸加入 Tasks 标准格式 | tasks-template.md | `agents/daima/SOUL.md` |
| 镜衡加入 6 维分析框架 | analyze.md 6 维 | `agents/shencha/SOUL.md` |
| 审微加入 11 维覆盖扫描 | clarify.md 11 维 | `agents/shenyi/SOUL.md` |
| 新增 CONSTRAINTS.md 模板 | constitution-template.md | `agents/CONSTRAINTS-TEMPLATE.md`（全局） |
| 追溯映射要求 | analyze.md coverage mapping | `WORKFLOW.md` 协议 |
| 强制「不确定即标注」 | `[NEEDS CLARIFICATION]` | `GOVERNANCE.md` |

### 4.2 Level 2：Dashboard 增强（中等代码量）

| 动作 | 说明 |
|------|------|
| 看板增加 Gate 步骤类型 | Task model 增加 `gate_required`，UI 上显示门控按钮 |
| 看板增加 Checklist 面板 | 每个任务可附带 checklist items，自动统计 pass/fail |
| 看板增加追溯矩阵视图 | FR-001 ↔ T012 的映射关系可视化 |

### 4.3 ❌ 不引入

| 模块 | 不引入原因 |
|------|-----------|
| Spec-Kit CLI 工具 | 只支持 Claude/Copilot 等，不支持 OpenClaw |
| Workflow Engine | OC-MACS 编排靠 OpenClaw sessions_spawn，不需要 YAML 引擎 |
| Extension/Preset 系统 | OC-MACS 扩展靠 add-agent.sh 加 Agent，不是命令扩展 |
| Hook 系统 | OC-MACS 工作流是看板驱动 |

---

## 五、总结表

| Spec-Kit 功能 | 评级 | OC-MACS 对应 | 融合方式 |
|---------------|------|-------------|---------|
| Spec Template | ⭐⭐⭐⭐⭐ | TASK.md | SOUL.md 改写 — 筹微 |
| Tasks Template | ⭐⭐⭐⭐⭐ | 锋铸自由拆解 | SOUL.md 改写 — 锋铸 |
| Analyze 6 维 | ⭐⭐⭐⭐⭐ | 镜衡审查 | SOUL.md 改写 — 镜衡 |
| Clarify 11 维 | ⭐⭐⭐⭐ | 审微审查 | SOUL.md 改写 — 审微 |
| Constitution | ⭐⭐⭐⭐ | 无 | 新增 CONSTRAINTS-TEMPLATE.md |
| Checklist 9 维 | ⭐⭐⭐⭐ | 无 | SOUL.md 改写 — 审微/镜衡 |
| Gate 步骤 | ⭐⭐⭐ | 无硬门控 | Dashboard 增强 |
| 追溯映射 | ⭐⭐⭐⭐ | 无 | WORKFLOW.md 协议 |
| Workflow Engine | ⭐⭐ | Edict Dashboard | ❌ 不引入 |
| Extension 系统 | ⭐⭐ | add-agent.sh | ❌ 不引入 |
| CLI 工具 | ⭐ | OpenClaw 原生 | ❌ 不引入 |
| Preset 系统 | ⭐ | shared-knowledge | ❌ 不引入 |
