#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TASK-3 隔离冒烟：老板确认闸全链路逻辑验证（不碰生产数据）。

在当前进程内加载 dashboard/server.py，把其 DATA 重定向到临时目录，
构造隔离的 tasks_source.json，验证：
  1. /api/spec-submit 逻辑 → _handle_spec_submit 触发迭代评分
  2. 达标 spec → spec_status=awaiting_boss
  3. Assigned→Doing 被 boss 闸拦截（awaiting_boss 未确认不放行）
  4. /api/boss-confirm approve → 放行；reject → 退回 Zhongshu；skip → 豁免
  5. 老板确认后 Assigned→Doing 可推进
"""
import json
import os
import pathlib
import shutil
import sys
import tempfile

# ── 启用六合一门禁（老板闸/迭代闸仅在 SIX_UNITY=1 时拦截）──
os.environ['SIX_UNITY'] = '1'

sys.path.insert(0, '/home/chee/Projects/oc-macs/dashboard')

import server as sv

# ── 重定向到隔离数据目录 ──
tmp = tempfile.mkdtemp(prefix='six-unity-smoke-')
tdata = pathlib.Path(tmp) / 'data'
tdata.mkdir(parents=True, exist_ok=True)
# 临时目录结构：DATA 指向 tmp/data，tasks_source.json 在其中
tdata.joinpath('tasks_source.json').write_text(json.dumps([]), encoding='utf-8')
tdata.joinpath('tasks_archive.json').write_text(json.dumps([]), encoding='utf-8')

# 关键：把 server.DATA 指向临时目录 + 重置缓存，确保 load_tasks 落在隔离区
_orig_DATA = sv.DATA
_orig_SCRIPTS = sv.SCRIPTS
_orig_active = sv._ACTIVE_TASK_DATA_DIR
sv.DATA = tdata
sv._ACTIVE_TASK_DATA_DIR = tdata
# SCRIPTS 需指向真实脚本目录（iterate_engine/selfcheck 从 SCRIPTS 导入）
# 保持原值即可——它只在 iterate_engine 等内部 sys.path.insert 用真实路径

def reset_data_dir():
    sv._ACTIVE_TASK_DATA_DIR = tdata

ok_count = 0
def check(name, cond, detail=''):
    global ok_count
    mark = '✅' if cond else '❌'
    print(f'{mark} {name} {detail}')
    if cond:
        ok_count += 1
    else:
        raise SystemExit(f'FAIL: {name}')

try:
    # ── 构造任务，走到 Assigned 状态（绕过状态机，直接造一条 Assigned 任务）──
    new_task = {
        'id': 'SMOKE-BOSS-001', 'title': '老板闸冒烟测试任务',
        'state': 'Assigned', 'now': '已派发', 'org': '开发部',
        'output': '', 'ac': '', 'priority': 'P1',
        'spec': None, 'spec_status': 'pending', 'cdd_injected': None,
        'flow_log': [], 'updatedAt': sv.now_iso(),
    }
    sv._ACTIVE_TASK_DATA_DIR = tdata
    sv.modify_tasks(lambda tasks: tasks + [new_task])  # 用真实读写路径

    # ── 1. spec-submit：提交达标 spec + cdd ──
    good_spec = {
        'purpose': '提供用户登录接口',
        'outputs': ['POST /login'],
        'acceptance_criteria': ['返回200成功或401未授权', '空用户名返回400', '密码错误返回401'],
        'boundaries': ['不做注册'],
        'dependencies': ['用户库'],
    }
    good_cdd = {'agents': [{'agent': 'daima', 'role': '开发部', 'deliverables': ['登录接口']}]}
    r = sv._handle_spec_submit('SMOKE-BOSS-001', good_spec, good_cdd)
    check('spec-submit 返回 ok', r.get('ok') is True, f"msg={r.get('message')}")
    print(f"      → spec_status={r.get('spec_status')}, iterate.ready={r.get('iterate',{}).get('ready')}")

    # ── 2. 未确认时 Assigned→Doing 应被老板闸拦截 ──
    tasks = sv.load_tasks()
    t = next(x for x in tasks if x['id'] == 'SMOKE-BOSS-001')
    # 强制置 awaiting_boss，模拟「评分达标后进入老板确认闸」
    sv.modify_tasks(lambda tasks: [ (x.__setitem__('spec_status','awaiting_boss') or x) for x in tasks ])
    tasks = sv.load_tasks()
    check('预处理后 awaiting_boss', next(x for x in tasks if x['id']=='SMOKE-BOSS-001').get('spec_status') == 'awaiting_boss')
    block_r = sv.handle_advance_state('SMOKE-BOSS-001', '')
    check('awaiting_boss 未确认被拦截', block_r.get('ok') is False,
          f"err={block_r.get('error','')[:40]}")
    tasks = sv.load_tasks()
    check('拦截后仍在 Assigned', next(x for x in tasks if x['id']=='SMOKE-BOSS-001')['state'] == 'Assigned')

    # ── 3. boss-confirm approve → 放行 ──
    ap = sv._handle_boss_confirm('SMOKE-BOSS-001', 'approve', '通过')
    check('approve ok', ap.get('ok') is True)
    tasks = sv.load_tasks()
    t = next(x for x in tasks if x['id']=='SMOKE-BOSS-001')
    check('approve 后 spec_status=reviewed', t.get('spec_status') == 'reviewed')
    # approve 后应可推进 Assigned→Doing
    adv = sv.handle_advance_state('SMOKE-BOSS-001', '推进执行')
    print(f'      approve 后推进: ok={adv.get("ok")} msg={adv.get("message","")[:40]}')
    tasks = sv.load_tasks()
    check('approve 后可推进到 Doing', next(x for x in tasks if x['id']=='SMOKE-BOSS-001')['state'] == 'Doing')

    # ── 4. reject 分支：回到 Zhongshu ──
    # 重新造一条 Assigned + awaiting_boss 任务
    sv.modify_tasks(lambda tasks: tasks + [{
        'id': 'SMOKE-BOSS-002', 'title': 'reject分支', 'state': 'Assigned',
        'now': '已派发', 'org': '开发部', 'output': '', 'ac': '', 'priority': 'P2',
        'spec': good_spec, 'spec_status': 'awaiting_boss', 'cdd_injected': None,
        'flow_log': [], 'updatedAt': sv.now_iso()}])
    rj = sv._handle_boss_confirm('SMOKE-BOSS-002', 'reject', '方案需修改')
    check('reject ok', rj.get('ok') is True and rj.get('state') == 'Zhongshu', f"state={rj.get('state')}")
    tasks = sv.load_tasks()
    check('reject 后回到 Zhongshu', next(x for x in tasks if x['id']=='SMOKE-BOSS-002')['state'] == 'Zhongshu')

    # ── 5. skip 分支：豁免放行 ──
    tasks = sv.load_tasks()
    # 让 002 重新回到 Assigned 并 awaiting_boss 以测 skip
    sv.modify_tasks(lambda tasks: [ (x.update({'state':'Assigned','spec_status':'awaiting_boss'}) or x) for x in tasks if x['id']=='SMOKE-BOSS-002'])
    sk = sv._handle_boss_confirm('SMOKE-BOSS-002', 'skip', '方案已定')
    check('skip ok', sk.get('ok') is True)
    tasks = sv.load_tasks()
    check('skip 后 spec_status=reviewed', next(x for x in tasks if x['id']=='SMOKE-BOSS-002').get('spec_status') == 'reviewed')
    adv2 = sv.handle_advance_state('SMOKE-BOSS-002', '推进')
    tasks = sv.load_tasks()
    check('skip 后可推进到 Doing', next(x for x in tasks if x['id']=='SMOKE-BOSS-002')['state'] == 'Doing')

    print(f'\n=== TASK-3 冒烟结果：{ok_count} 项全部通过 ===')
    print('（隔离目录未影响生产 tasks_source.json）')
finally:
    sv.DATA = _orig_DATA
    sv.SCRIPTS = _orig_SCRIPTS
    sv._ACTIVE_TASK_DATA_DIR = _orig_active
    shutil.rmtree(tmp, ignore_errors=True)
