# JJC-20260811-001 · CherryStudio 受管版 M1 Fork 层完整实现（F1-F12）— 权威定义

> 来源：`/mnt/chee_2/Chee/OpenClaw_C/基建/cherry-managed/docs/任务分解-v4.0.md`（2026-08-07）
> 前置：方向已定案（跟随官方最新 + Fork 适配）、4 轮质询收敛（质询记录-v4.0.md）
> 状态：M0（M0-1~5 + 收尾）已由老板 2026-08-11 拍板收口（003 cancelled，代码部分完成并验证，完整数据验证并入 M2 Sidecar 自动验证，见 docs/result-m0-收尾.md commit 4aa345b）

## M1 定义
**M1 = Fork 层完成**。交付判据：`/v1/admin/*` 全路由 + 独立 key + 受管保护 + 热更新 + 锁 UI

## Fork 层任务清单（F-1~F-12）

| ID | 任务 | 说明 | 依赖 |
|----|------|------|------|
| F-1 | 拉官方最新 + 建 Fork 分支 | official/main 镜像 + managed/xxx 分支策略 | M0-3 |
| F-2 | 加管理路由 `/v1/admin/*` | v1Routes 链追加 adminRoutes 插件，鉴权继承 | F-1 |
| F-3 | 独立管理 key | `feature.api_gateway.managed_key`，与普通 key 分离 | F-2 |
| F-4 | agents 管理路由 | AgentService CRUD（createAgentWithId/getAgent/listAgents/updateAgent/deleteAgent/reorder） | F-2 |
| F-5 | providers 管理路由 | ProviderService CRUD（create/update/delete/batchUpsert/addApiKey/replaceApiKeys） | F-2 |
| F-6 | skills/mcp 管理路由 | agentSkill 表 + mcpServer 表 | F-2 |
| F-7 | usage 管理路由 | 读 ai_usage_record 表，供 Sidecar 拉取 | F-2 |
| F-7b | 工作目录采集路由 | `/v1/admin/agent-files`：按 agent_id/路径枚举+读取智能体工作目录（accessible_paths 内） | F-2, F-4 |
| F-8 | 泛化受管保护 | cherryai 硬编码 → managed_registry 判定；受管 provider/agent 不可改/删 | F-1 |
| F-9 | 热更新 IPC 刷新广播 | 写 sqlite 后 emitAgentCreated/新广播 → 渲染 invalidate | F-2, M0-1 |
| F-10 | 锁死 UI（源码级） | 渲染组件加 managed 判断：隐藏删除按钮/受管项只读 | F-8 |
| F-11 | 禁用官方更新 | 改 feedURL 指向自建更新通道 + autoUpdate 配置接管 | F-1 |
| F-12 | Fork 分支收敛 | official/ + managed/ 分支策略落地，官方更新 rebase | F-1 |

## 关键路径
```
M0-3 → F-1 → F-2 → F-4/F-5 → M0-1(热更新验证) → F-9 → M1
```

## 需求覆盖（R1-R7 相关）
- R1 模型统一管控 → F-5 + Sidecar
- R2 Key 保护 → F-3（独立管理 key）+ 服务端花费监控
- R3 Agent 远程管理 → F-4 + Sidecar
- R5 锁死 UI → F-10（源码级 managed 判断 + lock_rules）
- R7 升级免疫 → F-11（禁用官方 feed + 自建通道）

## ⚠️ 现状（M0 收尾后，cherry-src 已具备的基础）
- commit `0ef01567f`：adminRoutes.ts 已 85→265 行，含 GET/POST/PUT /providers、PUT /providers/:id/api-keys、GET /usage、POST /agents（F-2/F-4/F-5/F-7 部分已实现）
- commit `963897128`：S2 通知对齐三端点 + S3 useProvider 订阅补齐 + S4 集成测试 10 用例（F-9 热更新基础已打通）
- 关键认知：广播用**模板路径 + entityIds**（dispatchDataChange 精确匹配模板路径，非具体路径）
- **M1 需补**：F-1 分支策略、F-3 独立管理 key、F-6 skills/mcp 路由、F-7b agent-files 路由、F-8 泛化受管保护、F-10 锁 UI、F-11 禁用官方更新、F-12 分支收敛

## 待老板确认项（任务分解 §七）
1. 升级触发标准（重要功能/安全修复才追）—— 已默认认可（M0 拍板时）
2. 真机实测需老板配合（无远程通道，SSH/RDP/SMB 全关，2334 是服务端端口员工机不开）