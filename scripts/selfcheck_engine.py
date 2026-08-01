#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""selfcheck_engine.py — 任务分解自查引擎（七维评分 D1-D7 + 补齐动作）

供 scripts/six_unity.py 调用。实现方案 §6 的持续迭代自查：
  - run_selfcheck(task, mode)     七维评分 → {score_pct, dims, verdict, short_dims}
  - gen_remediation(task, dims)   按短板生成补齐动作清单
  - record_audit(task, audit)     写审计 JSON 到 data/audit/

评分规则（方案 §6.2 D1-D7）：
  D1 可独立执行    —— 无"参考之前/类似/按惯例"等模糊引用
  D2 可独立验收    —— 有可验证 pass/fail 标准
  D3 边界覆盖      —— 覆盖异常/边界场景
  D4 依赖完整性    —— 前置依赖显式列出
  D5 模糊词消除    —— 无"尽快/适当/合理/必要时"等
  D6 模块完备      —— 输入→处理→输出→反馈 全链条
  D7 可测试性      —— 有可验证断言

单维度 ≤60 → 短板项（一票打回）。总分 = avg(D1..D7)。≥98 且无短板 → pass。
"""

import json
import pathlib

_SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
_DATA_DIR = _PROJECT_ROOT / 'data'

# 阈值（方案 §6）
PASS_THRESHOLD = 98.0     # 总分 ≥98%
SHORT_DIM = 60.0          # 单维度 ≤60 = 短板
MELTDOWN_ROUNDS = 3       # 连续3轮同维≤60 → 熔断

FUZZY_WORDS = ['优化', '提升', '改进', '尽快', '适当', '合理', '必要时', '相关方', '后续', '待定', '差不多', '尽量', '参考之前', '类似', '按惯例', '稍后', '再说']


def _txt(task):
    """把任务关键文本拼成一份可检索的字符串，供各维度打分。"""
    parts = []
    for k in ('title', 'now', 'output', 'ac'):
        v = task.get(k)
        if v:
            parts.append(str(v))
    spec = task.get('spec')
    if isinstance(spec, dict):
        for v in spec.values():
            if v:
                parts.append(json.dumps(v, ensure_ascii=False))
    return ' '.join(parts)


# ── 维度打分（各返回 0-100）──────────────────────────
def _d1_independent(text):
    """D1 可独立执行：查模糊引用词。完全清晰=100。"""
    score = 100
    for w in ['参考之前的', '类似', '按惯例', '原样', '同上', '沿用']:
        if w in text:
            score -= 25
    return max(score, 30)


def _d2_verifiable(text):
    """D2 可独立验收：有明确 pass/fail 标准。"""
    markers = ['验收', '通过标准', 'done', 'pass', '测试通过', '应返回', '校验', '断言', 'expected']
    if any(m in text.lower() for m in markers):
        return 100
    # 没有明确验收词 → 扣分
    if text.strip():
        return 55
    return 40


def _d3_boundary(text):
    """D3 边界覆盖：检查异常/边界场景关键词。"""
    markers = ['异常', '边界', '为空', '超时', '失败', '错误', '无网络', '空值', '回滚', '兜底', '降级', '并发', '超限']
    hits = sum(1 for m in markers if m in text)
    return min(40 + hits * 12, 100)


def _d4_dependency(task, text):
    """D4 依赖完整性：spec.dependencies 显式列出。"""
    spec = task.get('spec')
    deps = spec.get('dependencies') if isinstance(spec, dict) else None
    if isinstance(deps, list) and deps:
        return 100
    if any(w in text for w in ['依赖', '前置', '需要 ', '先 ', 'TBD']):
        return 75
    return 45


def _d5_fuzzy_words(text):
    """D5 模糊词消除：无模糊词=100，有则大扣。"""
    hits = [w for w in FUZZY_WORDS if w in text]
    if not hits:
        return 100
    return max(45 - len(hits) * 15, 0)


def _d6_module(text):
    """D6 模块完备：覆盖 输入→输出。"""
    has_in = any(w in text for w in ['输入', '入参', '参数', '接收'])
    has_out = any(w in text for w in ['输出', '返回', '产出', '交付', '结果'])
    if has_in and has_out:
        return 100
    if has_in or has_out:
        return 70
    return 50


def _d7_testable(text):
    """D7 可测试性：有测试/检查断言。"""
    markers = ['测试', '检查点', '验证', '冒烟', '用例', '断言', '验收', '回归']
    hits = sum(1 for m in markers if m in text)
    return min(35 + hits * 15, 100)


_DIM_FUNCS = {
    'D1': _d1_independent,
    'D2': _d2_verifiable,
    'D3': _d3_boundary,
    'D4': _d4_dependency,
    'D5': _d5_fuzzy_words,
    'D6': _d6_module,
    'D7': _d7_testable,
}


def run_selfcheck(task, mode='A'):
    """七维评分。mode: A=状态钩子 B=补齐后重检 C=人工。"""
    text = _txt(task)
    dims = {}
    for d, fn in _DIM_FUNCS.items():
        if d == 'D4':
            score = fn(task, text)
        else:
            score = fn(text)
        dims[d] = max(0, min(100, round(score)))

    total = sum(dims.values()) / len(dims)
    score_pct = round(total, 1)
    short_dims = [d for d, s in dims.items() if s <= SHORT_DIM]
    verdict = 'pass' if (score_pct >= PASS_THRESHOLD and not short_dims) else 'fail'
    return {
        'mode': mode,
        'score_pct': score_pct,
        'dims': dims,
        'short_dims': short_dims,
        'verdict': verdict,
        'ts': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
    }


# ── 补齐动作生成 ─────────────────────────────────────
_REMEDIATION_MAP = {
    'D1': ('补充可独立执行的输入条件与前置依赖', '增量补齐'),
    'D2': ('补充可验证的验收标准（pass/fail）', '增量补齐'),
    'D3': ('补充异常场景与边界条件覆盖', '增量补齐'),
    'D4': ('显式列出所有前置依赖及状态', '拆分补齐'),
    'D5': ('消除模糊词，改为可量化表述', '增量补齐'),
    'D6': ('补全 输入→处理→输出→反馈 链条', '拆分补齐'),
    'D7': ('补充测试用例/检查点与断言', '增量补齐'),
}


def gen_remediation(task, short_dims):
    """按短板维度生成补齐动作清单。"""
    from datetime import datetime
    rem = []
    for d in short_dims:
        desc, rtype = _REMEDIATION_MAP.get(d, ('补齐缺失内容', '增量补齐'))
        rem.append({
            'missing_dim': d,
            'missing_module': desc,
            'type': rtype,
            'content': desc,
            'owner': task.get('org', '锋铸'),
            'effort': '0.5h',
            'deadline': None,
            'acceptance': f'{d} 维度评分 >{SHORT_DIM:.0f}',
            'created': datetime.now().isoformat(timespec='seconds'),
        })
    return rem


# ── 审计记录 ─────────────────────────────────────────
def record_audit(task, audit):
    """写审计 JSON 到 data/audit/AUDIT-{date}-{seq}.json，返回 seq。"""
    d = _DATA_DIR / 'audit'
    d.mkdir(parents=True, exist_ok=True)
    import glob
    from datetime import datetime
    today = datetime.now().strftime('%Y-%m-%d')
    existing = glob.glob(str(d / f'AUDIT-{today}-*.json'))
    seq = len(existing) + 1
    rec = {
        'seq': seq,
        'task_id': task.get('id'),
        'task_title': task.get('title'),
        'audit': audit,
        'ts': datetime.now().isoformat(timespec='seconds'),
    }
    path = d / f'AUDIT-{today}-{seq:03d}.json'
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    return seq


# ── 熔断检测（连续3轮同维≤60）─────────────────────────
def is_meltdown(task):
    """查 task['decomp_audit'] 历史，连续3轮同维≤60 → 熔断。"""
    history = task.get('decomp_history')
    if not isinstance(history, list) or len(history) < MELTDOWN_ROUNDS:
        return False
    last3 = history[-MELTDOWN_ROUNDS:]
    for d in ('D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7'):
        if all(h.get('dims', {}).get(d, 100) <= SHORT_DIM for h in last3):
            return True
    return False
