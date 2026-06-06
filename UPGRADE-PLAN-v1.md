# 三省六部升级落地执行方案 v1

> 基于 Spec-Kit 深度分析 × OC-MACS 对比
> 日期: 2026-06-06 | 版本: v1 | 状态: 待执行

---

## 一、升级范围

### Scope: Level 1（SOUL.md 改写 + 模板新增 + 协议更新）

本次执行仅限 **零代码 / 零架构改动** 的 Level 1 项。Dashboard 增强（Level 2）留待单独评估。

| 模块 | 动作 | 影响文件 | 预估工时 |
|------|------|---------|---------|
| 筹微 SOUL.md 升级 | 需求模板标准化 + FR/SC/P1-P3 + Edge Cases | `agents/guihua/SOUL.md` | 1h |
| 审微 SOUL.md 升级 | 11 维覆盖扫描 + 9 维 Checklist | `agents/shenyi/SOUL.md` | 1h |
| 锋铸 SOUL.md 升级 | Tasks 标准格式 + Phase 分层 + 并行标记 | `agents/daima/SOUL.md` | 1h |
| 镜衡 SOUL.md 升级 | 6 维一致性分析 + 追溯映射 + Checklist | `agents/shencha/SOUL.md` | 1h |
| 新增 CONSTRAINTS-TEMPLATE.md | 项目宪章模板 | `agents/CONSTRAINTS-TEMPLATE.md` | 0.5h |
| WORKFLOW.md 协议更新 | 追溯映射要求嵌入手册 | `agents/WORKFLOW.md` | 0.3h |
| GOVERNANCE.md 升级 | 输入校验 + 强制「不确定即标注」 | `agents/GOVERNANCE.md` | 0.3h |
| 统稿自检 & 验证 | 文件完整性 + 版本标注 | — | 0.5h |
| **总计** | | | **~5.6h** |

---

## 二、执行顺序

```
Phase 1: 筹微 SOUL.md (1h)
   ↓
Phase 2: 审微 SOUL.md (1h)
   ↓
Phase 3: 锋铸 SOUL.md (1h)
   ↓
Phase 4: 镜衡 SOUL.md (1h)
   ↓
Phase 5: CONSTRAINTS-TEMPLATE.md + WORKFLOW.md + GOVERNANCE.md (1.1h)
   ↓
Phase 6: git commit + push (0.5h)
```

---

## 三、各文件详细改动说明

### 3.1 筹微 (`agents/guihua/SOUL.md`)

**改动点**:
1. TASK.md 模板升级：加入 **User Story 分级（P1/P2/P3）**
2. 每个子任务增加：**FR-xxx 与 User Story 的映射关系**
3. **Given-When-Then 验收场景** 替代模糊验收标准
4. 新增 **Edge Cases** 节
5. 新增 **占位符检测** 规则：禁止 `[FEATURE_NAME]` 等未替换模板占位符
6. 「范围边界」强化：参照 spec-template.md 的「Measurable Outcomes」节

**新模板结构**:
```markdown
# TASK.md — [项目名称] | 版本: v1 | 规划: 筹微

## 1. 目标
[一句话]

## 2. 范围边界
### ✅ 做 (穷举)
### ❌ 不做 (明确)

## 3. User Stories (优先级排序)
### US-P1 [最高优先级] — [标题]
**Given-When-Then 验收场景**:
1. **Given** [初始状态], **When** [操作], **Then** [预期结果]
2. **Given** [初始状态], **When** [操作], **Then** [预期结果]

**Measurable Outcome**: [量化指标]

### US-P2 [中等优先级] — [标题]
...

## 4. 子任务拆解
### T-001 [P] [名称] — 映射到 US-P1
- 类型: [文案/代码/设计/混合]
- 负责人: [Agent ID]
- 描述: [具体做什么]
- 需求追溯: FR-001, FR-002
- 产出: [文件列表]
- files_touched: (读/写/创建)
- 验收标准: [Given-When-Then 或量化指标, ≥ 2 条]
- 预估工时: Xh
- 依赖: [无 / T-002 完成后]

### T-002 [名称] — 映射到 US-P2
...

## 5. Edge Cases
- [边界条件1]: [处理方式]
- [边界条件2]: [处理方式]

## 6. 冲突检测矩阵
| 文件 | Agent A | Agent B | 冲突？ | 处理 |
|------|---------|---------|--------|------|

## 7. 执行顺序
- 阶段 1 (并行): T-001, T-002
- 阶段 2 (T-001 后): T-003

## 8. 风险登记
- 风险: [描述] | 概率: 高/中/低 | 缓解: [措施]
```

---

### 3.2 审微 (`agents/shenyi/SOUL.md`)

**改动点**:
1. 审议流程升级：引入 **Spec-Kit 11 维覆盖扫描** 替代原来 5 维（A-E）
2. 引入 **Checklist 9 维质量门控**（A-I 九维）
3. 第一关「完整性」升级为 11 维逐项扫描
4. 新增「占位符检测」节
5. 新增「需求完整性判定」规则（每条需求必须有 accept scenario，不得留模板占位符）

**11 维覆盖扫描**:
```
□ 1. 功能完整性 — 所有核心功能点是否都被覆盖？
□ 2. 数据/状态 — 数据模型、状态流转是否明确？
□ 3. UX/交互 — 用户操作路径是否完整？
□ 4. 非功能性需求 — 性能、安全、可访问性？
□ 5. 集成/接口 — 外部依赖、API 契约？
□ 6. 边界/错误 — 异常行为处理？
□ 7. 约束 — 工期/技术栈/合规？
□ 8. 术语/语言 — 文案一致性？
□ 9. 完成信号 — 什么叫「做完了」？
□ 10. 占位符 — 是否有未替换的模板占位符？
□ 11. 一致性/矛盾 — 需求间有无冲突？
```

**9 维质量门控**：
```
□ A. 完整性 — 全部需求有对应子任务
□ B. 清晰度 — 每项需求描述清楚无歧义
□ C. 一致性 — 需求间无矛盾
□ D. 可度量性 — 验收标准可量化可验证
□ E. 覆盖 — 无遗漏功能点
□ F. 边界/错误 — 异常场景已覆盖
□ G. 非功能性需求 — 性能/安全/可访问性
□ H. 依赖 — 外部依赖明确
□ I. 冲突 — 文件冲突矩阵完整
```

---

### 3.3 锋铸 (`agents/daima/SOUL.md`)

**改动点**:
1. 任务拆解格式升级：引入 **Phase 分层**（Setup → Foundational → User Story 1/2/3 → Polish）
2. 每个 Task 增加 `[P]` 并行标记 + `[US1]` Story 归属标记
3. 拆解模板加入依赖声明 + 并行机会枚举
4. 产出格式中增加 **需求追溯映射表**：FR-xxx → T-xxx
5. 新增 Phase Gate 概念：每个 Phase 完成后必须验证再进入下一 Phase

**新任务拆解格式**:
```markdown
## 任务拆解
### Phase 1: Setup (共享基础设施)
- [ ] T001 [P] [Setup] 初始化项目结构
- [ ] T002 [P] [Setup] 配置构建工具

### Phase 2: Foundational (基础依赖 — 阻塞所有 User Story)
- [ ] T003 [P] [Foundational] 数据库Schema
⚠️ ALL User Stories depend on Phase 2 completion

### Phase 3: User Story 1 (P1 — MVP)
- [ ] T004 [P] [US1] 创建 Entity Model
- [ ] T005 [US1] 实现核心服务 (依赖 T004)

### Phase 4: Polish (跨 Story 收尾)
- [ ] T006 [P] [Polish] 文档补全
```

---

### 3.4 镜衡 (`agents/shencha/SOUL.md`)

**改动点**:
1. 审查清单升级：引入 **Spec-Kit 6 维一致性分析框架**（Duplicate/Ambiguity/Incomplete/Principle/Gap/Contradiction）
2. 每项标注严重度：🔴 CRITICAL / 🟡 HIGH / 🟠 MEDIUM / 🔵 LOW
3. 新增 **需求-任务追溯映射检查**：检查 TASK.md 中 FR-xxx 是否都有对应 T-xxx
4. 新增产物与宪章一致性检查
5. 新增覆盖缺口检查（User Story 的任务覆盖是否完整）

**6 维分析框架**:
```
□ 1. 重复 (Duplicate) — 需求/任务有无重复定义？
□ 2. 歧义 (Ambiguity) — 是否有模糊不清的表述？
□ 3. 缺漏 (Incomplete) — 是否有未覆盖的需求？
□ 4. 原则对齐 (Principle) — 是否符合项目宪章/治理协议？
□ 5. 覆盖缺口 (Gap) — TASK.md(需求) vs TASKS.md(实现) 覆盖率？
□ 6. 矛盾 (Contradiction) — 需求间/任务间是否有矛盾？
```

**追溯映射检查**:
```markdown
## 需求-任务追溯映射
| 需求 (FR-xxx) | 对应任务 (T-xxx) | 覆盖率 |
|--------------|-----------------|--------|
| FR-001       | T-001, T-002    | ✅ 100% |
| FR-002       | ❌ 无对应任务    | 🔴 0% |
```

---

### 3.5 新增 CONSTRAINTS-TEMPLATE.md

参照 Spec-Kit constitution-template.md，设计 OC-MACS 项目宪章模板：

```markdown
# [项目名称] 项目宪章

## 版本控制
- **版本**: v1 | **创建**: [日期] | **最后修订**: [日期]

## 核心原则
### [原则1]
[描述]

### [原则2]
[描述]

### [原则3]
[描述]

## 约束条件
- **技术栈**: [规定]
- **工期**: [期限]
- **合规要求**: [如有]
- **不做的事**: [明确]

## 质量门控
- [门控1]: [条件]
- [门控2]: [条件]

## 治理
- 本宪章优先级高于其他项目文件
- 修改需经鲍澄确认
```

---

### 3.6 WORKFLOW.md 协议更新

在 WORKFLOW.md 增加**追溯映射要求**节：

```markdown
## 追溯映射（强制执行）

每个三省六部任务必须在以下环节执行追溯映射：

1. **筹微（Layer 1）**: 在 TASK.md 中，每个 User Story 标注 FR-xxx 编号
2. **审微（Layer 2）**: 验证 FR→Task 映射是否完整
3. **锋铸（Layer 4）**: 产出中附 FR→T 映射表
4. **镜衡（Layer 5）**: 检查映射覆盖率，缺失则打回
```

---

### 3.7 GOVERNANCE.md 升级

在「一、输入校验」中增加强制标注规则：

```
### 1.3 不确定即标注（新增）
任何 Agent 在以下情况必须标注 `[待确认]` 或 `[NEEDS_CLARIFICATION]`：
- 任务描述缺失关键信息
- 需要做技术/设计选择但方案未指定
- 模板占位符（如 [FEATURE_NAME]）未替换
- 无法从已有文档中推导的条件
❌ 禁止在以上情况中猜测缺省值
```

---

## 四、验证标准

| 验证项 | 方法 | 通过条件 |
|--------|------|---------|
| 文件完整性 | 列出全部改动文件，确认无遗漏 | 6 个文件全部更新 |
| SOUL.md 自恰 | 逐一检查不矛盾不冗余 | 无逻辑冲突 |
| 与原有体系兼容 | 对比 GOVERNANCE.md 不变冲突 | 不违反已有治理条款 |
| git commit 规范 | Conventional Commits | feat: 前缀 + 清晰描述 |
| push 成功 | git push 验证 | 远程仓库最新 |

---

## 五、反对意见预防

| 潜在问题 | 预防措施 |
|---------|---------|
| SOUL.md 过长导致 Agent 迷茫 | 新增内容使用「新增节」标记，与原有内容层次清晰 |
| 模板字段过多导致策划效率下降 | P1/P2/P3 和 FR-xxx 为推荐项（SHOULD），Given-When-Then 为强制项（MUST） |
| 审微维度过多（11+9=20 维） | 11 维覆盖为扫描（Scan），9 维门控为判定（Check），分两步执行 |
| 追溯映射增加工作量 | 只在 Layer 1 写一次映射，后面层只用检查不重新写 |
