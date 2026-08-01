# JJC-20260801-006 · SDD 契约（spec）

> **Feature**: 六合一闭环补全落地（SDD+CDD细化+迭代98%引擎+老板确认闸）
> **Created**: 2026-08-01 | **Status**: Draft → 待审微封驳
> **Language**: chinese | **Branch**: `feat/six-unity-close-loop`

---

## Purpose（为什么做）

把「三省六部」从"看板状态流转"升级为**真正闭环**：需求 → SDD(规范)+CDD(协作) → 迭代至98% → 老板确认 → 六部自动执行 → 品控验收 → 经验回流。当前六个断点导致流程只走到"派发/留痕"，未形成可拦截、可验收、可迭代的闭环。

---

## Outputs（交付物）

1. **task['spec']**：SDD 契约 dict（purpose/outputs/acceptance_criteria/boundaries/dependencies/edge_cases）—— 军师产出，非 None
2. **task['cdd']**：CDD 协作契约 dict（agents/interfaces/alignment_rules）—— 军师产出框架
3. **iterate 引擎接入**：Menxia→Assigned 时跑「评分→短板→补齐→重评」循环，≥98% 无短板才放行
4. **老板确认闸**：spec 达标后置 `awaiting_boss`，提供 /api/boss-confirm（通过/驳回/豁免），未确认无法 advance
5. **六部自动派发**：Doing 态读 task.targetDept 写回 org → 正确路由到六部
6. **品控验收留痕**：/api/qa-result PASS/FAIL，FAIL 自动打回并对齐到对应部门
7. **门禁开关**：SIX_UNITY + ITERATE_ENFORCE 环境变量，灰度优先

---

## Acceptance Criteria（可验证 pass/fail）

- **AC-001**: 新建任务（SIX_UNITY=1 + ITERATE_ENFORCE=1 下）→ 军师提交 spec+cdd 后，`task['spec']` 为 dict 且含全部 6 字段，`task['cdd']` 为 dict 且含全部 3 字段（pass：两者非 None 且字段齐全 / fail：任一缺失）
- **AC-002**: spec 初评 <98% → 自动产出 short_dims 短板清单 → 军师补齐 → 重评 ≥98% 且无短板才放行（pass：iterate 循环 ≥1 轮且最终 is_ready()=True / fail：不达 98% 被放行）
- **AC-003**: spec 达标 → `spec_status='awaiting_boss'`，此时 `handle_advance_state` 拒绝推进（pass：返回 error 不改变 state / fail：被推进）
- **AC-004**: 老板确认闸：`/api/boss-confirm {confirm:true}` → 放行执行；`{confirm:false, reason}` → 退回 Zhongshu；`manual_spec:skip` → 跳过确认闸（pass：三种分支行为正确 / fail：任一不符）
- **AC-005**: Doing 态带 `targetDept='开发部'` → `task['org']` 被写回 '开发部' 并被派发给对应部门 Agent（pass：派发 agent_id 正确 / fail：org=None 或派发跳过）
- **AC-006**: `/api/qa-result` PASS → 任务 Done；FAIL+reason → 任务自动回退到对应执行部门，flow_log 记录部门对齐（pass：PASS/FAIL 两分支正确 / fail：FAIL 不自动打回）
- **AC-007**: 门禁开关：SIX_UNITY=0 时全部只留痕不拦截（存量任务不破坏）；SIX_UNITY=1 + ITERATE_ENFORCE=1 时拦截生效（pass：开关切换行为符合 / fail：开关失效）
- **AC-008**: 全程可观测：flow_log + spec_status + cdd + iterate + audit 均有记录（pass：5 类观测点都有留痕 / fail：任一缺失）
- **AC-009**: **本地 git commit + push，GitHub 同步最新**（pass：`git status` 干净且远程 HEAD==本地 / fail：有未提交或未推送）

---

## Boundaries（范围边界 / 不做什么）

- ❌ 不重写看板状态机整体（保留现有 _STATE_FLOW，只增强钩子）
- ❌ 不改既有 Done/Cancelled 任务数据
- ❌ 不强制存量无 spec 任务补契约（只对新任务生效）
- ❌ 不做前端大改（dashboard.html 仅加确认区 + spec 摘要展示，不做全新 UI）
- ❌ 不引入新数据库/存储层（复用 data/*.json + file_lock 原子读写）

---

## Dependencies（前置依赖）

| 依赖 | 状态 | 说明 |
|------|------|------|
| iterate_engine.py | ✅ 已有(197行) | 需确认接入 lifecycle |
| selfcheck_engine.py | ✅ 已有(218行) | 七维评分 D1-D7 |
| six_unity.py | ✅ 已有(226行) | sdd_gate/decomp_check/cdd/SE |
| dashboard/server.py | ✅ 已有(4437行) | 挂载钩子 + 新增路由 |
| SIX_UNITY 环境变量 | 🟡 默认0 | 需 ITERATE_ENFORCE 配合灰度 |
| lossless-claw | ✅ 已有 | 上下文管理 |
| OCR 评审层 | ✅ 已有 | Review 自动触发 |

---

## Edge Cases（异常场景/边界）

- **EC-001**: iterate 引擎崩 / selfcheck 报错 → 降级为只留痕不拦截（decomp_check 已有 try/except）
- **EC-002**: 老板确认闸遗漏紧急任务 → manual_spec=skip 高优通道
- **EC-003**: 并发派发（多任务同时到 Assigned）→ 用 file_lock 原子读写避免竞态
- **EC-004**: 无 targetDept 的旧任务 → 默认路由到规划部原逻辑，不强行改 org
- **EC-005**: 迭代超过 MAX_ROUNDS=3 仍 <98% → 记录 iterate 轮次，标记"需人工决策"而非死循环
- **EC-006**: API 不可达（看板离线）→ 六合一钩子静默降级，不阻塞基础流转

---

## Success Criteria

- **SC-001**: 灰度期 1-2 个真实任务完整走通「SDD→迭代→老板确认→六部→品控→Done」全链路，0 人工干预
- **SC-002**: SIX_UNITY=1 下，无 spec 任务进 Review 被拦截率 100%
- **SC-003**: 六合一门禁开启后，存量任务流转不受影响（回归通过率 100%）

---

## Assumptions

- 老板已确认方案 v2 定稿（flow_log 已记录"老板已确认方案v2定稿"）
- 六部 Agent registry 已由 _AGENT_DEPTS / _ORG_AGENT_MAP 配置
- iterate 引擎、selfcheck、six_unity 现有实现作为基础，本任务聚焦接入与缺口补全

---

*军师（guihua）产出 · 待门下省审议封驳*
