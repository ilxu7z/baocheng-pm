# JJC-20260810-003 · M0收尾：扩展admin路由 + 一次实测（provider/key/usage热更新）

> **审计修正（shenyi 复审 2026-08-10，详见 m0-close-audit.md）**：① S2/S4 代码已提交 commit `0ef01567f`（adminRoutes.ts 已 265 行），S2/S4 由「待做」改为「已提交待对齐」；②【必须修正】key 写通知只广播 /providers，需补广播详情端点 /providers/:providerId/api-keys + /providers/:providerId，否则详情页/api-keys 面板无法热刷新；③ S3 是唯一硬缺口（useProvider.ts 无订阅）。

> 产出者：军师 guihua | 日期：2026-08-10 | 状态：待拆解执行
> 任务：把 M0-1 的最小 admin 路由（仅 `PUT /admin/agents/:id`）扩展到 **provider / key / usage** 三类，并完成一次实测验证「改后 UI 即时刷新、不重启」。
> 性质：M0 收尾。本计划基于**实际读源码**产出，不是重写方案；凡需核实处已先读代码。

---

## 〇、已核实的源码事实（本计划全部技术地基，先于任何结论）

### 0.1 现状代码（已读）
| 项 | 源码位置 | 现状 |
|----|---------|------|
| admin 路由 | `src/main/features/apiGateway/adminRoutes.ts`（85行） | 仅 `PUT /admin/agents/:id`，prefix='/admin'，走 `AgentService.updateAgent`，写后 `notifyDataApiDataChange([{endpoint:'/agents',kind:'projection'}])` |
| 挂载 | `src/main/features/apiGateway/app.ts` | `v1Routes` 链尾 `.use(adminRoutes)`，继承 `scoped` bearer/x-api-key 鉴权 |
| 鉴权 | `src/main/features/apiGateway/middleware/auth.ts` | `authorizeApiRequest`，key 错→403，路由不存在→404 |
| 通知机制 | `src/main/data/dataApiDataChange.ts` | `notifyDataApiDataChange()` → `DataApi_DataChanged` IPC → 渲染 `useDataChange`；commit 后才发，失败不影响写入 |
| Agent 热更新 | `src/renderer/hooks/agent/useAgent.ts` | **已订阅** `useDataChange('/agents', () => refetch())`（M0-1 已加） |
| Usage 热更新 | `src/renderer/pages/settings/UsageSettings/useUsageData.ts` | **已订阅** `useDataChange(['/ai-usage-records','/ai-usage-records/stats','/ai-usage-records/timeline'], refreshUsageReadModels)` |
| Usage 写通知 | `src/main/data/services/AiUsageRecordService.ts` | `recordInvocations` 已发 `AI_USAGE_RECORD_READ_MODEL_CHANGES`（含上述3个endpoint） |
| Provider 官方写路径 | `src/main/data/api/handlers/providers.ts` + `ProviderService.ts` | 见 §0.3 |

### 0.2 关键差异：Agent 热更新 OK，**Provider/Key 热更新缺失（本次核心工程点）**
- **渲染层 provider 读取用的是 SWR `useQuery`，不是 `useDataChange`**：
  - `src/renderer/hooks/useProvider.ts`：`useQuery('/providers')`、`useQuery('/providers/:providerId')`、`useQuery('/providers/:providerId/api-keys')`。
  - **全代码库没有任何 `useDataChange('/providers', ...)` 订阅**（grep 为空）。
- **SWR 全局配置 `revalidateOnFocus: false`**（`src/renderer/data/hooks/useDataApi.ts:80`）→ 窗口聚焦也不会重取。
- Provider 设置页只有 `revalidateOnMount: true`（`ProviderSettings/hooks/providerSetting/constants.ts`）+ 本地 mutation 的 `refresh` 数组。
- **结论**：外部 admin 写 provider/key 后，**已打开的设置页/模型下拉不会自动刷新**——这是与 Agent 的本质差别。要实现「改后 UI 即时刷新不重启」，**必须在 provider 层补 `useDataChange` 订阅**（镜像 useAgent.ts 的做法）。这是 003 最重要的工程决策。

### 0.3 Provider/Key 官方写路径（admin 路由复用，不直写 sqlite —— D20）
| 资源 | 官方端点 | 走 Service 方法 |
|------|---------|----------------|
| provider 列表 | GET `/providers` | `providerService.list` |
| provider 创建 | POST `/providers` | `providerService.create` |
| provider 更新 | PATCH `/providers/:providerId` | `providerService.update` |
| provider 删除 | DELETE `/providers/:providerId` | `providerService.delete` |
| key 列表 | GET `/providers/:providerId/api-keys` | `providerService.getApiKeys` |
| key 新增 | POST `/providers/:providerId/api-keys` | `providerService.addApiKey` |
| key 整体替换 | PUT `/providers/:providerId/api-keys` | `providerService.replaceApiKeys` |
| key 单条改 | PATCH `/providers/:providerId/api-keys/:keyId` | `providerService.updateApiKey` |
| key 单条删 | DELETE `/providers/:providerId/api-keys/:keyId` | `providerService.deleteApiKey` |
| auth-config | GET `/providers/:providerId/auth-config` | `providerService.getAuthConfig` |
| preset | GET `/providers/:providerId/preset` | `providerService.getByProviderId` + registry |
| 排序 | PATCH `/providers/:id/order`、`/providers/order:batch` | `providerService.move` / `reorder` |

### 0.4 Usage 本质：只读统计
- `ai_usage_record` 由 `AiUsageRecordService.recordInvocations`（真实 AI 调用）写入，**不是 admin CRUD 写的**。
- 渲染层 usage 页已经订阅官方通知，**usage 的「热更新」官方已原生打通**。
- admin 对 usage 的角色 = **只读 GET**（读统计），读操作无需通知（无写入）。

### 0.5 M0-1 状态核实（关键）
- **代码已交付**：commit `2f0dda5f2` = 3 文件（adminRoutes.ts 新建 / app.ts +4行 / useAgent.ts +3行），已提交已 push。M0-2 出包成功（CI 31363847257，SHA a4d335dc）。
- **本地集成测试通过**：routes.integration.test.ts 证实 `PUT /v1/admin/agents/:id` 无 key→401、key 错→403（路由已注册+鉴权正常）。
- **⚠️ V-M0-1 真机热更新①（改 Agent 名/提示词→UI 即时刷新不重启）尚未完成**：卡在「真实完整 API key（脱敏）+ m0test 的 id（需按 CreationTime 找最新 Agents 目录）」。见 memory/2026-08-10.md「M0-1 实测卡点（未完成）」。
- **→ 003 的「一次实测」必须包含补完 V-M0-1 ①**（agent 热更新真机验证），然后才是 provider/key/usage 三类。

### 0.6 计划文档 vs 现实差异（需向老板/审计官指出）
- plan-m0.md §B10 写「渲染层用 TanStack Query + invalidateQueries」，**实际是 SWR + useDataChange 广播**。M0-1 已正确用 useDataChange。后续 M0-4 的「UI 刷新」判据应基于 useDataChange，不是 invalidateQueries。

---

## 一、执行计划总览（子任务 + 优先级）

| # | 子任务 | 优先级 | 是否阻塞门禁 |
|---|--------|--------|------------|
| S1 | 补完 V-M0-1 ① agent 真机热更新（卡点解） | 🔴 最高 | 是（V-M0-1 门禁） |
| S2 | 扩展 admin 路由：provider + key | 🔴 高 | 是（003 核心交付） |
| S3 | 补 provider/key 渲染层 `useDataChange` 订阅（热更新打通） | 🔴 高 | 是（否则「UI即时刷新」判据不成立） |
| S4 | 扩展 admin 路由：usage 只读 GET | 🟡 中 | 否（S-6/D-6 依赖，非门禁） |
| S5 | 一次实测：真机 188/17 三类热更新 | 🔴 高 | 是（003 验收核心） |
| S6 | 验收 + 看板推进 + 文档更新 | 🟡 中 | 否 |

依赖：S1（真机环境就绪）→ S2/S3（代码）+ S5（实测）→ S6（验收）。

---

## 二、子任务详情

### S1 · 补完 V-M0-1 ①（agent 真机热更新）— 🔴 最高
**范围**：把 2026-08-10 卡点解掉，完成 agent 热更新真机验证。
**卡点与解法**：
1. **真实完整 API key**：`Y:\Chee\OpenClaw_C\基建\cherry-managed\APIkey.txt` 被 OpenClaw 脱敏（`cs-sk-366…5c93`）。需老板**手动完整复制**，若仍被脱敏，**拆两段/中间插空格**发送，我拼接还原。
2. **m0test id**：`Data\Agents\` 下多个 uuid 目录，agent id = 目录名。老板在 17 号机 PowerShell 跑：
   ```powershell
   Get-ChildItem "C:\Users\Administrator\AppData\Roaming\CherryStudio\Data\Agents" | Select-Object Name, CreationTime, LastWriteTime | Sort-Object CreationTime -Descending
   ```
   取 CreationTime 最新目录 = m0test id。
3. **执行 PUT**（改名字，如 `-backend-${timestamp}` 标记）→ 观察 **UI 不重启即时刷新**。
   ```bash
   curl -s -X PUT http://192.168.3.17:23333/v1/admin/agents/{m0test_id} \
     -H "x-api-key: {真实key}" -H 'Content-Type: application/json' \
     -d '{"name":"m0test-ok-0810"}'
   ```
**DoD**：① 返回 200 + 新 name；② 17 号机 UI 上 agent 名称**不重启**即变为新值。
**可量化 AC**：
- AC1：PUT 返回 200，body.name = 新值，updatedAt 更新。
- AC2：UI 上 agent 名 10 秒内刷新为新值，**无重启**（进程 PID 不变 / 无重新加载窗口）。
**优先级**：🔴 最高。**这是 V-M0-1 门禁，红则阻塞 M1**（方案 13.1）。
**老板配合点**：完整 key（拆段防脱敏）+ 跑 Agents 目录列表命令 + 观察 UI 刷新。

---

### S2 · 扩展 admin 路由：provider + key — 🔴 高
**范围**：在 `adminRoutes.ts` 新增 provider / key 两组 admin 路由，复用官方 Service（D20，不直写 sqlite），鉴权继承 scoped bearer。
**涉及文件**：`src/main/features/apiGateway/adminRoutes.ts`（主改动）、`src/main/features/apiGateway/app.ts`（无改动，路由已挂）。

**路由设计（复用官方 Service，端点前缀 `/admin`）**：

**Provider（V-M0-1 ②：派发 provider → 模型下拉即时可选）**
| 方法 | 端点 | 走 Service | 热更新通知 |
|------|------|-----------|-----------|
| POST | `/admin/providers` | `providerService.create` | 见 §三 |
| PUT | `/admin/providers/:providerId` | `providerService.update` | 见 §三 |
| DELETE | `/admin/providers/:providerId` | `providerService.delete` | 见 §三 |
| GET | `/admin/providers` | `providerService.list` | —（读无需通知） |

**Key（V-M0-1 ③：停 key 重建推新 key → 受管 provider 生效）**
| 方法 | 端点 | 走 Service | 热更新通知 |
|------|------|-----------|-----------|
| POST | `/admin/providers/:providerId/api-keys` | `providerService.addApiKey` | 见 §三 |
| PUT | `/admin/providers/:providerId/api-keys` | `providerService.replaceApiKeys` | 见 §三 |
| DELETE | `/admin/providers/:providerId/api-keys/:keyId` | `providerService.deleteApiKey` | 见 §三 |
| GET | `/admin/providers/:providerId/api-keys` | `providerService.getApiKeys` | — |

**写入模式（每路由统一骨架，镜像现有 PUT /agents/:id）**：
1. zod `safeParse` body → 失败 400。
2. 调官方 Service 方法（不直写 sqlite）。
3. Service 抛 notFound → 404；conflict → 409（复用 DataApiErrorFactory 语义）。
4. **写入 commit 成功后**（Service 返回后）调 `notifyDataApiDataChange([...])`（见 §三）。
5. 返回镜像官方响应 shape。

**DoD**：provider/key 的 create/update/delete 走 Service 写库成功，返回正确状态码，写后发通知。
**可量化 AC**：
- AC1：POST/PUT/DELETE 各返回正确状态码（200/201/404/409/400），错误 envelope 与现有路由一致。
- AC2：写库后 sqlite `user_provider` 表/`api_keys` 生效（走 Service，无绕过 D20）。
- AC3：写后调用 `notifyDataApiDataChange`（endpoint/kind 见 §三）。
- AC4：本地集成测试（见 S6）覆盖以上路由注册 + 鉴权 + 状态码。
**优先级**：🔴 高。

---

### S3 · 补 provider/key 渲染层 `useDataChange` 订阅（热更新打通）— 🔴 高
**范围**：让「改后 UI 即时刷新」对 provider/key 成立（当前缺失，见 §0.2）。
**涉及文件**：`src/renderer/hooks/useProvider.ts`（主改动）。

**做法**：在 provider 数据 hook 层补 `useDataChange` 订阅，镜像 useAgent.ts：
```ts
// useProviders 内
useDataChange(['/providers', '/providers/:providerId', '/providers/:providerId/api-keys'], () => refetch())
```
以及 `useProviderById` / `useProviderApiKeys` 内按需补对应 endpoint 订阅，或聚合到一个共享订阅点（在组件生命周期内持有）。**关键：endpoint 名必须与通知发送的 endpoint 精确一致**（DataApiDataChangeEffect 匹配规则）。

**注意**：`useDataChange` 的 endpoints 参数类型是 `GetMethodApiPaths`；`/providers`、`/providers/:providerId`、`/providers/:providerId/api-keys` 均为合法 GET path（schema 已定义），可编译。

**DoD**：外部 admin 写 provider/key 后，已打开的 provider 设置页/模型下拉**不重启**即时刷新。
**可量化 AC**：
- AC1：`useProvider.ts` 出现 `useDataChange('/providers', ...)`（或等价聚合订阅），endpoint 与 S2 通知一致。
- AC2：renderer 侧现有 `useProvider` 相关测试不回归（`useProvider.test.ts`）。
- AC3：真机实测（S5）②③ 通过。
**优先级**：🔴 高。**没有 S3，S5 的「UI 即时刷新」判据对 provider/key 必然失败。**

---

### S4 · 扩展 admin 路由：usage 只读 GET — 🟡 中
**范围**：读 `ai_usage_record`（模型+token 用量），为 S-6/D-6 铺路（M0-5，非门禁）。
**涉及文件**：`src/main/features/apiGateway/adminRoutes.ts`、`src/main/data/services/AiUsageRecordService.ts`（只读复用 `list`）。

**路由**：
| 方法 | 端点 | 走 Service | 说明 |
|------|------|-----------|------|
| GET | `/admin/usage` | `aiUsageRecordService.list` | `?from=&to=&device_id=` 过滤，字段映射 providerId/modelId/inputTokens/outputTokens/totalTokens/sourceType（SDD 4.2） |

**热更新通知**：**usage 只读，无需通知**。渲染层 usage 页已原生订阅官方 `AI_USAGE_RECORD_READ_MODEL_CHANGES`；admin 只读不产生写入，故不发通知（§0.4）。

**DoD**：GET `/admin/usage` 返回 200 + 字段完整。
**可量化 AC**：
- AC1：GET 返回 200，含 providerId/modelId/inputTokens/outputTokens/totalTokens/sourceType。
- AC2：读出的模型+token 与测试机实际调用一致。
- AC3：只读，无写锁风险（走 Service/drizzle 查询）。
**优先级**：🟡 中（非门禁，但属 M0 收尾完整交付）。

---

### S5 · 一次实测：真机三类热更新 — 🔴 高
**范围**：在 17（192.168.3.17）/188（192.168.3.188）真机验证 agent/provider/key/usage 热更新。**需老板配合**（无法远程控制 17 号机，见 memory）。

**实测步骤**（每类：改 → 观察 UI 不重启刷新）：
| 类 | 操作 | 判据 |
|----|------|------|
| ① Agent | `PUT /admin/agents/:id` 改名字 | UI agent 名不重启即时更新 |
| ② Provider | `POST /admin/providers` 派发 / `PUT` 改 enabled | 模型下拉即时可选（不重启） |
| ③ Key | `POST /admin/providers/:id/api-keys` 推新 key | 受管 provider 立即生效（不重启） |
| ④ Usage | 造一次 AI 调用 → `GET /admin/usage` | 读出模型+token，UI usage 页刷新 |

**本地集成测试（无需真机，先行）**：在 Linux 跑 `routes.integration.test.ts` 扩展用例，验证 provider/key/usage 路由注册 + 鉴权 + 状态码。这是 S5 真机前的必要前置。

**DoD**：①②③ 全绿（方案 13.1 V-M0-1），④ 可读。
**可量化 AC**：
- AC1：① agent 改名 → UI 10 秒内刷新，无重启。
- AC2：② provider 派发 → 模型下拉即时可选，无重启。
- AC3：③ replaceApiKeys 推新 key → 受管 provider 立即生效，无重启。
- AC4：④ GET /admin/usage 字段完整。
**老板配合点**：完整 key + 观察 UI + 真机执行（我无法远程 17 号机）。**任一红 → 按方案 5.3 降级方案 C（强制重启兜底）重评**。
**优先级**：🔴 高。

---

### S6 · 验收 + 看板推进 + 文档更新 — 🟡 中
**范围**：品控官 shencha 复核，看板 advance-state 推进，更新 plan-m0/记忆。
**涉及**：看板 API（`POST /api/advance-state`）、`memory/2026-08-10.md`、plan-m0.md（补 003 结果 + 修正 §B10 SWR 差异）。
**DoD**：V-M0-1~V-M0-5 中 ①②③④ 验收结论落档。
**优先级**：🟡 中。

---

## 三、热更新通知映射（本次核心设计决策）

| 写操作 | 通知 endpoint/kind | 依据 |
|--------|-------------------|------|
| Agent 改名/提示词 | `[{endpoint:'/agents', kind:'projection'}]` | M0-1 已实现；useAgent.ts 订阅 `/agents` |
| Provider 增/改/删 | `[{endpoint:'/providers', kind:'projection'}]` + 若需按 id 细分加 `{endpoint:'/providers/:providerId'}` | **需 S3 补渲染订阅**（当前缺失） |
| Key 增/改/删 | `[{endpoint:'/providers/:providerId/api-keys', kind:'projection'}]` + `{endpoint:'/providers/:providerId'}` | 需 S3 补渲染订阅 |
| Usage | **不发通知**（只读，官方 recordInvocations 已发原生通知） | §0.4 |

**匹配规则提醒**：`notifyDataApiDataChange` 的 effect endpoint 必须与渲染层 `useDataChange` 订阅的 endpoint **字面一致**（模板路径）。因此 S2 通知的 endpoint 与 S3 订阅的 endpoint 必须同一份定义，避免「通知发了 UI 不认」。

---

## 四、涉及文件清单（改动点汇总）

| 文件 | 改动点 | 子任务 |
|------|--------|--------|
| `src/main/features/apiGateway/adminRoutes.ts` | 新增 provider/key/usage 路由（S2+S4）；统一骨架 | S2,S4 |
| `src/main/features/apiGateway/app.ts` | 无改动（adminRoutes 已挂 v1Routes 链尾） | — |
| `src/renderer/hooks/useProvider.ts` | 补 `useDataChange('/providers'...` 订阅（S3） | S3 |
| `src/main/features/apiGateway/routes/__tests__/routes.integration.test.ts` | 新增 provider/key/usage 路由注册+鉴权+状态码用例 | S5,S6 |
| `src/renderer/hooks/__tests__/useProvider.test.ts` | S3 改动不回归确认 | S3 |
| `memory/2026-08-10.md` | 补 S1 结果 + 003 结论 | S6 |
| `/mnt/chee_2/.../docs/plan-m0.md` | 补 003 结果 + 修正 §B10 SWR 差异 | S6 |

---

## 五、DoD（整体）+ 可量化 AC（汇总）

**整体 DoD**：admin 路由覆盖 provider/key/usage 三类；provider/key 改后 UI 即时刷新不重启（S3 打通）；一次真机实测 V-M0-1 ① + ②③④ 全绿。

**量化 AC（验收判据）**：
- A1：`PUT /admin/agents/:id`（V-M0-1 ①）真机 200 + UI 不重启刷新。（S1）
- A2：provider/key/usage admin 路由本地集成测试通过（注册+鉴权+状态码）。（S5）
- A3：`POST /admin/providers` 派发 → 模型下拉即时可选（不重启）。（S5 ②）
- A4：`POST /admin/providers/:id/api-keys` 推新 key → 受管 provider 立即生效（不重启）。（S5 ③）
- A5：`GET /admin/usage` 字段完整（providerId/modelId/input/output/totalTokens/sourceType）。（S5 ④）
- A6：provider 渲染层 `useDataChange('/providers'...)` 存在且不回归现有测试。（S3）
- A7：走 Service 不直写 sqlite（D20），代码审查通过。（S2/S4）

---

## 六、风险与对策

| 风险 | 等级 | 对策 |
|------|------|------|
| **Provider/Key UI 不刷新**（当前无 useDataChange + revalidateOnFocus:false） | 🔴 高 | S3 必须补订阅；这是与 agent 的本质差别，不做必失败 |
| **通知 endpoint 与订阅不匹配** → 通知发了 UI 不认 | 🔴 高 | S2 通知 endpoint 与 S3 订阅 endpoint 用同一份定义；集成测试断言 |
| **V-M0-1 ① 卡 key/id**（真机无法远程） | 🔴 高 | S1 老板拆段发 key + 跑目录命令；**需老板配合** |
| **usage 只读被误当可写** → 过度设计 | 🟡 中 | S4 明确 usage 只读 GET，不发通知 |
| **Service 方法签名随基线漂移** | 🟡 中 | 按最新基线核对（plan-m0 §3.5）；走 Service 不直写 |
| **热更新判据真机红** | 🔴 高 | 如实上报 → 方案 5.3 降级方案 C（强制重启）重评；V-M0-1 红阻塞 M1 |
| **plan-m0 §B10 用 TanStack 误导** | 🟡 低 | S6 文档修正为 SWR + useDataChange |

---

## 七、需澄清点 [NEEDS CLARIFICATION]

1. **provider/key admin 路由端点范围**：本次是只做「更新/派发/推 key」（对 V-M0-1 ②③），还是连 **create/delete** 也做全（M0-4 的完整 CRUD）？—— 建议本次最小集先覆盖 V-M0-1 ②③ 所需（POST/PUT/DELETE provider + POST/PUT/DELETE key），完整 CRUD 归 M0-4/F-4/F-5。
2. **真机实测需要老板配合**：我无法远程 17 号机（无 SSH/RDP/SMB），实测①~③必须老板手动执行 + 观察 UI。**是否接受老板配合模式？**（若老板无法配合，只能本地集成测试 + 188 机若有远程手段则用 188。）
3. **usage 是否需要写端**：按源码 usage 是只读统计（官方 recordInvocations 写入），admin 只做 GET。**是否同意 usage 只读，不做 admin 写？**
4. **S3 订阅点**：在 `useProviders` 一个 hook 内聚合订阅 `/providers` 系列（改动最小），还是分别在 `useProviderById`/`useProviderApiKeys` 内各自订阅（覆盖面更细但改动更多）？—— 建议前者（聚合，最小侵入）。

---

## 八、建议执行顺序

1. **S1**（解 V-M0-1 ① 卡点，需老板 key+id）—— 并行启动，等老板输入。
2. **S2 + S3**（代码：admin 路由扩展 + provider 渲染订阅）—— 本机可做，不阻塞。
3. **S5 本地集成测试**（Linux 跑 routes.integration.test.ts 扩展）—— 验证路由注册+鉴权。
4. **S5 真机实测**（需老板配合，①②③④）—— 003 验收核心。
5. **S6**（验收 + 看板 + 文档）。

**关键路径**：S1(老板输入) ∥ S2+S3(代码) → 集成测试 → 真机实测 → 验收。