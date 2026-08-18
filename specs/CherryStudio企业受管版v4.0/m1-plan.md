# M1 执行计划 · CherryStudio 受管版 Fork 层完整实现（F1-F12）

> 军师（guihua，规划部）产出 | JJC-20260811-001
> 权威定义：`m1-f1-f12-def.md`（源自 NAS `/mnt/chee_2/Chee/OpenClaw_C/基建/cherry-managed/docs/任务分解-v4.0.md`，2026-08-07）
> 前置：M0 收尾已收口（003 cancelled，老板拍板，commit `4aa345b`；cherry-src HEAD = `963897128`）
> 说明：本计划所有「现状」均基于 2026-08-11 实读代码核实，非记忆推定。**不静默假设、不过度工程、不链式幻觉。**

---

## 〇、任务 ID 与产出摘要

- **任务 ID**：JJC-20260811-001
- **M1 交付判据**：`/v1/admin/*` 全路由 + 独立管理 key + 受管保护 + 热更新 + 锁 UI
- **关键路径（权威）**：`M0-3 → F-1 → F-2 → F-4/F-5 → M0-1(热更新验证) → F-9 → M1`

### 现状核实总表（实读代码）

| F | 任务 | 现状 | 判定 |
|---|------|------|------|
| F-1 | 官方最新镜像 + Fork 分支 | `managed/main` 基于 `origin/main` @ `12498d68e`；`origin`=CherryHQ，`managed`=leappower；**无 `official/main` 镜像分支** | 半成品-需补分支策略 |
| F-2 | `/v1/admin/*` 路由挂载 | ✅ `app.ts` 已把 `adminRoutes` 挂到 `v1Routes` scoped guard 末尾，鉴权继承 | 【已实现-仅验证】 |
| F-3 | 独立管理 key | ❌ 无 `feature.api_gateway.managed_key`；auth.ts 仅比对 `api_key` | 【需补】 |
| F-4 | agents 管理路由 | 半成品：`POST /agents` + `PUT /agents/:id` 已有；缺 list/get/delete/reorder | 【需补】 |
| F-5 | providers 管理路由 | 半成品：GET/POST/PUT + PUT api-keys 已有；缺 delete/batchUpsert/addApiKey | 【需补】 |
| F-6 | skills/mcp 管理路由 | ❌ 表存在（agentSkillTable/mcpServerTable）但无 admin 路由 | 【需补】 |
| F-7 | usage 管理路由 | ✅ `GET /usage` 已有 | 【已实现-仅验证】 |
| F-7b | agent-files 工作目录采集 | ❌ 无路由；但 agentDataDirectory.ts + agent_workspace 表 + accessible_paths 概念存在 | 【需补】 |
| F-8 | 泛化受管保护 | ❌ 现为硬编码 `cherryai` 特判（ProviderService）；**全库无 managed_registry 表** | 【需补】 |
| F-9 | 热更新 IPC 刷新广播 | ✅ notifyDataApiDataChange 模板路径+entityIds；useProvider S3 订阅；S4 10 用例 | 【已实现-仅验证】 |
| F-10 | 锁死 UI（源码级） | ❌ cherryai 仅隐藏于列表（isProviderSettingsListVisibleProvider）；无删除隐藏/只读 managed 判断 | 【需补】 |
| F-11 | 禁用官方更新 | ❌ feed 来自 electron-builder.yml publish `url: https://releases.cherry-ai.com`；autoUpdate=`app.dist.auto_update.enabled`；无 managed 接管 | 【需补】 |
| F-12 | Fork 分支收敛 | ❌ 无 official/main 镜像，无 rebase 流程落地 | 【需补】 |

**总体缺口统计**：已实现-仅验证 3 项（F-2/F-7/F-9）；半成品-需对齐 1 项（F-1，严格说是分支策略半落地）；需补 8 项（F-3/F-4/F-5/F-6/F-7b/F-8/F-10/F-11/F-12 中 F-12 独立算，实际 8+1）。

---

## 一、现状核实明细（实读代码证据）

### 1.1 Git / 分支现状（F-1、F-12）
```
当前分支: managed/main @ 963897128
remotes:
  origin   → https://github.com/CherryHQ/cherry-studio.git   (上游官方)
  managed  → https://github.com/leappower/cherry-studio-managed.git (管理 Fork)
fork point: merge-base(managed/main, origin/main) = 12498d68e
managed 独有提交（相对 main）: 963897128 / 0ef01567f / a4d335dc0 / 2f0dda5f2（即 M0 收尾 4 提交）
```
- 无 `official/main` 镜像分支（F-1 定义的镜像分支策略未落地）。
- `main` 本地分支落后（指向 c27e7584a，仅领先 origin/main 2 个 actions rescan 提交）。

### 1.2 路由挂载与鉴权（F-2、F-3）
- `src/main/features/apiGateway/app.ts`：`v1Routes` 用 `as: 'scoped'` guard，`adminRoutes` 挂载在链尾 → 继承 `x-api-key`/Bearer 鉴权。✅
- `src/main/features/apiGateway/middleware/auth.ts`：`authorizeApiRequest` 三方言 token 全部比对 `feature.api_gateway.api_key`；**无 managed_key 分支**。
- `src/shared/data/preference/preferenceSchemas.ts` L344-351：`feature.api_gateway` 仅有 `api_key/enabled/host/port` 四个键，**无 `managed_key`**。

### 1.3 adminRoutes 现有覆盖（F-2/F-4/F-5/F-7）
`src/main/features/apiGateway/adminRoutes.ts`（287 行），现有：
- `PUT /agents/:id`（updateAgent，广播 collection+detail）
- `POST /agents`（走 createAgent 编排，广播 collection+detail）
- `GET /providers`、`POST /providers`、`PUT /providers/:id`、`PUT /providers/:id/api-keys`
- `GET /usage`（AiUsageRecordService.list）
**缺口**：agents 无 list/get/delete/reorder；providers 无 delete/batchUpsert/addApiKey。

### 1.4 受管保护现状（F-8）
- `src/main/data/services/ProviderService.ts`：
  - `isManagedCherryAiProviderId` / `assertManagedCherryAiProviderPatchAllowed` / `assertManagedCherryAiProviderMutationAllowed`（update/replaceApiKeys 时对 `cherryai` 抛 invalidOperation）
- `src/shared/data/presets/cherryai.ts`：`CHERRYAI_PROVIDER_ID='cherryai'` 硬编码常量。
- **全库 grep `managed_registry`/`managedRegistry` 零命中** → 无泛化 registry，受管判定是硬编码 providerId 特判。

### 1.5 热更新（F-9）
- 广播：`notifyDataApiDataChange([{endpoint, kind, entityIds}])`，**模板路径 + entityIds**（dispatchDataChange 精确匹配模板路径）。
- 渲染订阅：`useProvider.ts` 的 `useProviderById` / `useProviderApiKeys` 已补 S3 `useDataChange`；`useProviders` 已补。
- S4 集成测试：`src/main/features/apiGateway/routes/__tests__/routes.integration.test.ts` L591-740 覆盖 admin 6 路径 spec 注册 + 401/403 + providers 3 写 + api-keys 广播 + usage + agents 2 写 ≈ 10 用例。✅

### 1.6 skills/mcp 表（F-6）
- `src/main/data/db/schemas/agentSkill.ts`（agentSkillTable）、`mcpServer.ts`（mcpServerTable）、`assistantRelations.ts`（agent_mcp_server / assistant_mcp_server 关联表）均存在。
- 但 `adminRoutes.ts` 无 skills/mcp 任何路由。

### 1.7 工作目录采集（F-7b）
- `src/main/ai/agents/agentDataDirectory.ts`：`createAgentDataDirectory` / `assertAgentStoragePath`（防 symlink 逃逸）/ `AGENT_DATA_FILES=['SOUL.md','USER.md']`。
- `src/main/data/db/schemas/agentWorkspace.ts`：`agent_workspace` 表（name/path/type/orderKey/timestamps）。
- 渲染层 `src/renderer/components/composer/variants/agent/accessiblePath.ts`：`accessiblePaths` / `isPathWithinAccessiblePath` 概念已存在（Claude Code 工具侧）。
- **无 `/v1/admin/agent-files` 路由**。

### 1.8 锁 UI（F-10）
- `src/renderer/utils/providerSettings.ts` `isProviderSettingsListVisibleProvider`：仅 `!isCherryAIProvider && !== LOCAL_EMBEDDING` 时显示 → cherryai 仅从列表隐藏。
- `ProviderSettings/` 下 grep `managed/cherryai/lock/readonly` 无真实 managed 锁逻辑（命中的是 ModelDrawer 无关项）。
- `src/shared/utils/provider.ts` `isCherryAIProvider` 存在。

### 1.9 禁用官方更新（F-11）
- `electron-builder.yml` L147-149：`publish: { provider: generic, url: https://releases.cherry-ai.com }` → 生成 app-update.yml，是官方 feed 来源。
- `src/main/services/AppUpdaterService.ts`：
  - L77：`autoUpdater.autoDownload = pref('app.dist.auto_update.enabled')`
  - L81：`autoUpdater.forceDevUpdateConfig = !app.isPackaged`
  - L173 日志「Using managed update feed」仅为日志串，实际 feed 是 releases.cherry-ai.com。
  - `configureUpdaterForCheck()` 控制 channel/region/headers，但**不改 feedURL**。
- `app.dist.auto_update.enabled` 默认值在 preferenceSchemas.ts L538（true）。

---

## 二、M1 执行计划（F1-F12 逐项）

> 优先级：P0=阻塞/交付判据必需，P1=必需但可后置，P2=增强。
> 每项含：子任务 / 文件 / DoD（完成定义）/ 量化AC（验收标准）/ 依赖。

---

### F-1 拉官方最新 + 建 Fork 分支策略 ｜ 半成品-需对齐 ｜ P0
**现状**：`managed/main` 基于 `origin/main`@12498d68e；无 `official/main` 镜像。
**目标**：建立 `official/main`（只读镜像官方 main）+ `managed/main`（含 M0/M1 改动）双分支策略。

子任务：
1. 建 `official/main` 分支指向 `origin/main` 最新（`git branch official/main origin/main`），并配置为只读镜像（不直接在此提交）。
2. 将 `managed/main` rebase 到最新 `origin/main`（先确认 M0 4 提交无冲突；官方已有 Auto I18N Sync 等新提交）。
3. 文档化分支收敛流程（见 F-12）。

文件：无代码文件（git 操作）；文档 `docs/fork-branch-strategy.md`
DoD：`official/main` 镜像存在且等于 `origin/main`；`managed/main` 无冲突 rebase 成功。
量化 AC：`git rev-parse official/main == git rev-parse origin/main`；`git log managed/main ^official/main` 仅含 M0/M1 提交。
依赖：M0-3（已完成）。
优先级：P0（所有后续 F-2 起跑前提）。

---

### F-2 `/v1/admin/*` 路由挂载 ｜ 已实现-仅验证 ｜ P0
**现状**：✅ adminRoutes 已挂到 v1Routes scoped guard 链尾，鉴权继承。
子任务：仅验证：`routes.integration.test.ts` 已覆盖 6 路径 spec 注册 + 401/403；补全 F-4/F-5/F-6/F-7b 新路由后同步更新 spec 断言。
文件：`src/main/features/apiGateway/app.ts`（如后续需调整挂载顺序）、`src/main/features/apiGateway/openapiDocs.ts`（新路由 DOC_DESCRIPTIONS）
DoD：所有 admin 路由挂在 scoped guard 内且鉴权一致。
量化 AC：OpenAPI spec 含全部 `/v1/admin/*` 新路由；未鉴权请求全部 401、错误 key 全部 403。
依赖：F-1。
优先级：P0。

---

### F-3 独立管理 key ｜ 需补 ｜ P0
**现状**：无 `feature.api_gateway.managed_key`；auth 仅比对 api_key。
子任务：
1. `preferenceSchemas.ts` 增加 `feature.api_gateway.managed_key: string | null`（+默认值 null）+ `preferenceTypes.ts` 类型同步。
2. `auth.ts`：`authorizeApiRequest` 增加 managed 判定——`/v1/admin/*` 路径要求 token 命中 `managed_key`；`/v1/*` 普通路径仍用 `api_key`。需在 `app.ts` guard 内区分路径或传参。
3. `openapiDocs.ts`/集成测试补充 managed_key 授权用例。
文件：`src/shared/data/preference/preferenceSchemas.ts`、`preferenceTypes.ts`、`src/main/features/apiGateway/middleware/auth.ts`、`app.ts`、`routes/__tests__/routes.integration.test.ts`
DoD：admin 路由仅接受 managed_key；普通 /v1 不受影响；两个 key 独立。
量化 AC：① 用 api_key 访问 `/v1/admin/*` → 403；② 用 managed_key 访问 `/v1/admin/*` → 200；③ 用 managed_key 访问普通 `/v1/models` → 403；④ 未配置 managed_key 时 admin 路由拒绝（403/404 依实现）。
依赖：F-2。
优先级：P0。

---

### F-4 agents 管理路由（补全 CRUD） ｜ 需补 ｜ P0
**现状**：POST/PUT 已有；缺 list/get/delete/reorder。AgentService 已具备 `listAgents/getAgent/deleteAgent/reorder`。
子任务（adminRoutes.ts 增补）：
1. `GET /agents`（listAgents）——只读，无需广播。
2. `GET /agents/:id`（getAgent）。
3. `DELETE /agents/:id`（deleteAgent + removeAgentDataDirectory 编排）——广播 `/agents` + `/agents/:agentId`。
4. `POST /agents/reorder` 或 `PUT /agents/:id/reorder`（reorder/reorderBatch）——广播 collection。
文件：`src/main/features/apiGateway/adminRoutes.ts`、`openapiDocs.ts`、集成测试
DoD：F-4 全 CRUD 覆盖。
量化 AC：GET list/get 200 且返回正确实体；DELETE 后 404 且广播触发；reorder 后 orderKey 持久化且广播。
依赖：F-2（挂载）、AgentService（已具备）。
优先级：P0。

---

### F-5 providers 管理路由（补全 CRUD） ｜ 需补 ｜ P0
**现状**：GET/POST/PUT + PUT api-keys 已有；缺 delete/batchUpsert/addApiKey。
子任务（adminRoutes.ts 增补）：
1. `DELETE /providers/:id`（providerService.delete）——广播 collection+detail。
2. `POST /providers/batch-upsert`（providerService.batchUpsert）——广播 collection。
3. `POST /providers/:id/api-keys`（addApiKey）——广播 list+detail+api-keys（对齐 S2 模板路径约定）。
文件：`src/main/features/apiGateway/adminRoutes.ts`、`openapiDocs.ts`、集成测试
DoD：F-5 全 CRUD 覆盖。
量化 AC：delete 后 GET 404 且广播；batchUpsert 批量创建/更新并广播；addApiKey 追加 key 且广播三端点。
依赖：F-2、ProviderService（已具备 delete/batchUpsert）。
优先级：P0。

---

### F-6 skills/mcp 管理路由 ｜ 需补 ｜ P1
**现状**：表存在（agentSkillTable/mcpServerTable）但无 admin 路由；需确认是否有对应 Service（无则可能需新建只读或薄 Service，见澄清）。
子任务：
1. 确认 `agentSkill` / `mcpServer` 是否已有数据 Service（grep 现有 Service 层）。
2. adminRoutes 增 `GET /skills`、`GET /mcp`、`GET /mcp/:id`（只读）；若需求含写则补 POST/PUT/DELETE（须走 Service，禁止直连 sqlite）。
文件：`src/main/features/apiGateway/adminRoutes.ts`、`openapiDocs.ts`、（可能）新 Service、集成测试
DoD：skills/mcp 可经 admin 读取；写操作（如定义）走 Service。
量化 AC：GET skills/mcp 200 返回表数据；写操作通过 Service 提交并广播。
依赖：F-2。
优先级：P1。

---

### F-7 usage 管理路由 ｜ 已实现-仅验证 ｜ P0
**现状**：✅ `GET /usage` 已有（AiUsageRecordService.list，支持 from/to 时间窗）。
子任务：仅验证。注意 adminRoutes.ts L~256 已标注 `[待确认] device_id 过滤`（官方 usage 服务无 device 维度）——M1 维持现状，不造 device 能力。
文件：无（验证）
DoD：usage 可读。
量化 AC：GET /usage 200；from/to 过滤生效；无 device 维度如实标注。
依赖：F-2。
优先级：P0。

---

### F-7b agent-files 工作目录采集路由 ｜ 需补 ｜ P1
**现状**：无路由；agentDataDirectory.ts + agent_workspace 表 + accessible_paths 概念已存在。
子任务：
1. 复用 `assertAgentStoragePath`（防 symlink 逃逸）+ `isPathWithinAccessiblePath`（accessible_paths 约束）。
2. adminRoutes 增 `GET /agents/:id/files`（按 agent_id/路径枚举+读取工作目录内文件，仅限 accessible_paths / agent_workspace.path 内）。
3. 明确「工作目录」= agent 数据目录（Data/Agents/<id>）还是 agent_workspace 表路径 → 见澄清项。
文件：`src/main/features/apiGateway/adminRoutes.ts`、`openapiDocs.ts`、（可能）新 Service、集成测试
DoD：可按 agent 枚举+读取受管工作目录内文件，路径越界被拒。
量化 AC：合法路径返回文件列表+内容；越界路径（..\、symlink、非 accessible）→ 4xx/空；不泄露 root 外文件。
依赖：F-2、F-4。
优先级：P1。

---

### F-8 泛化受管保护 ｜ 需补 ｜ P0
**现状**：硬编码 `cherryai` 特判（ProviderService），全库无 managed_registry。
子任务：
1. 新增 `managed_registry` 表（drizzle schema）+ 迁移（migrator）。字段建议：`provider_id` / `agent_id` / `managed`(bool) / `lock_rules`(json) / timestamps。
2. 新增 `ManagedRegistryService`（getManagedProviders/getManagedAgents/isManaged）。
3. 将 ProviderService / AgentService 的硬编码 `cherryai` 特判改造为读 managed_registry 判定；受管 provider/agent 不可改/删（抛 invalidOperation）。
4. 迁移既有 cherryai 为 managed_registry 首条种子数据（保持现行为不回归）。
文件：`src/main/data/db/schemas/managedRegistry.ts`（新）、migrator、`ManagedRegistryService.ts`（新）、`ProviderService.ts`、`AgentService.ts`、`src/shared/data/presets/cherryai.ts`（保留但受管判定改走 registry）、seeder、迁移/单元测试
DoD：受管判定不再依赖 cherryai 硬编码；受管项不可改/删；现有 cherryai 行为不回归。
量化 AC：① managed_registry 含 cherryai 种子；② 改/删受管 provider → 抛 invalidOperation；③ 新增注册一个自定义受管 provider → 同样被保护；④ 非受管项不受影响；⑤ 全部现有 ProviderService/AgentService 测试通过。
依赖：F-1。
优先级：P0。

---

### F-9 热更新 IPC 刷新广播 ｜ 已实现-仅验证 ｜ P0
**现状**：✅ notifyDataApiDataChange 模板路径+entityIds；useProvider S3 订阅；S4 10 用例。
子任务：仅验证 + 随新路由扩展广播覆盖（F-4/F-5/F-6/F-7b 新写操作须按模板路径广播）。
文件：`src/main/features/apiGateway/adminRoutes.ts`（新写操作广播）、集成测试
DoD：所有 admin 写操作触发渲染层 useDataChange 订阅刷新。
量化 AC：新写操作均有对应广播断言；渲染 useProvider/useAgent 订阅收敛。
依赖：F-2、F-4、F-5、M0-1（已完成）。
优先级：P0。

---

### F-10 锁死 UI（源码级） ｜ 需补 ｜ P0
**现状**：cherryai 仅从列表隐藏；无删除按钮隐藏/受管项只读。
子任务：
1. 渲染层新增 `isManagedEntity`（读 managed_registry 判定或沿用 provider 元数据 managed 标记）。
2. ProviderSettings：受管 provider 隐藏删除按钮、禁用编辑表单（只读）。
3. Agent 设置：受管 agent 隐藏删除/编辑（若 F-4 暴露受管 agent）。
4. lock_rules：若受管 registry 带 lock_rules，UI 按规则隐藏/锁定（对齐 R5）。
文件：`src/renderer/utils/providerSettings.ts`（扩展）、ProviderSettings 组件、`src/renderer/pages/settings/AgentSettings/`（若存在）、组件测试
DoD：受管 provider/agent 在 UI 上不可删除、只读。
量化 AC：受管 provider 列表无删除按钮；表单字段禁用；手动调用删除 mutation 仍被服务端拒绝（F-8 兜底）。
依赖：F-8。
优先级：P0。

---

### F-11 禁用官方更新 ｜ 需补 ｜ P0
**现状**：feed = electron-builder.yml publish `url: https://releases.cherry-ai.com`；autoUpdate=`app.dist.auto_update.enabled`。
子任务：
1. 新增 `app.dist.auto_update.feed_url`（或 managed 专用 preference）接管 feed。
2. `AppUpdaterService.configureUpdaterForCheck()`：受管构建覆盖 feedURL 指向自建更新通道（electron-updater `setFeedURL` 或 publish url 改写）。
3. electron-builder.yml：受管构建用独立 publish 配置（或构建时注入），官方 feed 仅在非受管构建生效。
4. autoUpdate 开关 `app.dist.auto_update.enabled` 受管默认策略化（可强制关闭或指向自建通道）。
文件：`electron-builder.yml`、`src/main/services/AppUpdaterService.ts`、`src/shared/data/preference/preferenceSchemas.ts`（feed_url 键）
DoD：受管构建不再访问 releases.cherry-ai.com 官方 feed；更新走自建通道或按策略禁用。
量化 AC：受管构建 checkForUpdates 请求打到自建 feed URL（非 releases.cherry-ai.com）；preference 可关闭官方 autoUpdate。
依赖：F-1。
优先级：P0。

---

### F-12 Fork 分支收敛 ｜ 需补 ｜ P1
**现状**：无 official/main 镜像，无 rebase 流程。
子任务：
1. 落地 `official/main` 镜像 + `managed/main` rebase 流程（文档化 + 可脚本化）。
2. 官方更新 → 先 rebase official/main，再 rebase managed/main，冲突人工处理。
3. 受管改动保持为 managed 独有提交（不污染 official/main）。
文件：`docs/fork-branch-strategy.md`、`scripts/`（可选 sync 脚本）
DoD：官方更新可平滑 rebase 到 managed/main；受管改动与官方隔离。
量化 AC：官方 main 新提交 → rebase 后 managed/main 保留全部 M0/M1 提交且无回归测试失败。
依赖：F-1。
优先级：P1。

---

## 三、执行顺序（关键路径 → 依赖拓扑）

```
F-1(分支) ──▶ F-2(挂载,已做仅验证) ──▶ F-3(managed_key)
                │                        │
                ├──▶ F-4(agents CRUD) ───┤
                ├──▶ F-5(providers CRUD)─┤
                ├──▶ F-6(skills/mcp) ────┤
                ├──▶ F-7b(agent-files) ──┤
                ├──▶ F-7(usage,已做) ────┘
F-1 ──▶ F-8(受管保护) ──▶ F-10(锁UI)
F-1 ──▶ F-11(禁用官方更新)
F-1 ──▶ F-12(分支收敛)
F-4/F-5/F-6/F-7b 写操作 ──▶ F-9(热更新广播扩展)
```

**建议派发批次**：
- 批次 1（P0，串行/低冲突）：F-1 → F-3 → F-8 → F-10（分支 + key + 受管 + 锁 UI，强关联）
- 批次 2（P0，可并行）：F-4 / F-5 / F-7b / F-6（CRUD 补全，文件主要在 adminRoutes.ts → 需注意文件冲突矩阵：**多 Agent 同时改 adminRoutes.ts 必须串行**，建议合并为一个开发 Agent 完成全部 admin 路由补全）
- 批次 3（P0，验证）：F-2/F-7/F-9 复核 + F-11
- 批次 4（P1）：F-12

⚠️ **文件冲突预检**：F-4/F-5/F-6/F-7b 都改 `adminRoutes.ts` + `openapiDocs.ts` + `routes.integration.test.ts` → **必须同一 Agent 串行完成**，不可并行拆分。

---

## 四、NEEDS CLARIFICATION 清单（需老板确认）

以下无法从现有代码/文档推导，禁止猜测：

1. **F-3 独立管理 key 的授权边界**：`managed_key` 是否应同时允许访问普通 `/v1/*` 非 admin 路由？还是严格限定 `/v1/admin/*`？建议（供老板拍板）：严格限定 admin；普通 /v1 仍用 api_key。（权威定义 F-3 仅说「与普通 key 分离」，未明确边界）

2. **F-6 skills/mcp 是否需写能力**：权威定义 F-6 说「agentSkill 表 + mcpServer 表」管理路由。需确认：仅只读（供 Sidecar 拉取），还是含写（增删改 skill/mcp）？现有表无对应完整 CRUD Service（需核实），若含写须新建 Service。

3. **F-7b 「工作目录」精确定义**：是 Agent 数据目录（`Data/Agents/<id>`，含 SOUL.md/USER.md）还是 `agent_workspace` 表记录的路径？accessible_paths 的约束范围以哪个为准？（`agent_workspace` 表和 `agentDataDirectory` 是两套概念，须指定其一为权威。）

4. **F-8 managed_registry 表结构确认**：字段是否含 `lock_rules`（R5 提到 lock_rules）？是否需要一个管理端写入注册表的入口（还是 M2 Sidecar 通过 admin 路由注册）？M1 阶段 managed_registry 是否只需种子 + 只读，写由 M2 负责？

5. **F-11 自建更新通道 URL**：受管构建的自建 feed 服务器地址/通道名是哪个？还是 M1 先做「强制禁用官方 autoUpdate」即可（通道搭建归 M2）？

6. **F-1 官方分支同步频率**：official/main 镜像手动同步还是配 CI 自动同步？rebase 冲突策略（保留受管提交 vs 压缩）？

7. **真机实测范围**（无远程通道，SSH/RDP/SMB 全关，2334 服务端端口员工机不开）：以下需老板配合在真机验证——
   - F-9 热更新：admin 写 → 渲染 UI 即时刷新（本机可跑集成测试，但真机 UI 收敛需人工目视）
   - F-10 锁 UI：受管 provider 在真实渲染下的只读表现
   - F-11 禁用官方更新：受管构建包在真机的更新检查行为
   - F-3 managed_key：真实网关进程对双 key 的鉴权
   建议：M1 完成代码+单测+集成测试后，打包受管构建给老板真机实测（对照 M0 收尾模式：代码验证 + 数据验证并入 M2）。

---

## 五、文件清单（本次产出）

- `m1-plan.md`（本计划，写入 `/home/chee/Projects/oc-macs/specs/CherryStudio企业受管版v4.0/`）
- 军师原始输出：`/home/chee/.openclaw/workspace-guihua/output/m1-plan.md`（副本）

files_touched（本 Agent，仅读+写计划，未改项目代码）：
- 读：`cherry-src` 下 adminRoutes.ts / app.ts / middleware/auth.ts / ProviderService.ts / AgentService.ts / useProvider.ts / providerSettings.ts / AppUpdaterService.ts / electron-builder.yml / preferenceSchemas.ts / cherryai.ts / agentDataDirectory.ts / agentWorkspace.ts / agentSkill.ts / mcpServer.ts / routes.integration.test.ts / git branch/log
- 创建：`/home/chee/Projects/oc-macs/specs/CherryStudio企业受管版v4.0/m1-plan.md`
- 创建：`/home/chee/.openclaw/workspace-guihua/output/m1-plan.md`

---

## 六、自检结果

- ✅ 每个 F 项现状均实读代码核实，非记忆推定（证据路径标注在 1.x）
- ✅ 无静默假设：无法推导处全部列入 NEEDS CLARIFICATION（第四节 7 项）
- ✅ 无过度工程：M1 只列 F-1~F-12 必需改动，未顺手重构
- ✅ 无链式幻觉：每项结论均引用实读文件
- ✅ 文件冲突矩阵已预检（adminRoutes.ts 多 F 项冲突 → 建议串行单 Agent）
- ✅ 量化 AC 覆盖每项 DoD

## 七、已知限制与风险

1. F-6 若含写能力，需确认/新建 Service，工作量大（M1 范围可能膨胀）→ 建议 M1 先只读，写归 M2。
2. F-7b 的「工作目录」权威定义不清 → 阻塞实现，须老板澄清（澄清项 3）。
3. F-8 managed_registry 迁移涉及既有 cherryai 种子回归 → 需保住现 ProviderService 测试不破。
4. F-11 无自建通道 URL → 若老板选择「先禁用」，M1 可降级实现；若需接通道，阻塞（澄清项 5）。
5. 真机 UI 验证（F-9/F-10/F-11）需老板配合，M1 只能交付代码+自动化测试，数据验证并入 M2（同 M0 收尾模式）。
6. 分支 rebase（F-1/F-12）需在干净工作区执行，避免与开发中提交冲突 → 建议 F-1 最先做，后续 F 项在 rebase 后分支上开发。