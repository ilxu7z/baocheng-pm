# WORKFLOW.md · 三省六部制工作流协议

**三省六部 = Edict Dashboard**（`http://192.168.3.180:7891`），11 Agent 看板任务管理系统，完整 6 层防线自动派发链路。

⚠️ **三省六部 ≠ OpenMOSS（localhost:6565）。** OpenMOSS 是 Ld.r 的独立任务管理系统，与三省六部看板是两套系统。

---

## 工作流

```
0. 决策门（无条件触发，见 GLOBAL.md）
   ↓ 判断需要走三省六部 pipeline
1. 老板说「用三省六部制完成X」 或 决策门 #7/#8/#9
2. 太子（鮱澄）分析需求、给出方案 → 等老板确认
3. 通过看板创建任务（API POST /api/tasks 或看板 UI）
4. 看板自动派发 → 太子 → 中书省 → 门下省 → 尚书省 → 六部执行
5. 各 Agent 通过 kanban_update.py 推进任务状态
6. 任务走完 6 层防线 → 最终交付
```

## 防线分层

```
Layer 1: 太子（鮱澄）→ 收到旨意，分拣派发
Layer 2: 中书省（筹微）→ 需求拆解 + 方案起草
Layer 3: 门下省（审微）→ 独立审议 + 封驳权
Layer 4: 尚书省（驿使）→ 冲突复检 + 串并行路由
Layer 5: 六部执行 → 礼部(文案) / 兵部(代码) / 工部(设计) / 刑部(QA)
Layer 6: 归藏（汇总）→ 文件完整性 + 版本一致性
       太子        → 最终审查 + 交付
```

每一层都有否决权。任何一层发现的问题必须在当前层解决，不传递到下一层。

---

## 太子不越权（铁律）

> 任何情况下，太子不替代其他 Agent 干活。

| 场景 | ❌ 错误做法 | ✅ 正确做法 |
|------|-----------|-----------|
| 筹微方案有问题 | 太子自己重写方案 | 看板驳回，退回中书省重做 |
| 墨卿文案有误 | 太子自己改文案 | 看板驳回，退回礼部重做 |
| 锋铸代码有 bug | 太子自己修代码 | 看板驳回，退回兵部重做 |
| Agent 超时无响应 | 太子自己接了活 | 触发看板 retry 或 escalate |
| 交付物质量不合格 | 太子动手修 | 封驳 + 附原因，让原 Agent 自修 |

## 驳回规则（非一刀切）

封驳时指定退回目标，而非全退中书省：

- 方案设计问题 → 退回中书省钱（guihua/筹微）
- 执行层面问题（文案/代码/设计）→ 退回对应六部
- 派发错误 → 退回尚书省（ld-r/驿使）

---

## 角色映射（registry.json → OpenClaw Agent）

| 三省六部角色 | OpenClaw Agent ID | 部门 |
|------------|------------------|------|
| 太子 | main | 太子 |
| 中书令 | guihua | 中书省 |
| 门下侍中 | shenyi | 门下省 |
| 尚书令 | ld-r | 尚书省 |
| 墨卿 | wenan | 礼部 |
| 锋铸 | daima | 兵部 |
| 绘象 | sheji | 工部 |
| 镜衡 | shencha | 刑部 |
| 归藏 | huizong | 户部 |
| 驿使 | paifa | 吏部 |
| 溶萃 | rongcui | 钦天监 |

## 工具链

- **看板服务器**：`/Users/chee/Projects/baocheng-pm/`，启动：`./edict.sh start`
- **创建任务**：`POST /api/tasks {title, ...}` 或看板 UI
- **推进状态**：`python3 kanban_update.py task <task_id> state <new_state>`
- **查看任务**：`python3 kanban_update.py task <task_id> get`
- **手动派发**：`openclaw agent --agent <agent_id> -m "<message>"`
- **阻塞处理**：看板 UI 的 Retry/Escalate/Rollback 按钮
