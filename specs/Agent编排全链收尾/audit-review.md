# 审议部审查报告 · JJC-20260807-001「Agent编排全链收尾」

**审查结论：驳回（打回补全 §3.3 之后缺失内容）**

## 驳回点

### ❌ B1【硬缺口】T3/T4/T5/T6 整段缺失（方案 §3.3 后传输截断）
- 方案仅覆盖 T1（HUMAN-UI 审批）+ T2（手动工具页），T3（inputSchema）/T4（开发文档）/T5（验收清单）/T6（遗留清理）无小节/DoD/AC
- 任务范围 6 项，缺 4 项 = 覆盖 33%
- 需补：T3 逐 tool schema 缺口 + 统一精度标准；T4 十层文档目录/产出物/写入人；T5 5维×3级矩阵 + 15-20 可测条目；T6 清理 SQL 与判据

### ❌ B2【权限放大】审批批准复用 `:run` 权限
- `:run` 用于「触发 Agent」（POST /run）与「审批批准/拒绝」是不同特权级
- 审批授权=高敏写授权（决定数据是否落库），与触发编排不同
- **建议新增 `ai:agent-orchestration:approve` 权限**，否则任何能触发 Agent 的用户都能批准写操作

### ❌ B1.2【接线缺口】`min_approval`→`requiresHumanConfirm` 翻译机制未定义
- `wgateCreate` 只接受 `requiresHumanConfirm?: boolean`，**没有从 capability 的 `min_approval` 字段自动裁决**
- registry.ts 默认 `requiresConfirm = !HIGH_SENSITIVITY.includes(toolName)`（中低敏全审批）
- 手动路由必须明确如何把 `min_approval`（'always'/'auto'/'never'）翻译成 `wgateCreate` 的 `requiresHumanConfirm`——**这是防后门的核心接线点**

### ❌ B6【硬缺口·新实锤】手工旁路 migration 不进 journal
- `meta/_journal.json` 共 23 条，末尾 0032_channel_soft_delete
- **0031_mcp_wgate_schema、0033_agent_capabilities、0034_agent_capability_switches、0035_seed_capabilities、0036_leads_status 全部不在 journal**（手工旁路执行）
- **后果**：全新环境/CI/部署跑 drizzle migrate **不会创建** W-GATE 表、agent_capabilities、agent_capability_switches、effective_enabled 视图、P1-P6 种子
- **另发现 0032 版本冲突**：`0032_departments.sql`（旁路）与 `0032_channel_soft_delete.sql`（journal）同名前缀，若 journal 化会版本冲突

## T1/T2 技术正确性（部分通过，含修正）

| 项 | 判定 |
|---|---|
| settleApproval 未接线 HTTP 路由 | ✅ 属实（grep 仅命中 wgate.ts:276 定义，无调用） |
| 手动出口复用 W-GATE + minApproval 裁决 | ⚠️ 设计成立，但接线缺口见 B1.2 |
| 权限复用 :run | ⚠️ 见 B2，需拆 :approve |
| 前端交互（审批页+手动页分离） | ✅ 合理，建议补「跳转参数契约」如 /ai/agent-approvals?requestId=xxx |
| 19 tool 清单（7读+12写+2 L0控制面） | ✅ 准确（核实 read.ts/write.ts/registry.ts） |
| 全部 19 tool 已注册 inputSchema | ⚠️ 但完整度不一致（部分 required:[] 为空，如 ams.adinsights.query；ams.adinsights.report required:[] 但 service 依赖 dateFrom/dateTo）——T3 应定义「统一精度标准」而非笼统补全 |

## AC 修正
- **T1-AC4 断言结构错误**：settleApproval 对已 processed 返回 `{status, settled:true}`，**不含 `decision:'approved'`**（wgate.ts:319）——AC4 断言需按实际返回结构写，若断言 decision 字段会失败
- **T2 缺越权用例**：无「L2 用户调 L4 工具应 403」用例，需补手动写走 `assertWriteLevel` 校验 AC
- **并发审批**：方案已覆盖（wgate.ts:319 `if status !== in_progress return` + (company_id,key) 复合唯一），建议 T5 补并发用例
- **L0 控制面权限未提**：手动页是否暴露 ams.agent.run/status？run.ts `requiresHumanConfirm:false` → 手动触发编排免审批，需明确授权策略

## 通过后品控官验收要点（补充）
1. B1：T3/T4/T5/T6 全小节存在 + DoD + AC
2. B2：新增 ai:agent-orchestration:approve 权限，审批路由用它
3. B1.2：min_approval→requiresHumanConfirm 映射实现 + 测试
4. B6：migration journal 补齐（含 0032 冲突处理）+ 全新环境可复现验证
5. T1-AC4 按实际返回结构断言
6. T2 补 assertWriteLevel 越权用例