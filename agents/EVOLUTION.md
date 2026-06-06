# EVOLUTION.md · 鲍澄军团自进化协议

> **目标**：让每个 Agent 越做越好，经验自动沉淀，Skill 自主创建并进化。
> **驱动者**：溶萃（钦天监）—— 系统进化引擎的核心执行者。
> **原则**：数据驱动，Draft 和正式分离，可晋升可降级可淘汰。

---

## 1. 架构概览

```
任务执行
  ↓
归藏交付 / 镜衡打回
  ↓
[复盘信号] → 执行 Agent 写复盘 → shared-knowledge/reviews/
  ↓
溶萃 cron 扫描（每天/每周）
  ↓ 同类经验 ≥3 次
蒸馏成 Skill Draft → shared-knowledge/skill-drafts/
  ↓ skill_manager 注册 → 下次任务自动注入
  ↓ 使用 ≥3 次 + 成功率 > 80%
晋升为正式 Skill → ~/.agents/skills/ 或 对应部门 Skill 目录
  ↓ 使用 ≥5 次 + 成功率稳定
固化（加入 Agent 默认 SOUL.md 或 SKILL.md）
```

### 与现有体系的关系

| 现有体系 | 进化系统 |
|---------|---------|
| knowledge_bridge.py | 进化系统的输入源——复盘数据存储 |
| skill_manager.py | 扩展支持 Draft 晋升、使用统计、淘汰 |
| 归藏（Layer 6） | 复盘触发点——交付后发复盘信号 |
| 镜衡（Layer 5） | 复盘触发点——打回时发复盘信号 |
| 溶萃（钦天监） | 进化引擎核心——蒸馏、创建、审查 Skill |
| design-taste EVOLUTION.md | 本协议的子集（视觉任务专用），与系统级并行 |

---

## 2. 数据结构

### 2.1 任务复盘记录

每个任务完成后，执行 Agent 在项目目录下创建：

```markdown
<!-- 路径: {项目}/.openclaw-project/reviews/{agent_id}-{timestamp}.md -->

## 任务复盘

- 任务ID: [ID]
- Agent: [代号]
- 部门: [兵部/礼部/工部/...]
- 结果: ✅ 通过 / 🚫 打回

### 做了什么
[3-5 句话描述执行过程]

### 遇到什么问题
- [问题1]: [描述]
- [问题2]: [描述]

### 怎么解决的
- [问题1]: [具体解决步骤]
- [问题2]: [具体解决步骤]

### 下次应该怎么做
- [经验1]: [可复用的做法]
- [经验2]: [可复用的做法]

### 差距归因
- [差距]: 原因属于 [品味判断/prompt策略/技术执行/素材质量/需求理解]
```

**字数控制**：200-500 字。不需要长篇大论，核心是「下次应该怎么做」。

### 2.2 Skill Draft

溶萃从复盘中蒸馏出通用模式后，创建：

```markdown
<!-- 路径: shared-knowledge/skill-drafts/{agent}-{skill-name}.md -->

# Skill Draft: {名称}

## 元数据
- 创建者: 溶萃
- 来源复盘: [复盘文件列表]
- 创建日期: YYYY-MM-DD
- 适用 Agent: [锋铸/墨卿/绘象/...]
- 适用场景: [描述什么情况下触发]
- 状态: 草稿 / 已验证 / 晋升候选 / 已晋升 / 已降级 / 已淘汰

## 触发条件
[什么任务/场景下应该加载这个 Skill]

## 核心步骤
1. [步骤1]
2. [步骤2]
3. ...

## 示例
[实际案例：上次这个 Skill 帮助解决了什么]

## 反模式
[不应该怎么做]

## 验证方法
[如何判断 Skill 是否生效]

## 使用统计
| 日期 | 任务ID | 结果 | 备注 |
|------|--------|------|------|
| | | | |
```

### 2.3 Skill 生命周期状态

```
草稿(Draft) → 已验证(Verified) → 晋升候选(Candidate) → 已晋升(Promoted) → 已固化(Embedded)
                                  ↓
                              已降级(Demoted) → 已淘汰(Retired)
```

| 状态 | 含义 | 触发条件 |
|------|------|---------|
| 草稿 | 溶萃刚从复盘中蒸馏出来 | 首次创建 |
| 已验证 | 被对应 Agent 使用 ≥3 次 | cron 统计 |
| 晋升候选 | 已验证 + 成功率 > 80% + 其他 Agent 也适用 | 溶萃审查 |
| 已晋升 | 注册为正式 Skill（~/.agents/skills/ 或部门 Skill 目录） | 溶萃审查通过 + 总办确认 |
| 已固化 | 写入 Agent 的 SOUL.md 或默认 SKILL.md，成为本能 | 使用 ≥5 次 + 成功率稳定 |
| 已降级 | 正式 Skill 打回率 > 30%，退回 Agent 专属 | 溶萃 cron 检测 |
| 已淘汰 | 连续 5 次未被触发，或经验已过时 | 溶萃审查 |

---

## 3. Layer 1: 任务复盘（每次任务）

### 3.1 触发机制

| 触发方 | 信号 | 复盘深度 | 格式 |
|--------|------|---------|------|
| 归藏（Layer 6 交付） | `[复盘信号] 请 {agent} 在任务完成后复盘` | 标准 | 完整复盘模板 |
| 镜衡（Layer 5 打回） | `[打回复盘信号] {agent} 请复盘本次打回原因` | 深度 | 完整复盘 + 根因分析 |

### 3.2 复盘流程

```
执行 Agent 收到复盘信号
  ↓
写复盘记录（200-500 字）
  ↓
保存到 {项目}/.openclaw-project/reviews/{agent}-{timestamp}.md
  ↓
回复溶萃「复盘完成」
```

### 3.3 可以跳过复盘的情况

- 微调任务（改一个颜色值、调一行间距）
- 纯技术修复（bug 修复，无经验可提炼）
- 老板明确说"就这样，不用再改了"
- 一次性探索性任务（结论是"此路不通"，无复用价值）

### 3.4 复盘质量要求

| 要求 | 说明 |
|------|------|
| 「下次应该怎么做」必须有 | 这是复盘的核心价值，没有就不算复盘 |
| 差距归因必须选一类 | 五选一：品味/prompt/技术/素材/需求理解 |
| 200-500 字 | 不需要长篇，但要具体 |
| 不允许空洞总结 | "下次更仔细" = 无效。必须写"下次执行 i18n 修复时，先用 grep 扫描所有 .js 文件的 CATEGORIES 硬编码" |

---

## 4. Layer 2: 经验蒸馏（溶萃驱动）

### 4.1 溶萃的进化职责（扩展）

溶萃（钦天监）原有职责：运维部署、技术支持、特殊任务。

**新增职责**（优先级最高）：
1. **定期扫描复盘记录** → 识别重复模式
2. **蒸馏 Skill Draft** → 同类经验 ≥3 次时创建
3. **管理 Skill 生命周期** → 统计、晋升、降级、淘汰
4. **进化报告** → 每周向总办汇报 Skill 库健康度

### 4.2 蒸馏流程

```
溶萃 cron 触发（每天扫描）
  ↓
读所有 reviews/*.md（跨项目）
  ↓
按 Agent + 差距归因 + "下次应该怎么做" 聚类
  ↓
找到同类经验 ≥3 次的模式
  ↓
判断：这个模式是否可以泛化？
  ├─ 否 → 记录为"Agent 专属经验"，不创建 Draft
  └─ 是 → 创建 Skill Draft
       ↓
     填写元数据 + 触发条件 + 核心步骤 + 示例 + 反模式
       ↓
     写入 shared-knowledge/skill-drafts/
       ↓
     通知 skill_manager 注册
```

### 4.3 蒸馏质量标准

| 标准 | 说明 |
|------|------|
| 来源 ≥3 次 | 不凭一次经验就创建 Draft |
| 触发条件明确 | 能让 Agent 在任务开始时判断"这个 Skill 适用于我" |
| 核心步骤可执行 | 不是描述性知识，是操作步骤 |
| 有反模式 | 知道什么不该做和知道该做什么一样重要 |
| 无冲突 | 和现有 Skill / GOVERNANCE.md 不矛盾 |

### 4.4 Agent 专属 vs 通用

| 类型 | 命名 | 适用范围 | 晋升条件 |
|------|------|---------|---------|
| Agent 专属 | `{agent}-{name}` | 仅该 Agent | 使用 ≥3 次 + 成功率 > 80% + 可泛化 |
| 通用 Skill | `{name}` | 所有同类任务 Agent | 从专属晋升 + 溶萃审查 + 总办确认 |

**先专属后通用**——等于灰度发布，避免未验证的经验污染全局。

---

## 5. Layer 3: Skill 进化管理（溶萃驱动）

### 5.1 使用统计

每次 Skill 被注入到任务中，skill_manager 自动记录：

```json
{
  "skill_id": "daima-i18n-fix-pattern",
  "task_id": "T-003",
  "agent": "daima",
  "timestamp": "2026-06-06T15:30:00+08:00",
  "result": "pass",  // pass / fail / reject
  "feedback": "节省了约 30% 时间"
}
```

### 5.2 晋升流程

```
Skill Draft（草稿）
  ↓ 使用 ≥3 次
已验证
  ↓ 成功率 > 80%
晋升候选
  ↓ 溶萃审查（检查质量/冲突/适用范围）
  ↓ 通过
已晋升（注册为正式 Skill）
  ↓ 使用 ≥5 次 + 成功率稳定
已固化（写入 SOUL.md / SKILL.md）
```

### 5.3 降级流程

```
正式 Skill（已晋升/已固化）
  ↓ 打回率 > 30%（最近 5 次使用）
已降级
  ↓ 退回 shared-knowledge/skill-drafts/
  ↓ 重新评估
  ├─ 修复后效果好 → 重新走晋升流程
  ├─ 效果持续差 → 已淘汰
  └─ 过时 → 已淘汰
```

### 5.4 淘汰流程

| 淘汰条件 | 处理 |
|---------|------|
| 连续 30 天未被触发 | 移到 `skill-drafts/_retired/` |
| 经验已过时（技术栈变更等） | 标注 `superseded_by: [新Skill]`，移到 `_retired/` |
| 效果持续差（降级后仍差） | 移到 `_retired/` |

淘汰不是删除——保留在 `_retired/` 目录，以备溯源。

---

## 6. skill_manager.py 扩展

### 6.1 新增能力

```python
# 现有能力
skill_manager.py → 扫描 agents/ 目录同步到 OpenClaw

# 新增能力
1. register_draft(draft_path)     # 注册 Skill Draft 到索引
2. record_usage(skill_id, task_id, result)  # 记录使用统计
3. get_skill_stats(skill_id)      # 获取成功率/使用次数
4. promote(draft_id)               # 晋升 Draft → 正式 Skill
5. demote(skill_id)               # 降级正式 Skill → Draft
6. retire(skill_id)               # 淘汰到 _retired/
7. scan_reviews()                  # 扫描 reviews/ 目录，返回聚类结果
8. evolution_report()              # 输出 Skill 库健康度报告
```

### 6.2 Skill 注入机制

Skill Draft 注册后，knowledge_bridge.py 在任务派发时检查：
- 当前任务的类型/Agent → 是否有匹配的已验证 Skill Draft？
- 有 → 注入到任务 prompt 前置

```python
def inject_skills(agent_id, task_context):
    drafts = skill_manager.get_verified_drafts(agent_id)
    for draft in drafts:
        if draft.matches(task_context):
            return draft.content  # 注入到任务 prompt
    return None
```

---

## 7. 进化节奏

### 7.1 每次任务

- Layer 1 复盘（归藏/镜衡触发）
- 执行 Agent 写复盘记录
- skill_manager 记录 Skill 使用统计

### 7.2 每天

- 溶萃扫描当日复盘记录
- 识别新模式 → 创建 Skill Draft（如满足 ≥3 次条件）
- 更新使用统计

### 7.3 每周

- 溶萃输出进化报告（见 7.4）
- 检查晋升候选 → 执行晋升审查
- 检查降级/淘汰条件 → 执行
- 清理 `_retired/` 中 >90 天的淘汰 Skill

### 7.4 每周进化报告模板

```markdown
## 进化报告 | YYYY-MM-DD

### Skill 库概览
- 正式 Skill: N 个
- 已验证 Draft: N 个
- 草稿 Draft: N 个
- 已淘汰: N 个

### 本周新增
- [Draft 名称] — 来源: [复盘文件] — 适用: [Agent/场景]

### 晋升/降级/淘汰
- [Skill] 晋升为正式 — 成功率: X%
- [Skill] 降级为 Draft — 原因: 打回率 X%
- [Skill] 淘汰 — 原因: [过时/无效/被替代]

### 复盘统计
- 本周复盘: N 份
- 差距归因分布: [技术N次 / prompt N次 / ...]

### 高频差距 Top 3
1. [描述] — 出现 N 次
2. [描述] — 出现 N 次
3. [描述] — 出现 N 次
```

---

## 8. 归藏/镜衡复盘信号

### 8.1 归藏（交付后）

归藏在交付报告末尾自动追加：

```markdown
---
[复盘信号] 请以下 Agent 在任务完成后复盘：
- [锋铸] 兵部代码执行复盘
- [墨卿] 礼部文案执行复盘
- [绘象] 工部设计执行复盘
```

### 8.2 镜衡（打回时）

镜衡在打回报告末尾自动追加：

```markdown
---
[打回复盘信号] 请 [原执行Agent] 复盘本次打回原因：
- 打回项: [具体项]
- 打回原因: [具体原因]
- 复盘要求: 深度复盘（必须包含根因分析和"下次应该怎么做"）
```

---

## 9. 溶萃 SOUL.md 新增职责摘要

```
钦天监 · 溶萃 — 系统进化引擎

职责优先级：
1. 进化管理（最高）— 扫描复盘、蒸馏 Skill Draft、管理生命周期
2. 运维部署 — 保持系统稳定
3. 技术支持 — 处理特殊技术任务

进化工作流：
  每天 cron → 扫描 reviews/ → 聚类 ≥3 次同类经验 → 创建 Draft
  每周 cron → 进化报告 → 晋升审查 → 降级/淘汰清理
  每次任务 → skill_manager 记录使用统计 → 数据驱动决策
```

---

## 10. 与 design-taste EVOLUTION.md 的关系

| 维度 | design-taste EVOLUTION.md（视觉专用） | 本文件（系统级） |
|------|-------------------------------------|----------------|
| 适用范围 | 视觉类任务（画册/官网/生图） | 所有部门/Agent |
| 驱动者 | 主 Agent 自己 | 溶萃（钦天监） |
| 蒸馏 | prompt 策略 | Skill Draft |
| 存储 | `shared-knowledge/visual-prompt-strategies.md` | `shared-knowledge/skill-drafts/` |
| 晋升目标 | SKILL.md 规则 | 正式 Skill（可注入 SOUL.md） |

两者并行运行，互不冲突。视觉类任务的复盘可以同时被两个系统处理：
- design-taste EVOLUTION → 提炼 prompt 策略
- 系统 EVOLUTION → 提炼通用 Skill（如果适用范围超出视觉任务）

---

## 更新日志

| 日期 | 变更 |
|------|------|
| 2026-06-06 | v1 创建：三层架构 + 五维归因 + Skill Draft 生命周期 + 溶萃进化职责 + 复盘信号机制 |
