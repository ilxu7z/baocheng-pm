# JJC-20260811-002 · 知识库清洗入口迁移 + 审批页优化 — 执行方案（审计修正版 v2）

> 起草：总办（鮱澄）| 审计：shenyi（2026-08-11 18:07）| 项目：AIMarketingSystem（dev）
> **重大修正**：审计实读发现任务 ~70% 已由 HEAD `fdb89158`（今日 18:06，任务同名 commit）落地。
> 本 v2 从「待执行」改为「**增量执行**」，只做真正剩余缺口。

---

## 一、已落地范围（fdb89158，当前 HEAD，勿重复做）

**A 系列（清洗入口迁移）——已落地**
- 后端：`POST /clean`（手动触发，recordIds 支持）、`GET /cleaning/conflicts`、`POST /cleaning/:id/decision`、bulk-import `autoClean` 导入后自动清洗；`/clean` 有 requireAuth + ai:knowledge-base:write 鉴权 ✅
- 前端知识库页：工具栏「🧹 清洗数据」+「待确认」按钮；清洗弹窗支持 all/selected/filtered 三 scope（selected 组装 recordIds）；待确认弹窗就地采纳/拒绝 ✅
- **即方案 A2「就近清洗」的完整实现**，走后端 `/clean`（runPipeline, manual_ui）非 Dify 编排卡片

**B（审批页）——部分落地**
- 已做：默认只显待审批、非 pending 不显示查看/处理按钮 ✅
- **未做**：`TOOL_PREFIX_TO_GROUP` 补 `ams.cleaning.` 映射 ❌

## 二、真正剩余工作（本 v2 要做的）

| ID | 内容 | 文件 | 状态 |
|----|------|------|------|
| **B-1** | TOOL_PREFIX_TO_GROUP 补 `['ams.cleaning.','knowledge']`（清洗审批归「知识库」岗位） | agent-approvals/index.jsx | **已改，待提交**（单行映射，P0，无需老板确认） |
| **A-1** | 编排页 knowledge-cleaning 卡片去留（双入口已存在） | agent-orchestration/index.jsx | **需老板拍板**：移除 or 保留跳转（建议移除） |
| **B-2** | 审批页 CSS 动态注入审查（CSS 注入覆盖坑） | agent-approvals 样式 | 只读审查，可并行 |
| **B-3** | 审批页其他优化诉求 | — | **需老板给方向**（布局/流程/性能/信息） |
| **测试** | 双入口 smoke、/clean 空选/recordIds 边界、autoClean 回归 | — | 待做 |

## 三、NEEDS CLARIFICATION（需老板拍板）

1. **【最高优先】A-1 编排页去留**：knowledge-cleaning 卡片仍在编排页，与知识库页清洗入口**双入口并存**。确认「移除」or「保留跳转」？（建议移除避免双入口）
2. **B-3 审批优化诉求**：老板只给标题。已定位 B-1（P0）。是否只收敛到 B-1 + B-2，还是还有其他诉求？
3. **B-2 CSS 审查**：只读无破坏性，建议直接做，不必等确认。

## 四、审计结论
- **有条件通过**。B-1 判定属实且为当前唯一实质代码缺口；方案已按 fdb89158 落地范围修正为增量执行。
- **可派发**：B-1（单行，已改）、B-2（只读审查，可并行）
- **阻塞项**：A-1 编排页去留（需老板拍板）、B-3 审批诉求（需老板给方向）
