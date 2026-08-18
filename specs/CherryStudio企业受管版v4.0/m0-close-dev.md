# 研发主管完成报告 · JJC-20260810-003 纯代码部分（S2+S3+S4）

**研发**：daima | **日期**：2026-08-10 | **Commit**：`963897128`（feat(m0-收尾): S2通知对齐+S3订阅补齐+S4集成测试）
**前置**：commit `0ef01567f`（S2/S4 路由已实现，本轮对齐+补缺口）

## 关键工程决策（偏离任务字面指令，但正确）
审计官/计划描述「广播详情端点时用 :providerId 实际值替换占位符」在本代码库**不成立**。核实 `DataApiService.dispatchDataChange` 用 `dataChangeListeners.get(endpoint)` **精确匹配模板路径**，广播具体路径 `/providers/abc/api-keys` 永不命中渲染层订阅 `/providers/:providerId/api-keys`。全库约定 = 广播**模板路径 + entityIds**，订阅方按 entityIds 过滤。遵循「改前先读实际代码」铁律。

## 改动（16 文件）
**S2 adminRoutes.ts**（审计官 must-fix）
- PUT /providers/:id/api-keys：广播 [/providers] → [/providers, /providers/:providerId, /providers/:providerId/api-keys]（均带 entityIds）
- POST/PUT /providers：补广播 /providers/:providerId
- POST/PUT /agents：补广播 /agents/:agentId

**S3 useProvider.ts**
- useProviders → useDataChange('/providers')
- useProviderById → useDataChange('/providers/:providerId', entityIds 过滤)
- useProviderApiKeys → useDataChange('/providers/:providerId/api-keys', entityIds 过滤)
- 补上 revalidateOnFocus:false 缺口，外部 admin 写 provider/key 无需重启即热刷新

**S4 routes.integration.test.ts**
- 新增 admin 路由 10 用例：OpenAPI 注册（6 路径）、鉴权 401/403、5 写路由 notifyDataApiDataChange effect 端点集合断言（验证 S2 广播对齐，含 api-keys 三端点）
- vi.mock stub providerService/agentService/aiUsageRecordService/createAgent/notifyDataApiDataChange，hermetic

**顺带修复（0ef01567f 遗留）**
- admin 路由 detail.description 硬编码英文 → DOC_DESCRIPTIONS 槽位 + i18n 主/翻模板键（openapiDocs.ts + 15 i18n 文件），修复既有 OpenAPI 全量翻译断言测试在 0ef01567f 上红的问题

## 测试结果
- ✅ pnpm typecheck（node+web+ai-core）全过
- ✅ pnpm i18n:check 通过
- ✅ routes.integration.test.ts 54/54（含新增 10 admin 用例）
- ✅ useProvider.test.ts 57/57 + useDataChange + DataApiService 通过
- ✅ Provider 消费方 15/15

## 阻塞
无。S1/S5 真机实测由老板配合。

## 验收提示（给品控）
- 真机验收重点：详情页/api-keys 页在外部 PUT 后无需刷新即更新
- 广播机制：模板路径+entityIds（非具体路径）