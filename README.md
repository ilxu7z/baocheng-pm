# 三省六部 · OpenClaw 多 Agent 协同工作系统

> 一套基于 OpenClaw Runtime 的多 Agent 协作框架。11 个 AI Agent 像朝廷团队一样分工协作，从需求拆解到交付验收，全程自动化流水线。  
> 附带 **OCR 代码审查**（open-code-review 深度融合）——看板触发式自动审查，critical/high 缺陷自动建 P0 任务。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 目录

- [一、架构总览](#一架构总览)
- [二、快速开始](#二快速开始)
- [三、系统组件](#三系统组件)
  - [3.1 Agent 角色](#31-agent-角色)
  - [3.2 看板 Dashboard](#32-看板-dashboard)
  - [3.3 OCR 代码审查](#33-ocr-代码审查)
  - [3.4 全局技能池](#34-全局技能池)
  - [3.5 模型路由](#35-模型路由)
- [四、工作流](#四工作流)
  - [4.1 三省六部完整流程](#41-三省六部完整流程)
  - [4.2 触发条件](#42-触发条件)
  - [4.3 OCR 自动审查在流程中的位置](#43-ocr-自动审查在流程中的位置)
- [五、部署与运维](#五部署与运维)
  - [5.1 安装](#51-安装)
  - [5.2 升级](#52-升级)
  - [5.3 自启动（systemd）](#53-自启动systemd)
  - [5.4 卸载](#54-卸载)
  - [5.5 扩编 Agent](#55-扩编-agent)
  - [5.6 换机/重装部署](#56-换机重装部署)
- [六、OCR 融合深度说明](#六ocr-融合深度说明)
  - [6.1 架构](#61-架构)
  - [6.2 API 端点](#62-api-端点)
  - [6.3 自动触发机制](#63-自动触发机制)
  - [6.4 去重与并发](#64-去重与并发)
- [七、技术架构](#七技术架构)
- [八、变更日志](#八变更日志)
- [九、致谢与 License](#九致谢与-license)

---

## 一、架构总览

```
老板（需求方）
  │
  ▼
╔══════════════════════════════════════════════════════╗
║                    总办 (鮱澄)                        ║
║              总揽全局 · 需求分析 · 最终交付             ║
╚══════════════════════════════════════════════════════╝
  │
  ┌─────────────── 三省六部 ───────────────┐
  │                                         │
  │  ┌──────────┐    ┌──────────┐           │
  │  │ 规划部    │ →  │ 审议部    │           │
  │  │ 筹微     │    │ 审微     │           │
  │  │ 起草方案  │    │ 独立审查  │           │
  │  └──────────┘    └──────────┘           │
  │       │                │                │
  │       ▼                ▼                │
  │  ┌──────────────────────────────────┐   │
  │  │       执行办（Ld.r）              │   │
  │  │       全权执行调度                │   │
  │  └──────────────────────────────────┘   │
  │       │                                │
  │       ▼                                │
  │  ┌──────────────────────────────────┐   │
  │  │        六部并行执行              │   │
  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
  │  │  │   内容部   │ │   开发部   │ │   设计部   │  │   │
  │  │  │   墨卿    │ │   锋铸    │ │   绘象    │  │   │
  │  │  │   文案    │ │   开发    │ │   视觉    │  │   │
  │  │  └──────────┘ └──────────┘ └──────────┘  │   │
  │  │  ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
  │  │  │   质控部   │ │ 交付汇总处 │ │ 人力路由处 │  │   │
  │  │  │   镜衡    │ │   归藏    │ │   驿使    │  │   │
  │  │  │   验收    │ │   整合    │ │   路由    │  │   │
  │  │  └──────────┘ └──────────┘ └──────────┘  │   │
  │  └──────────────────────────────────┘   │
  │                                         │
  └─────────────────────────────────────────┘
  │
  ▼
╔══════════════════════════════════════════════════════╗
║               OCR 代码审查自动触发                    ║
║     锋铸完成 → Review 状态 → 自动审查 → 缺陷建任务    ║
╚══════════════════════════════════════════════════════╝
  │
  ▼
  交付物（交付报告 · 代码 · 设计 · 文案）

```

### 核心设计原则

| 原则 | 说明 |
|------|------|
| **三省制衡** | 中书起草 → 门下审查 → 尚书执行，三方独立互不隶属 |
| **六部专业化** | 每个 Agent 专精一个领域，不跨职能 |
| **总办不粘锅** | 总办只做需求理解和最终交付，不参与具体执行，确保客观 |
| **自动审查** | OCR 代码审查在锋铸（开发）完成后自动触发，结果不阻塞流程 |
| **零外部依赖** | Dashboard 后端仅用 Python stdlib，无 pip install 依赖 |

---

## 二、快速开始

### 前置条件

| 依赖 | 版本要求 | 说明 |
|------|---------|------|
| OpenClaw | v2026.7.1+ | Agent 运行时 |
| Python | 3.10+ | Dashboard 后端 |
| Node.js | 18+ | OCR CLI（可选，如不启用 OCR 可跳过） |

### 安装

```bash
# 1. 克隆仓库
git clone https://github.com/ilxu7z/oc-macs.git
cd oc-macs

# 2. 安装并注册所有 Agent
chmod +x install.sh && ./install.sh

# 3. 首次需要为子 Agent 配置 API Key
openclaw agents add guihua
# 按提示输入 API Key，然后重新运行 install.sh 同步到所有 Agent

# 4. 启动看板
chmod +x start.sh && ./start.sh

# 5. 打开看板
open http://127.0.0.1:7891
```

安装脚本自动完成：
- ✅ 注册 11 个 Agent 到 OpenClaw
- ✅ 创建 workspace 和 skills 目录
- ✅ 同步 API Key 到所有 Agent
- ✅ 初始化 Dashboard 数据文件
- ✅ 配置 exec 超时保护（600 秒熔断）

### 启动后验证

```bash
# 看板健康检查
curl http://127.0.0.1:7891/healthz

# OCR 状态检查（如已安装）
curl http://127.0.0.1:7891/api/ocr/status
```

---

## 三、系统组件

### 3.1 Agent 角色

11 个 Agent 各具独立人格和专属技能，按需可随时扩编。

| Agent ID | 官号 | 省/部 | 品级 | 职责 | 推荐模型 |
|----------|------|------|:----:|------|---------|
| `main` | 鮱澄 | 总办 | 项目总控 | 总揽全局、需求分析、最终交付 | DeepSeek V4 |
| `ld-r` | Ld.r | 执行办·执行经理 | 正一品 | 项目管理、全权执行调度、任务分解 | DeepSeek V4 |
| `guihua` | 筹微 | 规划部·规划师 | 正二品 | 需求拆解 → 生成 TASK.md 方案 | DeepSeek V4 Pro |
| `shenyi` | 审微 | 审议部·审议官 | 正一品 | 独立审查 TASK.md → 通过或驳回 | DeepSeek V4 Pro |
| `paifa` | 驿使 | 人力路由处·人力路由负责人 | 正二品 | 任务路由 → 派发到执行部门 | DeepSeek V4 Flash |
| `wenan` | 墨卿 | 内容部·内容负责人 | 正二品 | 网站文案/品牌故事/SEO/翻译 | GLM-5.1 |
| `daima` | 锋铸 | 开发部·开发负责人 | 正二品 | 前端开发/功能实现/性能优化 | Claude / DeepSeek |
| `sheji` | 绘象 | 设计部·设计负责人 | 正二品 | 视觉规范/UI设计/图片生成 | Gemini |
| `shencha` | 镜衡 | 质控部·质控负责人 | 正二品 | 独立质量验收/对照标准评分 | DeepSeek V4 |
| `huizong` | 归藏 | 交付汇总处·交付负责人 | 正二品 | 整合交付/生成交付报告 | DeepSeek V4 Flash |
| `rongcui` | 溶萃 | 运维组·运维专员 | 正三品 | 晨间简报/团队状态日报 | DeepSeek V4 Flash |

### 3.2 看板 Dashboard

启动后访问 `http://127.0.0.1:7891`，提供以下页面：

| 页面 | 路由 | 功能 |
|------|------|------|
| **旨意看板** | `/` | 任务 Kanban 视图（Taizi/Zhongshu/Menxia/Assigned/Doing/Review/Done）<br>自动发现 OpenClaw 运行时活跃会话并同步到看板<br>支持手动创建/叫停/恢复/归档任务<br>15 分钟自动巡检阻塞任务 |
| **官员总览** | `/officials` | 11 个 Agent 的 Token 消耗、活跃度、功勋排行 |
| **配置中心** | `/config` | 每个 Agent 独立切换 LLM 模型 + 全局技能池开关 |
| **存档阁** | `/archive` | 已完成任务归档，可回溯历史 |

### 3.3 OCR 代码审查

集成 [open-code-review](https://github.com/alibaba/open-code-review)（阿里 OCR）v1.8.3，为三省六部流程提供自动代码审查能力。

**核心能力**：

| 能力 | 说明 |
|------|------|
| **diff 审查** | 基于 git diff 的增量代码审查，只审查变更部分 |
| **全量扫描** | 对整个目录做全量扫描，不依赖 git |
| **断点续审** | 超时或中断后可恢复，不丢已审查结果 |
| **自动触发** | 锋铸完成 → 任务进入 Review 状态时自动触发 |
| **去重保护** | 同一 task + 同一 commit hash 只审一次 |
| **并发控制** | 最多同时 N 个审查（Semaphore 保护） |
| **缺陷分级** | critical / high / medium / low，自动筛选 critical+high 建 P0 任务 |

**安装 OCR CLI**：

```bash
npm install -g @alibaba-group/open-code-review
# 或通过 install.sh 自动安装
# 配置 LLM 后验证
ocr --version
```

LLM 配置见 `~/.opencodereview/config.json`，支持 provider-based 格式（kimi / deepseek / z-ai 等）。

### 3.4 全局技能池

27+ 个预置技能自动发现并共享到所有 Agent：

`design-taste` · `systematic-debugging` · `bash-safety` · `test-driven-development` · `brainstorming` · `diagram-maker` · `image-generation` · `meme-maker` · …等

所有 Agent 在 Dashboard `/config` 页面可看到全局技能池，一键启用/禁用，无需手动编辑配置文件。

### 3.5 模型路由

每个 Agent 可独立配置 LLM 模型，通过 Dashboard 编辑或直接修改 `registry.json`：

```json
{
  "guihua": {
    "model": "deepseek/deepseek-v4-pro",
    "name": "筹微",
    "skills": ["分析", "规划"]
  },
  "wenan": {
    "model": "Pro/zai-org/GLM-5.1",
    "name": "墨卿",
    "skills": ["文案", "翻译"]
  }
}
```

推荐按角色匹配模型：

| 角色类型 | 推荐模型 | 原因 |
|---------|---------|------|
| 推理/分析（规划、审查） | DeepSeek V4 Pro / GPT | 长上下文、深度推理 |
| 文案（墨卿） | GLM-5.1 | 中文文案质量高 |
| 代码（锋铸） | Claude / DeepSeek V4 | 代码生成准确 |
| 视觉（绘象） | Gemini | 多模态理解强 |

---

## 四、工作流

### 4.1 三省六部完整流程

```
你说: "下旨：帮我做冲调类产品官网"

1. 总办（鮱澄）
   └─ 理解需求 → 生成需求摘要

2. 规划部（筹微）
   └─ 产出 TASK.md 方案

3. 审议部（审微）
   ├─ 独立审查方案
   ├─ 通过 → 进入派发
   └─ 驳回 → 退回规划部修改 → 重新审议

4. 执行办（Ld.r）
   └─ 全权派发执行

5. 六部并行执行
   ├─ 内容部（墨卿）→ 文案重写/多语种翻译
   ├─ 开发部（锋铸）→ 前端开发/页面实现
   ├─ 设计部（绘象）→ 视觉设计/图片生成
   ├─ 质控部（镜衡）→ 独立质量验收
   └─ 交付汇总处（归藏）→ 整合交付包

6. → 自动触发 OCR 代码审查（锋铸完成 → Review 状态）

7. 总办（鮱澄）
   └─ 最终审查 → 交付老板

你的投入: 给任务 → 关键决策点确认 → 收结果。中间不用管。
```

### 4.2 触发条件

总办根据任务复杂度自动判断是否走三省六部流程：

#### 🔴 走三省六部流程（复杂任务）

| 信号 | 示例 |
|------|------|
| 涉及多人协作/多环节 | "帮我做个产品官网" |
| 需要计划+拆解 | "写一份营销方案" |
| 需要独立审查 | "出一份竞品分析" |
| 有交付物需多方评审 | "帮出一套品牌VI方案" |
| 用户主动触发 | "下旨：产品画册设计" / "用三省六部制" |

#### 🟢 直接回答，不走流程（简单任务）

| 情况 | 示例 |
|------|------|
| 问信息 | "XX产品参数是什么" |
| 小改动 | "把这个按钮改成蓝色" |
| 讨论/决策 | "你觉得这个方案怎么样" |
| 查看状态 | "看看看板有没有异常" |

### 4.3 OCR 自动审查在流程中的位置

锋铸（开发部）完成代码产出后，任务状态推进到 `Review`，此时看板自动触发 OCR 审查：

```
锋铸完成 → 推进到 Review
  │
  ▼
看板 server.py 自动调用 ocr_auto_trigger
  ├─ 检查去重缓存（同 task + 同 commit 跳过）
  ├─ 执行 ocr_review（基于 git diff）
  ├─ 解析返回的评论
  ├─ 筛选 critical / high 级别缺陷
  └─ 构造 P0 任务对象（写入 task['ocr_auto']）
  │
  ▼
进入正常审微流程（不阻塞，OCR 异常由 try/except 包裹）
```

> ⚠️ OCR 审查是**异步副作用**，不阻塞状态流转。即使 LLM 调用超时或失败，任务仍正常进入 Review 状态。

---

## 五、部署与运维

### 5.1 安装

```bash
git clone https://github.com/ilxu7z/oc-macs.git
cd oc-macs
./install.sh
```

安装脚本自动完成：
- 注册 11 个 Agent 到 OpenClaw
- 创建 workspace 和 skills 目录
- 同步 API Key 到所有 Agent
- 初始化 Dashboard 数据文件
- 配置 exec 超时保护（600 秒熔断）
- 安装 OCR CLI（如 Node.js 已就绪）

### 5.2 升级

```bash
./install.sh --mode update
# 或简写
./install.sh update
```

升级模式特性：

| 版本变更 | 策略 | 说明 |
|---------|------|------|
| MAJOR 变更 | 覆盖 | 备份 `*.bak.YYYYMMDD-HHMMSS` 后覆盖 |
| MINOR/PATCH 变更 | 增量追加 | 逐段比对，只追加新内容 |
| 版本相同 | 跳过 | 不操作 |

版本标记基于文件头部 HTML 注释 `<!-- version:MAJOR.MINOR.PATCH -->`。

### 5.3 自启动（systemd）

三省六部看板通过 systemd user service 管理，随 OpenClaw Gateway 自动启停。

```bash
# 安装 systemd 服务
cp oc-macs-dashboard.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now oc-macs-dashboard.service

# 查看状态
systemctl --user status oc-macs-dashboard.service

# 查看日志
journalctl --user -u oc-macs-dashboard.service -f
```

依赖关系：

```
openclaw-gateway.service
  └─ BindsTo → oc-macs-dashboard.service
```

- Gateway 启动 → 看板自动启动
- Gateway 停止 → 看板自动停止
- 看板崩溃 → `Restart=always`，5 秒后自动重启
- 电脑重启 → `systemctl --user start openclaw-gateway` 即可全部恢复

### 5.4 卸载

```bash
# 清理子 Agent workspace（保留 main）
./uninstall.sh --mode clean

# 清理所有 Agent workspace（含 main）
./uninstall.sh --mode clean-all

# 清理 deprecated 标记段落
./uninstall.sh --mode clean-update

# 完全卸载
./uninstall.sh --mode uninstall

# 自动确认（跳过提示）
./uninstall.sh --mode uninstall --yes
```

> ⚠️ 卸载前自动备份 `openclaw.json` 到 `*.bak.pre-uninstall-*`，方便回滚。

### 5.5 扩编 Agent

需要新角色时，一键创建：

```bash
chmod +x scripts/add-agent.sh
./scripts/add-agent.sh shuju "数枢" "数据分析师" "数据采集、清洗、报表生成"
```

脚本自动完成：
1. 生成 SOUL.md（智能推荐适合该角色的 LLM 模型）
2. 注册到 `registry.json`
3. 注册到 OpenClaw
4. 创建 workspace + 同步 API Key
5. 更新 `sync_agent_config.py` 使 Dashboard 可配置

### 5.6 换机/重装部署

```bash
git clone https://github.com/ilxu7z/oc-macs.git
cd oc-macs
./install.sh
./start.sh
```

所有 Agent 配置和注册信息通过 Git 同步，换机一键恢复。

---

## 六、OCR 融合深度说明

### 6.1 架构

```
┌─────────────────────────────────────────────────────┐
│                   看板 Dashboard                      │
│                                                       │
│  /api/ocr/* 端点 ← 手动触发（curl / 前端面板）         │
│  handle_advance_state → Review 时自动触发             │
│                                                       │
└──────────────────────┬────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              scripts/ocr_bridge.py                    │
│                                                       │
│  ocr_review()  ──  diff-based 审查                    │
│  ocr_scan()    ──  全量扫描                          │
│  ocr_resume()  ──  断点续审                          │
│  ocr_status()  ──  CLI 状态检查                      │
│  save_ocr_result() ── 原子写入结果文件                │
│                                                       │
│  并发控制: threading.Semaphore(MAX_CONCURRENT)        │
│  超时保护: subprocess.run(timeout=...)                │
└──────────────────────┬────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              scripts/ocr_auto_trigger.py              │
│                                                       │
│  auto_review_and_create_tasks()                       │
│    ├─ 去重检查（同 task + 同 commit 跳过）            │
│    ├─ 调用 ocr_review()                               │
│    ├─ 筛选 critical/high 缺陷                         │
│    └─ 构造 P0 任务对象                                │
│                                                       │
│  data/ocr_dedup_cache.json ← 去重缓存                 │
└─────────────────────────────────────────────────────┘
                       │
                       ▼
           open-code-review CLI (v1.8.3)
           ~/.opencodereview/config.json ← LLM 配置
```

### 6.2 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/ocr/status` | 检查 OCR CLI 版本和 LLM 配置状态 |
| POST | `/api/ocr/review` | diff 审查，body: `{repoDir, rulePath, from?, to?}` |
| POST | `/api/ocr/scan` | 全量扫描，body: `{repoDir, rulePath, paths?}` |
| POST | `/api/ocr/resume` | 断点续审，body: `{repoDir, rulePath, sessionId}` |
| POST | `/api/ocr/results` | 查询历史结果，body: `{taskId?, sessionId?}` |

### 6.3 自动触发机制

在 `dashboard/server.py` 的 `handle_advance_state` → `_do_advance` 中（第 3250 行附近）：

```python
if next_state == 'Review':
    try:
        # 动态导入 ocr_auto_trigger
        trigger_result = ocat.auto_review_and_create_tasks(task_id, repo_dir)
        if trigger_result.get('tasks_created'):
            task['ocr_auto'] = {
                'triggered': True,
                'created': trigger_result['tasks_created']
            }
            # 写入 flow_log
    except Exception as e:
        log.warning(f"OCR 自动审查触发失败: {e}")
```

### 6.4 去重与并发

**去重**：`data/ocr_dedup_cache.json` 存储 `{task_id: commit_hash}` 映射。同一 task 同一 commit 直接跳过，不重复调用 LLM。

**并发**：`ocr_bridge.py` 中使用 `threading.Semaphore(MAX_CONCURRENT)` 保护，最多同时运行 N 个 OCR 审查进程。

---

## 七、技术架构

```
OpenClaw Multi-Agent Runtime
       │
       │ 自动发现（15s 间隔）
       ▼
sync_from_openclaw_runtime.py
       │
       ▼
tasks_source.json（看板数据源）
       │
       ▼
Dashboard（Python http.server + HTML/JS）
       │
       ├─ 看板 UI（Kanban 视图）
       ├─ 官员统计（Token/活跃度）
       ├─ 配置中心（模型/技能）
       ├─ 存档阁（历史归档）
       └─ OCR 端点（代码审查）
```

| 组件 | 技术栈 |
|------|--------|
| Agent 运行时 | OpenClaw Runtime |
| 数据同步 | Python（零外部依赖，仅 stdlib） |
| Dashboard 后端 | Python `http.server`（ThreadingHTTPServer） |
| Dashboard 前端 | 原生 HTML/JS + CSS |
| 数据存储 | JSON 文件 + 文件锁 |
| OCR 代码审查 | open-code-review v1.8.3 |
| 自启动 | systemd user service（BindsTo openclaw-gateway） |

---

## 八、变更日志

参见 [CHANGELOG.md](CHANGELOG.md)。

### 近期关键版本

| 版本 | 日期 | 内容 |
|------|------|------|
| v2.0.0 | 2026-07-31 | 部署系统全面升级，OCR 深度融合 Phase 1+2 |
| v2.1.0 | 2026-07-31 | systemd 自启动修复，自动触发 OCR 审查 |

---

## 九、致谢与 License

本项目看板引擎和架构设计受 [edict（三省六部）](https://github.com/cft0808/edict) 启发，Agent 层和调度逻辑完全重写以适配 OpenClaw 多 Agent 协同场景。

OCR 代码审查能力基于 [alibaba/open-code-review](https://github.com/alibaba/open-code-review) v1.8.3。

**License**: MIT