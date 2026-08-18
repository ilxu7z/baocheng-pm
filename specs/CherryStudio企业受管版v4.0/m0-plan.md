# M0 求证执行计划 · JJC-20260809-001「CherryStudio 企业受管版 M0 求证验证」

**执行方**：军师 guihua（规划部）
**上游依据**：JJC-20260807-002「CherryStudio 企业受管版 v4.0 深度任务分解与开发文档」
**求证对象**：`/home/chee/.openclaw/workspace-main/cherry-src/`（CherryHQ/cherry-studio **v2.0.1**）
**性质**：执行计划（非执行结果）。基于对 cherry-src 实际文件预读（package.json、electron.vite.config.ts、pnpm-workspace.yaml、src 目录树、IpcRouter、applyMigrations、electron-builder.yml、LICENSE、.github/CI、docs/），非臆断。

---

## 0. 预读结论（写计划前已确认的工程基线事实）

| 事实项 | 证据 | 影响 |
|---|---|---|
| **构建工具** | electron-vite；但 `pnpm-workspace.yaml` 将 vite override 为 **`rolldown-vite@7.3.0`**（非官方 Vite） | 构建栈非标准，版本兼容敏感 |
| **路由框架** | **TanStack Router**（`@tanstack/router-plugin/vite`，文件式路由，`src/renderer/routes/`，生成 `routeTree.gen.ts` 1088 行）——**非 React Router** | 002「React Router 路由表」假设需修正 |
| **IPC 机制** | 非逐条 ipcMain.handle。**单一通道 `IpcChannel.IpcApi_Request`** → `IpcApiService` → `IpcRouter`（zod 校验 + O(1) 派发），handler 在 `src/main/ipc/handlers/`（31 个 domain handler），schema 在 `src/shared/ipc/schemas/` | 受管化拦截点：`IpcApiService.handleRequest` 的 `validateSender` 门 + 单一 funnel |
| **引擎约束** | `engines.node: >=24.11.1 <24.16.0` + `engine-strict=true`；当前 **node v24.18.0** | 接近上限，pnpm 可能因 engine-strict 报错 |
| **pnpm 缺失** | `pnpm: 未找到命令` | 需先装 pnpm（corepack 或 npm i -g） |
| **依赖未安装** | `node_modules` 不存在、`out/` 不存在 | 必须 `pnpm install` |
| **数据层** | `src/main/data/db/` = **drizzle-orm + better-sqlite3**；迁移 `migrations/sqlite-drizzle/`（0000-0005）+ `applyMigrations.ts`（PRAGMA FK + customSqls FTS5 重放） | DB 改造挂点明确 |
| **打包** | `electron-builder.yml`（appId `com.kangfenmao.CherryStudio`，协议 `cherrystudio://`），脚本 `build:linux` 等 | 受管化需改 appId/productName/协议/签名 |
| **许可** | **AGPL-3.0** | 企业受管化合规风险，需法务评估 |
| **CI** | `.github/workflows/ci.yml` + release/nightly 等 20 个 workflow | 可从 upstream CI 裁剪 |
| **关键模块规模** | apiGateway 42 文件（ApiGatewayService.ts 239 行，Elysia 栈在 devDeps）；knowledge 95；mcp 86；AnalyticsService 单文件 114 行；provider-registry 153；aiCore 56 | 002 关注模块全定位，规模可控 |
| **源码规模** | main 1675 .ts/~41 万行；renderer 2513；shared 308；preload 4 | 基线盘点工作量明确 |
| **窗口** | main/quickAssistant/selection(toolbar+action)/migrationV2/userDataRelocation/subWindow（renderer rollup input 6 入口） | 受管化 UI 需逐窗口确认 |

> ⚠️ **对 002 关键修正**：002 若写「React Router」或「ipcMain.handle 逐条注册」，M0 证伪这两点，回填须纠正为 TanStack Router + 单一 IpcApi funnel。

---

## 1. 求证清单（M0-01 … M0-16）

每条含：要验证什么 / 怎么验证 / 预期产出 / 通过判据。

### A. 前置环境（先做，构建前提）
**M0-01 pnpm 可用性**：`corepack --version`；无则 `npm i -g pnpm@<lockfile 版本>`（查 pnpm-lock.yaml 头部）。判据：pnpm --version 可执行且与 lockfile 匹配。
**M0-02 node 版本合规**：`node -v`（v24.18.0）对照 engines。v24.18.0 超上限 0.02，engine-strict 可能拒绝，需实测 `pnpm install` 是否报 Unsupported engine；若拒绝用 nvm 切 24.12~24.15 [NEEDS CLARIFICATION：是否允许 nvm]。
**M0-03 网络可达性**：`npm ping` / `curl -sI https://registry.npmjs.org` / `curl -sI https://github.com`。任一可达继续；双不可达 → M0-NN 降级。

### B. 构建（核心，前置其他全部）
**M0-04 `pnpm install` 全量**：注意 8 patchedDependencies + better-sqlite3 postinstall build + electron 二进制下载。判据：exit 0，node_modules 出现，node_modules/electron 存在。
**M0-05 构建脚本与产物确认**：`cat package.json | jq '.scripts.build'` → `pnpm run typecheck && electron-vite build`；读 electron-builder.yml build 段。判据：脚本语义 + 产物路径（out/main/main.js、out/preload/、out/renderer/）确认。
**M0-06 `pnpm build` 通过**：`pnpm run build`（先 build @cherrystudio/ai-sdk-provider）。判据：exit 0；out/main/main.js、out/renderer/**/index.html、out/preload/preload.js 存在。⚠️ 10-20 分钟，后台跑。
**M0-07 dev 启动**：`pnpm dev`（= rebuild:electron + download:binaries + dotenv electron-vite dev）。判据：窗口打开，观察 HMR。网络受限仅记录脚本语义。
**M0-08 热更新机制确认**：读 electron.vite.config.ts renderer 段（@tanstack/router-plugin + react-swc + @tailwindcss/vite）；改 settings/about.tsx 观察 HMR；改 src/main/ handler 观察主进程重启。判据：renderer ≤3s 热更；main 触发重建。

### C. 基线盘点（静态，可并行）
**M0-09 版本与依赖基线**：`cat package.json` + pnpm-lock.yaml lockfileVersion。产出依赖总数 + 关键依赖清单（electron/better-sqlite3/drizzle-orm/@tanstack/router/elysia/electron-updater/electron-builder/vite→rolldown-vite override）。
**M0-10 目录结构与关键模块规模**：`find src -maxdepth 2 -type d` + 对 apiGateway/knowledge/mcp/AnalyticsService/provider-registry/aiCore 用 find|wc -l + wc -l。产出目录树 + 规模表。
**M0-11 前端路由结构**：`find src/renderer/routes -maxdepth 3` + routeTree.gen.ts Route 树 + settings/* 路由表。判据：确认受管化设置页挂点 = routes/settings/ 新增文件自动进路由树。
**M0-12 IPC 路由机制**：读 IpcRouter.ts / IpcApiService.ts / ipcSchemas.ts / ipcHandlers.ts。产出 IPC 调用链图 + handler 清单。判据：确认拦截点 = handleRequest 的 validateSender 后加受管策略门 + IpcRouter.dispatch 白名单。
**M0-13 数据层与迁移机制**：读 src/main/data/db/ + migrations/sqlite-drizzle/（0000-0005）+ docs/references/data/。判据：确认 DB 改造挂点 = 新增 drizzle migration + customSqls。
**M0-14 electron-builder 打包配置**：读 electron-builder.yml 全量。产出打包配置摘要 + 受管化需改项（appId/productName/协议 scheme/签名/自动更新 publish 端点）。
**M0-15 CI 现状**：读 .github/workflows/ci.yml + release.yml + nightly-build.yml 关键 step。产出 CI 流水线骨架（可复用构建命令序列）。
**M0-16 许可证/AGPL 合规初查**：`head LICENSE`（已确认 AGPL-3.0）+ README 许可声明 + find packages LICENSE。产出合规风险清单；结论标 [NEEDS CLARIFICATION：法务]。

### D. 网络受限降级方案
**M0-NN（若 M0-03 双不可达）**：不跑 pnpm install。① 静态读 pnpm-lock.yaml 完整依赖树（已存在 1MB）；② 查 pnpm store 缓存 [NEEDS CLARIFICATION：环境是否有 store]；③ 用 lockfile+package.json 完成 C 组静态盘点；④ M0-04/06/07/08 降级为「静态分析构建脚本 + 标记待网络恢复」，构建通过判据改为「代码层面静态可验证」。判据：C 组全产出；B 组标 BLOCKED-ON-NETWORK 而非失败。

---

## 2. 执行顺序
**串行前置**：M0-01 pnpm → M0-02 node → M0-03 网络探测 → M0-04 install（后台）→ M0-06 build（后台）
**并行组**（M0-06 启动后）：[M0-09][M0-10][M0-11][M0-12][M0-13][M0-14][M0-15][M0-16]
**构建成功后才做**：M0-07 dev 启动 → M0-08 热更新实测

## 3. 分工
- **daima（研发主管）主执行**：M0-01~08（环境/构建/热更新）+ M0-09~13（基线/路由/IPC/数据）
- **rongcui（运维）协助**：M0-14（打包）/M0-15（CI）/M0-03（网络）
- **产出回填**：M0 求证结果 → 回填 002 方案（消除「React Router」错误假设、确认 IPC 拦截点、DB 挂点、打包改造点）
- **验收**：shencha 对照本计划判据逐条核验

## 4. 风险与对策
| 风险 | 对策 |
|---|---|
| node 超 engines 上限被 engine-strict 拒 | nvm 切 24.12~24.15 或临时关 engine-strict |
| pnpm 缺失/版本不符 | corepack 或 npm i -g pnpm@lockfile 版本 |
| electron 二进制下载超时 | 配 ELECTRON_MIRROR 镜像 |
| rolldown-vite 兼容问题 | 记录报错，评估降级官方 vite |
| 构建 10-20 分钟 | 后台跑，先做 C 组静态项 |
| 网络不可达 | M0-NN 降级静态求证，B 组标 BLOCKED-ON-NETWORK |
| AGPL 合规 | T002 前置法务评估，不阻塞 M0 工程求证 |

## 5. 回填点（M0 求证消除的 002 不确定性）
1. 「React Router」→ 证伪，改 TanStack Router（M0-11）
2. 「ipcMain.handle 逐条」→ 证伪，改单一 IpcApi funnel（M0-12）
3. IPC 受管化拦截点明确：IpcApiService.handleRequest validateSender 后 + IpcRouter.dispatch 白名单（M0-12）
4. DB 改造挂点明确：drizzle migration + customSqls FTS5（M0-13）
5. 打包改造点明确：appId/productName/协议/sign/publish（M0-14）
6. AGPL 合规风险确认（M0-16）→ 回填 002 风险 R2