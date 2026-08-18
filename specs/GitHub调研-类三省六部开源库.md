# GitHub 调研：类「三省六部」高热度开源库

> 调研时间 2026-08-07 · 数据来源 GitHub Search API（真实 star 数）
> 「三省六部」特征：多 Agent 编排 + 角色分工 + 审批/审议流 + 任务/看板管理

## 最贴近「三省六部」的高热度项目

| 项目 | ★Stars | 语言 | 契合点 |
|------|--------|------|--------|
| **jnMetaCode/agency-agents-zh** | 18,934 | Shell | 267 个即插即用 AI 专家角色，覆盖 20 个部门（工程/设计/营销/金融），含 52 个中国市场智能体（小红书/抖音/飞书/钉钉）。编排器 agency-orchestrator 一句话让多位专家按 DAG 协作。**最贴近「六部制」** |
| **iflytek/astron-agent** | 9,248 | Java | 企业级 agentic 工作流平台（Apache-2.0），支持 low-code 工作流编排、审批/人工介入、MCP、RPA、SuperAgent。**最贴近「审批流」** |
| **hjcenry/openclaw-corp** | 1 | TypeScript | 与三省六部**同源思路**（基于 OpenClaw 定义组织架构/角色/多级 review→执行），有实时 dashboard。但热度极低 |

## 多 Agent 编排框架（高热度，通用）

| 项目 | ★Stars | 语言 | 说明 |
|------|--------|------|------|
| **langgenius/dify** | 151,648 | TS | Agentic 工作流 + RAG 平台（本司已用） |
| **FoundationAgents/MetaGPT** | 69,689 | Python | 首个 AI 软件公司，多角色协作（产品/架构/工程） |
| **microsoft/autogen** | 60,284 | Python | 微软 agentic AI 编程框架 |
| **crewAIInc/crewAI** | 56,723 | Python | 角色扮演自治 agent 协作 |
| **OpenBMB/ChatDev** | 33,942 | Python | LLM 多 Agent 协作开发 |
| **microsoft/semantic-kernel** | 28,428 | C# | LLM 应用 SDK |
| **microsoft/agent-framework** | 12,647 | Python/.NET | 多 agent 编排部署（MIT） |

## 结论
- 要「**六部制角色 + 部门分工**」：`jnMetaCode/agency-agents-zh`（18.9k★，中文生态最贴近）
- 要「**审批流 + 企业级编排**」：`iflytek/astron-agent`（9.2k★，Apache-2.0）
- 要「**多 Agent 通用编排**」：`MetaGPT` / `autogen` / `crewAI`
- `hjcenry/openclaw-corp` 是唯一与三省六部同思路（OpenClaw 组织架构）的项目，但仅 1★，无参考热度价值，可作思路对照