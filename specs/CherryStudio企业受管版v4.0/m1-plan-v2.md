# M1 执行计划 v2 · CherryStudio 受管版 Fork 层完整实现（F1-F12）

> 修订版 | JJC-20260811-001
> 修订依据：审计官（shenyi）独立审议 REJECT 结论（F-8 架构矛盾 / F-6 现状不完整 / F-3 缺约束）
> 原始版：`m1-plan.md`（军师，2026-08-11 14:46，25KB）
> 修订说明：本 v2 回应审计官三点驳回，其余内容沿用原始版（现状核实经审计官独立复核一致，可信）
> 前置：M0 收尾已收口（commit 4aa345b；cherry-src HEAD = 963897128）

---

## 〇、修订摘要（审计官三点驳回如何改）

| 驳回点 | 严重度 | 原始版问题 | v2 修订 |
|--------|--------|-----------|---------|
| 1. F-8 managed_registry 架构矛盾 | 🔴 致命 | 做成主 cherrystudio.sqlite 新表 + drizzle 迁移（migrator），违背 v4.0「旁路表独立 db、Sidecar 唯一写者、不动官方 schema、无迁移锁库风险」的权威定义 | **上升为 NEEDS CLARIFICATION，交老板拍板 (a)/(b)，不擅自选边**。见 §F-8 与 §四-澄清项 |
| 2. F-6 现状核实不完整 | 🟡 中 | 写「Service 待确认，无则新建」，把 F-6 工作量大化 | 确认 `McpServerService` + `AgentGlobalSkillService`（均全 CRUD）**已存在**，复用现有 Service，**只补 admin 只读路由**，删除「新建 Service」分支 |
| 3. F-3 缺 Bearer-only 约束 | 🟡 中 | 未引用 M0-1 已确立的约束 | 补充：admin 路由**只认 `Authorization: Bearer`，不认 `x-api-key`**（x-api-key→403，Bearer→200），写入 F-3 实现约束 |

**审计官确认项（v2 沿用，无需改）**：F-1~F-12 现状核实全部准确；F-7b 工作目录澄清必要性成立（workspace 是 session 路径模型，非简单 Data/Agents/<id>）。

---

## 一、现状核实总表（实读代码，审计官独立复核一致）

| F | 任务 | 现状 | 判定 |
|---|------|------|------|
| F-1 | 官方最新镜像 + Fork 分支 | `managed/main` 基于 `origin/main`@12498d68e；**无 official/main 镜像** | 半成品-需对齐 |
| F-2 | /v1/admin/* 挂载 | ✅ app.ts 已挂 v1Routes scoped guard 链尾 | 【已实现-仅验证】 |
| F-3 | 独立管理 key | ❌ 无 managed_key；auth 仅比对 api_key | 【需补】 |
| F-4 | agents CRUD | 半成品：POST/PUT 有；缺 list/get/delete/reorder | 【需补】 |
| F-5 | providers CRUD | 半成品：GET/POST/PUT+api-keys 有；缺 delete/batchUpsert/addApiKey | 【需补】 |
| F-6 | skills/mcp 路由 | ❌ 无路由；**但 McpServerService + AgentGlobalSkillService（全 CRUD）已存在** | 【需补，复用 Service】 |
| F-7 | usage 路由 | ✅ GET /usage 已有 | 【已实现-仅验证】 |
| F-7b | agent-files 采集 | ❌ 无路由；agentDataDirectory.ts + agent_workspace + accessible_paths 在 | 【需补】 |
| F-8 | 泛化受管保护 | ❌ 硬编码 cherryai 特判；全库无 managed_registry | 【需补+架构澄清】 |
| F-9 | 热更新广播 | ✅ notifyDataApiDataChange + useDataChange 订阅 | 【已实现-仅验证】 |
| F-10 | 锁死 UI | ❌ cherryai 仅列表隐藏；无删除隐藏/只读 | 【需补】 |
| F-11 | 禁用官方更新 | ❌ feed=releases.cherry-ai.com；无 managed 接管 | 【需补】 |
| F-12 | Fork 分支收敛 | ❌ 无 official/main 镜像，无 rebase 流程 | 【需补】 |

---

## 二、关键修订项（审计官驳回的三处）

### F-3 独立管理 key ｜ 需补 ｜ P0（修订：补 Bearer-only 约束）

**现状**：无 `feature.api_gateway.managed_key`；auth 仅比对 api_key。
**关键实现约束（M0-1 已实测确立）**：admin 路由**只认 `Authorization: Bearer` 头，不认 `x-api-key` 头**（x-api-key→403，Bearer→200）。F-3 实现必须保持此约束——managed_key 校验走 Bearer 头，与普通 key 走同一鉴权机制但比对不同值。

子任务：
1. `preferenceSchemas.ts` 增加 `feature.api_gateway.managed_key: string | null`（+默认 null）+ `preferenceTypes.ts` 类型同步。
2. `auth.ts`：`authorizeApiRequest` 增加 managed 判定——`/v1/admin/*` 路径要求 token 命中 `managed_key`；普通 `/v1/*` 仍用 `api_key`。**鉴权统一用 Bearer 头解析，不新增 x-api-key 分支**（维持 M0-1 约束）。
3. `openapiDocs.ts`/集成测试补充 managed_key 授权用例。

文件：`preferenceSchemas.ts`、`preferenceTypes.ts`、`middleware/auth.ts`、`app.ts`、`routes.integration.test.ts`
DoD：admin 路由仅接受 managed_key；普通 /v1 不受影响；两 key 独立；**Bearer-only 约束保持**。
量化 AC：① api_key 访问 `/v1/admin/*` → 403；② managed_key 访问 `/v1/admin/*` → 200；③ managed_key 访问 `/v1/models` → 403；④ 未配 managed_key 时 admin 拒绝；⑤ x-api-key 头访问 admin → 403（Bearer-only 回归断言）。
依赖：F-2。

### F-6 skills/mcp 管理路由 ｜ 需补 ｜ P1（修订：复用现有 Service，删新建分支）

**现状**：无 admin 路由。**Service 已确认存在（实读）**：
- `McpServerService.ts`：全 CRUD `getById/list/create/createMany/update/delete/reorder`
- `AgentGlobalSkillService.ts`：全 CRUD `getById/list/listAll/insert/update/deleteById` + join ops

子任务（**删除原始版「确认有无 Service、无则新建」分支**）：
1. 直接复用现有 `McpServerService` / `AgentGlobalSkillService`，不新建 Service。
2. adminRoutes 增 `GET /skills`、`GET /mcp`、`GET /mcp/:id`（只读，供 Sidecar 拉取）。写操作（增删改 skill/mcp）M1 不做，归 M2（经 admin 路由或直接写 registry）。

文件：`adminRoutes.ts`、`openapiDocs.ts`、集成测试
DoD：skills/mcp 可经 admin 只读；复用现有 Service。
量化 AC：GET /skills、GET /mcp、GET /mcp/:id 均 200 且返回表数据；不新建 Service。
依赖：F-2。

### F-8 泛化受管保护 ｜ 需补 ｜ P0（修订：架构矛盾上升为 NEEDS CLARIFICATION）

**现状**：硬编码 `cherryai` 特判（ProviderService），全库无 managed_registry。
**🔴 架构矛盾（审计官驳回点 1，致命）**：权威 v4.0 方案三处重复明示（§2.2 L136 / §3.5 L201 / §6.3 L380-381 / D20 L470-478）：
> 「受管标记旁路表 | 本地 `managed_registry.db`（sqlite），**Sidecar 唯一写者** | 记录 id→managed 映射；**不动官方 schema，无迁移锁库风险**」

原始版 F-8 把 managed_registry 做成**主 cherrystudio.sqlite 新表 + drizzle 迁移**——重新引入 v4.0 刻意规避的迁移/锁库风险，且写所有权（M1 无 Sidecar 时谁写）、F-10 渲染层读路径未闭环。**此架构变更未经老板拍板，不得擅自选边，必须上升为 NEEDS CLARIFICATION（§四-澄清项 4'）交老板裁决。**

**修订后的 F-8 待老板拍板二选一**：
- **(a) 遵循 v4.0（推荐）**：managed_registry 独立 `managed_registry.db`（sqlite），Sidecar 唯一写者；Fork 层 `ManagedRegistryService` 只读该独立 db（设计跨 db 读路径）；F-10 渲染层经 preload IPC 桥读。
- **(b) 改主库**：须先经权威定义（方案 v4.0）修订；明确 M1 写者（无 Sidecar 时谁写）、渲染层读路径、迁移与 cherryai 种子回归方案。

**M1 阶段最小落地（待老板选 (a)/(b) 后细化）**：
- 受管判定从硬编码 `cherryai` 特判，改为经 `ManagedRegistryService.isManaged(...)` 判定。
- 既有 cherryai 作为 registry 首条种子（保持现行为不回归）。
- 受管 provider/agent 不可改/删（抛 invalidOperation）。

文件：视老板选 (a)/(b) 而定——(a) 新增 `managedRegistry.ts`（独立 db）+ `ManagedRegistryService.ts`（只读）+ preload IPC 桥；(b) 主库 schema + migrator + 迁移/种子回归。
DoD：受管判定不再依赖 cherryai 硬编码；受管项不可改/删；现有 cherryai 行为不回归。
量化 AC：① registry 含 cherryai 种子；② 改/删受管 provider → invalidOperation；③ 新增自定义受管 provider 同样被保护；④ 非受管项不受影响；⑤ 现有 ProviderService/AgentService 测试全过。
依赖：F-1 + **老板澄清项 4'（选 (a)/(b)）**。

---

## 三、其余 F 项（沿用原始版，审计官确认无误）

> F-1、F-2、F-4、F-5、F-7、F-7b、F-9、F-10、F-11、F-12 内容与原始版 `m1-plan.md` 一致，仅 F-8 依赖老板澄清、F-10 依赖 F-8 决策后落地。此处不再重复全文，以原始版为准。

**关键点回顾**：
- F-4/F-5：AgentService/ProviderService 已具备底层方法（listAgents/getAgent/deleteAgent/reorder / delete/batchUpsert/addApiKey），adminRoutes 补全 CRUD + 广播。
- F-7b：复用 `assertAgentStoragePath`（防 symlink 逃逸）+ `isPathWithinAccessiblePath`；「工作目录」权威定义见澄清项 3。
- F-11：`app.dist.auto_update.feed_url` 接管 feed 或受管强制禁用，不再访问 releases.cherry-ai.com。
- F-9：所有 admin 新写操作按模板路径广播（对齐 S2 约定）。

---

## 四、NEEDS CLARIFICATION 清单（需老板确认，7+1 项）

> 4' 为审计官驳回新增，其余沿用原始版。

1. **F-3 授权边界**：managed_key 是否严格限定 `/v1/admin/*`？（建议：严格限定；普通 /v1 仍用 api_key）
2. **F-6 是否需写能力**：M1 只读（推荐，供 Sidecar 拉取）；写归 M2。
3. **F-7b 工作目录定义**：Agent 数据目录（Data/Agents/<id>）还是 agent_workspace 表路径？审计官确认 workspace 是 session 路径模型（buildSystemWorkspacePath / listAgentSessionWorkspacePaths），非简单 Data/Agents/<id>，此澄清必要且非平凡。
4. **F-8 表结构**：是否含 lock_rules？管理端写入口归 M2？（M1 建议种子 + 只读）
4'. **🔴 F-8 架构选型（审计官新增，必须 M1 前拍板）**：managed_registry 放**独立 db（方案 (a)，遵循 v4.0）**还是**主库（方案 (b)，需先改权威定义）**？这是 M1 F-8/F-10 的落地前提。
5. **F-11 自建通道 URL**：有自建 feed 服务器地址，还是 M1 先「强制禁用官方 autoUpdate」（推荐，通道搭建归 M2）？
6. **F-1 分支同步**：official/main 手动同步还是 CI 自动？rebase 冲突策略？
7. **真机实测范围**：无远程通道（SSH/RDP/SMB 全关，2334 员工机不开），M1 交付代码+单测+集成测试，真机 UI 验证并入 M2（同 M0 收尾模式）。

---

## 五、执行批次与文件冲突

**派发批次**（沿用原始版，审计官确认合理）：
- 批次 1（P0 串行）：F-1 → F-3 → F-8 → F-10（分支 + key + 受管 + 锁 UI）
- 批次 2（P0，**同一 Agent 串行**）：F-4 / F-5 / F-6 / F-7b（都改 adminRoutes.ts + openapiDocs.ts + 集成测试，冲突矩阵禁止并行）
- 批次 3（P0 验证）：F-2 / F-7 / F-9 复核 + F-11
- 批次 4（P1）：F-12

⚠️ **F-8 阻塞批次 1**：批次 1 中 F-8/F-10 依赖澄清项 4'（老板选 (a)/(b)）。老板拍板前，批次 1 可先做 F-1 + F-3（不依赖 F-8）。

---

## 六、风险（原始版 5 项 + 修订新增）

1. F-8 架构未拍板 → 阻塞 F-8/F-10（修订后已上升澄清，不再静默假设）
2. F-7b 工作目录定义不清 → 阻塞实现，须澄清（澄清项 3）
3. F-8 迁移涉及 cherryai 种子回归 → 若选 (b) 主库需保测试；选 (a) 独立 db 无迁移锁库风险
4. F-11 无自建通道 → 推荐 M1 先禁用（降级实现）
5. 真机 UI 验证需老板配合 → M1 交付代码+自动化测试，数据验证并入 M2

---

## 七、自检结果

- ✅ 现状核实实读代码（审计官独立复核一致）
- ✅ 审计官三点驳回全部响应（F-8 上升澄清 / F-6 复用 Service / F-3 补 Bearer 约束）
- ✅ 无静默假设：F-8 架构矛盾不擅自选边，交老板拍板
- ✅ 无过度工程：M1 只列 F-1~F-12 必需改动
- ✅ 文件冲突矩阵已预检（adminRoutes.ts 多 F 项 → 串行单 Agent）
- ✅ 量化 AC 覆盖每项 DoD

---

## 八、文件清单

- 本修订版：`m1-plan-v2.md`（写入 `/home/chee/Projects/oc-macs/specs/CherryStudio企业受管版v4.0/`）
- 原始版：`m1-plan.md`（保留，审计官已复核）
- 未改任何项目代码（cherry-src）
