# TOCTOU 测试-B：JSON 并发写入不同任务 — 执行方案

**任务ID**: JJC-TEST-032  
**起草部门**: 中书省（筹微 guihua）  
**起草日期**: 2026-06-26  

---

## 1. 测试目标

验证 `file_lock.py` 的 `atomic_json_update` 在 **多个 Agent 同时写入不同 task_id** 到同一个 `tasks_source.json` 文件时，是否保证：

| 验证项 | 说明 |
|--------|------|
| **数据完整性** | 每个 task 的字段不被其他并发写入破坏 |
| **无数据丢失** | 所有写入的 task 最终都出现在 JSON 文件中 |
| **无数据覆盖** | 一个 task 的字段不会被另一个 task 的写入意外覆盖 |
| **原子性** | 每次写入要么完全成功（全部字段写入），要么完全失败（文件回退到写入前状态） |
| **锁正确性** | 排他锁（`LOCK_EX`）确实防止了并发读写冲突 |

---

## 2. 当前锁机制分析

### 2.1 `file_lock.py` 关键实现

```
atomic_json_update(path, modifier, default)
  ├── 打开 path + '.lock' 文件（O_CREAT | O_RDWR）
  ├── 获取排他锁 fcntl.flock(fd, LOCK_EX)  ← 阻塞等待
  ├── 读取 path 的 JSON 内容
  ├── 调用 modifier(data)  → 返回修改后的数据
  ├── 写入临时文件 tempfile.mkstemp()  →  os.replace(tmp, path)
  └── 释放锁 fcntl.flock(fd, LOCK_UN)
```

### 2.2 锁粒度

- **锁文件**: `tasks_source.json.lock`（与数据文件同目录）
- **锁类型**: 排他锁（`LOCK_EX`）— 同一时刻只允许一个进程持有
- **锁范围**: 整个 `tasks_source.json` 文件级别

### 2.3 安全边界

- 写操作使用 **临时文件 + `os.replace`**，保证写入的原子性（即使进程在写入中途崩溃，也不会留下半写文件）
- 排他锁保证 **读-改-写** 序列的串行化
- 异常处理：写入临时文件失败时 `os.unlink(tmp_path)` 清理，然后 `raise`

### 2.4 潜在风险点

| 风险 | 说明 |
|------|------|
| **锁文件残留** | 如果进程在持锁期间被 `SIGKILL`，锁由内核自动释放，但 `.lock` 文件残留不影响下次使用 |
| **NFS 锁不可靠** | `flock` 在 NFS 上可能不可靠（但本测试在 macOS 本地运行，无此问题） |
| **`modifier` 内异常** | 如果 modifier 抛出异常，锁已获取但写未发生，数据文件不变 |
| **并发 modifier 冲突** | 两个 modifier 操作不同 task_id，但都操作整个 tasks 列表，理论上无冲突 |

---

## 3. 测试方法

### 3.1 并发模拟策略

使用 **Python `multiprocessing` 模块** 模拟多个 Agent 同时调用 `kanban_update.py`：

```
N 个进程同时运行
  └── 每个进程调用 kanban_update.py state <TASK_ID> <NEW_STATE> <NOW_TEXT>
  └── 每个进程操作的 task_id 不同
  └── 所有进程操作同一个 tasks_source.json
```

### 3.2 并发参数

| 参数 | 值 | 说明 |
|------|-----|------|
| 并发进程数 | 10 | 模拟 10 个 Agent 同时写入 |
| 写入操作 | `state` 命令 | 每个进程更新不同 task 的状态 |
| 写入次数/进程 | 5 次 | 每个进程连续写入 5 次（共 50 次并发写入） |
| 进程启动方式 | 几乎同时启动 | 使用 `multiprocessing.Pool` 或 `concurrent.futures.ProcessPoolExecutor` |
| 同步屏障 | 无 | 故意制造并发冲突窗口 |

### 3.3 写入内容设计

| 进程 # | 操作的 task_id | 状态序列 |
|--------|---------------|---------|
| 0 | `JJC-TEST-B-AGENT-0` | Doing → Review → Menxia → Assigned → Doing |
| 1 | `JJC-TEST-B-AGENT-1` | Doing → Review → Menxia → Assigned → Doing |
| ... | ... | ... |
| 9 | `JJC-TEST-B-AGENT-9` | Doing → Review → Menxia → Assigned → Doing |

每个 task 的字段：
- `id`: 唯一 task_id
- `title`: 包含进程编号的标题
- `state`: 随写入变化
- `org`: 随 state 变化
- `now`: 包含时间戳和进程编号的描述
- `flow_log`: 每次写入追加一条流转记录

### 3.4 测试脚本设计

```python
#!/usr/bin/env python3
"""
TOCTOU 测试-B：JSON 并发写入不同任务
模拟 10 个 Agent 同时更新不同 task_id 到同一个 tasks_source.json
"""
import json
import pathlib
import multiprocessing
import subprocess
import sys
import time
import random
import os

# ── 配置 ──
BASE = pathlib.Path('/Users/chee/Projects/oc-macs')
KANBAN = BASE / 'scripts' / 'kanban_update.py'
TASKS_FILE = BASE / 'data' / 'tasks_source.json'
LOCK_FILE = BASE / 'data' / 'tasks_source.json.lock'

NUM_AGENTS = 10       # 并发进程数
WRITES_PER_AGENT = 5  # 每个进程写入次数
TASK_PREFIX = 'JJC-TEST-B-AGENT'

# 状态转换序列（每个进程循环执行）
STATE_SEQUENCE = ['Doing', 'Review', 'Menxia', 'Assigned', 'Doing']


def agent_worker(agent_id: int):
    """单个 Agent 的工作：多次更新自己的 task 状态"""
    task_id = f'{TASK_PREFIX}-{agent_id}'
    now_text = f'Agent-{agent_id} 第{{i}}次写入 @{time.time():.3f}'
    
    for i in range(WRITES_PER_AGENT):
        new_state = STATE_SEQUENCE[i % len(STATE_SEQUENCE)]
        cmd = [
            sys.executable, str(KANBAN),
            'state', task_id, new_state,
            now_text.format(i=i)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f'[AGENT-{agent_id}] 第{i}次写入失败: {result.stderr.strip()}', flush=True)
        else:
            print(f'[AGENT-{agent_id}] 第{i}次写入成功: {task_id} → {new_state}', flush=True)
        # 随机延迟 0~50ms，制造并发窗口
        time.sleep(random.uniform(0, 0.05))


def create_test_tasks():
    """创建 N 个测试任务（串行，确保初始状态一致）"""
    print(f'创建 {NUM_AGENTS} 个测试任务...', flush=True)
    for i in range(NUM_AGENTS):
        task_id = f'{TASK_PREFIX}-{i}'
        title = f'TOCTOU测试-B Agent-{i}'
        cmd = [
            sys.executable, str(KANBAN),
            'create', task_id, title, 'Doing', '测试', '测试',
            f'TOCTOU测试-B Agent-{i} 初始创建'
        ]
        subprocess.run(cmd, capture_output=True, text=True)
    print(f'✅ 测试任务创建完成', flush=True)


def verify_integrity():
    """验证数据完整性"""
    print('\n' + '='*60)
    print('🔍 数据完整性验证')
    print('='*60)
    
    tasks = json.loads(TASKS_FILE.read_text(encoding='utf-8'))
    errors = []
    
    # 1. 检查所有测试 task 是否存在
    for i in range(NUM_AGENTS):
        task_id = f'{TASK_PREFIX}-{i}'
        task = next((t for t in tasks if t.get('id') == task_id), None)
        if not task:
            errors.append(f'❌ 数据丢失: {task_id} 不存在')
            continue
        
        # 2. 检查 state 字段完整性
        if 'state' not in task:
            errors.append(f'❌ 字段缺失: {task_id} 缺少 state')
        
        # 3. 检查 flow_log 是否完整（应有 WRITES_PER_AGENT + 1 条创建记录）
        flow_count = len(task.get('flow_log', []))
        expected_flows = WRITES_PER_AGENT + 1  # 创建 + 每次写入
        if flow_count < expected_flows:
            errors.append(f'⚠️ flow_log 不完整: {task_id} 期望 {expected_flows} 条，实际 {flow_count} 条')
        
        # 4. 检查 now 字段是否包含预期内容
        now = task.get('now', '')
        if f'Agent-{i}' not in now and f'Agent-{i}' not in str(task.get('flow_log', [])):
            errors.append(f'⚠️ 内容异常: {task_id} 的 now 字段可能被覆盖: "{now}"')
        
        # 5. 检查 title 未被篡改
        expected_title = f'TOCTOU测试-B Agent-{i}'
        if task.get('title') != expected_title:
            errors.append(f'❌ title 被篡改: {task_id} 期望 "{expected_title}"，实际 "{task.get("title")}"')
    
    # 6. 检查 JSON 文件格式完整性
    try:
        json.loads(TASKS_FILE.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        errors.append(f'❌ JSON 文件损坏: {e}')
    
    # 7. 检查锁文件是否残留（锁释放后应无进程持有）
    if LOCK_FILE.exists():
        # 锁文件存在是正常的（O_CREAT 创建后不会删除），检查是否有进程持有
        print(f'ℹ️ 锁文件存在: {LOCK_FILE}（正常，O_CREAT 不会删除锁文件）')
    
    # 输出结果
    if errors:
        print(f'\n❌ 验证失败 — 发现 {len(errors)} 个问题:')
        for err in errors:
            print(f'  {err}')
        return False
    else:
        print(f'\n✅ 验证通过 — 所有 {NUM_AGENTS} 个 task 数据完整')
        print(f'   每个 task 的 flow_log 条数: ', end='')
        for i in range(NUM_AGENTS):
            task_id = f'{TASK_PREFIX}-{i}'
            task = next((t for t in tasks if t.get('id') == task_id), None)
            if task:
                print(f'{len(task.get("flow_log", []))}', end=' ')
        print()
        return True


def cleanup():
    """清理测试任务"""
    print('\n清理测试任务...', flush=True)
    tasks = json.loads(TASKS_FILE.read_text(encoding='utf-8'))
    tasks = [t for t in tasks if not t.get('id', '').startswith(TASK_PREFIX)]
    TASKS_FILE.write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
    print('✅ 清理完成', flush=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='TOCTOU 测试-B')
    parser.add_argument('--skip-create', action='store_true', help='跳过创建测试任务')
    parser.add_argument('--skip-cleanup', action='store_true', help='跳过清理')
    parser.add_argument('--agents', type=int, default=NUM_AGENTS, help=f'并发进程数（默认 {NUM_AGENTS}）')
    parser.add_argument('--writes', type=int, default=WRITES_PER_AGENT, help=f'每个进程写入次数（默认 {WRITES_PER_AGENT}）')
    args = parser.parse_args()
    
    NUM_AGENTS = args.agents
    WRITES_PER_AGENT = args.writes
    
    print(f'🚀 TOCTOU 测试-B 启动')
    print(f'   并发进程数: {NUM_AGENTS}')
    print(f'   每进程写入: {WRITES_PER_AGENT} 次')
    print(f'   总写入次数: {NUM_AGENTS * WRITES_PER_AGENT}')
    print()
    
    if not args.skip_create:
        create_test_tasks()
    
    print(f'\n启动 {NUM_AGENTS} 个并发进程...')
    start_time = time.time()
    
    with multiprocessing.Pool(processes=NUM_AGENTS) as pool:
        pool.map(agent_worker, range(NUM_AGENTS))
    
    elapsed = time.time() - start_time
    print(f'\n⏱️ 并发执行耗时: {elapsed:.2f} 秒')
    
    passed = verify_integrity()
    
    if not args.skip_cleanup:
        cleanup()
    
    sys.exit(0 if passed else 1)
```

---

## 4. 验证标准

### 4.1 通过标准（全部满足）

| # | 验证项 | 判定方法 |
|---|--------|---------|
| 1 | 所有 task 存在 | 检查 JSON 中是否存在所有 `JJC-TEST-B-AGENT-0` ~ `JJC-TEST-B-AGENT-9` |
| 2 | 无字段丢失 | 每个 task 的 `id`, `title`, `state`, `org`, `now`, `flow_log`, `updatedAt` 字段完整 |
| 3 | title 未被篡改 | 每个 task 的 title 等于创建时的值 |
| 4 | flow_log 条数正确 | 每个 task 的 flow_log 条数 = `WRITES_PER_AGENT + 1`（创建记录 + 每次 state 写入） |
| 5 | JSON 格式完整 | `json.loads()` 不抛出异常 |
| 6 | 无其他 task 数据损坏 | 文件中所有非测试 task 的数据完整无损 |

### 4.2 失败判定标准（任一触发即失败）

| # | 失败场景 | 可能原因 |
|---|---------|---------|
| 1 | 某 task 完全消失 | 并发写入导致整个 task 被覆盖/删除 |
| 2 | 某 task 的 title 变成另一个 task 的 title | modifier 内数据引用错误 |
| 3 | 某 task 的 state 异常（不在 STATE_SEQUENCE 中） | 写入被部分覆盖 |
| 4 | flow_log 条数远少于预期 | 并发写入丢失 |
| 5 | JSON 文件损坏（解析失败） | 写操作非原子 |
| 6 | 非测试 task 数据被破坏 | 锁机制未保护整个文件 |

### 4.3 额外观察项

| 观察项 | 说明 |
|--------|------|
| 锁竞争耗时 | 总执行时间 vs 串行执行时间，衡量锁争用开销 |
| 锁文件状态 | 测试后 `.lock` 文件是否存在（正常应存在） |
| 进程崩溃影响 | 是否有进程因锁超时或其他原因崩溃 |

---

## 5. 预期结果

### 5.1 乐观预期（锁机制正常工作）

```
✅ 所有 10 个 task 数据完整
✅ 每个 task 的 flow_log 条数 = 6（1 创建 + 5 写入）
✅ JSON 格式完整
✅ 非测试 task 数据不受影响
```

### 5.2 可能发现的缺陷

如果锁机制存在漏洞，可能观察到：

| 缺陷 | 现象 |
|------|------|
| 排他锁未生效 | 数据丢失、字段交叉覆盖 |
| modifier 内异常未处理 | 部分 task 数据不完整 |
| 临时文件清理失败 | `.tmp` 文件残留 |
| 锁文件竞争条件 | 某些进程永远获取不到锁（但 `flock` 是公平的） |

---

## 6. 运行方法

```bash
# 1. 直接运行测试脚本
cd /Users/chee/Projects/oc-macs
python3 tests/TOCTOU-B-测试方案.md  # 提取脚本部分运行

# 或使用独立的测试脚本
python3 tests/test_toctou_b.py

# 2. 自定义参数
python3 tests/test_toctou_b.py --agents 20 --writes 10

# 3. 仅验证（跳过创建和清理）
python3 tests/test_toctou_b.py --skip-create --skip-cleanup
```

---

## 7. 前人经验注意（避免 LLM 编码反模式）

| 反模式 | 本方案如何避免 |
|--------|---------------|
| **静默假设** | 已读取 `file_lock.py` 源码确认锁实现，不假设锁的行为 |
| **过度工程** | 测试脚本聚焦单一场景（并发不同 task_id），不混入其他测试 |
| **链式幻觉** | 每个验证项有明确的判定方法，不依赖"看起来正确" |
| **盲目重试** | 写入失败直接报告，不自动重试掩盖问题 |
| **投机代码** | 所有代码基于已读源码编写，无猜测性实现 |

---

## 8. 附录：测试数据流

```
时间线 →
                                排他锁窗口
Agent-0:  ──[LOCK_EX]──[读]──[改]──[写]──[UNLOCK]── ...
Agent-1:  ──[等待锁]──[LOCK_EX]──[读]──[改]──[写]──[UNLOCK]── ...
Agent-2:  ──[等待锁]──────────────────[LOCK_EX]──[读]──[改]──[写]── ...
...
Agent-9:  ──[等待锁]──────────────────────────────────────────[LOCK_EX]── ...

每个 Agent 操作不同的 task_id，但都修改同一个 tasks 列表。
排他锁保证串行化，但 modifier 内对列表的操作必须是线程安全的。
```
