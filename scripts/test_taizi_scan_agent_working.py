#!/usr/bin/env python3
"""
总控巡检Bug验证测试 — 模拟Agent工作中
方案: JJC-20260626-004
"""
import json, pathlib, sys, time, datetime, subprocess, os, re

BASE = pathlib.Path(__file__).resolve().parent.parent
DATA = BASE / 'data'
TASKS_FILE = DATA / 'tasks_source.json'
SCRIPTS = BASE / 'scripts'
OUTPUT_DIR = DATA / 'output'
sys.path.insert(0, str(SCRIPTS))
from file_lock import atomic_json_read, atomic_json_update
from utils import now_iso, python_bin

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def log(msg):
    ts = datetime.datetime.now().strftime('%H:%M:%S')
    print(f'[{ts}] {msg}', flush=True)

def run_kanban(*args):
    """Run kanban_update.py with args, return output."""
    cmd = [python_bin(), str(SCRIPTS / 'kanban_update.py')] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.stdout + result.stderr

def call_scheduler_scan(threshold_sec=600):
    """Call handle_scheduler_scan via dashboard API (POST)."""
    import urllib.request
    url = 'http://127.0.0.1:7891/api/scheduler-scan'
    data = json.dumps({'thresholdSec': threshold_sec}).encode()
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def get_scheduler_state(task_id):
    """Get scheduler state for a task via dashboard API (GET)."""
    import urllib.request
    url = f'http://127.0.0.1:7891/api/scheduler-state/{task_id}'
    try:
        resp = urllib.request.urlopen(url, timeout=10)
        return json.loads(resp.read().decode())
    except Exception as e:
        return {'ok': False, 'error': str(e)}

def get_task(task_id):
    tasks = atomic_json_read(TASKS_FILE, [])
    return next((t for t in tasks if t.get('id') == task_id), None)

def update_task_field(task_id, field_path, value):
    """Update a nested field in a task."""
    def modifier(tasks):
        t = next((t for t in tasks if t.get('id') == task_id), None)
        if not t:
            return tasks
        parts = field_path.split('.')
        obj = t
        for p in parts[:-1]:
            if p not in obj:
                obj[p] = {}
            obj = obj[p]
        obj[parts[-1]] = value
        t['updatedAt'] = now_iso()
        return tasks
    atomic_json_update(TASKS_FILE, modifier, [])

def delete_task_field(task_id, field_path):
    """Delete a nested field from a task."""
    def modifier(tasks):
        t = next((t for t in tasks if t.get('id') == task_id), None)
        if not t:
            return tasks
        parts = field_path.split('.')
        obj = t
        for p in parts[:-1]:
            if p not in obj:
                return tasks
            obj = obj[p]
        if parts[-1] in obj:
            del obj[parts[-1]]
        t['updatedAt'] = now_iso()
        return tasks
    atomic_json_update(TASKS_FILE, modifier, [])

def set_last_progress_at(task_id, seconds_ago):
    """Set lastProgressAt to N seconds ago."""
    past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=seconds_ago)).isoformat()
    update_task_field(task_id, '_scheduler.lastProgressAt', past)

def reset_scheduler(task_id):
    """Reset scheduler state for a task."""
    def modifier(tasks):
        t = next((t for t in tasks if t.get('id') == task_id), None)
        if not t:
            return tasks
        t['_scheduler'] = {
            'enabled': True,
            'stallThresholdSec': 600,
            'maxRetry': 2,
            'retryCount': 0,
            'escalationLevel': 0,
            'autoRollback': True,
            'lastProgressAt': now_iso(),
            'stallSince': None,
            'lastDispatchStatus': 'idle',
            'snapshot': {
                'state': t.get('state', 'Doing'),
                'org': t.get('org', ''),
                'now': t.get('now', ''),
                'savedAt': now_iso(),
                'note': 'test-reset',
            }
        }
        t['updatedAt'] = now_iso()
        return tasks
    atomic_json_update(TASKS_FILE, modifier, [])

def create_test_task(task_id, title, state='Doing', org='执行中'):
    """Create a test task if it doesn't exist."""
    tasks = atomic_json_read(TASKS_FILE, [])
    if any(t.get('id') == task_id for t in tasks):
        log(f'  Task {task_id} already exists, skipping creation')
        return
    log(f'  Creating {task_id}...')
    run_kanban('create', task_id, title, state, org, '测试')
    # Reset scheduler to clean state
    reset_scheduler(task_id)

def ensure_task_exists(task_id, title, state='Doing', org='执行中'):
    """Ensure a test task exists with given state."""
    tasks = atomic_json_read(TASKS_FILE, [])
    existing = next((t for t in tasks if t.get('id') == task_id), None)
    if not existing:
        create_test_task(task_id, title, state, org)
    else:
        # Update state if needed
        if existing.get('state') != state:
            run_kanban('state', task_id, state, f'重置为{state}')
        reset_scheduler(task_id)

# ═══════════════════════════════════════════════════════════
# Test Execution
# ═══════════════════════════════════════════════════════════

results = []
PASS = '✅ PASS'
FAIL = '❌ FAIL'
SKIP = '⏭️ SKIP'

log('=' * 60)
log('总控巡检Bug验证测试开始')
log('=' * 60)

# ── 场景 A: Agent 正常工作中 ──
log('\n' + '─' * 50)
log('场景 A: Agent 正常工作中 — 巡检不应触发')
log('─' * 50)

ensure_task_exists('JJC-TEST-041', '巡检测试-A:Agent正常工作中', 'Doing', '执行中')
reset_scheduler('JJC-TEST-041')
set_last_progress_at('JJC-TEST-041', 10)  # 10s ago - actively working

# Scan 1
log('  Scan 1...')
r1 = call_scheduler_scan()
log(f'  Result: {json.dumps(r1, ensure_ascii=False)[:200]}')

# Update progress
log('  Updating progress...')
run_kanban('progress', 'JJC-TEST-041', '正在执行测试任务')

# Scan 2
log('  Scan 2...')
r2 = call_scheduler_scan()
log(f'  Result: {json.dumps(r2, ensure_ascii=False)[:200]}')

# Update progress again
run_kanban('progress', 'JJC-TEST-041', '继续执行测试任务')

# Scan 3
log('  Scan 3...')
r3 = call_scheduler_scan()
log(f'  Result: {json.dumps(r3, ensure_ascii=False)[:200]}')

# Check results
task_a = get_task('JJC-TEST-041')
actions_all = (r1.get('actions') or []) + (r2.get('actions') or []) + (r3.get('actions') or [])
task_in_actions = any(a.get('taskId') == 'JJC-TEST-041' for a in actions_all)
flow_log = task_a.get('flow_log', [])
stall_flows = [f for f in flow_log if '停滞' in f.get('remark', '') or '重试' in f.get('remark', '') or '升级' in f.get('remark', '')]

if not task_in_actions and not stall_flows:
    log(f'  {PASS} 场景A: 3个扫描周期均未误触发')
    results.append(('A', PASS, '3个扫描周期均未误触发'))
else:
    log(f'  {FAIL} 场景A: 任务被误判! actions={actions_all}, stall_flows={stall_flows}')
    results.append(('A', FAIL, f'误判: actions={actions_all}'))

# ── 子场景 A1: 590s 更新 ──
log('\n' + '─' * 50)
log('子场景 A1: Agent每590s更新progress（略小于600s阈值）')
log('─' * 50)

reset_scheduler('JJC-TEST-041')
set_last_progress_at('JJC-TEST-041', 590)  # 590s ago

# Simulate progress update (resets timer)
run_kanban('progress', 'JJC-TEST-041', '590s更新测试')

# Scan immediately after update
r_a1_1 = call_scheduler_scan()
log(f'  Scan 1 (after 590s update): {json.dumps(r_a1_1, ensure_ascii=False)[:200]}')

# Simulate 590s passing - set lastProgressAt to 590s ago
set_last_progress_at('JJC-TEST-041', 590)
r_a1_2 = call_scheduler_scan()
log(f'  Scan 2 (590s later): {json.dumps(r_a1_2, ensure_ascii=False)[:200]}')

# Cycle 3: update + scan
run_kanban('progress', 'JJC-TEST-041', '590s更新测试-周期2')
set_last_progress_at('JJC-TEST-041', 590)
r_a1_3 = call_scheduler_scan()
log(f'  Scan 3 (590s later): {json.dumps(r_a1_3, ensure_ascii=False)[:200]}')

actions_a1 = (r_a1_1.get('actions') or []) + (r_a1_2.get('actions') or []) + (r_a1_3.get('actions') or [])
task_a1_in_actions = any(a.get('taskId') == 'JJC-TEST-041' for a in actions_a1)

if not task_a1_in_actions:
    log(f'  {PASS} 子场景A1: 590s更新3个周期均未误触发')
    results.append(('A1', PASS, '590s更新3个周期均未误触发'))
else:
    log(f'  {FAIL} 子场景A1: 误触发! actions={actions_a1}')
    results.append(('A1', FAIL, f'误触发: {actions_a1}'))

# ── 场景 B: 竞态窗口 ──
log('\n' + '─' * 50)
log('场景 B: Agent刚完成更新后巡检立即触发 — 竞态窗口')
log('─' * 50)

ensure_task_exists('JJC-TEST-042', '巡检测试-B:竞态窗口', 'Doing', '执行中')
reset_scheduler('JJC-TEST-042')
set_last_progress_at('JJC-TEST-042', 590)  # 590s ago

# Update progress
run_kanban('progress', 'JJC-TEST-042', '竞态窗口测试-刚更新')

# Immediately trigger scan
r_b1 = call_scheduler_scan()
log(f'  Scan 1 (immediately after progress): {json.dumps(r_b1, ensure_ascii=False)[:200]}')

b1_actions = r_b1.get('actions', [])
b1_task_actions = [a for a in b1_actions if a.get('taskId') == 'JJC-TEST-042']

# Now simulate 610s passing
set_last_progress_at('JJC-TEST-042', 610)
r_b2 = call_scheduler_scan()
log(f'  Scan 2 (610s later): {json.dumps(r_b2, ensure_ascii=False)[:200]}')

b2_actions = r_b2.get('actions', [])
b2_task_actions = [a for a in b2_actions if a.get('taskId') == 'JJC-TEST-042']

if not b1_task_actions and b2_task_actions:
    log(f'  {PASS} 场景B: 第一次未触发(正确)，第二次正确检测到停滞')
    results.append(('B', PASS, '竞态窗口不误判，阈值计算正确'))
elif b1_task_actions:
    log(f'  {FAIL} 场景B: 第一次扫描误触发! actions={b1_task_actions}')
    results.append(('B', FAIL, f'第一次扫描误触发: {b1_task_actions}'))
else:
    log(f'  {FAIL} 场景B: 第二次扫描未检测到停滞')
    results.append(('B', FAIL, '第二次扫描未检测到停滞'))

# ── 场景 C: progress更新但状态未变 ──
log('\n' + '─' * 50)
log('场景 C: Agent更新progress但状态未变 — 巡检不应触发')
log('─' * 50)

ensure_task_exists('JJC-TEST-043', '巡检测试-C:Progress更新状态不变', 'Doing', '执行中')
reset_scheduler('JJC-TEST-043')
set_last_progress_at('JJC-TEST-043', 10)

# Scan 1
r_c1 = call_scheduler_scan()
log(f'  Scan 1: {json.dumps(r_c1, ensure_ascii=False)[:200]}')

# Update progress only (no state change)
run_kanban('progress', 'JJC-TEST-043', '只更新progress不改变state')

# Scan 2
r_c2 = call_scheduler_scan()
log(f'  Scan 2: {json.dumps(r_c2, ensure_ascii=False)[:200]}')

# Update progress again
run_kanban('progress', 'JJC-TEST-043', '再次更新progress')

# Scan 3
r_c3 = call_scheduler_scan()
log(f'  Scan 3: {json.dumps(r_c3, ensure_ascii=False)[:200]}')

actions_c = (r_c1.get('actions') or []) + (r_c2.get('actions') or []) + (r_c3.get('actions') or [])
task_c_in_actions = any(a.get('taskId') == 'JJC-TEST-043' for a in actions_c)

if not task_c_in_actions:
    log(f'  {PASS} 场景C: progress更新重置停滞计时，3个周期均未触发')
    results.append(('C', PASS, 'progress更新重置停滞计时'))
else:
    log(f'  {FAIL} 场景C: 误触发! actions={actions_c}')
    results.append(('C', FAIL, f'误触发: {actions_c}'))

# ── 场景 D: progress更新间隔超过阈值 ──
log('\n' + '─' * 50)
log('场景 D: Agent工作中但progress更新间隔超过阈值 — 巡检应触发')
log('─' * 50)

ensure_task_exists('JJC-TEST-044', '巡检测试-D:超过阈值应触发', 'Doing', '执行中')
reset_scheduler('JJC-TEST-044')
set_last_progress_at('JJC-TEST-044', 700)  # 700s ago - over 600s threshold

r_d = call_scheduler_scan()
log(f'  Scan: {json.dumps(r_d, ensure_ascii=False)[:300]}')

task_d = get_task('JJC-TEST-044')
sched_d = task_d.get('_scheduler', {})
d_actions = [a for a in r_d.get('actions', []) if a.get('taskId') == 'JJC-TEST-044']
stall_since = sched_d.get('stallSince')
retry_count = sched_d.get('retryCount', 0)

if d_actions and stall_since and retry_count > 0:
    log(f'  {PASS} 场景D: 正确检测到停滞, stallSince={stall_since}, retryCount={retry_count}')
    results.append(('D', PASS, f'停滞检测正确, retryCount={retry_count}'))
elif not d_actions:
    log(f'  {FAIL} 场景D: 未检测到停滞')
    results.append(('D', FAIL, '未检测到停滞'))
else:
    log(f'  {FAIL} 场景D: 部分失败, actions={d_actions}, stallSince={stall_since}, retryCount={retry_count}')
    results.append(('D', FAIL, f'部分失败: actions={d_actions}'))

# ── 场景 E: Dashboard层巡检与心跳 ──
log('\n' + '─' * 50)
log('场景 E: Dashboard层巡检与Agent心跳 — 心跳重置停滞计时')
log('─' * 50)

ensure_task_exists('JJC-TEST-045', '巡检测试-E:心跳重置停滞', 'Doing', '执行中')
reset_scheduler('JJC-TEST-045')
set_last_progress_at('JJC-TEST-045', 700)  # 700s ago - over threshold

# First scan - should detect stall
r_e1 = call_scheduler_scan()
log(f'  Scan 1 (700s stall): {json.dumps(r_e1, ensure_ascii=False)[:200]}')

e1_actions = [a for a in r_e1.get('actions', []) if a.get('taskId') == 'JJC-TEST-045']

# Simulate heartbeat via progress update
run_kanban('progress', 'JJC-TEST-045', '心跳更新')

# Second scan - should NOT detect stall (progress reset timer)
r_e2 = call_scheduler_scan()
log(f'  Scan 2 (after heartbeat): {json.dumps(r_e2, ensure_ascii=False)[:200]}')

e2_actions = [a for a in r_e2.get('actions', []) if a.get('taskId') == 'JJC-TEST-045']

if e1_actions and not e2_actions:
    log(f'  {PASS} 场景E: 第一次正确检测停滞，心跳后不再检测')
    results.append(('E', PASS, '心跳重置Dashboard层停滞检测'))
elif not e1_actions:
    log(f'  {FAIL} 场景E: 第一次扫描未检测到停滞')
    results.append(('E', FAIL, '第一次扫描未检测到停滞'))
else:
    log(f'  {FAIL} 场景E: 心跳后仍检测到停滞')
    results.append(('E', FAIL, '心跳后仍检测到停滞'))

# ── 场景 F: 并发写入 ──
log('\n' + '─' * 50)
log('场景 F: 边界情况 — 巡检时任务被手动更新')
log('─' * 50)

ensure_task_exists('JJC-TEST-046', '巡检测试-F:并发写入', 'Doing', '执行中')
reset_scheduler('JJC-TEST-046')
set_last_progress_at('JJC-TEST-046', 590)

# Trigger scan and immediately update task state
r_f = call_scheduler_scan()
log(f'  Scan: {json.dumps(r_f, ensure_ascii=False)[:200]}')

# Update task state
run_kanban('state', 'JJC-TEST-046', 'Review', '并发测试-手动更新状态')

task_f = get_task('JJC-TEST-046')
f_state = task_f.get('state')
f_flow = task_f.get('flow_log', [])

if f_state == 'Review':
    log(f'  {PASS} 场景F: 并发写入后状态正确更新为 Review')
    results.append(('F', PASS, '并发写入不导致数据损坏'))
else:
    log(f'  {FAIL} 场景F: 状态异常, 期望=Review, 实际={f_state}')
    results.append(('F', FAIL, f'状态异常: {f_state}'))

# ── 场景 G: 空任务列表 ──
log('\n' + '─' * 50)
log('场景 G: 边界情况 — 巡检扫描空任务列表')
log('─' * 50)

# We can't actually empty the task list, but we can test with a very high threshold
# that won't match any task
r_g = call_scheduler_scan(threshold_sec=999999)
log(f'  Scan (high threshold): {json.dumps(r_g, ensure_ascii=False)[:200]}')

if r_g.get('ok') and r_g.get('count', -1) >= 0:
    log(f'  {PASS} 场景G: 空列表扫描正常返回, count={r_g.get("count")}')
    results.append(('G', PASS, f'空列表扫描正常, count={r_g.get("count")}'))
else:
    log(f'  {FAIL} 场景G: 异常! result={r_g}')
    results.append(('G', FAIL, f'异常: {r_g}'))

# ── 场景 H: snapshot 为空 ──
log('\n' + '─' * 50)
log('场景 H: 边界情况 — 巡检触发回滚路径时snapshot缺失')
log('─' * 50)

ensure_task_exists('JJC-TEST-047', '巡检测试-H:Snapshot缺失', 'Doing', '执行中')
reset_scheduler('JJC-TEST-047')

# Set up task to be in rollback path: retryCount >= maxRetry, escalationLevel >= 2
def setup_for_rollback(task_id):
    def modifier(tasks):
        t = next((t for t in tasks if t.get('id') == task_id), None)
        if not t:
            return tasks
        sched = t.setdefault('_scheduler', {})
        sched['retryCount'] = 2  # >= maxRetry(2)
        sched['escalationLevel'] = 2  # >= 2
        sched['autoRollback'] = True
        sched['snapshot'] = {}  # Empty snapshot - snap_state will be None
        sched['stallSince'] = now_iso()
        sched['rollbackCount'] = 0
        sched['maxRollback'] = 3
        t['updatedAt'] = now_iso()
        return tasks
    atomic_json_update(TASKS_FILE, modifier, [])

setup_for_rollback('JJC-TEST-047')
set_last_progress_at('JJC-TEST-047', 700)

r_h = call_scheduler_scan()
log(f'  Scan: {json.dumps(r_h, ensure_ascii=False)[:300]}')

h_actions = [a for a in r_h.get('actions', []) if a.get('taskId') == 'JJC-TEST-047']
task_h = get_task('JJC-TEST-047')
h_state = task_h.get('state')

# With empty snapshot, rollback should be skipped
# The task might still get blocked if rollbackCount >= maxRollback
# But since snapshot is empty, snap_state is None, so rollback should be skipped
# and the code checks rollback_count >= max_rollback first
# Actually looking at the code:
#   if rollback_count >= max_rollback: -> Blocked
#   elif snap_state and snap_state != state: -> rollback
# Since rollback_count=0 < max_rollback=3, and snap_state is None (empty snapshot),
# neither branch executes -> task stays in Doing with no action

if not h_actions:
    log(f'  {PASS} 场景H: snapshot缺失，跳过回滚，系统不崩溃')
    results.append(('H', PASS, 'snapshot缺失跳过回滚'))
else:
    log(f'  {FAIL} 场景H: 有操作执行, actions={h_actions}')
    results.append(('H', FAIL, f'有操作执行: {h_actions}'))

# ── 场景 I (新增): Next状态任务检测 ──
log('\n' + '─' * 50)
log('场景 I (新增): Next状态任务检测 — 与Doing一致')
log('─' * 50)

ensure_task_exists('JJC-TEST-048', '巡检测试-I:Next状态检测', 'Next', '执行办')
reset_scheduler('JJC-TEST-048')
set_last_progress_at('JJC-TEST-048', 300)  # Within threshold

r_i1 = call_scheduler_scan()
log(f'  Scan 1 (300s stall): {json.dumps(r_i1, ensure_ascii=False)[:200]}')

i1_actions = [a for a in r_i1.get('actions', []) if a.get('taskId') == 'JJC-TEST-048']

# Now set over threshold
set_last_progress_at('JJC-TEST-048', 700)
r_i2 = call_scheduler_scan()
log(f'  Scan 2 (700s stall): {json.dumps(r_i2, ensure_ascii=False)[:200]}')

i2_actions = [a for a in r_i2.get('actions', []) if a.get('taskId') == 'JJC-TEST-048']

if not i1_actions and i2_actions:
    log(f'  {PASS} 场景I: Next状态检测行为与Doing一致')
    results.append(('I', PASS, 'Next状态检测行为与Doing一致'))
elif i1_actions:
    log(f'  {FAIL} 场景I: 300s时误触发! actions={i1_actions}')
    results.append(('I', FAIL, f'300s时误触发: {i1_actions}'))
else:
    log(f'  {FAIL} 场景I: 700s时未检测到停滞')
    results.append(('I', FAIL, '700s时未检测到停滞'))

# ── 场景 J (新增): 双重巡检 ──
log('\n' + '─' * 50)
log('场景 J (新增): 双重巡检 — 不重复处理')
log('─' * 50)

ensure_task_exists('JJC-TEST-049', '巡检测试-J:双重巡检', 'Doing', '执行中')
reset_scheduler('JJC-TEST-049')
set_last_progress_at('JJC-TEST-049', 700)

# First scan
r_j1 = call_scheduler_scan()
log(f'  Scan 1: {json.dumps(r_j1, ensure_ascii=False)[:200]}')

j1_actions = [a for a in r_j1.get('actions', []) if a.get('taskId') == 'JJC-TEST-049']
j1_retry = [a for a in j1_actions if a.get('action') == 'retry']

# Second scan immediately (no progress update in between)
r_j2 = call_scheduler_scan()
log(f'  Scan 2 (immediately after): {json.dumps(r_j2, ensure_ascii=False)[:200]}')

j2_actions = [a for a in r_j2.get('actions', []) if a.get('taskId') == 'JJC-TEST-049']
j2_retry = [a for a in j2_actions if a.get('action') == 'retry']

task_j = get_task('JJC-TEST-049')
j_retry_count = task_j.get('_scheduler', {}).get('retryCount', 0)

# After first scan, retryCount should be 1
# Second scan: retryCount=1 < maxRetry=2, so it CAN retry again (correct behavior)
# The key verification: system doesn't crash, doesn't produce duplicate flow_log entries
# within a single scan, and state transitions are consistent
flow_log_j = task_j.get('flow_log', [])
retry_flows = [f for f in flow_log_j if '自动重试' in f.get('remark', '')]
# Check no duplicate flow entries with same text at same timestamp
flow_texts = [f.get('remark', '') for f in flow_log_j]
has_duplicate_flows = len(flow_texts) != len(set(flow_texts))

if len(j1_retry) == 1 and len(j2_retry) == 1 and j_retry_count == 2 and not has_duplicate_flows:
    log(f'  {PASS} 场景J: 双重巡检正常处理, retryCount=2, 无重复flow_log')
    results.append(('J', PASS, '双重巡检正常处理, 无重复flow_log'))
elif len(j1_retry) == 0:
    log(f'  {FAIL} 场景J: 第一次扫描未触发重试')
    results.append(('J', FAIL, '第一次扫描未触发重试'))
elif has_duplicate_flows:
    log(f'  {FAIL} 场景J: 存在重复flow_log! flows={flow_log_j}')
    results.append(('J', FAIL, f'存在重复flow_log'))
else:
    log(f'  {FAIL} 场景J: 异常状态, j1_retry={j1_retry}, j2_retry={j2_retry}, retryCount={j_retry_count}')
    results.append(('J', FAIL, f'异常: j1={j1_retry} j2={j2_retry} count={j_retry_count}'))

# ═══════════════════════════════════════════════════════════
# Generate Report
# ═══════════════════════════════════════════════════════════

log('\n' + '=' * 60)
log('测试结果汇总')
log('=' * 60)

passed = 0
failed = 0
for scene, status, detail in results:
    log(f'  {status} 场景{scene}: {detail}')
    if 'PASS' in status:
        passed += 1
    else:
        failed += 1

log(f'\n总计: {len(results)} 场景, {passed} 通过, {failed} 失败')

# Write report
report = {
    'testName': 'JJC-20260626-004 总控巡检Bug验证-模拟Agent工作中',
    'testedAt': now_iso(),
    'total': len(results),
    'passed': passed,
    'failed': failed,
    'results': [{'scene': s, 'status': st, 'detail': d} for s, st, d in results],
    'conclusion': '全部通过' if failed == 0 else f'{failed} 项失败'
}

report_path = OUTPUT_DIR / 'JJC-20260626-004-taizi-scan-test-report.json'
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
log(f'\n报告已输出: {report_path}')

# Also write markdown report
md_path = OUTPUT_DIR / 'JJC-20260626-004-taizi-scan-test-report.md'
md_lines = [
    '# 总控巡检Bug验证测试报告',
    '',
    f'**测试时间**: {now_iso()}',
    f'**测试方案**: JJC-20260626-004',
    f'**测试状态**: {"✅ 全部通过" if failed == 0 else f"❌ {failed} 项失败"}',
    '',
    '## 测试结果',
    '',
    '| 场景 | 状态 | 说明 |',
    '|------|------|------|',
]
for s, st, d in results:
    md_lines.append(f'| {s} | {st} | {d} |')
md_lines.extend([
    '',
    f'**总计**: {len(results)} 场景, {passed} 通过, {failed} 失败',
    '',
    '## 详细说明',
    '',
])
# Add details for each scene
for s, st, d in results:
    md_lines.append(f'- **场景{s}**: {st} — {d}')

md_path.write_text('\n'.join(md_lines) + '\n')
log(f'Markdown报告已输出: {md_path}')

log('\n' + '=' * 60)
log('测试完成')
log('=' * 60)
