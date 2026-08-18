# JJC-20260811-002 · AMS 性能优化与内存管控落地实施 — 执行计划

> 起草：总办（鮱澄）基于权威方案 `docs/4G-memory-optimization-plan.md`（5503aa19，2026-08-11）
> 军师三次写文件失败（系统性，failed: completed），改由总办起草 + 审计官审议
> 项目：`/home/chee/Projects/AIMarketingSystem` | 生产：阿里云 47.82.122.201（2核/3.4Gi，多次 OOM）

---

## ⚠️ 审计修正（shenyi 2026-08-11，实读代码挖出 P2 基线严重错误）

**有条件通过，P2 修正前不得放行。** 关键修正：
1. **P2-1 目标文件/基线错**：`dify-deploy/` 目录不存在；实际是根目录 `docker-compose.dify.yml`，且 7 个 aimarket-dify 容器**当前无内存上限**（不是降配，是首次加）。Dify 的 db/redis 在 `docker-compose.dev.yml`（dify-db 512M / dify-redis 128M），不在 dify.yml。当前值不得照搬上游表，须先 `docker stats` 实测稳态 RSS，上限=稳态×(1.2~1.5) 余量。
2. **P2-2 Chatwoot 基线低估**：实际 app 1G/sidekiq 512M/pg 512M/redis 128M（非 512/384/256/192），按计划拟值会一次性砍 50%+，须核生产真实值。
3. **P1-3 技术路径错**：纯 tsc 编译因 `@shared/@server/@client` path 别名无法运行时解析（tsc 不重写别名）+ tsconfig noEmit 只 typecheck → 会启动失败。需改 **esbuild/tsup 打包**（非补 tsc build 脚本）。
4. **补充风险**：① Postiz/Temporal（dev.yml social 约 3.1G 上限）未纳入预算，须确认生产机没跑；② AMS PG shared_buffers 128→256 是增非减；③ AMS Redis noeviction→allkeys-lru 是行为变更（会淘汰 key）。

**可直接本地做（不需老板确认）**：P1-3（esbuild 打包）、P3-1（依赖瘦身，排在 P1-3 后避免 package.json 冲突）。

## 〇、目标与边界
- 目标：不砍功能前提下常驻内存压到 ~3G + 2G swap，稳定运行 4G 环境
- 方案权威文档已完整（swap/降配/代码层/执行顺序），本计划负责「落地执行」组织
- ⚠️ **生产访问约束**：SSH 47.82.122.201 **publickey 被拒**（Permission denied (publickey)）→ 生产系统级操作需老板提供访问/配合

## 一、任务分类总览

| 批次 | 内容 | 分类 | 前置 | 说明 |
|------|------|------|------|------|
| P0 | 加 swap + swappiness（§七） | 【需生产访问】 | 无 | 第一优先级止损，消除 OOM 卡死 |
| P1 | AMS 代码层 A1（NODE_OPTIONS 堆上限）| 【需生产访问】改 compose+env | 无 | app 384M / worker 256M |
| P1 | AMS 代码层 A2（worker command 修正）| 【需生产访问】改 compose | 无 | 修 dist 不存在 bug，剥离生成重活 |
| P1 | AMS 代码层 B（tsx→tsc build）| 【本地可做】改 package.json+build 脚本 | 无 | 补后端 tsc 编译 |
| P2 | Dify 9 容器降配（§四）| 【需生产访问】改 docker-compose.dify.yml | 备份 | 逐个降配观察 |
| P2 | Chatwoot 4 容器降配（§五）| 【需生产访问】改 compose | 备份 | sidekiq 10→4 需确认吞吐 |
| P2 | 三套 PG/Redis 降配（§六）| 【需生产访问】| 备份 | max_connections 100→40 + 客户端池同步 |
| P3 | 依赖瘦身（§三 C）| 【本地可做】改 package.json | 无 | 省镜像体积，优先级低 |

## 二、子任务明细

### P0-1 加 swap + swappiness（第一优先级，止损）
- **分类**：【需生产访问】
- **改动**：生产服务器创建 2-4G swapfile + `vm.swappiness=10` 持久化
  ```bash
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
  sysctl -w vm.swappiness=10 && echo 'vm.swappiness=10' >> /etc/sysctl.conf
  ```
- **DoD**：`free -h` 显示 swap 2G + swappiness 生效
- **验证**：`free -h`（Swap 行非 0）、`cat /proc/sys/vm/swappiness`=10
- **回滚**：`swapoff /swapfile && rm /swapfile` + 移除 fstab 行
- **风险**：磁盘 49G 充裕；swappiness=10 不影响业务

### P1-1 AMS A1：NODE_OPTIONS 堆上限
- **分类**：【需生产访问】改 compose/env
- **改动**：app 容器加 `NODE_OPTIONS=--max-old-space-size=384`；worker 容器 `=256`
- **DoD**：compose 生效，`docker stats` app RSS 有界不无限吞
- **验证**：`docker stats` app RSS 稳定 ~≤500M
- **回滚**：移除 env 重启
- **风险**：低，V8 超限走 GC

### P1-2 AMS A2：worker command 修正（部署 bug）
- **分类**：【需生产访问】改 compose
- **改动**：worker 容器 command 从 `node dist/server/worker/index.js`（不存在）改为真实文件 `node --import tsx/esm src/server/modules/ai/creative/workers/generation-worker.ts`，把生成重活剥离到独立 worker
- **DoD**：worker 容器实际跑生成任务，app 进程内不再叠 worker
- **验证**：`docker stats` app RSS 下降；生成任务正常
- **回滚**：改回原 command 重启
- **风险**：中，需确认 generation-worker.ts 路径存在（军师/执行时核实）

### P1-3 AMS B：tsx→tsc 编译（本地代码）
- **分类**：【本地可做】
- **改动**：package.json 补后端 build 脚本（当前只做 vite）；先 `tsc` 编译到 dist 再跑纯 `node dist/...`
- **DoD**：`npm run build` 产出后端 dist；生产可 `node dist/...` 运行
- **验证**：本地 build 成功 + 启动正常；生产部署后 `docker stats` 启动内存峰值下降
- **回滚**：git revert / 保留原 tsx 启动方式
- **风险**：中，需核对 tsconfig 覆盖后端 src；改动涉及启动脚本需完整回归

### P2-1 Dify 降配（§四表）
- **分类**：【需生产访问】改 `docker-compose.dify.yml`（行号插入 + 备份 .bak，勿整文件覆盖）
- **改动**：api 1g→512m(workers 4→2)、worker 768m→384m、plugin_daemon 512m→256m、sandbox 256m→192m、ssrf 128m→64m、db 384m→256m、redis 256m→192m；web/nginx 保留
- **DoD**：容器内存上限按表生效
- **验证**：`docker stats` Dify 各容器 RSS ≤ 配额；功能回归（workflow run）
- **回滚**：恢复 .bak 重启
- **风险**：中，gunicorn workers 别降过头（1核≈3）

### P2-2 Chatwoot 降配（§五表）
- **分类**：【需生产访问】
- **改动**：app 512m→384m(WEB_CONCURRENCY 2→1)、sidekiq 384m→256m(SIDEKIQ_CONCURRENCY 10→4)、postgres 256m→192m、redis 192m→96m
- **DoD**：按表生效
- **验证**：`docker stats`；消息处理可用
- **回滚**：恢复 .bak
- **风险**：**sidekiq 并发降低降吞吐，需老板确认业务可接受**（NEEDS CLARIFICATION）

### P2-3 三套 PG/Redis 降配（§六表）
- **分类**：【需生产访问】
- **改动**：PG max_connections 100→40、shared_buffers 按表分配（AMS256/Dify256/Chatwoot192）、work_mem 8-16M；Redis maxmemory（AMS128/Dify192/Chatwoot96）+ allkeys-lru
- **⚠️ 必须同步调客户端连接池**（防假故障）：Chatwoot DB_POOL、Dify SQLAlchemy pool_size、AMS Node pg pool
- **DoD**：连接数生效且无「连接池满」假故障
- **验证**：应用正常连库；`docker stats` PG/Redis RSS 下降
- **回滚**：恢复配置重启
- **风险**：中，连接池同步是重点

### P3-1 依赖瘦身（§三 C，本地）
- **分类**：【本地可做】
- **改动**：package.json 剔除 @aws-sdk 全家桶（按需加载）、sharp、@electric-sql/pglite（dev）；保留 bullmq/echarts/xlsx/mammoth
- **DoD**：生产镜像体积下降；无引用缺失
- **验证**：build 通过 + 启动回归
- **回滚**：git revert
- **风险**：低（省磁盘非运行内存），优先级最低

## 三、执行顺序（严格按方案九）
```
P0-1 swap（止损）→ 观察 OOM 消失
→ P1-1/P1-2/P1-3 AMS 代码层（本地可做先落地，生产部署需配合）
→ 逐个降配：先 Dify（P2-1）观察 24-48h RSS → 再 Chatwoot（P2-2）→ 再 PG/Redis（P2-3）
→ P3-1 依赖瘦身（本地）
```
- 每步 `docker stats` 看真实 RSS（非镜像体积），稳定再动下一个，**不要一次性全压**
- swap 是兜底，先加 swap 再逐步压内存

## 四、NEEDS CLARIFICATION（需老板拍板）
1. **【阻塞】生产访问**：SSH publickey 被拒，swap/降配需生产执行。老板提供 SSH 密钥？还是阿里云控制台配合？还是老板本地跑脚本？
2. **【阻塞】002 范围**：老板把 002 重定义为性能优化。之前的清洗入口迁移（fdb89158 + B-1 00cce6ff 已基本完成）是否算完成收口？是否 002 只聚焦性能优化？
3. **worker 剥离（P1-2/A2/A3）**：生成重活剥离独立 worker 是否现在做，还是分阶段（先保稳定再剥离）？
4. **Chatwoot sidekiq 并发 10→4**：降低吞吐是否业务可接受？
5. **功能增量**：后续是否升配 8G（4G 是极限压榨，余量有限）？

## 五、验证与监控
- swap：`free -h`；内核：`cat /proc/sys/vm/swappiness`
- 容器：`docker stats`（真实 RSS，非镜像体积）
- 日志：json-file 限 50m + max-file=2 防磁盘写满
- 长期：监控 RSS 趋势定位泄漏源（Sidekiq 长任务/Dify 插件/Node buffer）

## 六、遗留风险
- 生产多次 OOM 失联（SSH banner 超时/443 不响应），需先阿里云控制台重启再执行
- worker command 指向不存在 dist 是部署遗留 bug（P1-2 修）
- 4G 余量有限，功能增量建议 8G
