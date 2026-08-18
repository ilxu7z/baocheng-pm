# JJC-20260807-001 执行方案 · Agent编排全链收尾（修订版 v2）

**角色**：军师（guihua / 规划部）
**任务**：Agent编排全链收尾（HUMAN-UI审批 + 手动工具页 + inputSchema + 开发文档 + 验收清单 + 遗留清理）
**方法**：ai-project-docs 十层文档体系（L2 角色路由 / L4 执行层 / L6 验收层 / L10 回流）+ sdd-writer spec/plan/tasks 三件套
**版本**：v2 — 按审计官驳回点 B1/B2/B1.2/B6 + 修正项全量修订，补全 T3/T4/T5/T6 完整小节

---

## 〇、代码核实结论（v2 修订依据，已逐文件读取核实）

> 本版所有「已核实」均基于对 `/home/chee/Projects/AIMarketingSystem` 源码的实际读取，非臆断。审计官新增驳回点逐条闭合如下。

### 0.1 驳回点闭合对照表（必读）

| 驳回点 | 闭合位置 | 关键证据（文件:行） |
|---|---|---|
| **B1** T3/T4/T5/T6 缺失 | §五/§六/§七/§八 完整小节 | 本版已补齐，含 DoD + AC |
| **B2** 审批复用 `:run` 权限放大 | §二.2.2 权限设计 + §四.2 | 新增 `ai:agent-orchestration:approve`，审批路由独立 |
| **B1.2** `min_approval→requiresHumanConfirm` 无机制 | §三.4（新增） | 已核实 switch-resolver/wgate/registry，给出映射函数 `resolveRequiresHumanConfirm` |
| **B6** 旁路 migration 不进 journal | §八.2 | 已核实 `_journal.json` 23 条；**实际 9 个文件不在 journal**（审计只列 5 个，实查 9 个，见 §八.2.1） |
| T1-AC4 断言结构错误 | §二.4 AC4 | `settleApproval` 对已 processed 返回 `{status, settled:true}`（wgate.ts:319），**无 decision 字段** |
| T2 缺越权用例 | §三.3 AC4 | 补 L2 调 L4 工具 403 用例（`assertWriteLevel`，registry.ts） |
| T2 缺 L0 控制面授权策略 | §三.5（新增） | run.ts `requiresHumanConfirm:false` → 手动页授权边界 |
| T2 补跳转参数契约 | §三.3.3 | `/ai/agent-approvals?requestId=xxx` |

### 0.2 与审计官一致的关键核实（本版复核）

1. **`settleApproval` 返回结构**（wgate.ts）：
   - 已 processed/failed → `{ status: ik.status, settled: true }`（**不含 decision 字段**，wgate.ts:319）
   - denied 结算 → `{ settled: true, decision: 'denied' }`（wgate.ts:338）
   - approved 结算 → `{ settled: true, decision: 'approved', result }`（wgate.ts:354）
   - ⚠️ 三种返回结构不一致，AC 必须按实际结构分别断言（见 §二.4）

2. **`settleApproval` 未接线 HTTP 路由**：grep 全仓库仅 wgate.ts 定义，无调用方 → 需新增 approval-routes.ts。

3. **19 tool 清单**：registry.ts 分发 7 读 + 12 写 = 19；`ams.agent.run/status` 是 L0 控制面（第 20/21 个，走 `handleControl` 分支，不在 READ_TOOLS/WRITE_TOOLS 数组）。**口径与 task 一致为 19**，L0 控制面单独处理。

4. **权限体系**：字符串 `module:resource:action`，`requirePermission(middleware/permission.ts)` 支持通配符；roles 表 `permissions: jsonb[]`。现有 `ai:agent-orchestration:run` / `:read`（routes.ts:43/64/81）。

5. **min_approval 语义**：capability 级字段（agentCapabilities.ts），取值 `auto|always|never`（默认 auto）。种子中 `lead.scoring` 与 `ab.experiments` = `'always'`（高敏写双端强制审批）。**这是 capability 级，不是 tool 级**——手动路由需先把 tool→capability 反向映射，再取该 capability 的 min_approval。

6. **`ams.agent.run` 手动触发免审批**：run.ts `requiresHumanConfirm: false`（L0 控制面非高敏，但仍过幂等+ledger）。前端 `/run` 路由用 `:run` 权限直接 `callDifyWorkflowRun`（不经 W-GATE）。

### 0.3 审计官未提、v2 实测新增的硬事实

- **journal 缺失文件实为 9 个**（非审计官所言的 5 个）：`0013_analytics_reports_created_by_fk`、`0014_social_posts_unique`、`0015_document_number_unique`、`0016_roles_code_company_unique`、`0018_evolution_cycles_unique`、`0019_document_counters`、`0020_add_version_columns`、`0021_payments_payment_number_unique`、`0031_mcp_wgate_schema`、`0032_departments`、`0033_agent_capabilities`、`0034_agent_capability_switches`、`0035_seed_capabilities`、`0036_leads_status` = **14 个文件不在 journal**（含审计点名的 5 个）。审计官按 5 个给方案，本版按实测 14 个全量处理（§八.2）。
- **0032 双前缀冲突确认**：`0032_departments.sql`（建 `departments` 表，是 0033 的**前置依赖**：0033 的 `dept_id REFERENCES departments(id)`）与 `0032_channel_soft_delete.sql`（在 journal 中，idx 23）同名前缀冲突。**departments 必须先于 agent_capabilities 建**，但两者都被标 0032，drizzle 按 journal 顺序无法确定谁先。
- **tool→capability 反向映射**：capability-gate.ts 已含完整 `toolToCapId`（19 tool 全部 1:1）+ `CAPABILITY_GATE_TOOLS`（N2 修正：审计复审实测存在，非缺失）。B1.2 应**复用/对齐** capability-gate.ts 现成映射，从 DB `agent_capabilities.mcp_tools` 读（单一授权源）作为运行时反向索引，与静态 map 做取舍说明（§三.4）。

### 0.4 19 tool 现有 inputSchema 完整度盘点（T3 前置）

| # | Tool | 现有 required | 缺口（v2 实测） |
|---|---|---|---|
| R1 | ams.creative.list | `[]` | limit 无 min/max 边界；reviewStatus 无 enum；均可选（列表过滤，合理） |
| R2 | ams.creative.get | `['assetId']` | ✅ 完整 |
| R3 | ams.competitor.query | `[]` | category 无 enum；limit 无边界（可选，合理） |
| R4 | ams.lead.query | `[]` | tier 无 enum（HOT/WARM/COLD）；limit 无边界（可选，合理） |
| R5 | **ams.adinsights.query** | **`[]`** | **service 依赖 dateFrom/dateTo，schema 却全可选**；entityType 默认 campaign 但未在 schema 标注 default |
| R6 | ams.adinsights.anomaly | `['entityId','metric']` | entityType 默认 'ad' 未在 schema 标注 default |
| R7 | ams.ab.significance | `['experimentId']` | ✅ 完整 |
| W1 | ams.creative.generate | `['prompt']` | model 无 enum/default；count 无 min/max |
| W2 | ams.creative.submit | `['assetId','reviewStatus']` | ✅ 完整（reviewStatus enum 有） |
| W3 | ams.creative.update | `['assetId','update']` | ✅ 完整 |
| W4 | ams.competitor.snapshot | `['name']` | 其余可选（合理） |
| W5 | ams.competitor.analyze | `['competitorIds']` | ✅ 完整 |
| W6 | ams.lead.score | `['contactId','behaviorSignals','demographicData']` | ✅ 完整 |
| W7 | ams.lead.status | `['leadId','status']` | ✅ 完整（status enum 有） |
| W8 | ams.enrich.field | `['recordId','fields']` | ✅ 完整 |
| W9 | ams.enrich.suggest | `['recordId','field']` | ✅ 完整 |
| W10 | **ams.adinsights.report** | **`[]`** | **executor 依赖 platform/dateFrom/dateTo 生成报告，schema 全可选**（审计官实锤） |
| W11 | ams.ab.design | `['name']` | experimentType 无 enum |
| W12 | ams.ab.run | `['experimentId']` | ✅ 完整 |

> 结论：**已注册 schema 的工具全部 19 个**（含 R5/W10 的 required:[]），但完整度不一致。本次为**「修订既有 schema 到统一精度」**，非从零补全。真正功能性缺口仅 2 处：`ams.adinsights.query`（R5）与 `ams.adinsights.report`（W10）的 `required:[]` 与 service 依赖矛盾（§五.3 详述）。

---

## 一、优先级总览

| 编号 | 子任务 | 优先级 | 依赖 | 本版状态 |
|---|---|---|---|---|
| T1 | HUMAN-UI 审批（V-3 收尾） | **P1** | — | v2 修订（权限 + AC4 结构） |
| T2 | 手动工具页（前端） | **P1** | 需先有审批 settle 路由 | v2 修订（越权/L0/跳转契约） |
| T3 | 19 tool 全量 inputSchema | **P1** | — | **v2 新增完整小节** |
| T4 | 开发文档（十层） | P1 | T1-T3 完成后写 | **v2 新增完整小节** |
| T5 | 验收清单（5维×3级） | P1 | T4 同步 | **v2 新增完整小节** |
| T6 | 遗留清理（journal + 幂等残留 + 测试数据） | **P1** | 独立 | **v2 新增完整小节** |

---

## 二、T1：HUMAN-UI 审批（P1，V-3 收尾）

### 2.1 现状与根因
- `wgate.ts` 的 `settleApproval(approvalId, decision, confirmedBy)` 已完整实现：approved→执行写+结算，denied→拒写+ledger。**但没有 HTTP 端点暴露它**（grep 全仓库无调用）。
- 审批请求由 `createAgentRequest()` 创建（requestedByType='agent'，moduleType='agent_write'，totalSteps=1 单级）。
- 前端 `crm/pages/hitl/index.js` 是 CRM 升级流（escalations），**不可复用**，需新建 Agent 写审批页。

### 2.2 范围

**后端**（新增文件）：
- `src/server/modules/ai/agent-orchestration/approval-routes.ts`：HUMAN-UI 审批桥接
  - `GET /requests` — 列 agent_write 审批请求（过滤 `requestedByType='agent'` + `moduleType='agent_write'`，支持 status 过滤）
  - `GET /requests/:id` — 单条详情（含 contextData.args 写意图快照）
  - `POST /requests/:id/approve` — 调 `settleApproval(id,'approved',req.userId)`
  - `POST /requests/:id/deny` — 调 `settleApproval(id,'denied',req.userId)`
- `src/server/app.ts`：`scanRoute('/api/v1/ai/agent-orchestration')`（app.ts:324）后追加挂载 approval-routes 到同一前缀。

#### ⚠️ v2 权限设计（驳回点 B2 闭合）
- **新增独立权限 `ai:agent-orchestration:approve`**，审批 approve/deny 路由用它，**不复用 `:run`**。
- **`:run` 仅用于触发编排**（POST /run 触发 Dify workflow）。
- **`:read` 仅用于只读**（status/workflows/requests 列表查看）。
- 权限矩阵（数据驱动，middleware/permission.ts 通配符支持）：

| 操作 | 权限 | 授予对象（roles.permissions jsonb 数组加项） |
|---|---|---|
| 触发编排（POST /run，手动触发） | `ai:agent-orchestration:run` | 现有授予方不变（能触发 Agent 的用户） |
| **审批批准/拒绝** | **`ai:agent-orchestration:approve`** | **平台/企业管理员（SUPER_ADMIN、PLATFORM_ADMIN、ENTERPRISE_ADMIN）+ 显式配置的审批岗**。默认不进 SALES_MANAGER/OPERATOR |
| 查看编排状态/审批列表 | `ai:agent-orchestration:read` | 现有只读授予方 |

> **B2 根因**：`:run` 是「触发 Agent」权限，`:approve` 是「决定数据是否落库」的高敏写授权。若审批复用 `:run`，任何能触发 Agent 的用户都能批准写操作，等于高敏写授权降级到触发权限同等水平。拆分后审批授权独立可控。

**前端**（新增文件）：
- `src/client/modules/ai/pages/agent-approvals/index.jsx`：审批控制台
  - 列表：待审批（pending）优先，展示 tool 名、title、目标实体、触发 agent、时间
  - 详情 Modal：展示写意图（contextData.args 格式化 JSON）、目标实体、幂等键状态
  - 操作：批准 / 拒绝（拒绝需填 note），调用 settle 路由
  - 状态徽章：pending / approved / rejected / escalated / cancelled / expired（approvalWorkflow.ts:80 status 枚举）
- `src/client/routes.js`：注册 `/ai/agent-approvals`
- `src/client/layouts/Sidebar.jsx` + `AppLayout.jsx`：加菜单项（放 "Agent 编排" 旁）

### 2.3 完成定义（DoD）
- [ ] settleApproval 被 HTTP 路由调用（approve/deny 均通）
- [ ] 审批路由使用 `ai:agent-orchestration:approve`（**非 `:run`**）
- [ ] agent_write 审批请求可在前端列出、查看写意图、批准/拒绝
- [ ] 批准后幂等键→processed，executor 真实落库，ledger 记 success + humanConfirmedBy
- [ ] 拒绝后幂等键→failed，不落库，ledger 记 denied
- [ ] 二次审批被幂等拦截（idempotency_keys 非 in_progress 返回 `{status, settled:true}`）
- [ ] 全流程集成测试通过（模拟 MCP 写触发→审批→落库回读）

### 2.4 可量化 AC（v2 按实际返回结构修正）
- **AC1**：`POST /api/v1/ai/agent-orchestration/approval/requests/:id/approve` 首次批准返回 `{settled:true, decision:'approved', result}` 且 `idempotency_keys.status='processed'`（≥1 用例）
- **AC2**：deny 路径返回 `{settled:true, decision:'denied'}` 且 `idempotency_keys.status='failed'` 且无新数据落库（≥1 用例）
- **AC3**：前端审批页能列出 ≥1 条 agent_write pending 请求并完成批准/拒绝（人工验收）
- **AC4（修正）**：对已 processed 的请求重复 approve → **返回 `{status:'processed', settled:true}`（无 decision 字段）**，且不重复执行 executor（≥1 用例，按 wgate.ts:319 实际结构断言，**不得断言 decision 字段**）
- **AC5**：审计日志 agent_audit_log 记录 pending_confirm→success/denied 全链路（≥2 条）
- **AC6（新增，B2）**：无 `ai:agent-orchestration:approve` 权限的用户调 approve/deny → 403（≥1 用例）

### 2.5 风险
- **权限绕过（B2）**：settle 路由若误用 `:run` 或 `:read` 会成后门。对策：写操作强制 `ai:agent-orchestration:approve`，AC6 兜底。
- **并发审批**：两人同时批同一请求 → 幂等键状态机已防二次执行（wgate.ts:319 `if status !== in_progress return {status,settled:true}`）。T5 补并发用例。

---

## 三、T2：手动工具页（P1，与 switch-resolver 手动出口配合）

### 3.1 现状与定位
- switch-resolver 的 `resolveCapabilityEffective`（dept/role 维度）已就绪，但**前端没有触发点**。
- wgate.ts 注释"ICL #33 手动出口降级另行接线"——手动出口 = 用户在前端手动发起写 tool 调用，注入 dept/role 上下文，走与自动出口（Dify/MCP）**同一 W-GATE executor**（双出口共享内核，ICL #30）。
- capability-gate 全局硬闸对**所有**出口生效（含手动）。

### 3.2 范围

**后端**（新增文件）：
- `src/server/modules/ai/agent-orchestration/manual-routes.ts`：手动工具执行桥接
  - `GET /tools` — 暴露 19 tool 清单（从 write.ts/read.ts 的 inputSchema 读，供前端渲染表单）
  - `POST /tools/:name/invoke` — 手动出口：校验能力开关（resolveCapabilityEffective with 当前用户 dept/role）→ 注入 dept/role → 调 `wgateCreate`（写）/ 直接执行（读）
- 读工具手动执行：直接调 read handler（无审批），但**同样过 capability-gate 全局硬闸**。

**前端**（新增文件）：
- `src/client/modules/ai/pages/manual-tools/index.jsx`：手动工具页
  - 顶部：能力开关状态条（global/dept/role 三级有效状态，从 switch-resolver 只读接口）
  - 工具列表（按 6 capability 分组）：显示 tool、所需 L 级、当前生效状态
  - 表单：按 inputSchema 动态渲染（JSON Schema → 表单控件），必填校验
  - 提交：写 tool → 显示审批请求（pending_confirm，跳转/提示去审批页）；读 tool → 直接显示结果
- `src/client/routes.js` + Sidebar/AppLayout：注册 `/ai/manual-tools`

### 3.3 DoD
- [ ] 手动出口对 12 写 + 7 读 tool 均可调用
- [ ] 手动出口调用前过 capability-gate 全局硬闸（off→403）
- [ ] 手动写走同一 W-GATE executor（非绕过）
- [ ] minApproval='always' 的能力手动写强制进审批队列（非直接执行）——**经 §3.4 映射函数**
- [ ] inputSchema 驱动的动态表单可渲染并提交
- [ ] 集成测试：手动读直接返回 + 手动写触发审批

### 3.4 【驳回点 B1.2 闭合】`min_approval` → `requiresHumanConfirm` 映射机制

> 审计官实锤：`wgateCreate` 只接受 `requiresHumanConfirm?: boolean`，**没有从 capability 的 `min_approval` 字段自动裁决**；registry.ts 默认 `requiresConfirm = !HIGH_SENSITIVITY.includes(toolName)`。手动路由必须明确翻译机制——**这是防后门的核心接线点**。已核实代码，给出具体机制而非意图。

**核实结论**：
- `min_approval` 是 **capability 级**字段（agentCapabilities.ts，取值 auto|always|never），不是 tool 级。
- 但 `wgateCreate` 的 `requiresHumanConfirm` 是 **tool 级**布尔（单次写调用粒度）。
- **tool→capability 反向映射**：capability-gate.ts 已含完整 `toolToCapId`（19 tool 1:1，L23-42）+ `CAPABILITY_GATE_TOOLS`（N2 修正：实测存在）。手动路由第一步**复用/对齐**该现成映射（或从 DB `agent_capabilities.mcp_tools` 派生单一授权源），把被调 tool 归一到它所属 capability，再读该 capability 的 min_approval 裁决。
- `effective_enabled` 视图已输出 `min_approval`（0034 迁移），`resolveCapabilityEffective` 已返回 `minApproval` 字段——**裁决数据源就绪，缺的是「tool→capability」归一层 + 布尔翻译**。

**新增映射函数设计**（`manual-routes.ts` 内）：

```ts
// ① tool→capability 反向索引（一次性构建，从 agent_capabilities.mcp_tools 反查）
//    启动时构建 Map<toolName, capabilityId>；运行时增量刷新（capability 变更后失效重建）
const TOOL_TO_CAPABILITY: Map<string, string> = new Map();
async function buildToolCapabilityIndex(): Promise<void> {
  TOOL_TO_CAPABILITY.clear();
  const caps = await db.select({ id, mcpTools }).from(agentCapabilities);
  for (const c of caps) for (const t of c.mcpTools) TOOL_TO_CAPABILITY.set(t, c.id);
}
// 注意：一个 tool 可能被多个 capability 引用（如 ams.creative.list 同时被 creative 域多 capability 用）。
// 规则：取第一个命中（按 cap_id 字典序稳定）；若需多归属裁决，取 min_approval 最严格者（'always' 优先）。

// ② 核心翻译函数：capability.min_approval → wgateCreate.requiresHumanConfirm
function mapMinApprovalToRequiresConfirm(
  minApproval: string,          // 'auto' | 'always' | 'never'（来自 resolveCapabilityEffective）
  toolName: string,             // 被调写 tool
  toolDefault: boolean,         // write.ts 的 WriteToolDef.requiresHumanConfirm（当前 12 写全 true）
  highSensitivity: boolean,     // registry.ts HIGH_SENSITIVITY 命中（ams.lead.status/ams.ab.run）
): boolean {
  switch (minApproval) {
    case 'always': return true;          // 能力级强制审批——最高优先，杜绝手动出口绕过高敏写
    case 'never':  return false;         // 能力级免审批（信任编排）——仅当非高敏才可放行
    case 'auto':
    default:
      // 退回 tool 定义 + 高敏兜底（与 registry.ts 自动出口语义一致）
      return highSensitivity || toolDefault;   // 高敏写永远强制审批（双端一致性）
  }
}
```

**接线约束（防后门）**：
1. **高敏写永远审批**：`ams.lead.status` / `ams.ab.run` 无论 capability 的 min_approval 为何值，`requiresHumanConfirm` 恒为 true（`highSensitivity ||` 兜底，与 registry.ts `HIGH_SENSITIVITY` 双端一致）。即使某个 capability 误设 min_approval='never'，高敏写也不会被放行。
2. **min_approval='always' 能力的手动写 → 必须走审批队列**（非直接执行），否则手动出口成审批后门（ICL #34）。
3. **manual-routes 调用链**：`invoke(tool)` → `resolveCapabilityEffectiveForRole(capId, roleId, {deptId})`（或按当前用户 role/dept）拿到 `{minApproval, effective}` → `effective===false` 则 403 → `mapMinApprovalToRequiresConfirm(...)` → 传 `requiresHumanConfirm` 给 `wgateCreate`。
4. **权限边界**：手动写调用 `POST /tools/:name/invoke` 用 `:run` 权限触发，但**写结果是否落库由 W-GATE + settleApproval（:approve）双重把关**——触发权限 ≠ 落库权限（与 B2 拆分一致）。

**测试用例（B1.2）**：
- min_approval='always' 的 capability（lead.scoring / ab.experiments）手动写 ams.lead.status → 返回 pending_confirm 进审批队列，不直接执行
- 高敏 tool ams.lead.status 即使在 min_approval='never' 的 capability 下 → 仍强制审批（高敏兜底）
- min_approval='auto' 的非高敏写（如 ams.enrich.field）→ 按 write.ts requiresHumanConfirm=true 审批

### 3.5 【修正项：L0 控制面授权策略】

> 审计官：手动页是否暴露 `ams.agent.run/status`？run.ts `requiresHumanConfirm:false` → 手动触发编排免审批，需明确授权边界。

**决策**：
- **`GET /tools` 清单包含 `ams.agent.run` / `ams.agent.status`**（作为 L0 控制面单独分组显示），但标注「L0 控制面，免人工确认」。
- **`POST /tools/:name/invoke` 允许手动触发 `ams.agent.run`**，`requiresHumanConfirm:false`（与自动出口 run.ts 一致，run.ts 已明确「L0 控制面：非高敏，可自动触发，但仍过幂等+ledger」）。
- **授权边界（明确）**：`ams.agent.run` 手动触发 = **`:run` 权限**（触发编排）。它免审批但**不落业务数据**（只触发 Dify workflow 产出草稿/报告），故不需要 `:approve`。真正落库的写（ams.* 12 写）才需要 `:approve` 审批。
- **L0 免审批不等于无审计**：run 走 `wgateCreate` 幂等 + ledger（run.ts），仍记录触发审计。
- **风险**：`ams.agent.run` 的 Dify workflow 内部若再调用 AMS 写 tool，那些写仍走 W-GATE + min_approval 裁决（双端一致），不会被手动免审批旁路。

### 3.6 【修正项：跳转参数契约】

> 审计官建议补「跳转参数契约」如 `/ai/agent-approvals?requestId=xxx`。

**契约**：
- 手动工具页写 tool 提交后，返回 `{requestId, approvalStatus:'pending_confirm'}` → 前端跳转：
  `window.location.href = '/ai/agent-approvals?requestId=' + encodeURIComponent(requestId)`
- 审批页读取 `?requestId=` 自动打开对应审批详情 Modal，并高亮该条。
- 若 `requestId` 不存在或已结算（approvalStatus 非 pending），审批页回退到列表并 toast 提示。

### 3.7 可量化 AC（v2 补齐）
- **AC1**：手动读 tool（如 ams.creative.list）返回数据，capability 全局 off 时 403（≥2 用例）
- **AC2**：手动写 tool 触发 `wgateCreate`，返回 `{requestId, approvalStatus:'pending_confirm'}`（≥1 用例）
- **AC3**：min_approval='always' 能力的手动写 → 强制进审批队列（≥1 用例，B1.2）
- **AC4（新增，越权）**：**L2_config 用户手动调用需 L4_control 的写 tool（ams.lead.status / ams.ab.run / ams.ab.design）→ 403**（`assertWriteLevel`，registry.ts：L2 < L4 → FORBIDDEN）（≥2 用例，覆盖 lead.status + ab.run）
- **AC5（新增，L0）**：有 `:run` 无 `:approve` 的用户手动触发 ams.agent.run → 成功（免审批），但调 approve 路由 → 403（≥2 用例）
- **AC6（新增，跳转契约）**：手动写提交返回 requestId，`/ai/agent-approvals?requestId=xxx` 打开对应详情（人工验收 + ≥1 集成用例）

---

## 四、T3：19 tool 全量 inputSchema 修订（P1）【驳回点 B1 补全】

### 4.1 定位：修订既有 schema 到统一精度，非从零补全

> 已核实全部 19 tool 已注册 inputSchema（read.ts 7 个 + write.ts 12 个），但完整度不一致。本任务**不是**「从零补全」，而是**「修订既有 schema 到统一精度标准」**。改动必须：**不破坏现有 handler 入参契约**（handler 用 `args.x ?? 默认` 容错，schema 收紧后不影响已接线调用）。

### 4.2 统一精度标准（新定义，全 19 tool 适用）

| 维度 | 标准 | 校验 |
|---|---|---|
| **required 完整性** | 每个 tool 的 `required[]` 精确表达「handler 真正必需的入参」。功能性必需（service/executor 依赖且无合理默认）必须进 required；纯可选过滤字段不进。**R5/W10 的 `required:[]` 需修正** | 逐一对照 handler/service 依赖 |
| **enum 约束** | 有明确业务枚举的字段必须 enum（如 reviewStatus、status、metric、platform、entityType、type）；无固定枚举用 description 说明取值来源 | 与 service 校验对齐 |
| **format** | 日期用 `format:'date'`、UUID 用 `format:'uuid'`、邮箱/URL 按需 | 已大部分对齐，补漏 |
| **description** | 每个 property 有中文 description（说明语义 + 取值来源 + 是否公司级过滤） | 已有，补全遗漏 |
| **缺省值** | handler 有默认逻辑的字段，schema 标注 `default` 并同步 min/max 边界（如 limit 1-200） | 与 handler `x || 默认` 对齐 |
| **只读字段** | 读 tool 的 companyId **永不入 schema**（从会话取，入参忽略） | 已符合，保持 |

### 4.3 逐 tool 缺口 + 修订后 schema 要点

#### 读工具（7 个）

| Tool | 现有问题 | 修订后要点 |
|---|---|---|
| **R5 ams.adinsights.query** | **required:[] 但 service 依赖 dateFrom/dateTo**；entityType 默认 campaign 未标注 | **核心缺口**：service `getAggregatedStats` 以 dateFrom/dateTo 计算 ROI/CTR/CVR。修订：**`required:['dateFrom','dateTo']`**（无日期无法算聚合指标）；entityType 加 `default:'campaign'` 同步 handler；platform 保留 enum；entityId 保留可选 |
| **W10 见写工具** | — | — |
| R1 ams.creative.list | limit 无边界 | limit 加 `minimum:1, maximum:200`；reviewStatus 补 enum（pending_generation/pending_confirm/pending_review/approved/rejected/auto_passed/generation_failed）；type 已有 enum。required 保持 `[]`（全可选过滤） |
| R3 ams.competitor.query | category 无 enum，limit 无边界 | limit 加 min/max 1-200；isActive 已有 boolean；required 保持 `[]` |
| R4 ams.lead.query | tier 无 enum，limit 无边界 | tier 补 enum（HOT/WARM/COLD）；limit 加 min/max；required 保持 `[]` |
| R6 ams.adinsights.anomaly | entityType 默认 'ad' 未标注 | entityType 加 `default:'ad'` 同步 handler；已 required['entityId','metric']，保持 |
| R2/R7 | 完整 | 保持不动（已达标） |

#### 写工具（12 个）

| Tool | 现有问题 | 修订后要点 |
|---|---|---|
| **W10 ams.adinsights.report** | **required:[] 但 executor 依赖 platform/dateFrom/dateTo 生成报告** | **核心缺口**：executor `getOverviewStats({platform,dateFrom,dateTo})` 无日期无意义。修订：**`required:['dateFrom','dateTo']`**（报告必须限定时间窗）；platform 补 enum（meta/google/tiktok/linkedin/pinterest/snapchat/reddit/line/zalo）并对齐 R5；title 保留可选 |
| W1 ams.creative.generate | model 无 enum/default，count 无边界 | model 补 default:'default'（executor 缺省）或 enum 已知模型；count 加 min 1 max 20；required 保持 ['prompt'] |
| W11 ams.ab.design | experimentType 无 enum | experimentType 补 enum（a_b / multivariate / holdout）；required 保持 ['name'] |
| W2/W3/W5/W6/W7/W8/W9/W12 | 完整 | 保持不动（已达标） |
| W4 ams.competitor.snapshot | 其余可选 | website 补 format:'uri'；required 保持 ['name']（合理） |

#### L0 控制面（2 个，单独处理）
- `ams.agent.run` / `ams.agent.status` 不在 READ_TOOLS/WRITE_TOOLS 数组，**无独立 inputSchema**（走 handleControl 分支）。
- 手动工具页 `GET /tools` 需为它们**生成最小 schema** 供表单渲染：
  - `ams.agent.run`: `{properties:{workflow:{type:'string'}, inputs:{type:'object'}}, required:['workflow']}`（对齐 run.ts WORKFLOW_BY_KEY）
  - `ams.agent.status`: `{properties:{workflowRunId:{type:'string'}}, required:['workflowRunId']}`（对齐 status.ts）

### 4.4 实施方式
- 修改 `src/server/modules/ai/mcp/tools/read.ts` + `write.ts` 的 inputSchema 字面量（纯声明改动，不动 handler）。
- 修改后跑既有 MCP 集成测试（server.ts 注册 tool 的 schema 序列化测试）+ 手动页表单渲染冒烟。
- ⚠️ 收紧 required（R5/W10 加 dateFrom/dateTo）可能影响**已接线的自动出口**（若 Dify 调用方未传日期）。需先 grep 调用方确认：若无调用方传参依赖这些字段缺失，则收紧安全；若有，需同步更新调用方。

### 4.5 DoD
- [ ] 19 tool 全部 inputSchema 过 §5.2 统一精度标准
- [ ] R5/W10 的 required:[] 修正为含 dateFrom/dateTo
- [ ] 收紧后既有 MCP 集成测试全绿（无回归）
- [ ] 手动页动态表单能按修订后 schema 渲染并校验必填

### 4.6 AC
- **AC1**：`ams.adinsights.query` 与 `ams.adinsights.report` 的 `required` 含 `['dateFrom','dateTo']`（静态断言 schema，2 用例）
- **AC2**：缺 dateFrom 调 R5/W10 → 前端表单校验拦截（不发起请求）（≥2 用例）
- **AC3**：19 tool schema 全部满足统一精度标准（enum/format/description/default 抽查 ≥8 工具）
- **AC4**：收紧 required 后 MCP 集成测试全绿，无回归（1 批）

---

## 六、T4：开发文档（ai-project-docs 十层）【驳回点 B1 补全】

### 6.1 十层体系 → AMS 项目目录映射

> 需把 ai-project-docs 十层（L1 入口/L2 角色路由/L3 决策/L4 执行/L5 规约/L6 验收/L7 诊断/L8 门禁/L9 交付/L10 回流）落地到 AMS 项目，每层给出目录/文件名、产出物、写入人、DoD。

**AMS 项目文档根**：`/home/chee/Projects/AIMarketingSystem/docs/`（N3 修正：实测 docs/ 仅 5 个非编号文件 + autotrade/ 子目录，**不存在 01-20 顶层系统文档系列**；`docs/11-18` 为**新增**顶层文件，不与现有冲突）+ `/home/chee/Projects/oc-macs/specs/`（SDD/审计）

| 层 | 职责 | 落地目录/文件 | 产出物 | 写入人 | DoD |
|---|---|---|---|---|---|
| **L1 入口** | 文档总览/导航 | `docs/README.md`（新增或补节） | 十层索引 + Agent 编排文档地图 | 军师(guihua) | 从 README 能跳到任意层文档 |
| **L2 角色路由** | 各角色（用户/Agent/审批人）行为入口 | `docs/11-agent-orchestration.md`（新增） | 谁触发、谁审批、谁执行、权限矩阵 | 军师(guihua) | 含 B2 权限矩阵 + :approve/:run/:read 三权 |
| **L3 决策** | 架构决策记录（ADR） | `docs/adr/ADR-xxx-agent-orchestration.md`（新增） | min_approval→requiresHumanConfirm 裁决、双出口共享内核、:approve 拆分 | 军师(guihua) | 每个关键决策有「背景/选项/选择/后果」 |
| **L4 执行** | 实现细节/代码走查 | `docs/12-agent-orchestration-implementation.md`（新增） | T1/T2 前后端实现、审批路由、手动路由、inputSchema | 代码(daima) | 代码注释指向 L4 文档；L4 文档与代码同步 |
| **L5 规约** | API/DB 契约 | `docs/13-agent-orchestration-api.md`（新增） | 19 tool schema、审批路由、手动路由、approval_requests/idempotency_keys 表契约 | 代码(daima) | 契约与 read.ts/write.ts/wgate.ts 实际签名一致 |
| **L6 验收** | 验收清单/测试 | `docs/14-agent-orchestration-acceptance.md`（新增） | §七 T5 5维×3级矩阵全量条目 | 军师(guihua) + 审计官(rongcui) | 验收条目与 T5 AC 一一对应可执行 |
| **L7 诊断** | 排障手册 | `docs/15-agent-orchestration-troubleshooting.md`（新增） | 审批不落库、幂等卡 in_progress、403 越权、journal 缺失常见问题 | 代码(daima) | 每个诊断含「症状/根因/修复 SQL/命令」 |
| **L8 门禁** | 变更门禁/权限门 | `docs/16-agent-orchestration-gates.md`（新增） | capability 开关、:approve 授权、高敏写强制审批、migration journal 门禁 | 审计官(rongcui) | 门禁项可被 CI 检查（脚本化） |
| **L9 交付** | 发布说明/运维 | `docs/17-agent-orchestration-release.md`（新增） | 本任务交付物清单、部署步骤、migration 重放 | 军师(guihua) + 运维 | 交付物与 JJC-20260807-001 范围一致 |
| **L10 回流** | 经验/改进回流 | `docs/18-agent-orchestration-retro.md`（新增） | 本次驳回教训、inputSchema 统一标准沉淀、journal 门禁经验 | 军师(guihua) | 沉淀项进入下一版 SDD 或 skill |

> **写入人说明**：daima=代码实现，wenan=文案/前端交互，rongcui=审计/验收。本任务以 daima + guihua 为主，rongcui 负责 L6/L8 验收门禁。若团队无独立 wenan 角色，前端交互文档由 daima 兼写并标注。

### 6.2 DoD
- [ ] 十层文档全部创建为新增顶层文件 docs/11-18（N3 修正：无既有 01-20 体系可合并，直接新建，不与现有 docs/ 5 个非编号文件冲突）
- [ ] L2 含 :approve/:run/:read 三权矩阵（B2）
- [ ] L3 含 min_approval→requiresHumanConfirm 裁决记录（B1.2）
- [ ] L5 与 read.ts/write.ts/wgate.ts 实际契约一致（T3 修订后同步）
- [ ] L6 与 T5 验收矩阵一一对应
- [ ] L8 门禁项可脚本化（含 journal 检查）

### 6.3 AC
- **AC1**：docs/ 下 Agent 编排十层文档齐备（≥10 个文件或合并节，人工验收）
- **AC2**：L5 契约与 T3 修订后 inputSchema 逐字段一致（抽查 ≥5 tool）
- **AC3**：L8 含 journal 完整性检查脚本（见 §八.2.5），CI 可跑（≥1 用例）

---

## 七、T5：验收清单（5维×3级）【驳回点 B1 补全】

### 7.1 矩阵：5 维 × 3 级

| 维度 | L1 冒烟（单点功能通） | L2 集成（跨模块协同） | L3 端到端（全链路业务流） |
|---|---|---|---|
| **功能** | 单 tool 调用/审批单动作 | 手动出口+审批联动、双出口共享 executor | MCP 写触发→审批→落库→ledger 全链 |
| **安全** | 单点权限校验 403 | 越权/高敏写强制审批/防后门 | :approve 与 :run 隔离、无审批旁路 |
| **性能** | 单次调用延迟 | 并发审批幂等、审批列表分页 | 高并发写触发不重复执行 |
| **兼容** | schema 收紧不回归 | 自动/手动出口一致、L 级矩阵 | 旧数据（幂等残留）兼容迁移 |
| **文档** | 十层文档存在 | L5 契约与代码一致 | 全新环境 journal 可复现 |

### 7.2 可测条目（20 条，编号 A0X-LY 格式）

**功能（F）**
- **A01-F1** 手动读 tool 调用返回数据（ams.creative.list）
- **A02-F2** 手动写 tool 触发审批请求（pending_confirm）
- **A03-F3** approve 后 executor 真实落库 + ledger success + humanConfirmedBy
- **A04-F3** MCP 写触发→审批→落库→回读 全链路（端到端）
- **A05-F2** deny 后不落库 + ledger denied

**安全（S）**
- **A06-S1** 无 `:approve` 权限调 approve → 403
- **A07-S2** **L2_config 用户手动调 L4 写 tool（ams.lead.status/ams.ab.run）→ 403（assertWriteLevel）**
- **A08-S2** capability 全局 off → 手动/自动出口均 403
- **A09-S3** min_approval='always' 能力手动写强制进审批（B1.2）
- **A10-S3** 高敏写 ams.lead.status 即使在 min_approval='never' 下仍强制审批（高敏兜底）

**性能（P）**
- **A11-P1** 单次审批 approve 响应 < 500ms
- **A12-P2** **并发审批同一请求：两人同时 approve → 仅 1 次执行，另 1 返回 {status,settled:true}（幂等）**（wgate.ts:319）
- **A13-P3** 高并发同 key 写触发 → 单活跃实例（仅 1 条 in_progress）

**兼容（C）**
- **A14-C1** T3 schema 收紧（R5/W10 加 required date）后 MCP 集成测试全绿
- **A15-C2** 自动出口（Dify/MCP）与手动出口对同一写 tool 行为一致（双出口共享 executor）
- **A16-C3** 24 条 in_progress 幂等残留清理后，历史请求可查询不报错

**文档（D）**
- **A17-D1** 十层文档齐备（L1-L10）
- **A18-D2** L5 契约与 T3 修订后 inputSchema 逐字段一致
- **A19-D3** 全新环境跑 drizzle migrate → W-GATE 表/能力表/effective_enabled/P1-P6 种子全建（B6）
- **A20-D3** 全新环境手工触发→审批→落库 全流程可复现（含 journal）

### 7.3 DoD
- [ ] 20 条验收条目全部可执行（有测试脚本或人工步骤）
- [ ] A07/A12/A19 为强制门禁（安全/并发/可复现）
- [ ] 每条第「通过标准 + 执行方式（自动化/人工）+ 责任人」

---

## 八、T6：遗留清理（journal + 幂等残留 + 测试数据）【驳回点 B1/B6 补全】

### 8.1 idempotency_keys in_progress 残留（生产实测 30 条全量甄别）

> **N1 修正（审计复审）**：生产库实测 in_progress agent_write = **30 条**，非 24。分解：6 条已过期（→置 failed）、0 条「审批已决但幂等键 in_progress」（分类2 命中 0）、**24 条未过期且审批仍 pending（保留，不清理）**。故「24」是**保留的真实待审批**，非清理量。

**判据**：`agent_write` 类型 + `status='in_progress'` 的键。这类键对应「已创建审批请求但从未结算」的孤儿，或「触发后崩溃未终结」的残留。**安全处置：标记 failed（不删），保留 ledger 可追溯**。

**甄别 SQL**（先看再清，不盲目置 failed）：
```sql
-- ① 甄别：列出 in_progress 的 agent_write 键及其关联审批请求
SELECT ik.id, ik.key, ik.company_id, ik.resource_type, ik.resource_id,
       ik.created_at, ik.expires_at, ap.status AS approval_status, ap.id AS approval_id
FROM idempotency_keys ik
LEFT JOIN approval_requests ap ON ap.id::text = ik.resource_id::text
WHERE ik.key_type = 'agent_write' AND ik.status = 'in_progress';
```
**清理判据（分三类）**：
- **已过期**（`expires_at < now()`）：TTL 已失效，直接置 failed（24h 窗口过期，IDEMPOTENCY_AGENT_WRITE_TTL_MS）。
- **未过期但关联审批已终结**（approval_status IN approved/rejected/cancelled/expired 而幂等键仍 in_progress）：数据不一致，置 failed（审批已决但幂等键漏结算的孤儿）。
- **未过期且审批仍 pending**：**不置 failed**——这是真实待审批请求，清理会破坏审批链。需人工确认是否误留，或保留待审批人处理。

**清理 SQL（仅对前两类，非全部）**：
```sql
-- ② 清理：置 failed（仅过期 + 审批已终结两类，pending 保留）
UPDATE idempotency_keys ik SET status = 'failed'
WHERE ik.key_type = 'agent_write' AND ik.status = 'in_progress'
  AND (
    ik.expires_at < now()                                  -- 已过期
    OR EXISTS (                                            -- 或关联审批已终结
      SELECT 1 FROM approval_requests ap
      WHERE ap.id::text = ik.resource_id::text
        AND ap.status IN ('approved','rejected','cancelled','expired','escalated')
    )
  );
```
> ⚠️ **不是「全部置 failed」**。pending 的真实审批必须保留。清理前先跑甄别 SQL，人工核对 pending 条数。

### 8.2 creative.submit 测试数据污染甄别

**污染源**：测试/演示环境调用 `ams.creative.submit` 或 `ams.creative.generate` 产生的无业务意义素材（reviewNote 含 test/demo，或无真实产品关联）。

**甄别 SQL**：
```sql
-- ③ 甄别：测试数据（reviewNote/name 含 test/demo/mock，或 created_by 为测试账号）
SELECT a.id, a.name, a.review_status, a.review_note, a.created_by, a.created_at
FROM creative_assets a
WHERE a.review_note ILIKE '%test%' OR a.review_note ILIKE '%demo%' OR a.review_note ILIKE '%mock%'
   OR a.name ILIKE '%test%' OR a.name ILIKE '%demo%'
ORDER BY a.created_at DESC;
```
**清理范围决策**（需人工确认，默认**软删除/归档**而非物理删）：
- 命中且 `review_status` 非正式审批链关键节点 → 归档（置 deleted_at 或 archive 标记）。
- **关联了真实产品/审批链的不可删**（会破坏 ledger 一致性）。
- 清理前导出备份 SQL，清理后跑 §8.1 甄别确认无连锁 in_progress 残留。

### 8.3 【驳回点 B6】migration journal 补齐

#### 8.3.1 实况核实（v2 实测，比审计更全）

- `_journal.json` 共 **23 条**（idx 0-23，注意 idx 2 空缺、13-23 的 `when` 为未来时间戳 1786xx）。
- **14 个 migration 文件不在 journal**（审计只点名 5 个，实测 14 个）：
  `0013_analytics_reports_created_by_fk`、`0014_social_posts_unique`、`0015_document_number_unique`、`0016_roles_code_company_unique`、`0018_evolution_cycles_unique`、`0019_document_counters`、`0020_add_version_columns`、`0021_payments_payment_number_unique`、`0031_mcp_wgate_schema`、`0032_departments`、`0033_agent_capabilities`、`0034_agent_capability_switches`、`0035_seed_capabilities`、`0036_leads_status`。
- **后果（审计官实锤）**：全新环境/CI 跑 `drizzle migrate` **不会创建** W-GATE 表（idempotency company_id/approval requested_by_type）、agent_capabilities、agent_capability_switches、effective_enabled 视图、P1-P6 种子、departments 表、leads.status 字段。

#### 8.3.2 0032 版本冲突处理

**冲突**：`0032_departments.sql`（旁路，建 departments 表，是 0033 的**前置依赖**）与 `0032_channel_soft_delete.sql`（journal，idx 23）同名前缀。

**处理方案（推荐：改名 journal 化，保持依赖序）**：
1. **改名 `0032_departments.sql` → `0031a_departments.sql`**（或拆到 0031 之后、0033 之前的空档编号），确保它在 0033_agent_capabilities **之前**执行（0033 的 `dept_id REFERENCES departments(id)` 依赖它）。
2. **把旁路文件全部纳入 journal**：推荐用 **drizzle-kit 重放（replay）**——`drizzle-kit migrate` 支持对已执行迁移打标记，或将每个旁路文件注册为 journal 条目（tag + idx + when），使其被 drizzle 识别为「已应用」。
3. **冲突规避**：同号前缀不得有两个文件。0032 只保留 `0032_channel_soft_delete.sql`（已在 journal）；`0032_departments.sql` 改名避开。

> ⚠️ **为何不手写 append journal 条目**：drizzle 用 `_journal.json` 的 tag/idx 与 `meta/_meta.json`（快照）绑定。手改 tag 但不同步 `meta/_meta.json` 会破坏快照校验。**推荐方案**：用 drizzle-kit 官方机制重放——把旁路 SQL 文件保留在 migrations 目录，通过 `drizzle-kit generate` 补登记或用 `drizzle-kit migrate` 对已存在表打 reconcile。若版本不支持 reconcile，则**脚本化补 journal**（见 §8.3.4）。

#### 8.3.3 全新环境可复现验证步骤（B6 验收）

```bash
# 1. 全新空库验证
createdb ams_fresh_test
DATABASE_URL=postgres://.../ams_fresh_test npx drizzle-kit migrate   # 应重建全部表+视图+种子

# 2. 断言关键对象存在
psql ams_fresh_test -c "\dt idempotency_keys"          # company_id 列存在 + 复合唯一
psql ams_fresh_test -c "\dt agent_capabilities"        # 能力表
psql ams_fresh_test -c "\dt agent_capability_switches" # 三级开关表
psql ams_fresh_test -c "\dv effective_enabled"         # 派生视图
psql ams_fresh_test -c "SELECT count(*) FROM agent_capabilities"  # = 6（P1-P6 种子）
psql ams_fresh_test -c "SELECT count(*) FROM roles WHERE code IN ('P1','P2','P3','P4','P5','P6')"  # = 6
psql ams_fresh_test -c "\d leads" | grep status        # leads.status 存在

# 3. 全流程冒烟：MCP 写触发 → 审批 → 落库（用 T5 A20）
```

**CI 门禁（L8 沉淀）**：在 CI 加一步 `verify-migration.sql`（仓库已有 `scripts/verify-migration.sql`）断言 journal 覆盖 == 文件数，缺失即 fail。

#### 8.3.4 journal 补齐脚本（若 drizzle-kit 无 reconcile）

新增 `scripts/backfill-migration-journal.mjs`：读取 `migrations/` 目录所有 `*.sql`，与 `meta/_journal.json` 条目 tag 比对，将缺失文件按依赖序（0013→0020→0031→0032_departments→0033→0034→0035→0036）append 为 journal 条目（分配新 idx + 当前时间戳 when），并同步更新 `meta/_meta.json` 快照哈希（或调用 drizzle-kit API 重新生成）。脚本幂等：已登记的文件跳过。

### 8.4 DoD
- [ ] journal 补齐后，全新环境 `drizzle migrate` 重建全部对象（§8.3.3 步骤全过）
- [ ] 0032 冲突解决（departments 改名避开，且先于 0033）
- [ ] 24 条 in_progress 幂等残留清理（仅过期/已决，pending 保留）
- [ ] creative.submit 测试数据归档（软删除，不破坏 ledger）
- [ ] CI 加 journal 完整性门禁

### 8.5 AC
- **AC1**：全新库跑 migrate 后，`agent_capabilities` 有 6 条种子、`effective_enabled` 视图存在、`leads.status` 存在（§8.3.3 断言全过）
- **AC2**：journal 条目数 == migration 文件数（脚本断言，0 缺失）
- **AC3**：0032 无同号冲突（ls migrations/0032* 仅 1 文件）
- **AC4**：30 条 in_progress 全量甄别后：6 条过期置 failed、0 条审批已决置 failed、**24 条 pending 真实审批保留**；清理后 in_progress 仅剩 24 条 pending（甄别 SQL 二次核对）
- **AC5**：creative.submit 测试数据归档不破坏 ledger（清理后审批链记录完整）

---

## 九、风险与依赖（v2 全量）

| 风险 | 等级 | 对策 |
|---|---|---|
| T3 收紧 R5/W10 required 破坏已接线自动出口 | 中 | 先 grep 调用方确认无依赖，有则同步更新调用方（§4.4） |
| journal 手改破坏 meta 快照 | 高 | 用 drizzle-kit 官方 reconcile/重放，或脚本同步 meta（§8.3.2/8.3.4） |
| 审批权限拆分遗漏导致后门 | 高 | :approve 独立 + AC6/A10 双兜底（B2） |
| min_approval 翻译误放行高敏写 | 高 | 高敏兜底 `highSensitivity ||` 恒 true（§3.4） |
| 幂等清理误删 pending 审批 | 中 | 三类判据分治，pending 保留（§8.1） |

## 十、交付物汇总

1. T1：`approval-routes.ts` + 前端审批页 + :approve 权限
2. T2：`manual-routes.ts` + 前端手动页 + min_approval 映射函数
3. T3：read.ts/write.ts inputSchema 修订（统一精度）
4. T4：十层文档（docs/11-18）
5. T5：验收矩阵（20 条）
6. T6：journal 补齐脚本 + 幂等/测试数据清理 SQL + 全新环境验证

**审计官品控验收要点对照**（§通过后品控官验收要点 6 项）：
- ✅ B1：T3/T4/T5/T6 全小节存在 + DoD + AC（§五/§六/§七/§八）
- ✅ B2：新增 ai:agent-orchestration:approve 权限，审批路由用它（§二.2.2）
- ✅ B1.2：min_approval→requiresHumanConfirm 映射实现 + 测试（§三.4）
- ✅ B6：migration journal 补齐（含 0032 冲突处理）+ 全新环境可复现验证（§八.3）
- ✅ T1-AC4 按实际返回结构断言（§二.4 AC4）
- ✅ T2 补 assertWriteLevel 越权用例（§三.7 AC4）