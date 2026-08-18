# 审议部复审结论：有条件通过 ✅（N1-N3 已修正闭合）

## 复审判定
修订版 v2 方案（564 行）经逐文件实测（wgate/registry/switch-resolver/capability-gate/read/write/control/permission/_journal.json/37 migration + 生产库验证），**B1/B2/B1.2/B6 及全部修正项实质闭合**，方案主体真实可落地。发现 3 处非致命缺陷（N1/N2/N3），经 main 应用修正后**全部闭合**。

## 三处缺陷修正确认
| # | 缺陷 | 修正（已应用到 plan.md） |
|---|---|---|
| N1 | 「24 条 in_progress 残留清理」与清理 SQL 矛盾（实测 30 条：6 过期、0 已决、24 pending 保留） | 标题/AC4 改「30 条全量甄别：6 置 failed、0 已决、24 pending 保留」 |
| N2 | 「tool→capability 反向映射不存在」失实（capability-gate.ts 已有 toolToCapId 19 tool 1:1） | §0.3/§3.4 改「复用/对齐 capability-gate.ts 现成映射，从 DB 派生单一授权源」 |
| N3 | 「docs/ 已有 01-20 系统文档」失实（实测仅 5 非编号 + autotrade/） | §6.1 改「docs/11-18 为新增顶层文件，不与现有冲突」 |
| 轻微 | §8.1 清理 SQL 分类2 未含 'escalated' | 已补入 IN 列表 |

## 品控官验收要点清单（对照任务 6 项）
1. **T1 HUMAN-UI 审批**：approval-routes.ts 4 端点；settleApproval 被 HTTP 真实调用（当前无调用方）；approve/deny 用 `:approve` 非 `:run`（防 B2 后门）；批准→幂等 processed+ledger success+humanConfirmedBy；拒绝→failed+ledger denied
2. **T2 手动工具页**：19 tool 手动可调；过 capability-gate 全局硬闸（off→403）；手动写走同一 W-GATE executor；min_approval='always' 强制进审批队列；L2 调 L4→403（assertWriteLevel）；L0 控制面免审批但走幂等+ledger
3. **T3 inputSchema**：19 tool 统一精度（required 完整/enum/format/description）；adinsights.query/report 收紧 required:['dateFrom','dateTo']（实测零调用方，零回归）
4. **T4 开发文档**：docs/11-18 十层新增文件；L2 三权矩阵/L3 ADR/L5 契约/L8 门禁脚本/L10 回流
5. **T5 验收清单**：5维×3级 + 20 条 A0X-LY；A07/A12(并发审批)/A19 强制门禁
6. **T6 遗留**：30 条 in_progress 甄别（6 failed/0 已决/24 pending 保留）；creative.submit 测试数据归档不破坏 ledger；journal 补齐（14 缺失）+ 0032 改名 0031a + 全新库 migrate 全对象重建（journal 数==文件数）

## 判定
通过，可进入 main 拍板 → paifa 派发执行
