# JJC-20260811-003 · CherryStudio 受管版 M2 — Sidecar 闭环完整实现（方案B）执行计划

> 起草：总办（鮱澄）基于 v4.0 任务分解 S-1~S-10 + 前作 sidecar.py 原型 + 方案A 通信协议
> 军师四次写文件失败（系统性，failed: completed），改由总办起草 + 审计官审议
> 技能参考：sdd-writer（spec/plan/tasks 三件套）、ai-project-docs（验收矩阵）

---

## ⚠️ 审计修正（shenyi 2026-08-11，实读代码，有条件通过）

1. **【核心】S-3 端点决策缺失**：计划说 S-3「复用 cherry_client.create_agent」——但 cherry_client 走**官方 API**（HTTP 127.0.0.1:23333 `/v1/agents`），而 v4.0 派发要走 **Fork 管理路由**（HTTPS 127.0.0.1 + managed_key + `/v1/admin/agents`）。两者不同端点。要打 managed 标记（S-8）必须走 Fork `/v1/admin/*` → **S-3/S-4/S-5 需新增 `fork_client` 传输层**（HTTPS + managed_key + /v1/admin base path），不能只复用 cherry_client。此决策需老板拍板（官方 API vs Fork 管理路由）。
2. **F-7b 半成品依赖**：S-6b 标「本地可做」但依赖半成品 Fork F-7b → 无法端到端本地测，需**先确认 F-7b 实现状态**再排 S-6b。
3. **S-8 补 IPC 读通道**：managed_registry.db 除 Sidecar 写外，需暴露 **IPC 读通道给渲染层**（F-10 锁 UI 依赖）——计划只写「旁路表可读写」，漏了 IPC。
4. **安全缺口**：managed_key 存储需**加密不落明文**（v4.0 2.1）；S-6b 内容传输（含对话/产出）应**升级 WSS/TLS**（v4.0 可升级），计划未提。
5. **D-1 引用 A0-A1 开发文档**：已有 `开发文档A0-A1-服务端骨架与单机派发.md` 定义 D-1 结构（main.py/ws_server.py/device_registry.py/dispatch.py），非从零，计划应引用。
6. **DoD 收紧**：S-5「生效」→ 定义可测断言；S-6b「不越权」→ 加测试断言；S-9「不损坏」→ 定义回滚后健康检查。

## 〇、任务边界（M2 = Sidecar 闭环）
- **范围**：Sidecar 层 S-1~S-10（独立进程，连服务端 WS 2334 + 调 Fork 管理路由）
- **不在本任务**：Fork 层（M1 已完成）、服务端 Web 后台/花费监控/数据仓库（M3 D-1~D-10）
- **边界说明**：Sidecar 要「连服务端」测闭环，需服务端**最小 WS 服务**（D-1 骨架，FastAPI WS 2334）。**server/ 目录当前为空**（前作 A0-A1 仅方案文档，代码未落地）→ M2 需补 D-1 最小 WS 服务作为 Sidecar 对接端点，其余 D-2~D-10 留 M3。
- **真机约束**：无远程通道（SSH/RDP/SMB 全关）→ 参照 M0 收尾模式：代码 + 自动化测试交付，真机验证并入后续里程碑。

## 一、现状核实（实读代码）
| 组件 | 现状 | 证据 |
|------|------|------|
| sidecar.py | M2 原型：probe/agents/models/deploy 连单机（list.json 机器清单）| `/mnt/chee_2/.../cherry-managed/sidecar/sidecar.py`（6371B）|
| lib/cherry_client.py | 官方 API 客户端完整：health/list_agents/get_agent/create_agent/patch_agent/put_agent/delete | sidecar/lib/cherry_client.py（6539B）|
| server/ | **空目录**，无服务端代码 | cherry-managed/server/ |
| 通信协议 | 方案A 文档定义（WS 2334、register/dispatch/回执/status/usage）| docs/方案A-服务端Sidecar远程闭环.md（已作废但协议可参考）|

## 二、任务分解（S-1~S-10，含分类 + 依赖）

### S-1 Sidecar 骨架（常驻进程）
- **内容**：sidecar.py 从「命令行单机工具」升级为「常驻进程」：连接服务端 WS 2334 + 心跳 + 断线重连 + 指令分发循环
- **分类**：【本地代码可做】需补 D-1 最小 WS 服务做对接测试
- **依赖**：D-1（服务端 WS 骨架）
- **DoD**：Sidecar 连上服务端 WS，register 成功，收指令循环工作
- **验证**：本地起 server + sidecar，`register` 消息送达 + 心跳
- **回滚**：git revert
- **优先级**：P0（全部依赖它）

### S-2 设备注册
- **内容**：register 消息（device_id + token + cherry_version + git_bash_installed + 本机 key），服务端登记返回期望清单
- **分类**：【本地代码可做】+ 需 D-1 支持
- **依赖**：S-1
- **DoD**：设备上线，服务端记录设备状态
- **优先级**：P0

### S-3 派发 Agent
- **内容**：dispatch_agent（create/update/delete/disable + managed 标记 + package_url）→ 复用 cherry_client.create_agent/patch_agent/put_agent；幂等（同名先查再建）
- **分类**：【本地代码可做】协议+幂等逻辑；【需真机】验证真正派发到 CherryStudio
- **依赖**：S-1
- **DoD**：派发指令到端到端，回执 dispatch_result 含 agent_id
- **优先级**：P0

### S-4 派发模型 provider
- **内容**：dispatch_provider（add/remove/update + key）。⚠️ 官方 `/v1/providers` 404（M1 已加 Fork `/v1/admin/providers`）→ Sidecar 应调 Fork 管理路由而非官方 API
- **分类**：【本地代码可做】客户端逻辑；【需真机】验证 Fork 管理路由
- **依赖**：S-1、Fork F-5（M1 已完成）
- **DoD**：provider 派发走 Fork `/v1/admin/providers`
- **优先级**：P1

### S-5 SKILLS 派发
- **内容**：拉 skills 包 → 写 agent_skill 表 + 符号链接
- **分类**：【本地代码可做】+ 需 Fork F-6（M1）接口
- **依赖**：S-1、Fork F-6
- **DoD**：SKILLS 包下发并生效
- **优先级**：P1

### S-6 usage 采集上报
- **内容**：定时拉 ai_usage_record → 汇总上报服务端（走 Fork F-7 GET /usage）
- **分类**：【本地代码可做】
- **依赖**：S-1、Fork F-7（M1 已完成）
- **DoD**：usage 周期汇总上报服务端存储
- **优先级**：P0（花费监控 M3 依赖）

### S-6b 工作目录采集上报
- **内容**：按服务端指令拉 Fork `/v1/admin/agent-files`（Agent 工作目录上下文+产出）→ 上报，限 accessible_paths 内不越权
- **分类**：【本地代码可做】逻辑；【需真机】Fork F-7b 是否已实现待核
- **依赖**：S-1、S-3、Fork F-7b（M1 半成品，需确认）
- **DoD**：按需采集工作目录内容上报，不越权
- **优先级**：P1（边界敏感，需老板确认采集范围）

### S-7 对账
- **内容**：调 list_agents 比对服务端期望清单，缺的补/受管保护/非受管忽略
- **分类**：【本地代码可做】
- **依赖**：S-3
- **DoD**：对账一致，非受管 Agent 不误动
- **优先级**：P1

### S-8 受管标记旁路表 managed_registry.db
- **内容**：本地 sqlite，Sidecar 维护受管标记（provider/agent 不可改/删）
- **分类**：【本地代码可做】
- **依赖**：S-1
- **DoD**：受管项标记正确，旁路表可读写
- **优先级**：P0

### S-9 自愈
- **内容**：Fork 升级失败回滚上一版；注入失败重跑
- **分类**：【本地代码可做】回滚逻辑；【需真机】验证
- **依赖**：S-1
- **DoD**：升级失败自动回滚不损坏
- **优先级**：P1

### S-10 NSSM 服务注册
- **内容**：Windows 服务（NSSM），自启动，与 Fork 解耦
- **分类**：【需真机/Windows】打包 + 安装验证
- **依赖**：S-1、M0-2（Windows 构建）
- **DoD**：Sidecar 注册为 Windows 服务自启动
- **优先级**：P1（真机受限，可先交付脚本+说明，验收并入后续）

### D-1 服务端最小 WS 骨架（M2 前置，补）
- **内容**：FastAPI + uvicorn + WS 2334，设备连接管理（register 处理 + 心跳 + 派发指令下发）
- **分类**：【本地代码可做】
- **依赖**：无
- **DoD**：WS 服务起在 2334，Sidecar 能连上完成 register
- **优先级**：P0（S-1 依赖）

## 三、执行顺序（关键路径）
```
D-1 服务端 WS 骨架 → S-1 Sidecar 骨架 → S-2 设备注册 → S-8 managed_registry
→ S-3 派发 Agent → S-6 usage 采集 → S-7 对账
→ S-4 provider / S-5 SKILLS / S-6b 工作目录 / S-9 自愈 / S-10 NSSM（P1，按依赖推进）
```
- 本地代码全部可交付 + 自动化测试；真机验证（S-10 NSSM、S-4 Fork 管理路由、S-9 升级回滚）并入后续里程碑

## 四、验收矩阵（参考 ai-project-docs 5维×3级）
| 维度 | P0 门槛 | 目标 | 理想 |
|------|--------|------|------|
| 连接 | WS 2334 握手成功 | register 全通 | 断线自动重连 |
| 派发 | dispatch_agent 幂等 | create/update/delete 全通 | 批量派发 |
| 数据 | usage 拉取成功 | 汇总上报 | 工作目录按需采集 |
| 对账 | list 比对 | 受管保护 | 非受管忽略 |
| 自愈 | 回滚逻辑代码 | 升级失败回滚 | NSSM 自启动 |

## 五、NEEDS CLARIFICATION（需老板拍板）
1. **「方案B」指代确认**：任务标题「方案B」，但 NAS 文档是「方案A-服务端Sidecar远程闭环」（已作废）。是否「方案B」= v4.0 完整 Sidecar 实现（S-1~S-10）？还是另有方案B文档？
2. **D-1 服务端骨架**：server/ 为空，M2 需补最小 WS 服务做对接。确认归入本任务（M3 前只做 D-1 最小骨架）？
3. **S-6b 工作目录采集边界**：采集 Agent 工作目录（上下文+产出，含对话内容）。确认「按需采集」边界（调用数据回传分析时才采集，公司内部合规）？
4. **真机验收范围**：无远程通道。是否参照 M0 收尾模式（代码+自动化测试交付，真机验证并入后续）？
5. **S-10 NSSM**：本轮只交付脚本+说明，还是必须真机装好？

## 六、遗留风险
- Fork F-7b（工作目录采集路由）M1 是半成品，需核实是否可用
- server/ 无代码，M2 需从零建 D-1 最小 WS 骨架
- 真机无远程通道，Windows 侧（NSSM/Fork 管理路由）验证受限
