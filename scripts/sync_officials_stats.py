#!/usr/bin/env python3
"""同步各官员统计数据 → data/officials_stats.json"""
import json, os, pathlib, datetime, logging
from file_lock import atomic_json_write
from utils import get_openclaw_home

log = logging.getLogger('officials')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

BASE = pathlib.Path(os.environ.get('EDICT_HOME', '')) if os.environ.get('EDICT_HOME') else pathlib.Path(__file__).resolve().parent.parent
DATA = BASE / 'data'
OPENCLAW_HOME = get_openclaw_home()

# Registry: 三省六部角色 ↔ 实际 Agent 映射
_REGISTRY_PATH = BASE / 'registry.json'
_registry_cache = None
_registry_cache_mtime = 0
def _load_registry():
    global _registry_cache, _registry_cache_mtime
    p = _REGISTRY_PATH
    try:
        mtime = p.stat().st_mtime_ns
        if _registry_cache is not None and mtime == _registry_cache_mtime:
            return _registry_cache
        raw = json.loads(p.read_text())
        if not isinstance(raw, list):
            raw = []
        _registry_cache = raw
        _registry_cache_mtime = mtime
    except Exception:
        if _registry_cache is None:
            _registry_cache = []
    return _registry_cache

def _role_to_agent(role_id):
    """三省六部角色 ID → 实际 OpenClaw Agent ID"""
    for entry in _load_registry():
        if isinstance(entry, dict) and entry.get('courtId') == role_id:
            return entry['id']
    # 特殊兼容：总办用 main
    if role_id == 'taizi':
        return 'main'
    return role_id
AGENTS_ROOT = OPENCLAW_HOME / 'agents'
OPENCLAW_CFG = OPENCLAW_HOME / 'openclaw.json'

# Anthropic 定价（每1M token，美元）
MODEL_PRICING = {
    # USD 定价
    'anthropic/claude-sonnet-4-6':  {'in':3.0, 'out':15.0, 'cr':0.30, 'cw':3.75},
    'anthropic/claude-opus-4-5':    {'in':15.0,'out':75.0, 'cr':1.50, 'cw':18.75},
    'anthropic/claude-haiku-3-5':   {'in':0.8, 'out':4.0,  'cr':0.08, 'cw':1.0},
    'openai/gpt-4o':                {'in':2.5, 'out':10.0, 'cr':1.25, 'cw':0},
    'openai/gpt-4o-mini':           {'in':0.15,'out':0.6,  'cr':0.075,'cw':0},
    'google/gemini-2.0-flash':      {'in':0.075,'out':0.3, 'cr':0,    'cw':0},
    'google/gemini-2.5-pro':        {'in':1.25,'out':10.0, 'cr':0,    'cw':0},
    # RMB 定价（deepseek 缓存命中/未命中分开计费）
    # 官方定价（元/百万tokens）：
    #   v4-flash: 未命中输入1.0 / 缓存命中0.02 / 输出2.0
    #   v4-pro:   未命中输入3.0 / 缓存命中0.025 / 输出6.0
    'deepseek/deepseek-v4-flash':   {'in':1.0, 'out':2.0, 'cr':0.02, 'cw':0, 'currency':'cny'},
    'deepseek/deepseek-v4-pro':     {'in':3.0, 'out':6.0, 'cr':0.025,'cw':0, 'currency':'cny'},
}

OFFICIALS = [
    {'id':'taizi',   'label':'总办',    'role':'项目总控',    'emoji':'🤴','rank':'负责人'},
    {'id':'zhongshu','label':'规划部',  'role':'军师',      'emoji':'📜','rank':'负责人'},
    {'id':'menxia',  'label':'审议部',  'role':'审计官',      'emoji':'🔍','rank':'负责人'},
    {'id':'shangshu','label':'执行办',  'role':'调度长',    'emoji':'📮','rank':'负责人'},
    {'id':'libu',    'label':'内容部',  'role':'内容主管',  'emoji':'📝','rank':'负责人'},
    {'id':'hubu',    'label':'交付汇总处','role':'交付主管',  'emoji':'💰','rank':'负责人'},
    {'id':'bingbu',  'label':'开发部',  'role':'研发主管',  'emoji':'⚔️','rank':'负责人'},
    {'id':'xingbu',  'label':'质控部',  'role':'品控官',  'emoji':'⚖️','rank':'负责人'},
    {'id':'gongbu',  'label':'设计部',  'role':'视觉主管',  'emoji':'🔧','rank':'负责人'},
    {'id':'libu_hr', 'label':'人力路由处','role':'路由主管','emoji':'👔','rank':'负责人'},
    {'id':'zaochao', 'label':'运维组',  'role':'运维主管',     'emoji':'📰','rank':'负责人'},]

def rj(p, d):
    try:
        return json.loads(pathlib.Path(p).read_text(encoding='utf-8'))
    except Exception:
        return d


# Pre-load openclaw config once (avoid re-reading per agent)
_OPENCLAW_CACHE = None

def _load_openclaw_cfg():
    global _OPENCLAW_CACHE
    if _OPENCLAW_CACHE is None:
        _OPENCLAW_CACHE = rj(OPENCLAW_CFG, {})
    return _OPENCLAW_CACHE


def normalize_model(model_value, fallback='anthropic/claude-sonnet-4-6'):
    if isinstance(model_value, str) and model_value:
        return model_value
    if isinstance(model_value, dict):
        return model_value.get('primary') or model_value.get('id') or fallback
    return fallback

def get_model(agent_id):
    cfg = _load_openclaw_cfg()
    default = normalize_model(cfg.get('agents',{}).get('defaults',{}).get('model',{}), 'anthropic/claude-sonnet-4-6')
    # 翻译三省六部角色 ID 为实际 Agent ID
    real_id = _role_to_agent(agent_id)
    for a in cfg.get('agents',{}).get('list',[]):
        if a.get('id') == real_id:
            return normalize_model(a.get('model', default), default)
    return default

def scan_agent(agent_id):
    """从 sessions.json 读取 token 统计（累计所有 session）
    自动将三省六部角色 ID 翻译为实际 Agent ID。
    """
    real_id = _role_to_agent(agent_id)
    if real_id != agent_id:
        log.info(f'scan_agent: {agent_id} → {real_id}')
        agent_id = real_id
    sj = AGENTS_ROOT / agent_id / 'sessions' / 'sessions.json'
    if not sj.exists():
        return {'tokens_in':0,'tokens_out':0,'cache_read':0,'cache_write':0,'sessions':0,'last_active':None,'messages':0}
    
    data = rj(sj, {})
    tin = tout = cr = cw = 0
    last_ts = None
    
    for sid, v in data.items():
        tin += v.get('inputTokens', 0) or 0
        tout += v.get('outputTokens', 0) or 0
        cr  += v.get('cacheRead', 0) or 0
        cw  += v.get('cacheWrite', 0) or 0
        ts = v.get('updatedAt')
        if ts:
            try:
                t = datetime.datetime.fromtimestamp(ts/1000) if isinstance(ts,int) else datetime.datetime.fromisoformat(ts.replace('Z','+00:00'))
                if last_ts is None or t > last_ts: last_ts = t
            except Exception: pass
    
    # Estimate message count from most recent session JSONL
    msg_count = 0
    if data:
        try:
            sf_key = max(data.keys(), key=lambda k: data[k].get('updatedAt',0) or 0, default=None)
        except Exception:
            sf_key = None
    else:
        sf_key = None
    if sf_key and data[sf_key].get('sessionFile'):
        sf = AGENTS_ROOT / agent_id / 'sessions' / pathlib.Path(data[sf_key]['sessionFile']).name
        try:
            lines = sf.read_text(errors='ignore').splitlines()
            for ln in lines:
                try:
                    e = json.loads(ln)
                    if e.get('type') == 'message' and e.get('message',{}).get('role') == 'assistant':
                        msg_count += 1
                except Exception: pass
        except Exception: pass

    return {
        'tokens_in': tin, 'tokens_out': tout,
        'cache_read': cr, 'cache_write': cw,
        'sessions': len(data),
        'last_active': last_ts.strftime('%Y-%m-%d %H:%M') if last_ts else None,
        'messages': msg_count,
    }

def calc_cost(s, model):
    """计算成本，返回 (cost_cny, cost_usd)。
    DeepSeek 使用国内定价（缓存命中/未命中分开），直接返回人民币。

    OpenClaw sessions.json 语义：
      - tokens_in     = 未命中缓存的输入 tokens（实际发送给模型的部分）
      - cache_read    = 从缓存命中的输入 tokens（独立计数，不包含在 tokens_in 中）
      - tokens_out    = 输出 tokens
      - cache_write   = 写入缓存的 tokens（通常不计费）
    因此：
      - 未命中输入费用 = tokens_in / 1M × 未命中单价
      - 缓存命中费用   = cache_read / 1M × 缓存命中单价
      - 输出费用        = tokens_out / 1M × 输出单价
    """
    p = MODEL_PRICING.get(model, MODEL_PRICING['anthropic/claude-sonnet-4-6'])
    if p.get('currency') == 'cny':
        # DeepSeek: tokens_in 就是未命中输入，cache_read 是缓存命中输入
        cny = (s['tokens_in']  / 1e6 * p['in']           # 未命中输入
             + s['cache_read'] / 1e6 * p.get('cr', 0)    # 缓存命中输入
             + s['tokens_out'] / 1e6 * p['out'])         # 输出
        return round(cny, 2), round(cny / 7.25, 4)
    # USD 定价模型
    usd = (s['tokens_in']/1e6*p['in'] + s['tokens_out']/1e6*p['out']
         + s['cache_read']/1e6*p['cr'] + s['cache_write']/1e6*p['cw'])
    return round(usd * 7.25, 2), round(usd, 4)

def get_task_stats(org_label, tasks, alt_org=None):
    """计算该官员的任务统计。
    alt_org 是备选 org 匹配模式（如 '三省-审计官'），因为实际任务 org 不一定是官制名。
    """
    def _org_match(t):
        o = t.get('org', '')
        if o == org_label:
            return True
        if alt_org and o == alt_org:
            return True
        return False
    done   = [t for t in tasks if t.get('state')=='Done' and _org_match(t)]
    active = [t for t in tasks if t.get('state') in ('Doing','Review','Assigned') and _org_match(t)]
    # flow_log 匹配：也用备选 org
    fl = sum(1 for t in tasks for f in t.get('flow_log',[])
             if f.get('from') in (org_label, alt_org) or f.get('to') in (org_label, alt_org))
    # 参与的任务（JJC）列表 — 只保留活跃（非终态）任务
    participated = []
    matched_ids = set()
    for t in tasks:
        if not str(t.get('id','')).startswith('JJC'): continue
        if t.get('state') in ('Done', 'Cancelled'): continue  # 跳过已结束任务
        for f in t.get('flow_log',[]):
            if f.get('from') in (org_label, alt_org) or f.get('to') in (org_label, alt_org):
                tid = t['id']
                if tid not in matched_ids:
                    matched_ids.add(tid)
                    participated.append({'id':tid,'title':t.get('title',''),'state':t.get('state','')})
                break
    if not participated:
        # 兜底：如果 org/flow_log 都没匹配到，用 agentId 匹配（来自 sourceMeta）
        agent_id = _role_to_agent(org_label)
        for t in tasks:
            if str(t.get('id','')).startswith('JJC'):
                if t.get('state') in ('Done', 'Cancelled'): continue  # 跳过已结束任务
                sid = t.get('sourceMeta',{}).get('agentId','')
                if sid and sid == agent_id:
                    tid = t['id']
                    if tid not in matched_ids:
                        matched_ids.add(tid)
                        participated.append({'id':tid,'title':t.get('title',''),'state':t.get('state','')})
        if participated:
            done   = [t for t in tasks if t.get('state')=='Done' and t.get('sourceMeta',{}).get('agentId')==agent_id]
            active = [t for t in tasks if t.get('state') in ('Doing','Review','Assigned') and t.get('sourceMeta',{}).get('agentId')==agent_id]
            fl = sum(1 for t in tasks if t.get('sourceMeta',{}).get('agentId')==agent_id)
    return {'tasks_done':len(done),'tasks_active':len(active),
            'flow_participations':fl,'participated_edicts':participated}

def get_hb(agent_id, live_tasks):
    real_id = _role_to_agent(agent_id)
    for t in live_tasks:
        ta = t.get('sourceMeta',{}).get('agentId','')
        if ta == real_id and t.get('heartbeat'):
            return t['heartbeat']
    return {'status':'idle','label':'⚪ 待命','ageSec':None}

def main():
    tasks = rj(DATA/'tasks_source.json', [])
    live  = rj(DATA/'live_status.json', {})
    live_tasks = live.get('tasks', [])

    # 构建 officials 的 alt_org 映射：角色 ID → '三省-{name}'
    registry = _load_registry()
    alt_org_map = {}
    for entry in registry:
        if isinstance(entry, dict) and entry.get('name'):
            cid = entry.get('courtId', '')
            if cid:
                alt_org_map[cid] = f"三省-{entry['name']}"

    result = []
    for off in OFFICIALS:
        model   = get_model(off['id'])
        ss      = scan_agent(off['id'])
        alt_org = alt_org_map.get(off['id'])
        ts      = get_task_stats(off['label'], tasks, alt_org)
        hb      = get_hb(off['id'], live_tasks)
        cost_cny, cost_usd = calc_cost(ss, model)

        result.append({
            **off,
            'model': model,
            'model_short': model.split('/')[-1] if isinstance(model, str) and '/' in model else str(model),
            'sessions': ss['sessions'],
            'tokens_in': ss['tokens_in'],
            'tokens_out': ss['tokens_out'],
            'cache_read': ss['cache_read'],
            'cache_write': ss['cache_write'],
            'tokens_total': ss['tokens_in'] + ss['tokens_out'] + ss['cache_read'] + ss['cache_write'],
            'messages': ss['messages'],
            'cost_usd': cost_usd,
            'cost_cny': cost_cny,
            'last_active': ss['last_active'],
            'heartbeat': hb,
            'tasks_done': ts['tasks_done'],
            'tasks_active': ts['tasks_active'],
            'flow_participations': ts['flow_participations'],
            'participated_edicts': ts['participated_edicts'],
            'merit_score': ts['tasks_done']*10 + ts['flow_participations']*2 + min(ss['sessions'],20),
        })

    result.sort(key=lambda x: x['merit_score'], reverse=True)
    for i, r in enumerate(result): r['merit_rank'] = i+1

    totals = {
        'tokens_total': sum(r['tokens_total'] for r in result),
        'cache_total':  sum(r['cache_read']+r['cache_write'] for r in result),
        'cost_usd':     round(sum(r['cost_usd'] for r in result), 2),
        'cost_cny':     round(sum(r['cost_cny'] for r in result), 2),
        'tasks_done':   sum(r['tasks_done'] for r in result),
    }
    top = max(result, key=lambda x: x['merit_score'], default={})

    payload = {
        'generatedAt': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'officials': result,
        'totals': totals,
        'top_official': top.get('label',''),
    }
    atomic_json_write(DATA/'officials_stats.json', payload)
    log.info(f'{len(result)} officials | cost=¥{totals["cost_cny"]} | top={top.get("label","")}')

if __name__ == '__main__':
    main()
