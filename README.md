# MACS — Multi-Agent Collaboration System（三省六部）

> 一个通用的 OpenClaw 多 Agent 协同工作系统。**三省六部**架构，11 个 AI Agent 像真实朝廷团队一样协作。

## 🎯 是什么

基于 OpenClaw 的多 Agent 协同工作框架。一个 **调度 Agent（太子）** 居中协调，一个 **项目经理（尚书省）** 全权执行，**8 个专业 Agent** 各司其职，形成完整的"需求→分析→审议→派发→执行→质检→交付"流水线。

```
老板下发任务
  ↓
太子(鲍澄): 理解需求 → 分析 → 生成需求摘要
  ↓
┌────────── 三省六部 ──────────┐
│                               │
│  中书省(筹微) → 起草 TASK.md    │
│       ↓                       │
│  门下省(审微) → 独立审查/封驳    │
│       ↓                       │
│  准奏 → 派发                   │
│       ↓                       │
│  尚书省(Ld.r) → 全权执行调度     │
│       ↓                       │
│  六部并行执行                  │
│   ├─ 礼部(墨卿) — 文案/翻译     │
│   ├─ 兵部(锋铸) — 前端/开发     │
│   ├─ 工部(绘象) — 视觉/生图     │
│   ├─ 刑部(镜衡) — 质量验收      │
│   └─ 户部(归藏) — 整合交付      │
│       ↓                       │
│  吏部(驿使) → 任务路由          │
│       ↓                       │
│  钦天监(溶萃) → 每日朝报         │
│                               │
└───────────────────────────────┘
  ↓
太子: 最终审查 → 交付老板
```

## 🏛️ 三省六部 Agent 角色

11 个 Agent 各具独立人格和专属技能，按需随时扩编。

| Agent | 官号 | 省/部 | 品级 | 职责 |
|-------|------|------|------|------|
| `main` | 鮱澄 | 太子 | 储君 | 总揽全局、需求分析、最终交付 |
| `ld-r` | Ld.r | 尚书省·尚书令 | 正一品 | 项目管理、全权执行调度 |
| `guihua` | 筹微 | 中书省·中书令 | 正二品 | 需求拆解 → 生成 TASK.md |
| `shenyi` | 审微 | 门下省·侍中 | 正一品 | 独立审查 TASK.md → 准奏或封驳 |
| `paifa` | 驿使 | 吏部·吏部尚书 | 正二品 | 任务路由 → 派发到执行部门 |
| `wenan` | 墨卿 | 礼部·礼部尚书 | 正二品 | 网站文案/品牌故事/SEO/翻译 |
| `daima` | 锋铸 | 兵部·兵部尚书 | 正二品 | 前端开发/功能实现/性能优化 |
| `sheji` | 绘象 | 工部·工部尚书 | 正二品 | 视觉规范/UI设计/图片生成 |
| `shencha` | 镜衡 | 刑部·刑部尚书 | 正二品 | 独立质量验收/对照标准评分 |
| `huizong` | 归藏 | 户部·户部尚书 | 正二品 | 整合交付/生成交付报告 |
| `rongcui` | 溶萃 | 钦天监·朝报官 | 正三品 | 晨间简报/团队状态日报 |

## 🚀 快速安装（即装即用）

```bash
# 1. 克隆
git clone https://github.com/ilxu7z/MACS-pm.git
cd MACS-pm

# 2. 一键安装（自动注册所有 Agent + 创建 workspace + 同步配置）
chmod +x install.sh && ./install.sh

# 3. 添加 Agent 的 API Key（首次需要）
openclaw agents add guihua
# 按提示输入 API Key，然后重新运行 install.sh 同步到所有 Agent

# 4. 启动 Dashboard
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

### 🔄 升级模式（`--mode update`）

如果已经安装过，使用升级模式进行增量更新：

```bash
./install.sh --mode update
# 或简写
./install.sh update
```

升级模式自动完成：
- ✅ 版本比对（读取文件头部 `<!-- version:MAJOR.MINOR.PATCH -->` 标记）
- ✅ **MAJOR 变更** → 备份后覆盖（文件结构不兼容）
- ✅ **MINOR/PATCH 变更** → 增量追加（逐段比对，不重复写入）
- ✅ **版本相同** → 跳过，不做任何操作
- ✅ 大文件（>5MB）跳过，提示手动处理
- ✅ 非 UTF-8 编码文件跳过增量追加，避免乱码
- ✅ 无需重新注册 Agent 或重建 workspace

## 🗑️ 卸载

```bash
# 清理子 Agent workspace（保留 main）
./uninstall.sh --mode clean

# 清理所有 Agent workspace（含 main）
./uninstall.sh --mode clean-all

# 清理 deprecated 标记段落（默认模式）
./uninstall.sh --mode clean-update

# 完全卸载所有 Agent 注册 + 文件
./uninstall.sh --mode uninstall

# 自动确认（跳过确认提示）
./uninstall.sh --mode uninstall --yes
```

| 模式 | 说明 |
|------|------|
| `clean` | 清理子 Agent workspace 目录，保留 main 配置 |
| `clean-all` | 清理所有 Agent 的 workspace（含 main） |
| `clean-update` | 清理文件中带有 `deprecated` 标记的段落（默认），备份保存为 `*.bak.clean-*` |
| `uninstall` | 完全卸载：删除 Agent 注册、配置文件、workspace 目录，恢复环境 |

> ⚠️ 卸载前会自动备份 `openclaw.json` 到 `*.bak.pre-uninstall-*`，方便回滚。

## 📦 版本升级策略

系统采用 **版本标记协议** 实现智能升级，每个受管文件头部包含 HTML 注释格式的版本标记：

```html
<!-- version:v2.0.0-system -->
```

### 版本比较规则

| 版本变更 | 策略 | 说明 |
|---------|------|------|
| 目标不存在 | 创建 | 直接复制 |
| MAJOR 变更 | 覆盖 | 备份 `*.bak.YYYYMMDD-HHMMSS` 后覆盖 |
| MINOR/PATCH 变更 | 增量追加 | 逐段比对，只追加新内容 |
| 版本相同 | 跳过 | 不操作 |

### 增量追加算法

`append_incremental()` 函数实现智能追加：

1. 读取目标文件全部内容到内存
2. 逐段比对源文件段落（以空行分隔）
3. 只追加目标文件中**不存在**的段落
4. 大文件模式（>1MB）使用 grep 批量预检，不加载全量
5. 编码检测：`file -I` 识别非 UTF-8/US-ASCII 文件，跳过追加

> 升级前自动创建备份文件，支持回滚。

## 🔍 OCR 集成

OCR（OpenClaw + Crestodian + RAG）融合系统为三省六部制提供 SDD/CDD 方案支持，实现一键安装升级。

### 安装与验证

安装脚本自动安装 OCR CLI：

```bash
# 验证 OCR 版本
ocr --version

# 如果版本低于 1.8.0，install.sh 自动升级
```

### 规则文件

OCR 规则文件位于 `.github/ocr-rules.md`，包含：

- **版本协议**：文件头部 `<!-- version:MAJOR.MINOR.PATCH-system -->` 标记
- **写入策略**：MAJOR 覆盖 / MINOR 增量追加 / 版本相同跳过
- **大文件处理**：>5MB 提示手动处理，>1MB≤5MB grep 预检
- **编码检测**：`file -I` 检测，非 UTF-8 跳过
- **备份规则**：覆盖/增量追加前自动创建备份文件

此规则文件同时被 GitHub Actions 工作流引用，确保 CI/CD 流程中的版本一致性。

---

## 📋 看板 Dashboard

启动后访问 `http://127.0.0.1:7891`，提供：

- **旨意看板** — 所有任务的实时状态（Kanban 列视图）
  - 自动发现 OpenClaw 运行时的活跃会话，同步到看板
  - 支持手动创建/叫停/恢复任务
  - **阻塞任务巡检** — 每 15 分钟自动扫描 Blocked 任务，发现时通知
- **官员总览** — 11 个 Agent 的 Token 消耗、活跃度、功勋排行
- **技能配置** — 全局技能池（27+ 个共享技能）+ 每个 Agent 独立开关
- **模型配置** — 每个 Agent 独立切换 LLM 模型
- **奏折阁** — 已完成任务自动归档，可回溯

### Dashboard 页面

| 页面 | 功能 |
|------|------|
| `/` 看板 | 任务 Kanban 视图（Doing/Review/Blocked/Done） |
| `/officials` 官员 | 各 Agent 消耗统计和活跃度 |
| `/config` 配置 | 每个 Agent 的模型设置 + 全局技能开关 |
| `/archive` 存档 | 已完成任务归档查询 |

## 🎓 全局技能池（v4 新增）

27+ 个预置技能自动发现并共享到所有 Agent：
- `design-taste` — 设计品味方法论
- `systematic-debugging` — 系统化调试流程
- `bash-safety` — Shell 安全规范
- `test-driven-development` — TDD 开发规范
- `brainstorming` — 头脑风暴方法论
- …等 27+ 个技能

所有 Agent 在 `/config` 页面可以看到全局技能池，一键启用/禁用。

## 🛡️ 自动保护机制（v4 新增）

- **exec 超时熔断** — 所有 shell 命令 600 秒自动终止，防止脚本卡死阻塞整个流程
- **阻塞任务巡检** — 后台每 15 分钟扫描 Blocked 任务，超过 30 分钟自动通知
- **调度自动恢复** — 任务停滞超 600 秒自动触发重试 + 升级机制（门下省→尚书省）
- **Gateway 重启保护** — 独立后台进程不依赖 Gateway 生命周期

## 🔧 工作流

### 什么时候走三省六部

太子（鮱澄）根据任务复杂度自动判断：

#### 🔴 走三省六部流程（复杂任务）

| 信号 | 示例 |
|------|------|
| 涉及多人协作/多环节 | "帮我做个产品官网" |
| 需要计划+拆解 | "写一份营销方案" |
| 需要独立审查 | "出一份竞品分析" |
| 有交付物需多方评审 | "帮出一套品牌VI方案" |
| 用户主动触发三省六部 | "下旨：产品画册设计" |

#### 🟢 直接回答，不走流程（简单任务）

| 情况 | 示例 |
|------|------|
| 问信息 | "XX产品的参数是什么" |
| 小改动 | "把这个按钮改成蓝色" |
| 讨论/决策 | "你觉得这个方案怎么样" |
| 查看状态 | "看看看板有没有异常" |

### 如何主动触发

说以下任意一句，调度 Agent 就会启动三省六部流程：

```
用三省六部制，帮我做个XX
下旨：XX
启动三省六部，帮我XX
```

看板上也有「👑 下旨」按钮，效果一样。

### 🔄 完整流程

```
你说: "下旨：帮我做冲调类产品官网"

太子:
1. 理解需求 → 生成需求摘要
2. → 筹微(中书省) → 产出 TASK.md
3. → 审微(门下省) → 独立审查 → 准奏/封驳
4. 封驳则修改 → 重新审议
5. 准奏 → Ld.r(尚书省) → 全权派发执行
6. → 六部并行执行：
   ├─ 墨卿(礼部) → 文案重写/多语种翻译
   ├─ 锋铸(兵部) → 前端开发/页面实现
   ├─ 绘象(工部) → 视觉设计/图片生成
   ├─ 镜衡(刑部) → 独立质量验收
   └─ 归藏(户部) → 整合交付包
7. 太子最终审查 → 交付老板
```

**你的投入：给任务 → 关键决策点确认 → 收结果。中间不用管。**

## 🔄 换电脑 / 重装部署

```bash
git clone https://github.com/ilxu7z/MACS-pm.git
cd MACS-pm
./install.sh
./start.sh
```

所有 Agent 配置和注册信息通过 Git 同步，换机一键恢复。

## ⚔️ 扩编 Agent

当项目需要当前军团没有的角色时，一键创建：

```bash
# 用法: add-agent.sh <agent_id> <display_name> <role> <description>
chmod +x scripts/add-agent.sh
./scripts/add-agent.sh shuju "数枢" "数据分析师" "数据采集、清洗、报表生成"
```

脚本自动完成：
1. 生成 SOUL.md（智能推荐适合该角色的 LLM 模型）
2. 注册到 `registry.json`
3. 注册到 OpenClaw
4. 创建 workspace + 同步 API Key
5. 更新 `sync_agent_config.py` 让 Dashboard 可配置

然后 `git add -A && git commit && git push`，任何电脑 clone 后 `./install.sh` 即可同步。

## 🔌 模型路由配置

系统支持每个 Agent 独立配置 LLM 模型，通过 Dashboard 管理或直接编辑 `registry.json`：

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
- **推理/分析型**（规划、审查）→ DeepSeek / GPT
- **文案型**（文案）→ GLM-5.1
- **代码型**（开发）→ Claude
- **视觉型**（设计/生图）→ Gemini

## 🧬 技术架构

```
OpenClaw Multi-Agent Runtime
       ↓ 自动发现(15s间隔)
sync_from_openclaw_runtime.py
       ↓
tasks_source.json (看板数据源)
       ↓
Dashboard (React + Vite + Python http.server)
       ↓
看板UI、官员统计、模型配置、归档
```

| 组件 | 技术栈 |
|------|--------|
| Agent 运行时 | OpenClaw Runtime |
| 数据同步 | Python（零外部依赖, 仅 stdlib） |
| Dashboard 后端 | Python `http.server`（零外部依赖） |
| Dashboard 前端 | React 18 + TypeScript + Vite |
| 数据存储 | JSON 文件 |

## 📄 致谢

本项目看板引擎和架构设计受 [edict (三省六部)](https://github.com/cft0808/edict) 启发，Agent 层和调度逻辑完全重写以适配 OpenClaw 多 Agent 协同场景。

## 📜 License

MIT
