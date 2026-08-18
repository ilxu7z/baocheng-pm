# 审议部审查报告 · JJC-20260810-003「M0收尾：扩展admin路由+实测热更新」

**审计官**：shenyi（审议部）| **日期**：2026-08-10 | **审查对象**：m0-close-plan.md（军师 S1-S6）

## 结论：**有条件通过**（1 项必须修正 + 3 项需澄清）

## 一、军师 5 条事实声明核验
| # | 声明 | 结果 | 证据 |
|---|------|------|------|
| 1 | provider 层无 useDataChange 订阅 + SWR revalidateOnFocus:false | ✅ 属实 | grep 全库 6 处 useDataChange，provider 0 处；useDataApi.ts DEFAULT_SWR_OPTIONS revalidateOnFocus:false（行~80） |
| 2 | V-M0-1 ① 真机热更新未完成 | ✅ 属实 | memory/2026-08-10.md 卡点记录：占位符 id+脱敏 key 跑 PUT 返回 403 |
| 3 | usage 只读 + 渲染层已原生订阅 | ✅ 属实 | useUsageData.ts:162 已 useDataChange(['/ai-usage-records','/ai-usage-records/stats','/ai-usage-records/timeline']) |
| 4 | plan-m0 §B10 写 TanStack Query 有误 | ⚠️ 部分属实 | 实质判断正确（SWR+useDataChange），但引用目标 /mnt/chee_2/.../plan-m0.md 无法定位 |
| 5 | 通知 endpoint 必须与订阅字面一致 | ✅ 属实（关键机制） | DataApiService.dispatchDataChange 用 dataChangeListeners.get(endpoint) 精确匹配，无通配 |

## 二、⚠️ 最重要发现：代码已超前于计划（S2/S4 已完成，但通知不一致）
1. **S2+S4 代码已提交** commit `0ef01567f`（adminRoutes.ts 85→265 行：GET/POST/PUT /providers、PUT /providers/:id/api-keys、GET /usage、POST /agents），工作树干净。**计划把 S2/S4 描述「待做」已过时**。
2. **通知 endpoint 不一致（阻断性）**：
   - 计划 §三：key 写应广播 `['/providers/:providerId/api-keys'] + ['/providers/:providerId']`
   - 已提交代码：PUT /providers/:id/api-keys **只广播 `/providers`**，未广播详情端点
   - 因精确匹配 → 详情页 useProviderById（/providers/:providerId）、useProviderApiKeys（/providers/:providerId/api-keys）**收不到通知，不刷新**
3. **S3 仍未完成，唯一硬缺口**：useProvider.ts 无订阅。没有 S3，「改后 UI 即时刷新」对 provider/key 必失败——军师论断正确。

## 三、【必须修正】S2/S3 通知一致性
执行前必须：
1. adminRoutes.ts key replace 通知补为 `['/providers', '/providers/:providerId/api-keys', '/providers/:providerId']`
2. S3 订阅与广播端点**逐字对齐**（含 /providers/:providerId 详情端点）
3. routes.integration.test.ts 增加断言：admin 写后 notifyDataApiDataChange 收到 effect 端点集合

## 四、3 项需澄清
1. **provider/key admin 端点范围**：本次最小集（②③所需）还是完整 CRUD？（建议最小集，完整归 M0-4）
2. **真机实测老板配合**：我无法远程 17 号机（无 SSH/RDP/SMB），①②③需老板手动执行+观察 UI
3. **usage 只读**：同意 admin 只 GET 不做写
4. ⚠️ adminRoutes.ts 注释「[待确认] device_id 过滤」——SDD 4.2 若要求 device_id 需显式确认（当前 Service/schema 无 device 维度）

## 五、可执行验收要点
**S1**：AC1 老板提供完整 key（拆段）+ m0test id（17号机 PowerShell 按 CreationTime 找最新 Agents 目录）；AC2 PUT 返回 200+新name；AC3 UI 10 秒刷新 PID 不变；AC4 记录 memory
**S2**：✅修正通知对齐；状态码 200/201/404/409/400；写库走 Service(D20)；集成测试断言注册+鉴权+通知端点集合
**S3**：✅useProvider.ts 补 useDataChange 逐字一致；useProvider.test.ts 不回归；确认三 UI 面（列表/详情/api-keys）均可触达
**S4**：GET /usage 200 字段完整（providerId/modelId/tokens/sourceType）；只读无写锁不发通知
**S5**：本地集成测试扩展（admin 路由+鉴权）先绿；真机①②③④全绿（老板配合）；任一红→降级方案 C 强制重启重评
**S6**：记录 SHA 0ef01567f；修正 plan-m0 §B10（先定位真实文件）；看板推进

## 附：审计发现的其他事实
- 军师原始输出路径 workspace-guihua/output/ 不存在，实际计划在 specs/m0-close-plan.md
- 集成测试 routes.integration.test.ts（554 行）**完全未覆盖 admin 路由**，扩展用例必须