<!-- version:v2.0.0-system -->
# WORKFLOW.md · 三省执行部门制工作流协议

**三省执行部门 = Edict Dashboard**（`http://192.168.3.180:7891`），11 Agent 看板任务管理系统，完整 6 层防线自动派发链路。

## 工作流

```
0. 决策门（无条件触发，见 GLOBAL.md）
   ↓ 判断需要走三省执行部门 pipeline
1. 老板说「用三省执行部门制完成X」 或 决策门 #7/#8/#9
2. 总办（鮱澄）分析需求、给出方案 → 等老板确认
3. 通过看板创建任务（API POST /api/tasks 或看板 UI）
4. 看板自动派发 → 总办 → 规划部 → 审议部 → 执行办 → 执行部门
5. 各 Agent 通过 kanban_update.py 推进任务状态
6. 任务走完 6 层防线 → 最终交付
```

## 防线分层

```
Layer 1: 规划部（筹微）→ 需求拆解 + 方案起草（Spec 模板 + FR-xxx 编号）
Layer 2: 审议部（审微）→ 独立审议 + 驳回权（SCHK-01~09 结构化审查）
Layer 3: 执行办（驿使）→ 冲突复检 + 串并行路由 + FR→T 映射传递
Layer 4: 执行部门 → 内容部(文案) / 开发部(代码) / 设计部(设计) / 质控部(QA)
Layer 5: 归藏（汇总）→ 文件完整性 + 版本一致性
       镜衡（审查）→ 独立质量验收（RCHK-01~06 + 追溯覆盖率）
       总办       → 最终审查 + 交付
```

## 总办不越权（铁律）

> 任何情况下，总办不替代其他 Agent 干活。

| 场景 | ❌ 错误做法 | ✅ 正确做法 |
|------|-----------|-----------|
| 筹微方案有问题 | 总办自己重写方案 | 看板驳回，退回规划部重做 |
| 墨卿文案有误 | 总办自己改文案 | 看板驳回，退回内容部重做 |
| 锋铸代码有 bug | 总办自己修代码 | 看板驳回，退回开发部重做 |
| Agent 超时无响应 | 总办自己接了活 | 触发看板 retry 或 escalate |
| 交付物质量不合格 | 总办动手修 | 驳回 + 附原因，让原 Agent 自修 |

## 驳回规则（非一刀切）
驳回时指定退回目标，而非全退规划部：
- 方案设计问题 → 退回规划部（筹微）
- 执行层面问题（文案/代码/设计）→ 退回对应执行部门
- 派发错误 → 退回执行办（ld-r/驿使）

## 角色映射（registry.json → OpenClaw Agent）

| 组织角色 | OpenClaw Agent ID | 部门 |
|------------|------------------|------|
| 总办 | main | 总办 |
| 规划师 | guihua | 规划部 |
| 审议官 | shenyi | 审议部 |
| 执行经理 | ld-r | 执行办 |
| 内容负责人 | wenan | 内容部 |
| 开发负责人 | daima | 开发部 |
| 设计负责人 | sheji | 设计部 |
| 质控负责人 | shencha | 质控部 |
| 交付负责人 | huizong | 交付汇总处 |
| 人力路由负责人 | paifa | 人力路由处 |
| 运维专员 | rongcui | 运维组 |

## 追溯映射（强制执行 — ✨ vSPEC-KIT）

每个三省执行部门任务必须在下述环节执行需求-任务追溯映射：

```
Layer 1: 筹微 → TASK.md 中标注 FR-xxx 编号，每个 User Story 关联对应 FR
Layer 2: 审微 → 验证 FR→Task 映射是否完整，不完整则驳回
Layer 3: 驿使 → Work Package 中携带 FR→T 映射，传递给执行部门
Layer 4: 执行 Agent → 产出中附 FR→T 映射表，标注覆盖率
Layer 5: 镜衡 → 检查映射覆盖率：💯全覆盖 ✅ / 有缺失 🔴 打回
Layer 6: 归藏 → 最终版本中 FR→T 映射归档
```

## 工具链
- **看板服务器**：`/Users/chee/Projects/baocheng-pm/`，启动：`./edict.sh start`
- **创建任务**：`POST /api/tasks {title, ...}` 或看板 UI
- **推进状态**：`python3 kanban_update.py task <task_id> state <new_state>`
- **手动派发**：`openclaw agent --agent <agent_id> -m "<message>"`
- **阻塞处理**：看板 UI 的 Retry/Escalate/Rollback 按钮