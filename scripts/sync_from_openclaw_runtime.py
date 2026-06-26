#!/usr/bin/env python3
"""
MACS-pm OpenClaw Runtime Session Scanner (v2 — OpenClaw 5.12+ / 5.28+ compatible)

Changelog v2 (2026-06-02):
- parse_timestamp(): 兼容 int ms / ISO 8601 string / None 三种时间戳格式（含 bool instanceof 保护）
- load_sessions(): sessions.json 兼容 dict / list 两种顶层格式
- sessionFile: transcriptPath fallback + 路径存在性校验，不存在时跳过 activity 加载
- origin: 非 dict 时安全 fallback 到空 dict
- abortedLastRun: 兜底 state=='error' 检测
- token 字段: snake_case 兼容
"""
import json
import os
import pathlib
import time
import datetime
import traceback
import logging
import hashlib
from file_lock import atomic_json_write, atomic_json_read
from utils import get_openclaw_home

log = logging.getLogger('sync_runtime')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

_script_dir = pathlib.Path(os.environ.get('EDICT_HOME', '')) if os.environ.get('EDICT_HOME') else pathlib.Path(__file__).resolve().parent.parent
BASE = _script_dir
DATA = BASE / 'data'
DATA.mkdir(exist_ok=True)
SYNC_STATUS = DATA / 'sync_status.json'
SESSIONS_ROOT = get_openclaw_home() / 'agents'


def write_status(**kwargs):
    atomic_json_write(SYNC_STATUS, kwargs)


def ms_to_str(ts_ms):
    if not ts_ms:
        return '-'
    try:
        return datetime.datetime.fromtimestamp(ts_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return '-'


def state_from_session(age_ms, aborted):
    if aborted:
        return 'Blocked'
    if age_ms <= 2 * 60 * 1000:
        return 'Doing'
    if age_ms <= 60 * 60 * 1000:
        return 'Review'
    return 'Next'


def parse_timestamp(ts_raw):
    """兼容 int ms / ISO 8601 string / None 三种时间戳格式（5.12 → 5.28+ 向前兼容）"""
    if ts_raw is None:
        return 0
    if isinstance(ts_raw, (int, float)) and not isinstance(ts_raw, bool):
        return int(ts_raw)
    if isinstance(ts_raw, str):
        try:
            dt = datetime.datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
            return int(dt.timestamp() * 1000)
        except (ValueError, AttributeError):
            return 0
    return 0


def load_sessions(sessions_file: pathlib.Path):
    """加载 sessions.json，兼容 dict / list 两种顶层格式（5.12 dict, 5.28+ 可能变为 list of dicts）"""
    try:
        raw = json.loads(sessions_file.read_text())
    except Exception:
        return []  # 文件损坏/不存在，返回空
    if isinstance(raw, dict):
        return [(session_key, row) for session_key, row in raw.items() if isinstance(row, dict)]
    if isinstance(raw, list):
        items = []
        for item in raw:
            if isinstance(item, dict):
                sk = item.get('sessionKey') or item.get('sessionId') or item.get('key') or ''
                items.append((sk, item))
        return items
    return []


def detect_official(agent_id):
    mapping = {
        # original 三省六部
        'main':    ('储君', '太子'),
        'taizi':   ('储君', '太子'),
        'zhongshu': ('中书令', '中书省'),
        'menxia':  ('侍中', '门下省'),
        'shangshu': ('尚书令', '尚书省'),
        'hubu':    ('户部尚书', '户部'),
        'libu':    ('礼部尚书', '礼部'),
        'bingbu':  ('兵部尚书', '兵部'),
        'xingbu':  ('刑部尚书', '刑部'),
        'gongbu':  ('工部尚书', '工部'),
        'libu_hr': ('吏部尚书', '吏部'),
        'zaochao': ('钦天监', '钦天监'),
        # 鲍澄军团映射
        'baocheng': ('储君', '鲍澄'),
        'guihua':  ('筹微', '三省-筹微'),
        'shenyi':  ('审微', '三省-审微'),
        'paifa':   ('驿使', '三省-驿使'),
        'wenan':   ('墨卿', '三省-墨卿'),
        'daima':   ('锋铸', '三省-锋铸'),
        'sheji':   ('绘象', '三省-绘象'),
        'shencha': ('镜衡', '三省-镜衡'),
        'huizong': ('归藏', '三省-归藏'),
        'ld-r':    ('尚书令', '尚书省'),
        'rongcui': ('钦天监', '钦天监'),
    }
    return mapping.get(agent_id, ('尚书令', '尚书省'))


def load_activity(session_file, limit=12):
    p = pathlib.Path(session_file or '')
    if not p.exists():
        return []
    rows = []
    try:
        lines = p.read_text(errors='ignore').splitlines()
    except Exception:
        return []

    # Read all valid JSON lines first
    events = []
    for ln in lines:
        try:
            item = json.loads(ln)
            events.append(item)
        except:
            continue

    # Process events to extract meaningful activity
    # We want to show what the agent is *thinking* or *doing*
    for item in reversed(events):
        msg = item.get('message') or {}
        role = msg.get('role')
        ts = item.get('timestamp') or ''

        if role == 'toolResult':
            tool = msg.get('toolName', '-')
            details = msg.get('details') or {}
            # If tool output is short, show it
            c_list = msg.get('content') or [{'text': ''}]
            content = c_list[0].get('text', '') if c_list else ''
            if len(content) < 50:
                text = f"Tool '{tool}' returned: {content}"
            else:
                text = f"Tool '{tool}' finished"
            rows.append({'at': ts, 'kind': 'tool', 'text': text})

        elif role == 'assistant':
            text = ''
            for c in msg.get('content', []):
                if c.get('type') == 'text' and c.get('text'):
                    raw_text = c.get('text').strip()
                    # Clean up common prefixes
                    clean_text = raw_text.replace('[[reply_to_current]]', '').strip()
                    if clean_text:
                        text = clean_text
                    break
            if text:
                # Prioritize showing the "thought" - usually the first few sentences
                summary = text.split('\n')[0]
                if len(summary) > 200:
                    summary = summary[:200] + '...'
                rows.append({'at': ts, 'kind': 'assistant', 'text': summary})
                
        elif role == 'user':
             # Also show what user asked, can be context relevant
             text = ''
             for c in msg.get('content', []):
                if c.get('type') == 'text':
                     text = c.get('text', '')[:100]
             if text:
                 rows.append({'at': ts, 'kind': 'user', 'text': f"User: {text}..."})

        if len(rows) >= limit:
            break

    # Re-order to chronological for display if needed, but the caller usually takes the first (latest)
    return rows


def _session_file_exists(task):
    """检查 AUTO 任务对应的 session .jsonl 文件是否存在"""
    # output 字段在 build_task 中已设置为 sessionFile 路径
    session_file = task.get('output', '')
    return bool(session_file and pathlib.Path(session_file).exists())


def _is_main_session(task):
    """检查 AUTO 任务是否来自 agent:*:main 主会话（非工作任务）"""
    import re
    session_key = task.get('sourceMeta', {}).get('sessionKey', '') or task.get('flow', {}).get('dispatch', '')
    return bool(re.match(r'agent:[\w-]+:main$', session_key))


def build_task(agent_id, session_key, row, now_ms):
    # ── 字段提取（全部 safe_get，向前兼容变更）──
    session_id = row.get('sessionId') or row.get('id') or session_key

    # updatedAt: 兼容 int ms / ISO 8601 / None
    updated_at = parse_timestamp(row.get('updatedAt'))

    # aborted: 兜底检测 state==error
    aborted = bool(row.get('abortedLastRun') or row.get('state') == 'error')

    age_ms = max(0, now_ms - updated_at) if updated_at else 99 * 24 * 3600 * 1000
    state = state_from_session(age_ms, aborted)

    official, org = detect_official(agent_id)

    # origin: 5.28+ 可能加 namespace 嵌套，安全取值
    origin = row.get('origin') if isinstance(row.get('origin'), dict) else {}
    channel = row.get('lastChannel') or origin.get('channel') or '-'
    title_label = origin.get('label') or session_key or ''

    # sessionFile: 5.28+ transcript 路径可能重写，加存在性校验
    session_file = row.get('sessionFile') or row.get('transcriptPath') or ''
    session_file_exists = bool(session_file and pathlib.Path(session_file).exists())

    # 跳过僵尸会话：sessions.json 有记录但 .jsonl 文件已不存在
    # Gateway 可能在内存中保留了会话引用并持续刷新 updatedAt，
    # 但实际对话文件已删除/移动，这类条目不应出现在看板上
    if not session_file_exists:
        return None

    # ── Activity 提取 ──
    latest_act = '等待指令'
    acts = []
    if session_file_exists:
        try:
            acts = load_activity(session_file, limit=5)
        except Exception:
            acts = []

    if acts:
        first_act = acts[0]
        if first_act['kind'] == 'tool' and len(acts) > 1:
            for next_act in acts[1:]:
                if next_act['kind'] == 'assistant':
                    latest_act = f"正在执行: {next_act['text'][:80]}"
                    break
            else:
                latest_act = first_act['text'][:60]
        elif first_act['kind'] == 'assistant':
            latest_act = f"思考中: {first_act['text'][:80]}"
        else:
            latest_act = acts[0]['text'][:60]

    # ── 标题推断 ──
    import re
    # 跳过非工作会话：heartbeat、dashboard、gateway-fallback、main 等内部会话
    # agent:*:main 是 Agent 自身的主聊天会话，不是工作任务
    if re.search(r':heartbeat', session_key) or re.search(r':dashboard:', session_key) or 'gateway-fallback' in session_key:
        return None
    if re.match(r'agent:[\w-]+:main$', session_key):
        return None
    if re.match(r'agent:\w+:cron:', title_label):
        title = f"{org}定时任务"
    elif re.match(r'agent:\w+:subagent:', title_label):
        title = f"{org}子任务"
    elif title_label == session_key or len(title_label) > 40:
        title = f"{org}会话"
    else:
        title = f"{title_label}"

    # ── token 统计（兼容字段名变化）──
    input_tokens = row.get('inputTokens') or row.get('input_tokens')
    output_tokens = row.get('outputTokens') or row.get('output_tokens')
    total_tokens = row.get('totalTokens') or row.get('total_tokens')

    # ── 生成任务记录 ──
    activity_summary = []
    if session_file_exists:
        try:
            activity_summary = load_activity(session_file, limit=10)
        except Exception:
            pass

    return {
        'id': f"JJC-AUTO-{agent_id}-{hashlib.md5(session_key.encode()).hexdigest()[:10]}",
        'title': title,
        'official': official,
        'org': org,
        'state': state,
        'now': latest_act,
        'eta': ms_to_str(updated_at),
        'block': '上次运行中断' if aborted else '无',
        'output': session_file,
        'flow': {
            'draft': f"agent={agent_id}",
            'review': f"updatedAt={ms_to_str(updated_at)}",
            'dispatch': f"sessionKey={session_key}",
        },
        'ac': '来自 OpenClaw runtime sessions 的实时映射',
        'activity': activity_summary,
        'sourceMeta': {
            'agentId': agent_id,
            'sessionKey': session_key,
            'sessionId': session_id,
            'updatedAt': updated_at,
            'ageMs': age_ms,
            'systemSent': bool(row.get('systemSent')),
            'abortedLastRun': aborted,
            'inputTokens': input_tokens,
            'outputTokens': output_tokens,
            'totalTokens': total_tokens,
        }
    }


def main():
    start = time.time()
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    now_ms = int(time.time() * 1000)

    try:
        tasks = []
        scan_files = 0

        if SESSIONS_ROOT.exists():
            for agent_dir in sorted(SESSIONS_ROOT.iterdir()):
                if not agent_dir.is_dir():
                    continue
                agent_id = agent_dir.name
                sessions_file = agent_dir / 'sessions' / 'sessions.json'
                if not sessions_file.exists():
                    continue
                scan_files += 1

                # 使用向前兼容的 load_sessions（dict + list 双格式）
                rows = load_sessions(sessions_file)
                for session_key, row in rows:
                    if not session_key:
                        continue
                    try:
                        result = build_task(agent_id, session_key, row, now_ms)
                        if result is not None:
                            tasks.append(result)
                    except Exception as be:
                        log.warning(f'build_task failed for {agent_id}/{session_key}: {be}')

        # merge mission control tasks (最小接入)
        mc_tasks_file = DATA / 'mission_control_tasks.json'
        if mc_tasks_file.exists():
            try:
                mc_tasks = json.loads(mc_tasks_file.read_text())
                if isinstance(mc_tasks, list):
                    tasks.extend(mc_tasks)
            except Exception:
                pass

        # merge manual parallel tasks (用于军机处并行看板展示)
        manual_tasks_file = DATA / 'manual_parallel_tasks.json'
        if manual_tasks_file.exists():
            try:
                manual_tasks = json.loads(manual_tasks_file.read_text())
                if isinstance(manual_tasks, list):
                    tasks.extend(manual_tasks)
            except Exception:
                pass

        tasks.sort(key=lambda x: x.get('sourceMeta', {}).get('updatedAt', 0), reverse=True)

        # 去重（同一 id 只保留第一个=最新的）
        seen_ids = set()
        deduped = []
        for t in tasks:
            if t['id'] not in seen_ids:
                seen_ids.add(t['id'])
                deduped.append(t)
        tasks = deduped

        # ── 过滤掉非活跃的系统会话，防止看板噪音 ──
        # 规则: 仅保留 24小时内更新的活跃会话，且排除 cron/subagent 等纯后台任务
        filtered_tasks = []
        one_day_ago = now_ms - 24 * 3600 * 1000
        for t in tasks:
            # JJC-AUTO 和 OC 任务按相同规则过滤（保留活跃会话）
            # JJC- 人工下旨任务始终保留（但 JJC-AUTO 不是人工任务，走过滤）
            updated = t.get('sourceMeta', {}).get('updatedAt', 0)
            title = t.get('title', '')
            
            # 1. 排除太旧的 (超过24小时)
            if updated < one_day_ago:
                continue
            
            # 2. 排除纯后台 cron / subagent 任务，除非它们正在报错
            if '定时任务' in title or '子任务' in title:
                # 只有当它 block 或者 error 时才显示，否则视为噪音
                if t.get('state') != 'Blocked':
                    continue

            # 3. 排除已冷却的 OC 会话，避免污染看板
            # 保留 Doing（<2min）、Review（<60min）、Blocked（报错）
            # 仅过滤掉 Next（>60min 无响应）等已结束/闲置的会话
            state = t.get('state')
            if state not in ('Doing', 'Review', 'Blocked'):
                continue

            filtered_tasks.append(t)
        
        tasks = filtered_tasks
        
        # ── 保留已有的 JJC-* 旨意任务（不覆盖皇上下旨记录）──
        # JJC 任务的 now 字段由 Agent 自己通过 kanban_update.py progress 命令主动上报，
        # 不再从会话日志中被动抓取。这里只做合并，不做 activity 映射。
        existing_tasks_file = DATA / 'tasks_source.json'
        if existing_tasks_file.exists():
            try:
                existing = json.loads(existing_tasks_file.read_text())
                jjc_existing = [t for t in existing if str(t.get('id', '')).startswith('JJC')]
                
                # 去掉 tasks 里人工下旨的 JJC 任务（以防重复），但保留 JJC-AUTO 自动发现任务
                # dashboard 旨意看板只显示 /^JJC-/i 的任务，故自动发现也以 JJC-AUTO 前缀
                tasks = [t for t in tasks if not (str(t.get('id', '')).startswith('JJC') and not str(t.get('id', '')).startswith('JJC-AUTO'))]
                # 过滤掉已不存在的 AUTO 任务（session .jsonl 文件已删除但 sessions.json 还有僵尸条目）
                jjc_existing = [t for t in jjc_existing if not (str(t.get('id', '')).startswith('JJC-AUTO') and not _session_file_exists(t))]
                # 过滤掉 agent:*:main 主会话的 AUTO 任务（Agent 主聊天不是工作任务）
                jjc_existing = [t for t in jjc_existing if not (str(t.get('id', '')).startswith('JJC-AUTO') and _is_main_session(t))]
                tasks = jjc_existing + tasks
                # 再次去重（jjc_existing 和 tasks 中可能有相同 id 的 JJC-AUTO 任务）
                seen = set()
                unique = []
                for t in tasks:
                    if t['id'] not in seen:
                        seen.add(t['id'])
                        unique.append(t)
                tasks = unique
            except Exception as e:
                log.error(f'merge existing JJC tasks failed: {e}')
                pass

        atomic_json_write(DATA / 'tasks_source.json', tasks)

        duration_ms = int((time.time() - start) * 1000)
        write_status(
            ok=True,
            lastSyncAt=now,
            durationMs=duration_ms,
            source='openclaw_runtime_sessions',
            recordCount=len(tasks),
            scannedSessionFiles=scan_files,
            missingFields={},
            error=None,
        )
        log.info(f'synced {len(tasks)} tasks from openclaw runtime in {duration_ms}ms')

    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        write_status(
            ok=False,
            lastSyncAt=now,
            durationMs=duration_ms,
            source='openclaw_runtime_sessions',
            recordCount=0,
            missingFields={},
            error=f'{type(e).__name__}: {e}',
            traceback=traceback.format_exc(limit=3),
        )
        raise


if __name__ == '__main__':
    main()
