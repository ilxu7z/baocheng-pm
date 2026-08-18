# P0 落地执行计划 · JJC-20260810-002「客户数据清洗多Agent编排 P0」

**执行方**：军师 guihua（规划部）
**上游设计**：JJC-20260810-001 方案 v2.1（已 Done）→ `docs/autotrade/JJC-20260810-001-客户录入数据清洗多Agent编排设计方案.md`
**性质**：P0 落地研发执行计划（L2 去重 + L3 冲突检测 + 人工确认闸）

---

## 0. 前置核实结论（已通读设计 + 读代码）

| 核实项 | 结论 | 依据 |
|---|---|---|
| W-GATE 闭环 | `ams.cleaning.value` 必须注册为真实写 executor（`registerWriteExecutor`），由 settleApproval→`executeWriteAndSettle`→`getWriteExecutor` 调用；**不得裸调 createAgentRequest** | wgate.ts settleApproval 硬依赖 `contextData.idempotencyKeyId`（wgate.ts:318），H3 致命点 |
| 工具注册多处 | ① write.ts WRITE_TOOLS / read.ts READ_TOOLS；② capability-gate.ts toolToCapId；③ registry.ts WRITE_MIN_LEVEL + HIGH_SENSITIVITY；④ manual-routes.ts WRITE_MIN_LEVEL + HIGH_SENSITIVITY（双端必须一致） | registry.ts / manual-routes.ts / capability-gate.ts |
| executor 注册触发点 | `registerWriteExecutors()` 在 manual-routes.ts:211（手动出口显式幂等注册）；MCP 走 server.ts ensureStarted。`ams.cleaning.value` executor 必须在 `registerWriteExecutors()` 内注册 | manual-routes.ts:211 |
| capability seed 现状 | agent_capabilities 已 seed 6 cap（0035），无 data.cleaning.main；新增走 0041b 迁移 | 0035_seed_capabilities.sql |
| approval UI 复用 | agent-approvals/index.jsx 的 TOOL_PREFIX_TO_GROUP 已有 ams.knowledge.→knowledge，**无 ams.cleaning. 前缀** → 需补映射（否则落 other 组） | index.jsx |
| Dify workflow 真实路径 | **dify/workflows/**（Dify DSL v0.7.0），非 docs/autotrade/dify-workflows/（空目录）。参照 lead-scoring.yml tool 节点模式（MCP provider ams-real-3999） | 代码核实 |
| config/autoMode | **无现成 cleaning.autoMode 配置存储**；core-config 模块可作承载（待选型） | core-config/ 存在 |
| L2 主记录选取 | 设计 §附录B 待确认项，未定 | 设计 |
| 检索增强 | 设计 §3 属 P1；**P0 不含**（锁定边界） | 设计 §9 |

---

## 1. P0 范围锁定与边界

### 1.1 P0 纳入
- **L2 去重**：规则粗筛 + LLM 精判分档（>0.95 自动重复 / 0.85-0.95 需人确认 / <0.85 不同）
- **L3 冲突检测**：同 category 同主题矛盾信息，时间线分析分类（更新/矛盾/别名）
- **人工确认闸**：L3 矛盾、L2 0.85-0.95、可疑无效 → 强制挂 W-GATE 审批队列；L1/L4 高置信/L2>0.95 自动通过
- **落库 + 血缘**：写 customer_cleaned_value 表（只增不改），ams.cleaning.value 走完整 W-GATE executor
- **能力注册**：data.cleaning.main cap + 白名单 + toolToCapId + WRITE_MIN_LEVEL/HIGH_SENSITIVITY + 前端 group

### 1.2 P0 不含（明确排除）
- **检索增强层**（设计 §3，LEFT JOIN + COALESCE）→ P1
- **L1 格式规范化独立落库** → 仅 Dify 预处理节点内联，不单独建表
- **L5 语义消歧**（设计 §1.5）→ P2
- **CRM 客户主数据清洗**（领域边界，老板拍板不可改）

> ⚠️ **[NEEDS CLARIFICATION] P0 落库表承载范围**：clean_type 含 format|dedup|conflict|invalid|semantic。P0 只做 L2/L3，是否也写 L1/L4 判定（clean_type='format'/'invalid'）？建议 P0 只写 dedup/conflict 两型（+ 关联 L4 invalid 兜底），L1 format 留 P1。需确认避免字段枚举超范围。

---

## 2. 子任务拆解

### 【T1】数据库层：清洗结果表 + cap 种子迁移

**涉及文件**
- `src/shared/db/migrations/0041-customer-cleaned-tables.sql`（新建，手工旁路）
- `src/shared/db/migrations/0041b-seed-capability-cleaning.sql`（新建，手工旁路）

**DoD**
1. `customer_cleaned_value` 表按设计 §4.1：`id BIGSERIAL` / `company_id UUID NOT NULL` / `source_kb_id UUID NOT NULL REFERENCES knowledge_base(id)` / `field_name` / `cleaned_value TEXT` / `original_value TEXT` / `clean_type VARCHAR(32)`（format|dedup|conflict|invalid|semantic）/ `confidence NUMERIC(4,3)` / `processing_status`（pending|auto_approved|pending_human|human_approved|human_rejected|applied|rolled_back）/ `human_confirmed BOOL` / `approval_id BIGINT` / `source_ref_chain JSONB` / `version INT` / 时间戳 + `UNIQUE (company_id, source_kb_id, field_name, cleaned_value)`
2. `customer_cleaning_batch` 表按 §4.1（batch 血缘，含 workflow_run_id）
3. 5 索引：idx_cleaned_company / idx_cleaned_source_kb / idx_cleaned_status / idx_cleaned_confidence / idx_cleaned_clean_type + 审批队列索引 idx_cleaned_approval（WHERE approval_id IS NOT NULL）
4. 全部 IF NOT EXISTS 幂等，注释「手工旁路执行（与 0031/0032/0034/0035/0040 一致，不进 journal）」
5. 0041b 插入 data.cleaning.main cap：business_domain='content'、role_id=P5（内容运营）、mcp_tools=['ams.cleaning.pipeline','ams.cleaning.value','ams.cleaning.get','ams.cleaning.tasks','ams.cleaning.lineage','ams.cleaning.conflicts']、route_mode='auto+manual'、min_approval='always'、permission_base='L4_control'；WHERE NOT EXISTS(cap_id) 防重

**可量化 AC**
- AC1-1：SQL 重复执行 N 次不报错、不重复建表/索引（幂等实测）
- AC1-2：psql `\d customer_cleaned_value` 字段/约束/索引与设计 §4.1 逐项一致
- AC1-3：agent_capabilities 出现 data.cleaning.main，mcp_tools 含 6 个 ams.cleaning.*
- AC1-4：source_kb_id 为 UUID（H1），company_id NOT NULL（C4）

**优先级**：P0-P1（阻塞一切）

---

### 【T2】MCP 工具层：新增 ams.cleaning.* 工具 + 注册

**涉及文件**
- mcp/tools/write.ts（新增 2 写 + executor 注册）
- mcp/tools/read.ts（新增 4 读）
- mcp/tools/capability-gate.ts（toolToCapId 补 6 条）
- mcp/tools/registry.ts（WRITE_MIN_LEVEL 补 ams.cleaning.value='L4_control'；HIGH_SENSITIVITY 决策）
- agent-orchestration/manual-routes.ts（WRITE_MIN_LEVEL 同步补，双端一致）

**DoD**
1. **写 `ams.cleaning.pipeline`**：{recordIds?[], fields?[]}，触发异步批量巡检，requiresHumanConfirm=false（决策 A 先入库后扫），走 W-GATE 幂等防重复
2. **写 `ams.cleaning.value`**（S5 唯一真写入口）：{cleanedValueId, decision:'apply'|'reject'|'rollback'}，必须实现 targetEntity=cleanedValueId / semanticSign=hash(cleanedValueId+decision) / title=知识库清洗确认: {sourceKbId}/{field_name} / requiresHumanConfirm=true
3. **读工具**（全部强制 companyId 过滤，T-SEC-4）：get{sourceKbId,fieldName?} / tasks{batchId?,status?} / lineage{sourceKbId?} / conflicts{status?}
4. **executor 注册**（write.ts registerWriteExecutors() 内）：registerWriteExecutor('ams.cleaning.value',...) 调真实清洗落库 service；pipeline 注册触发巡检 executor。不得复制两份（ICL #30）
5. toolToCapId 补 6 条（S2/S3/S5：value 只留写侧，读侧用 get）
6. WRITE_MIN_LEVEL 补 ams.cleaning.value:'L4_control'；HIGH_SENSITIVITY 决策（§7）

**可量化 AC**
- AC2-1：6 新工具在 GET /tools 出现，按 data.cleaning.main cap 正确分组
- AC2-2：读工具未加白名单返回 403（S3），加后通过
- AC2-3：getWriteExecutor('ams.cleaning.value') 返回真实 executor（非 undefined）
- AC2-4：get（读）与 value（写）不互相遮蔽（S5：dispatchMcpTool 读先于写查）
- AC2-5：schema 严格校验 required，缺失返回 400

**优先级**：P0-P2（依赖 T1）

---

### 【T3】W-GATE 审批闭环：清洗确认走完整链路

**涉及文件**
- mcp/wgate.ts（复用，不改）
- knowledge-base/cleaning-service.ts（**新建**，落库核心 service）
- （后续由 daima 补全 settleApproval→executor 调测）

**DoD**（核心）
1. `cleaning-service.ts` 实现 apply/reject/rollback 落库逻辑：apply→processing_status 更新为 applied + INSERT 清洗值 + 血缘链；reject→human_rejected；rollback→rolled_back 保留 original_value
2. ams.cleaning.value 注册为真实 executor，settleApproval 批准后调它落库（非裸调），ledger 记 success + humanConfirmedBy
3. 拒绝/回滚不落清洗值，原始表永不 UPDATE（只增不改）
4. 幂等：已 applied 的 cleanedValueId 重复 settle → 幂等返回，不重复 INSERT
5. 审批队列：pending_human 项挂 approval_requests，前端 agent-approvals 可列出

**可量化 AC**
- AC3-1：审批批准后 customer_cleaned_value 出现新行（applied），原始 knowledge_base 行未被覆盖
- AC3-2：审批拒绝后无新行，状态 human_rejected
- AC3-3：重复 settle 幂等返回，不重复落库
- AC3-4：清洗项出现在 agent-approvals 审批队列（pending_human）

**优先级**：P0（核心闭环）

---

### 【T4】Dify workflow：knowledge-cleaning.yml

**涉及文件**
- `dify/workflows/knowledge-cleaning.yml`（新建，Dify DSL v0.7.0，参照 lead-scoring.yml）

**DoD**
1. 节点链对齐设计 §2：L2 去重粗筛（code）→ LLM 精判分档 → L3 冲突检测（时间线 + 权威度）→ 人工确认闸 → ams.cleaning.value 写回
2. MCP tool 节点用 provider ams-real-3999（参照 lead-scoring.yml）
3. LLM 节点 max_tokens 放大（避免 ad-creative/ad-audience 曾踩的 JSONDecodeError）+ prompt 尾部 JSON 硬约束（禁 think/代码块/截断）
4. code 节点 outputs 声明完整 + 容错解析（剥 think → 整体 parse → 兜底空结构）

**可量化 AC**
- AC4-1：workflow 发布成功（Dify console publish 200）
- AC4-2：实测运行 succeeded，run_id 落 batch 表 workflow_run_id
- AC4-3：LLM 输出无 JSONDecodeError（对比历史 ad-audience 修复套路）

**优先级**：P0-P3（依赖 T1/T2 工具可用）

---

### 【T5】人工审核流 + autoMode 开关

**涉及文件**
- agent-approvals/index.jsx（TOOL_PREFIX_TO_GROUP 补 ams.cleaning.→cleaning 前缀映射）
- core-config（或新 config 表，承载 cleaning.autoMode）[选型待定]

**DoD**
1. 前端审批页补 ams.cleaning. 前缀分组，清洗项显示 tool 名/目标实体/写意图
2. autoMode 开关：一键切换纯自动（低风险跳过人工）/ 人工确认模式；管理侧可关层级清洗
3. 审批页岗位筛选分流（QUEUE_FULL 防堆积）

**可量化 AC**
- AC5-1：清洗项在前端审批页按 cleaning 组正确列出
- AC5-2：autoMode=auto 时 L2>0.95 自动通过不进队列；autoMode=manual 时全部挂队伍列
- AC5-3：切层级开关后对应 clean_type 清洗被启用/停用

**优先级**：P0-P3（依赖 T3 闭环）

---

## 3. 执行顺序
**串行**：T1（建表/cap）→ T2（工具+注册）→ T3（W-GATE 闭环）→ T4（Dify workflow）→ T5（前端+autoMode）
**并行**：T4 可与 T3 并行（T4 依赖 T2 工具可用）

## 4. 分工
- **daima 主执行**：T1-T5 全部代码
- **rongcui 协助**：迁移执行 + Dify workflow 发布
- **shencha 验收**：对照 P0 验收 4 条 + 通用项
- **guihua 复核**：方案对齐设计
- **huizong 整合**：交付

## 5. P0 验收对照
| P0 验收标准 | 对应 |
|---|---|
| ① 去重分档正确率≥90%（抽样） | 样本集调测 |
| ② 冲突项 100% 挂审批（W-GATE 完整链路） | AC3-4 + AC2-3 |
| ③ 人工确认后正确落库（settleApproval 调 executor） | AC3-1 |
| ④ 无原始内容被覆盖 | AC3-1 + 只增不改约束 |

## 6. 风险与对策
| 风险 | 对策 |
|---|---|
| settleApproval 依赖 idempotencyKeyId 断链 | ams.cleaning.value 必须走完整 wgateCreate 链路 + registerWriteExecutor，不裸调 |
| LLM JSON 截断/带 think | max_tokens 放大 + prompt JSON 硬约束 + code 容错解析（复用 ad-audience/ad-creative 修复套路） |
| Dify workflow 节点体系与库错位 | 以 Dify 库 draft graph 为准（拉 GET draft 看节点 id），非本地 yml |
| capability 注册缺失 403 | 补 toolToCapId + 白名单 + WRITE_MIN_LEVEL 双端一致 |
| 审批堆积 | 前端岗位筛选 + autoMode 低风险自动放行 |
| 误判/误改 | 只增不改 + original_value 留存 + human_rejected/rolled_back 支持回退 |

## 7. [NEEDS CLARIFICATION] 待老板/开发确认
1. **P0 落库表承载范围**：只写 dedup/conflict（建议），还是含 format/invalid？
2. **L2 自动化主记录选取策略**：保留最早 or 最全？（设计附录B 待确认）
3. **autoMode 配置存储**：core-config vs 新 config 表？（开发选型）
4. **HIGH_SENSITIVITY 决策**：ams.cleaning.value 是否入 HIGH_SENSITIVITY？（建议：是，人工确认高敏写）
5. **表名**：customer_cleaned_value 保留（现设计）还是改 knowledge_cleaned_value（设计遗留备注建议）？