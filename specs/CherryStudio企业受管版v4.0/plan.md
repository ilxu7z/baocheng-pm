# JJC-20260807-002 · CherryStudio 企业受管版 v4.0 深度任务分解与开发文档 · 执行方案

> 起草：军师（guihua/规划部）| 状态：待审计官审议

## §0 现场调研与前置准备（实测）

**实测技术栈：** Electron + Vite + React + TypeScript；pnpm monorepo；shadcn/ui。
**关键调研发现（实测）：** 本地已有 CherryStudio 开源版源码 `/home/chee/.openclaw/workspace-main/cherry-src/`（CherryHQ/cherry-studio **v2.0.1**，package.json 已核实）。因此本任务定位为**受管化改造**而非从零开发——最大杠杆在于复用既有 `apiGateway`、`provider-registry`、`knowledge`、`mcp`、`AnalyticsService`，叠加企业管控横切层。

| 维度 | 实测 | 对企业版影响 |
|---|---|---|
| API 网关 | `src/main/features/apiGateway/` 已存在（ApiGatewayService/routes/middleware/proxyStream/openrouter） | ⭐ 企业统一网关**增强复用，非从零** |
| 模型/供应商 | `src/main/ai/provider/`(credential/config/factory/gatewayRouting) + `packages/provider-registry/`(40+ 供应商) | 白名单/配额挂此层 |
| 知识库 | `features/knowledge/`(ingestion/pipeline/query) | 知识库权限增强 |
| MCP | `ai/mcp/`(Catalog/Runtime/Package) + `packages/mcp-trace` | MCP/插件白名单管控点 |
| 用量 | `services/AnalyticsService.ts` + 设置页 `usage.tsx` | 增强为部门分摊 |
| 数据层 | `main/data/`(db/migration) | 审计日志复用 db |
| 设置路由 | `routes/settings/`(provider/model/usage/api-gateway/mcp) | 管理员控制台复用框架 |

**前置准备（阻断性，先做）：**
- **P0.1** 从 v2.0.1 fork 私有企业版仓库 `enterprise/`，保留 git 历史
- **P0.2 [NEEDS CLARIFICATION]** 部署形态：纯私有化客户端 vs 客户端+服务端混合
- **P0.3 [NEEDS CLARIFICATION]** SSO IdP：OIDC 还是 SAML 优先
- **P0.4 [NEEDS CLARIFICATION]** 合规标准（等保/SOC2/内部）+ 审计保留周期
- **P0.5 [NEEDS CLARIFICATION]** 统一网关形态：客户端内置(复用 apiGateway) vs 独立服务端网关

## §一 深度任务分解（Phase 0–11 + 66 任务）

**Phase 0 · 前置与基线**（P0）：T001 建仓fork / T002 许可证合规评估 / T003 ADR-001 架构决策 / T004 基线构建与CI / T005 十层文档初始化

**Phase 1 · 账号身份**（P0）：T101 OIDC/SAML 登录 / T102 RBAC 角色矩阵 / T103 多租户隔离 / T104 个人/企业身份切换 / T105 令牌管理

**Phase 2 · 模型接入管控**（P0）：T201 供应商白名单 / T202 模型配额费用管控 / T203 API Key 托管(不暴露终端) / T204 统一网关增强 / T205 可用性探测 fallback / T206 模型调用审计埋点

**Phase 3 · 管理员控制台**（P0）：T301 控制台 UI / T302 策略模型与下发协议 / T303 版本强制更新 / T304 策略审计 / T305 控制台权限隔离

**Phase 4 · 安全合规**（P0）：T401 审计日志系统(防篡改) / T402 数据脱敏 / T403 内容过滤 / T404 本地优先私有化存储 / T405 安全加固(CSP/IPC白名单) / T406 合规报告导出

**Phase 5 · 知识库/插件/MCP 管控**（P0/P1）：T501 知识库权限 / T502 插件白名单 / T503 MCP 工具管控 / T504 知识库内容审查 / T505 MCP 服务器白名单

**Phase 6 · 用量计费**（P0/P1）：T601 用量采集增强 / T602 部门成本分摊 / T603 用量报表看板 / T604 预算告警

**Phase 7 · 客户端受管加固**（P0/P2）：T701 受管模式锁定 / T702 IPC 权限校验 / T703 网络出口白名单 / T704 设备指纹

**Phase 8 · 集成与端到端测试**（P0/P1）：T801 E2E(Playwright) / T802 安全渗透 / T803 性能压测 / T804 兼容回归

**Phase 9 · 部署形态**（P0/P1）：T901 Docker 镜像 / T902 K8s+Helm / T903 客户端分发 / T904 运维监控

**Phase 10 · 文档完善**（P0/P1）：T1001 十层落全 / T1002 SDD 三件套 / T1003 知识回流

**Phase 11 · 终验交付**（P0）：T1101 终态验收 / T1102 交付物清单 / T1103 v4.0.0 发布

## §二 开发文档规划（十层 + SDD 三件套）

| 层 | 产出物 | 写入人 |
|---|---|---|
| L1 入口 | README.md | wenan |
| L2 导航 | docs/00-INDEX + AGENT-README | guihua |
| L3 决策 | docs/adr/*.md + PLAN.md | guihua |
| L4 执行 | 源码索引/成熟度矩阵/接口验证/开发指南 | daima |
| L5 规约 | specs/<feature>/{spec,plan,tasks}.md | guihua+shenyi |
| L6 验收 | UI验收清单/验收矩阵(5维×3级) | shencha |
| L7 诊断 | 运行时错误手册 | daima |
| L8 门禁 | 提交前检查/CI钩子 | rongcui |
| L9 交付 | 交付物清单模板 | huizong |
| L10 回流 | 缺陷修复日志+联动规则 | 全链路 |

SDD 三件套至少覆盖 7 个核心模块：identity、model-gateway、rbac、audit、admin-console、usage-billing、deployment。

## §三 里程碑
M1(前置基线)→M2(身份+模型管控)→M3(管理+安全)→M4(知识库/MCP/用量)→M5(加固+集成测试)→M6(部署+文档)→M7(终验交付 v4.0.0)。终态判据 5 维量化：代码(覆盖率>80%)、安全(渗透通过/Key无泄漏)、性能(P95<2s/网关500QPS)、文档(十层+7三件套全绿)、合规(无硬编码密钥/审计完整)。

## §四 依赖图谱
串行链：T102(RBAC)→T103(多租户)→T301(控制台)；T206(审计埋点)→T601(用量)；P0 阻断全部。并行组：P1{T101,T104}∥P5{T501,T503}。冲突组：T401(审计表)与 T601(用量表)同写 `data/db` 须串行。

## §五 分工（7 层防线）
鮱澄总控→军师起草/ADR/SDD→审计官审议封驳→调度长督办→路由主管冲突路由→执行部门(开发/内容/设计/质控)→交付主管整合。

## §六 风险对策
R1 上游漂移→锁 v2.0.1 基线 / R2 AGPL 合规→T002 前置 / R3 Key 泄漏→加密存储+渗透 / R4 租户遗漏→隔离测试+L10 回流 / R5 性能→压测前置+异步审计 / R6 范围蔓延→不做什么清单+门禁 / R7 误判从零开发→实测已确认走增强路线。

## §七 待确认项 [NEEDS CLARIFICATION]
P0.2 部署形态 / P0.3 SSO IdP / P0.4 合规标准 / P0.5 网关形态 / P0.1 仓库位置。前 4 项不阻塞 Phase 0（基线/ADR/十层骨架可先行）。

## 已知限制
1. 网络不可用（web_search 禁用、web_fetch 被内网 IP 拦截），调研基于本地实测源码 + 既有技能知识
2. 5 项 [NEEDS CLARIFICATION] 未确认前，Phase 1/2/3/9 最终设计有不确定性
3. 建议交审计官(shenyi)逐条审议 Acceptance Scenarios 后再进入执行