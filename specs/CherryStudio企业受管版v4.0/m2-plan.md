# M2 执行计划 · CherryStudio 受管版 Sidecar 闭环完整实现（方案 B）

> JJC-20260811-003 | 老板 2026-08-11 拍板方案 B（完整做齐后统一测试）
> 权威定义：`任务分解-v4.0.md`（S-1~10 / D 服务端 / E 构建发布 / 里程碑）+ `sdd-企业受管版.md`（WS 协议 / 数据模型 / 技术选型 / 验收）+ `方案-企业受管版-v4.0.md`
> 前置：M1（F1-F12）已完成并 push（cherry-studio-managed main=e6d1e0b68）
> 起草：主 Agent 基于权威文档 + 军师探索成果（子 Agent 长任务边界提前终止，改由主 Agent 兜底产出）

> **老板拍板（2026-08-12 11:48，按主 Agent 建议全面完成）**：
> - schema 选 **(iii) 修订 SDD 对齐 M1**（保留 M1 复合主键，SDD §4.1 正式修订对齐）
> - 服务端部署：**192.168.3.181**（或独立服务机）
> - 更新通道 E-2 feed：**放服务端同机**（patch_repo/ 静态目录）
> - Sidecar 语言：**Python**（沿用现有原型）
> - 真机测试机：**待老板提供**（不影响批次 A/B/C/D/E）

---

## 〇、范围界定：M2 做 vs M3 不做

**M2 = Sidecar 闭环**（S-1~S-10）＋ 最小服务端骨架（够 Sidecar 闭环用）＋ 自建更新通道（E-2）＋ 真机实测。

**明确归 M3（本计划不做，仅留接口）**：
- Web 管理后台完整版（D-2 web_admin 完整 UI）
- 花费监控模块（D-6 cost_monitor：聚合看板 / 异常告警 / 停 key / 中转对接）
- skills_repo / patch_repo / gitbash_repo 完整仓库
- 数据仓库规模化（PostgreSQL）

**M2 最小服务端**只做 Sidecar 闭环必需：WS 服务 + 设备注册表 + 派发调度 + 接收 usage/工作目录上报 + 基础对账入口。

---

## 一、现状核实（主 Agent 实读代码/目录确认）

| 项 | 现状 | 判定 |
|----|------|------|
| M1 admin 路由 | /agents CRUD + /agents/:id/files + /providers CRUD + /skills + /mcp + /mcp/:id + /usage 全部可用 | ✅ 已具备 |
| managed_key | M1 F-3 已做，Bearer-only 约束已落地 | ✅ 已具备 |
| managed_registry.db | M1 F-8 落地：`managed_entity(kind,id,created_at)`，位置 `{userData}/Data/managed_registry.db` | ⚠️ schema 漂移（见 §三） |
| 禁用官方更新 | M1 F-11 已做（CHERRY_MANAGED_BUILD + feed_url） | ✅ 已具备 |
| Sidecar 原型 | `sidecar.py`(187行) + `lib/cherry_client.py`(154行)，仅 probe/列清单/单Agent部署 | 需补全 S-1~10 |
| 服务端 | `server/` 目录空，无代码，2334 无监听，仅 A0-A1 文档骨架 | 从零建最小骨架 |
| 更新通道 | 未做（E-2） | 需建 |
| 真机 | 无测试机就绪，需老板配合 | 待办 |

---

## 二、Sidecar 层 S-1~S-10 逐项拆解

> Sidecar 技术栈（SDD §5）：Python + `websocket-client`；NSSM Windows 服务；PyInstaller 打包 exe。现有 sidecar.py/cherry_client.py 为基础扩展。

| ID | 任务 | 现状 | 要做 | 依赖 | AC（量化） |
|----|------|------|------|------|-----------|
| S-1 | Sidecar 骨架 | 有单机原型 | 扩展为常驻主进程：WS 长连接（指数退避重连）+ 心跳 + 指令循环 + config/sidecar.json | — | 连接 WS 2334；断线重连；心跳 |
| S-2 | 设备注册 | 无 | register 消息（device_id/hostname/os/版本/git_bash 状态/token）→ 服务端登记 | S-1 | 服务端设备表出现，状态在线 |
| S-3 | 派发 Agent | 有单 Agent 部署 | dispatch_agent 全动作（create/update/delete/disable）+ managed 标记 + package_url 拉取 | S-1, F-4 | Agent 出现/收回/禁用/升级；幂等（request_id） |
| S-4 | 派发 provider | 无 | dispatch_provider（add/remove/update + key），经 /v1/admin/providers | S-1, F-5 | 模型下拉出现；key 生效；员工看不到 key 原文 |
| S-5 | SKILLS 派发 | 无 | 拉 skills 包 → 写 agent_skill 表 + 符号链接 | S-1, F-6 | skills 落地可用 |
| S-6 | usage 采集上报 | 无 | 定时拉 /v1/admin/usage → 汇总上报服务端 | S-1, F-7 | 服务端数据仓库有记录 |
| S-6b | 工作目录采集 | 无 | 按服务端指令拉 /v1/admin/agents/:id/files → 上报，限 accessible_paths | S-1, F-7b | 读出目录上下文+产出，不越权 |
| S-7 | 对账 | 无 | 调 list_agents 比对服务端期望清单，缺的补/受管保护/非受管忽略 | S-3 | 员工手动改/删受管项被修复 |
| S-8 | 受管标记旁路表 | M1 已建只读 | **Sidecar 成为唯一写者**：写 managed_registry.db；schema 对齐见 §三 | S-1 | 注册自定义受管实体；cherryai 不回归 |
| S-9 | 自愈 | 无 | Fork 升级失败回滚上一版；注入失败重跑 | S-1 | 模拟升级失败→回滚，Sidecar 不崩 |
| S-10 | NSSM 服务注册 | 无 | Windows 服务，开机自启，与 Fork 解耦 | M0-2 | 服务自启；手动/崩溃自愈 |

---

## 三、⚠️ managed_registry schema 漂移矛盾（S-8 关键）

**矛盾**：
- SDD 权威定义（§4.1）：`managed_registry(id TEXT PK, type TEXT, managed INTEGER DEFAULT 1, created_at)`
- M1 实际落地（F-8）：`managed_entity(kind, id, created_at)`，位置 `{userData}/Data/managed_registry.db`

**影响**：S-8 要求 Sidecar 成为 managed_registry.db 唯一写者，但写前必须统一 schema。若沿用 M1 的 `managed_entity(kind,id)`，与 SDD 的 `managed_registry(id,type,managed)` 不一致——Sidecar 按 SDD 写会产生两张不同结构的表。

**审计官审查要点（技术中立呈现）**：M1 的 `managed_entity(kind, id)` **复合主键实际是更优的数据模型**（避免不同实体类型 id 碰撞）；SDD 的 `managed_registry(id PK)` 单列主键假设 id 全局唯一，反而较弱；M1 的 `managed` 列冗余（行存在即受管）。**但这不是装饰性问题**：S-8 要 Sidecar 成为唯一写者，若 Sidecar 按 SDD 格式写入而 Fork 按 M1 格式读取，循环会断开——必须统一。

**三选项（待老板拍板，审计官裁定为需澄清项）**：
- **方案 (i) 对齐 SDD**：改 M1 表 + 全部读路径为 `managed_registry(id,type,managed,created_at)`，`isManaged(kind,id)`→`isManaged(type,id)`。需迁移现有 db。符合 v4.0 单一事实源，但改更多代码、换更弱 schema（单列主键）。
- **方案 (ii) 沿用 M1**：认可 `managed_entity(kind,id)` 为实际落地，修订 SDD §4.1 对齐。改动小，保留更优复合主键，但偏离 SDD 文档措辞。
- **方案 (iii) 修订 SDD 对齐 M1**（审计官提出）：SDD 是权威单一事实源，但 M1 已落地更优 schema，可走正式 spec 修订把 §4.1 更新为 M1 格式（需老板签核）。
- **审计官倾向**：方案 (i) 技术上未必更好（可能是更差技术选择），建议老板在 (i)/(ii)/(iii) 间裁决，中立呈现 trade-off，不默认推荐 (i)。

**✅ 老板已拍板（2026-08-12）：选 (iii) 修订 SDD 对齐 M1**——保留 M1 复合主键（更优），走 SDD §4.1 正式修订对齐。批次 C 按 (iii) 执行：更新 SDD §4.1 措辞 + Sidecar 写 M1 格式。

---

## 四、最小服务端（FastAPI + websockets，端口 2334）

> 从零建最小骨架，仅 Sidecar 闭环必需。技术栈（SDD §5）：Python FastAPI + uvicorn + `websockets`；SQLite 起步。

**模块**（对齐 SDD §1.1，只做最小集）：
- `main.py`：应用入口，启动 uvicorn on 2334
- `ws_server.py`：设备连接管理，WS 长连接 + 心跳 + 断线重连 + 指令幂等队列
- `device_registry.py`：设备注册表（devices 表：device_id/hostname/os/版本/online/last_seen/group/token）+ 分组
- `dispatch.py`：派发调度（dispatch_agent/dispatch_provider/dispatch_skills + 幂等 request_id + 离线入队）
- `collect.py`：接收 usage 上报 + 工作目录上报 → 写数据仓库
- `reconcile.py`：对账入口（服务端期望清单比对）
- `data/`：SQLite 数据仓库（devices/dispatch_log/usage_agg/agent_files/audit_log）
- `config.json`：服务端配置（端口/token 校验/数据目录）

**不做（归 M3）**：web_admin 完整 UI、cost_monitor、skills_repo/patch_repo/gitbash_repo 完整仓库、PostgreSQL。

**数据模型**（SDD §4.3，全建）：
- `devices(device_id PK, hostname, os, cherry_version, fork_version, online, last_seen, group, token)`
- `dispatch_log(request_id, device_id, type, action, status(pending/success/fail), created_at)`
- `usage_agg(device_id, provider, model, input_tokens, output_tokens, total_tokens, period)`
- `agent_files(device_id, agent_id, path, content, captured_at)`
- `audit_log(operator, action, target, timestamp, request_id)`

**WS 协议**：M2 只实现 S-1~10 闭环需要的消息子集——register(3.1)/dispatch_agent(3.2)/dispatch_provider(3.3)/usage(3.5)/dispatch_result(3.6)/status(3.7) + 幂等(3.9)。
> **审计官修正**：sync_lock_rules(3.4)、fetch_patch(3.8)、install_gitbash(3.8) 属 M3 范围（lock_rules 迭代 D-5、Fork 升级/装 Git Bash 是 D 系列），M2 最小服务端**不在 WS 层实现其业务**，仅预留消息类型占位 handler 返回 not_implemented，避免误报「严格按 3.1~3.9 全实现」。

**S-6b 触发机制（审计官指出协议缺口）**：SDD §3 无显式「fetch_agent_files」消息，R6 采集是「服务端发起/排查时」。M2 定义：新增 WS 消息 `fetch_agent_files`（服务端→Sidecar，含 device_id/agent_id/accessible_paths/request_id），Sidecar 回 `dispatch_result` 带采集内容；或退化为 HTTP 回调 `POST /v1/admin/agents/:id/files` 拉取。实现时二选一，推荐 WS 消息（与派发链路一致、可幂等）。

---

## 五、自建更新通道 E-2

**目标**：替代官方 `releases.cherry-ai.com`，M1 F-11 的 feed_url 指向自建 feed。

**方案**：electron-updater `generic` provider，静态托管 `latest.yml` + 安装包。
- 托管位置：服务端 `patch_repo/`（或独立静态目录）
- `latest.yml`：electron-builder 生成的版本元数据
- feed_url 指向：`http://<server>/patch_repo/latest.yml`（服务端同机或独立）
- **待澄清**：托管在服务端 2334 同机（推荐，简单）还是独立 CDN/静态站

**M2 落地**：搭 generic feed + 验证 electron-updater 从自建源拉取更新。签名暂缓（M4 发布环节处理）。

---

## 六、真机实测方案

**约束**：无远程通道（SSH/RDP/SMB 全关，2334 是服务端端口员工机不开）。真机需老板配合。

**测试准备**：
- 员工机（Windows）装 M0-2 已出的安装包（Cherry-Studio-2.0.3-x64-setup.exe，286MB）或 M2 重新构建包
- 员工机装 Sidecar（PyInstaller exe / NSSM 服务）
- 服务端跑在 192.168.3.181 或独立机

**全链路验证（对照 V-M2-1~8）**：
| 验收 | 步骤 | 通过标准 |
|------|------|---------|
| V-M2-1 设备注册 | Sidecar 启动连 WS | 服务端设备表在线 |
| V-M2-2 派发 Agent | 服务端派 dispatch_agent | 员工端 Agent 出现，可收回/禁用/升级 |
| V-M2-3 派发模型 | 派 dispatch_provider | 模型下拉出现，key 生效，看不到 key 原文 |
| V-M2-4 对账 | 员工手动改/删受管项 | Sidecar 修复，服务端可见告警 |
| V-M2-5 usage 上报 | 定时拉 /usage 上报 | 数据仓库有记录 |
| V-M2-6 工作目录采集 | 拉 /agents/:id/files | 读出目录内容，限 accessible_paths |
| V-M2-7 自愈 | 模拟升级失败 | 回滚，Sidecar 不崩 |
| V-M2-8 断线重连 | 断开 WS 再连 | 重连成功，指令幂等不重复 |

---

## 七、执行批次与派发顺序

> 串行为主（多文件强关联：服务端模块、Sidecar 模块、Fork 路由）。子 Agent 长任务易提前终止，**拆小步 + 主 Agent 兜底关键产出**。

- **批次 A（服务端最小骨架）**：main.py + ws_server + device_registry + dispatch + collect + reconcile + data + config → 单测（WS 协议、注册、派发幂等）
- **批次 B（Sidecar 全闭环）**：基于原型扩展 S-1~10，接服务端 WS + Fork admin 路由 → 单测
- **批次 C（managed_registry schema 对齐 + S-8 写者）**：待老板拍板 §三 (i)/(ii)
- **批次 D（E-2 更新通道）**：generic feed + 验证
- **批次 E（集成 + 打包）**：Sidecar PyInstaller + NSSM + 端到端集成测试
- **批次 F（真机实测）**：需老板配合，装员工机跑 V-M2-1~8

---

## 八、风险

| 风险 | 等级 | 对策 |
|------|------|------|
| 服务端从零建，工作量大 | 高 | 最小集先行，M3 完整业务后置 |
| managed_registry schema 漂移 | 中 | 老板拍板 §三 (i)/(ii) 后统一 |
| Sidecar 与 Fork 集成（调 admin 路由） | 中 | 复用 M1 已验证路由，单测覆盖 |
| NSSM/Windows 环境 | 中 | 真机阶段验证，本地 Linux 用进程方式先测逻辑 |
| 真机依赖老板 | 高 | 提前准备安装包/脚本，老板提供测试机 |
| 子 Agent 长任务提前终止 | 中 | 拆小步 + 主 Agent 兜底关键产出（本方案即主 Agent 起草） |
| 更新通道签名/分发 | 低 | 签名归 M4，M2 只做 generic feed 拉取验证 |

---

## 九、NEEDS CLARIFICATION（需老板拍板）

1. ~~managed_registry schema~~ **✅ 已拍板 (iii) 修订 SDD 对齐 M1**（2026-08-12）
2. ~~服务端部署位置~~ **✅ 已拍板：192.168.3.181**（或独立服务机）
3. ~~更新通道托管~~ **✅ 已拍板：放服务端同机**（patch_repo/ 静态目录）
4. **真机测试机**：老板提供哪台员工机？（Windows，装包 + Sidecar）
5. ~~Sidecar 语言~~ **✅ 已拍板：Python**（沿用现有原型）

---

## 十、自检

- ✅ 范围界定 M2 vs M3 清晰
- ✅ S-1~10 逐项拆解 + AC 量化
- ✅ 最小服务端范围明确（数据模型全建，业务后置）
- ✅ E-2 更新通道方案
- ✅ 真机测试方案（V-M2-1~8）
- ✅ 执行批次 + 派发顺序
- ✅ 风险 + NEEDS CLARIFICATION
- ✅ managed_registry schema 漂移矛盾已指出（不擅自选边，审计官裁定为需澄清项）
- ✅ 审计官修正已落地：WS 范围收紧（sync_lock_rules/fetch_patch/install_gitbash 归 M3）、S-6b 触发机制定义、schema 三选项中立呈现
- ⚠️ 审计官裁定：**需澄清**（非硬驳回）——方案基本健全，待老板裁决 schema + 确认 M2/M3/M4 边界后即可派执行批次 A/B/D/E
