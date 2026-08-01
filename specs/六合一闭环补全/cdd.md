# JJC-20260801-006 · CDD 协作契约（cdd）

> **Feature**: 六合一闭环补全落地
> **Created**: 2026-08-01 | **Language**: chinese
> **框架产出**: 军师（guihua） | **注入**: 系统派发时 `_build_cdd_context`

---

## Agents（涉及 Agent 与交接物）

| agent | role | deliverables |
|-------|------|--------------|
| daima (开发部) | 后端开发 | server.py 新增路由、门禁增强、_build_cdd_context |
| sheji (设计部) | 前端 | dashboard.html 确认区/展示/编辑入口（小改动） |
| xingbu/shencha (质控部) | 品控 | /api/qa-result 调用、PASS/FAIL 提交、验收报告 |
| guihua (规划部/军师) | SDD+CDD | 本契约 author、spec/cdd 产出 |
| menxia (门下省/审微) | 审议 | 封驳 spec/cdd，SCHK 审查 |

---

## Interfaces（Agent 间接口契约）

| from | to | contract | must_match |
|------|----|----------|------------|
| daima → shencha | 提供 `task['spec'].acceptance_criteria` 全量清单 | 品控验收必须逐条对照 spec.ac |
| shencha → daima | FAIL 打回时必须带 `qa_result.reason` + 目标部门 | daima 按 reason 修复，不能猜 |
| daima → sheji | 提供任务 spec 摘要 + iterate 分 + cdd 摘要的 JSON 结构 | dashboard 字段名与 server 返回一致 |
| sheji → 全 Agent | 展示的 spec/cdd/iterate 字段 | 不得改字段语义（只增展示） |
| guihua → daima | spec 契约 dict schema | daima 落库时字段名严格一致 |
| xingbu → 总办 | 验收报告路径（/api/qa-result 返回值） | 报告可追溯至 task_id |

---

## Alignment Rules（对齐规则）

1. **同一套验收标准**：所有执行 Agent 使用 `task['spec'].acceptance_criteria`（AC-001~009）作为唯一验收依据，任何人不得私自改标准
2. **字段命名统一**：spec/cdd/iterate/qa_result 的 JSON 字段名一旦确认，任何人不得私自改名（防多 Agent 各写各的）
3. **交接物落 shared-knowledge**：daima 改的代码 diff、sheji 改的 UI、shencha 的验收报告，交接物必须可追溯（写 flow_log + 对应 data 文件）
4. **SDD 契约军师唯一 author**：task['spec'] 只允许 guihua 写，执行 Agent 只读不写
5. **门禁开关一致**：SIX_UNITY/ITERATE_ENFORCE 由总办统一控制，各 Agent 不得私自改动
6. **封驳优先**：门下省封驳结论（SCHK 报告）优先级高于执行 Agent 的判断，被封驳先自检再反驳

---

## CDD 注入说明（系统侧）

派发时由 server.py `_build_cdd_context(task)` 构造以下注入 context，喂给**每个涉及的 Agent**：

```
CDD_CONTEXT = {
  "feature": "六合一闭环补全落地",
  "agents": [daima, sheji, xingbu, guihua, menxia],
  "contracts": [接口契约如上],
  "alignment": [对齐规则如上],
  "spec_ref": "specs/六合一闭环补全/spec.md",
  "iterate_threshold": 98.0,
  "boss_gate": "awaiting_boss"
}
```

目的：保证多 Agent 干同一任务时看到的是**同一套协作约束**（信息统一），这是 CDD 的本质。

---

*军师（guihua）产出 · 系统派发时注入*
