# Implementation Plan: 三省六部 → 现代化组织改名

**Branch**: `feat/six-unity`（实际实施分支） | **Date**: 2026-08-01 | **Spec**: [spec.md](./spec.md)

## Summary
将三省六部看板全链路（后端 server.py、前端 dashboard.html、群聊 court_discuss.py、同步/测试脚本、Agent 提示词、README、历史数据）的古代命名，彻底改为现代化组织命名（方案2，含数据迁移）。**契约边界：英文 ID、状态机 key、API 路径、Agent ID、CSS 动态拼 class 规则一律不变**。核心设计是建立**唯一真源常量表 `ORG_MODERN`**，让所有函数统一引用，未来改名只改一处。

## Technical Context
- 语言: Python 3（server.py FastAPI 风格本地服务器）、原生 JS + HTML（dashboard.html 单文件前端）
- 依赖: 无新增第三方；复用 Flask/Python 标准库
- 存储: `data/tasks_source.json`（JSON 数组，任务数据源）、`data/officials_stats.json`（官员统计，由脚本生成）、`data/agent_config.json`
- 测试: `scripts/test_final.py`（断言依赖中文'准奏'）、`scripts/toctou_test_runner.py`、`scripts/test_taizi_scan_agent_working.py`
- 门禁: `scripts/selfcheck_engine.py`（七维分解 D1-D7 ≥98）、`scripts/six_unity.py`（sdd_gate/cdd/decomp）
- 约束: `SIX_UNITY=1` 门禁生效中（用 `env SIX_UNITY=1` 启动）；`/api/six-unity` 的 `sdd_enforce` 必须保持 true

## Constitution Check
*GATE: 通过后进入实现*

- ✅ 不破坏既有 API 契约（C-001）
- ✅ 不改英文 ID / 状态机 / Agent ID
- ✅ 数据迁移有备份可回滚
- ✅ 覆盖 agent 提示词一致性（WORKFLOW.md 角色映射表同步）

无违规，无需要豁免的项目。

## Project Structure（新增/改动）
```
新增:
  specs/现代化改名/spec.md            # 已完成
  specs/现代化改名/plan.md            # 本文档
  specs/现代化改名/tasks.md           # 任务分解
  scripts/migrate_org_names.py        # 历史数据迁移脚本（新）
改动:
  dashboard/server.py                 # 常量表 + 文案
  dashboard/dashboard.html            # 前端文案/class/key/JS逻辑
  dashboard/court_discuss.py          # 官员画像现代化
  scripts/sync_from_openclaw_runtime.py
  scripts/sync_officials_stats.py
  scripts/sync_agent_config.py
  scripts/kanban_update.py
  scripts/six_unity.py                # 措辞(封驳→驳回)微调
  scripts/test_final.py / toctou_test_runner.py / test_taizi_scan_agent_working.py
  agents/GLOBAL.md / DISPATCH.md / WORKFLOW.md / EVOLUTION.md / IDENTITY.md / MEMORY.md
  README.md
暂缓(不纳入): edict/backend, edict/frontend, docs/历史, data/output/历史产出
```

## Architecture Decisions

- **AD-001**：建立唯一真源常量表 `ORG_MODERN` + `ORG_LEGACY_MAP` 于 server.py 顶部。理由：消灭散落硬编码，改名/回滚只动一处；`ORG_LEGACY_MAP` 同时服务数据迁移与前端 fallback。
- **AD-002**：前端 `DEPT_COLOR`/`phaseColors`/`DEPT_MONITOR`/`_agentLabels` 的 key（现为中文古名）统一改为现代名，并**全部改为从单一 `ORG_MODERN` 派生的同构映射**，避免与后端漂移。
- **AD-003**：CSS class 仍保持 `dt-<org字符串>` 动态拼规则，只把 8 个 `.dt-中书省` 等改名与 org 字符串一致；不引入额外映射层，降低耦合。
- **AD-004**：L2302 正则 `/省|部/g` 改为基于映射表的归一函数 `orgToId(org)`（查 ORG_MODERN/ORG_LEGACY_MAP），彻底摆脱"省/部后缀"假设。
- **AD-005**：数据迁移用独立脚本 `migrate_org_names.py`（`--dry-run` + 备份 + 真实迁移），不内嵌进 server 启动，避免污染运行时。
- **AD-006**：测试断言语现代化（'准奏'→'驳回' 语义按新文案），保持断言强度不等同但覆盖等价路径。
- **AD-007**：每 Stage 一个 git 提交点，出问题 revert 对应提交 + 恢复数据备份回滚。

## Stage 拆分（对齐 tasks.md）
1. **Stage A**：常量表 + 后端 server.py 文案 + court_discuss.py
2. **Stage B**：前端 dashboard.html（文案/class/key/JS逻辑/正则）
3. **Stage C**：数据迁移脚本 + 执行迁移
4. **Stage D**：同步/测试脚本 + six_unity 微调
5. **Stage E**：Agent 提示词 + README
6. **Stage F**：回归验证 + 全仓 grep 清零 + 门禁复核
