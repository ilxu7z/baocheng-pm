#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""six_unity.py — 六合一融合钩子（SDD/CDD/任务分解/SE），供 dashboard/server.py 调用

六合一 = SDD(规范驱动) + CDD(上下文驱动) + 任务分解(颗粒度自查) 
        + 上下文管理(lossless-claw) + ORC(已实现) + SE(技能自进化)

本模块只封装"在看板状态机里埋的钩子逻辑"，不重写看板：
  1. SDD 契约门禁   —— 任务进 Review 前校验 spec 契约完整
  2. CDD 注入留痕   —— 派发时记录注入了哪些上下文
  3. 任务分解自查   —— 七维评分 + 补齐动作（引擎在 selfcheck_engine.py）
  4. SE 经验卡/复用 —— Done 后异步经验回流

模块开关：环境变量 SIX_UNITY=0/1（默认 0 = 只留痕不拦截，安全过渡）
"""

import json
import os
import pathlib
import sys

# ── 路径 ──────────────────────────────────────────────
_SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
_DATA_DIR = _PROJECT_ROOT / 'data'

# ── 开关（默认 0：只留痕不拦截，避免一上线就卡死现有流转）──
def enabled() -> bool:
    """SIX_UNITY=1 时启用拦截类门禁；默认 0 = 过渡模式(只留痕)。"""
    return os.environ.get('SIX_UNITY', '0') == '1'


# ── 模糊词表（SDD 契约校验用）─────────────────────────
FUZZY_WORDS = ['优化', '提升', '改进', '尽快', '适当', '合理', '必要时', '相关方', '后续', '待定', '差不多', '尽量']


def _now_iso():
    from datetime import datetime
    return datetime.now().isoformat(timespec='seconds')


def _audit_dir():
    d = _DATA_DIR / 'audit'
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── 1. SDD 契约校验 ───────────────────────────────────
def sdd_spec_valid(task):
    """SDD 契约完整性校验。返回 (ok, reason)。

    校验：spec 存在、有 purpose/outputs、验收标准非空且无模糊词。
    旧任务无 spec → 视为"未达标但不拦截"（由 enabled() 决定是否驳回）。
    """
    spec = task.get('spec')
    if not isinstance(spec, dict):
        return False, '无 spec 契约字段'
    if not spec.get('purpose'):
        return False, '缺 purpose（一句话目标）'
    if not spec.get('outputs'):
        return False, '缺 outputs（交付物）'
    ac = spec.get('acceptance_criteria')
    if not ac:
        # 兼容旧字段
        ac = task.get('ac', '')
    if isinstance(ac, list):
        if not ac:
            return False, '验收标准为空'
    elif not str(ac or '').strip():
        return False, '验收标准为空'
    # 模糊词检查
    blob = json.dumps(spec, ensure_ascii=False) + ' ' + str(task.get('title', ''))
    hit = [w for w in FUZZY_WORDS if w in blob]
    if hit:
        return False, f'Spec 含模糊词: {",".join(hit)}'
    return True, ''


def sdd_gate(task_id, task, flow_log_append):
    """SDD 契约门禁钩子（进 Review 前调用）。

    enabled()=1 时：不合格 → 驳回（不推进），写 flow_log。
    enabled()=0 时：只标记 spec_status，不拦截（过渡）。
    返回 (allow, reason)：allow=False 表示应阻止推进。
    """
    ok, reason = sdd_spec_valid(task)
    if ok:
        task['spec_status'] = 'reviewed'
        return True, ''
    if enabled():
        task['spec_status'] = 'blocked'
        flow_log_append({
            'from': 'SDD门禁', 'to': 'Zhongshu',
            'remark': f'SDD 契约不完整，驳回规划部：{reason}',
        })
        return False, reason
    # 过渡模式：标记但不拦截
    task['spec_status'] = 'pending'
    flow_log_append({
        'from': 'SDD门禁', 'to': '(过渡)',
        'remark': f'[过渡] SDD 契约不完整（未拦截）：{reason}',
    })
    return True, reason


# ── 2. CDD 注入留痕 ───────────────────────────────────
def cdd_record_injection(task, layer, knowledge_src, agent=None, spec_hash=None):
    """记录 CDD 注入痕迹到 task['cdd_injected']（可观测，防'没注入'）。"""
    task['cdd_injected'] = {
        'layer': layer,
        'knowledge_src': knowledge_src,
        'spec_hash': spec_hash or (hash(str(task.get('spec'))) & 0xffffffff),
        'timestamp': _now_iso(),
        'agent': agent or task.get('lastAgent', ''),
    }
    return task['cdd_injected']


# ── 3. 任务分解自查（委托 selfcheck_engine）────────────
def decomp_check(task_id, task, flow_log_append):
    """任务分解自查钩子（Menxia→Assigned 前调用）。

    加载 selfcheck_engine.py 做七维评分；不达标且 enabled()=1 时生成补齐动作并驳回。
    返回 (allow, audit)：
      allow=False → 应阻止推进到 Assigned（转补齐）
      audit      → {'score', 'dims', 'verdict', 'remediation'}
    """
    try:
        sys.path.insert(0, str(_SCRIPT_DIR))
        import selfcheck_engine as sce
    except Exception as e:
        # 引擎缺失/报错 → 不拦截（降级），只留痕
        task['decomp_audit'] = {'error': str(e), 'verdict': 'skip'}
        return True, task['decomp_audit']

    if not enabled() and 'spec_status' in task and task['spec_status'] == 'pending':
        pass  # 过渡模式继续

    audit = sce.run_selfcheck(task, mode='A')
    seq = sce.record_audit(task, audit)
    audit['audit_seq'] = seq
    task['decomp_audit'] = audit

    if audit['verdict'] == 'pass':
        return True, audit

    # 不达标
    if enabled():
        rem = sce.gen_remediation(task, audit.get('short_dims', []))
        audit['remediation'] = rem
        task['decomp_audit']['remediation'] = rem
        flow_log_append({
            'from': '自查引擎', 'to': '锋铸补齐',
            'remark': f'任务分解未达标({audit.get("score_pct", 0)}%)，生成{len(rem)}条补齐动作',
        })
        return False, audit
    # 过渡模式：标注不拦截
    flow_log_append({
        'from': '自查引擎', 'to': '(过渡)',
        'remark': f'[过渡] 任务分解未达标({audit.get("score_pct", 0)}%)，未拦截',
    })
    return True, audit


# ── 4. SE 技能自进化（Done 后异步）────────────────────
def se_try_extract_experience(task_id, task, flow_log_append):
    """Done 后尝试产出经验卡（异步委托，不阻塞归档）。

    从任务 flow_log + skill_ref 提炼一条经验卡写入 data/experience-cards.jsonl，
    供审微评审池扫描。若任务无可提炼内容则跳过。
    """
    title = task.get('title', '')
    skill_ref = task.get('skill_ref')
    # 经验卡内容：简单基于任务元数据生成（完整提炼依赖 lossless-claw 回看，后续增强）
    card = {
        'task_id': task_id,
        'title': title,
        'state': 'done',
        'skill_refs': skill_ref if isinstance(skill_ref, list) else [],
        'ts': _now_iso(),
        'status': 'pending_review',   # 待审微评审
        'source': 'six_unity_se',
    }
    try:
        f = _DATA_DIR / 'experience-cards.jsonl'
        with open(f, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(card, ensure_ascii=False) + '\n')
        flow_log_append({
            'from': 'SE', 'to': '评审池',
            'remark': f'经验卡已入评审池（待审微评审）',
        })
        return card
    except Exception as e:
        flow_log_append({
            'from': 'SE', 'to': '(异常)',
            'remark': f'经验卡产出失败: {e}',
        })
        return None


def se_register_skill_ref(task, skill_id, result=None):
    """任务引用 skill 时留痕 task['skill_ref']（环④ 复用反馈）。"""
    refs = task.get('skill_ref')
    if not isinstance(refs, list):
        refs = []
    entry = {'skill_id': skill_id, 'ts': _now_iso()}
    if result:
        entry['result'] = result   # success / rework / pitfall
    refs.append(entry)
    task['skill_ref'] = refs
    return refs


# ── 简述（供调试/审计）────────────────────────────────
def summarize_task(task):
    return {
        'id': task.get('id'),
        'title': task.get('title'),
        'state': task.get('state'),
        'spec_status': task.get('spec_status'),
        'cdd_injected': bool(task.get('cdd_injected')),
        'decomp_score': (task.get('decomp_audit') or {}).get('score_pct'),
        'ocr_auto': bool(task.get('ocr_auto')),
        'experience_card': bool(task.get('experience_card')),
        'skill_ref': task.get('skill_ref'),
    }
