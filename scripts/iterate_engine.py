#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""iterate_engine.py — 迭代至98%引擎（六合一闭环核心）

实现「持续拉高内容颗粒度，补齐全部缺失模块；整体反复迭代，
直至整套方案落地把握达到 98%，再输出最终成品」的循环。

与 selfcheck_engine.py 关系：
  - selfcheck_engine: 单次七维评分（D1-D7，PASS_THRESHOLD=98）
  - iterate_engine:   在其之上做「短板→补齐动作→重评→累积迭代」循环，
                      直到 is_ready() 返回 True（≥98 且无短板）。

用法（被 dashboard/server.py 在 Menxia→Assigned 门禁中调用）：
  from iterate_engine import score, iterate, is_ready
"""

import hashlib
import json
import pathlib
import sys

_SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
_DATA_DIR = _PROJECT_ROOT / 'data'


def content_hash(task):
    """对任务的可迭代内容做稳定 hash（spec+cdd+title+output+ac）。

    用于跨 submit 周期比对：本次 iterate 起始内容 vs 上次 iterate 记录的
    整改 hash —— 相同则说明「补齐动作未被规划部消化」，判定 stalled（停滞）。
    """
    blob = {
        'spec': task.get('spec'),
        'cdd': task.get('cdd'),
        'title': task.get('title', ''),
        'output': task.get('output', ''),
        'ac': task.get('ac', ''),
    }
    raw = json.dumps(blob, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _load_selfcheck():
    """懒加载 selfcheck_engine（避免循环导入）。"""
    sys.path.insert(0, str(_SCRIPT_DIR))
    import selfcheck_engine as sce
    return sce


# ── 阈值（与 selfcheck 一致，98 即老板要求的「把握度 98%」）──
PASS_THRESHOLD = 98.0
MAX_ROUNDS_DEFAULT = 3          # 默认最多迭代轮数
_MIN_SPEC_FIELDS = ['purpose', 'outputs', 'acceptance_criteria']


def spec_present(task):
    """SDD 契约是否已提交（spec 是 dict 且含核心字段）。"""
    spec = task.get('spec')
    if not isinstance(spec, dict):
        return False, '无 SDD 契约（spec 为 None）'
    missing = [f for f in _MIN_SPEC_FIELDS if not spec.get(f)]
    if missing:
        return False, f'SDD 契约缺核心字段: {",".join(missing)}'
    return True, ''


def cdd_present(task):
    """CDD 协作契约框架是否已提交（军师写的 task['cdd']）。"""
    cdd = task.get('cdd')
    if not isinstance(cdd, dict):
        return False, '无 CDD 协作契约（cdd 为 None）'
    agents = cdd.get('agents')
    if not isinstance(agents, list) or not agents:
        return False, 'CDD 缺 agents（涉及哪些 Agent 协作）'
    return True, ''


def score(task, mode='A'):
    """七维评分 → {score_pct, dims, short_dims, verdict}（委托 selfcheck）。"""
    sce = _load_selfcheck()
    try:
        audit = sce.run_selfcheck(task, mode=mode)
    except Exception as e:
        # 引擎异常 → 降级：视为未就绪但记录错误
        return {
            'mode': mode, 'score_pct': 0.0, 'dims': {},
            'short_dims': ['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7'],
            'verdict': 'fail', 'error': str(e),
        }
    return audit


def short_dims_of(audit):
    """从评分结果取短板维度列表。"""
    if not audit:
        return []
    sd = audit.get('short_dims') or []
    # 若总分不足但无显式短板（如文本为空），按 D2/D5 兜底提示
    if not sd and audit.get('score_pct', 0) < PASS_THRESHOLD < 100:
        sd = [d for d, s in (audit.get('dims') or {}).items() if s <= 60] or ['D2', 'D5']
    return sd


def is_ready(task, audit=None):
    """是否已就绪（≥98 且无短板 + SDD/CDD 契约齐全）。"""
    spec_ok, spec_why = spec_present(task)
    if not spec_ok:
        return False, spec_why
    cdd_ok, cdd_why = cdd_present(task)
    if not cdd_ok:
        return False, cdd_why
    if audit is None:
        audit = score(task, mode='C')
    ready = audit.get('verdict') == 'pass' and (audit.get('score_pct') or 0) >= PASS_THRESHOLD
    if not ready:
        why = f'评分 {audit.get("score_pct")}% < {PASS_THRESHOLD}% 或存在短板 {short_dims_of(audit)}'
        return False, why
    return True, ''


def iterate(task, max_rounds=None, flow_log_append=None):
    """迭代补齐循环。

    每轮：
      1. 评分 → 短板清单
      2. 若就绪 → 返回 ready
      3. 否则按短板生成补齐动作，写入 task['decomp_audit']['iterate']，
         提示军师补齐（通过 flow_log 留痕）

    【停滞检测（跨 submit 周期）】收敛判定必须跨 submit 周期比对：
      用本次 iterate 起始的 content hash 对比上次 iterate 记录的整改
      remediation_hash（见末尾持久化）。相同 → 本轮内容与上一轮未变化，
      即「补齐动作未被消化」→ 置 stalled=True 并立即停止，不误报达标。
      （不能在单次 iterate 内部几轮间比，那样内容每轮不变必然误判。）

    返回 {'ready': bool, 'score_pct': float, 'rounds': int, 'history': [...],
           'why': str, 'stalled': bool}
    """
    max_rounds = max_rounds or MAX_ROUNDS_DEFAULT
    history = []
    spec_ok, spec_why = spec_present(task)
    if not spec_ok:
        # 军师还没交 SDD → 未就绪
        return {'ready': False, 'score_pct': 0.0, 'rounds': 0,
                'history': history, 'why': spec_why, 'stalled': False}

    sce = _load_selfcheck()
    now_hash = content_hash(task)

    # ── 跨 submit 周期停滞判定 ──
    # 上次 iterate 结束时记录的「整改 hash」：规划部若已按要求改 spec 重交，
    # 本次 content hash 应不同；若相同说明整改未消化。
    prev_iter = (task.get('decomp_audit') or {}).get('iterate') or {}
    prev_hash = prev_iter.get('remediation_hash')
    stalled = False
    if prev_hash and prev_hash == now_hash and not prev_iter.get('ready'):
        stalled = True
        if flow_log_append:
            flow_log_append({
                'from': '迭代引擎', 'to': '规划部补齐',
                'remark': f'停滞检测：本轮 spec 与上次整改一致（未消化补齐），未放行',
            })
        history.append({'round': 0, 'stalled': True,
                        'score_pct': prev_iter.get('final_score_pct') or 0.0,
                        'short_dims': [], 'verdict': 'stalled'})
        item = {
            'ready': False, 'score_pct': (prev_iter.get('final_score_pct') or 0.0),
            'rounds': 0, 'history': history,
            'why': '整改未消化：上次补齐要求未反映到 spec（内容 hash 未变），请规划部按要求改写后重新提交',
            'stalled': True,
        }
        _persist_iterate(task, item, now_hash, final_audit=None, history=history)
        return item

    final_audit = None
    for rnd in range(1, max_rounds + 1):
        audit = score(task, mode='A' if rnd == 1 else 'B')
        final_audit = audit
        sd = short_dims_of(audit)
        sc = audit.get('score_pct', 0.0)
        ready = (audit.get('verdict') == 'pass' and sc >= PASS_THRESHOLD)
        round_rec = {'round': rnd, 'score_pct': sc, 'short_dims': sd, 'verdict': audit.get('verdict')}
        history.append(round_rec)

        if ready:
            if flow_log_append:
                flow_log_append({'from': '迭代引擎', 'to': '老板确认',
                                 'remark': f'第{rnd}轮评分 {sc}% ≥ 98%，方案就绪'})
            break

        # 未就绪 → 生成补齐动作（提示军师）
        remediation = sce.gen_remediation(task, sd) if sd else []
        round_rec['remediation'] = remediation
        if flow_log_append:
            dims_txt = ','.join(sd) if sd else '内容不足'
            flow_log_append({'from': '迭代引擎', 'to': '规划部补齐',
                             'remark': f'第{rnd}轮 {sc}% 未达98%，短板[{dims_txt}]，生成{len(remediation)}条补齐动作'})

    ready_final = final_audit and final_audit.get('verdict') == 'pass' and (final_audit.get('score_pct', 0) >= PASS_THRESHOLD)
    result_rec = {
        'ready': ready_final,
        'score_pct': final_audit.get('score_pct') if final_audit else 0.0,
        'rounds': len(history),
        'history': history,
        'why': '' if ready_final else f'第{max_rounds}轮仍 <98%，需继续补齐（见 history.short_dims）',
        'stalled': False,
    }
    _persist_iterate(task, result_rec, now_hash, final_audit=final_audit, history=history)
    return result_rec


def _persist_iterate(task, rec, now_hash, final_audit=None, history=None):
    """把 iterate 结果落盘到 task['decomp_audit']['iterate']，持久化当前
    content hash 供下一次 submit 周期做停滞比对。"""
    task.setdefault('decomp_audit', {})
    it = {
        'ready': rec['ready'],
        'final_score_pct': final_audit.get('score_pct') if final_audit else rec.get('score_pct'),
        'rounds': rec.get('rounds', 0),
        'history': rec.get('history') or history or [],
        'stalled': rec.get('stalled', False),
        'spec_hash': now_hash,
        # 整改基准 hash：即便本轮未达 98，也把当前内容 hash 记下，
        # 规划部按要求改完后重交 → 下次 content hash 变化 → 视为消化。
        'remediation_hash': now_hash,
        'ts': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
    }
    task['decomp_audit']['iterate'] = it


def summarize(task):
    """调试/看板展示用简述。"""
    it = (task.get('decomp_audit') or {}).get('iterate') or {}
    return {
        'ready': it.get('ready', False),
        'stalled': it.get('stalled', False),
        'final_score_pct': it.get('final_score_pct'),
        'rounds': it.get('rounds', 0),
        'spec_present': bool(task.get('spec')),
        'cdd_present': bool(task.get('cdd')),
    }


if __name__ == '__main__':
    # 自测：构造一个就绪/未就绪任务
    import json as _json
    ready_task = {
        'id': 'TEST-READY',
        'title': '实现用户登录接口，输出JSON，含异常与空值处理，验收标准为返回200或401',
        'org': '开发部',
        'spec': {
            'purpose': '提供登录接口',
            'outputs': ['POST /login'],
            'acceptance_criteria': ['返回200成功或401未授权，空用户名返回400'],
            'boundaries': ['不做注册'],
            'dependencies': ['用户库'],
        },
        'cdd': {'agents': [{'agent': 'daima', 'role': '开发部', 'deliverables': ['登录接口']}]},
    }
    r = iterate(ready_task, max_rounds=2)
    print('READY iter:', _json.dumps({'ready': r['ready'], 'score': r['score_pct'], 'rounds': r['rounds']}, ensure_ascii=False))

    # 自测2：停滞检测（跨 submit 周期）——同一内容不消化 → 第2次提交应判 stalled
    task_full = {
        'id': 'TEST-SPEC',
        'title': '实现用户登录接口，输出JSON，含异常与空值处理，验收标准为返回200或401',
        'org': '开发部',
        'spec': {
            'purpose': '提供登录接口',
            'outputs': ['POST /login'],
            'acceptance_criteria': ['返回200成功或401未授权，空用户名返回400'],
            'boundaries': ['不做注册'],
            'dependencies': ['用户库'],
        },
        'cdd': {'agents': [{'agent': 'daima', 'role': '开发部', 'deliverables': ['登录接口']}]},
    }
    # 用残缺 spec 制造不达标 → 首次迭代未 ready，并持久化 remediation_hash
    task_full['spec']['acceptance_criteria'] = '返回200'  # 过简
    first = iterate(task_full, max_rounds=3)
    print('FIRST  iter:', _json.dumps({'ready': first['ready'], 'score': first['score_pct'], 'stalled': first.get('stalled')}, ensure_ascii=False))
    # 第2次提交：内容未消化（原样重提）→ 应 stalled=True
    second = iterate(task_full, max_rounds=3)
    print('STALLED iter:', _json.dumps({'ready': second['ready'], 'stalled': second.get('stalled'), 'why': second.get('why')}, ensure_ascii=False))
    assert second.get('stalled') is True, '应该触发跨 submit 停滞检测'
    assert second['ready'] is False, '停滞时绝不放行'
    # 第3次：规划部真的改了内容（补齐）→ 不再 stalled，重新评分
    task_full['spec']['acceptance_criteria'] = ['返回200成功或401未授权，空用户名返回400，密码错误返回401']
    third = iterate(task_full, max_rounds=2)
    print('DIGESTED iter:', _json.dumps({'ready': third['ready'], 'stalled': third.get('stalled'), 'score': third['score_pct']}, ensure_ascii=False))
