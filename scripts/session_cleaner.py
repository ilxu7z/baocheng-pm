#!/usr/bin/env python3
"""
Session Cleaner — 清理 OpenClaw Agent 的过期 session 文件，防止磁盘膨胀。

清理策略：
  - ld-r / openmoss-* : > 1 天（cron 每次创建新 session，旧的无用）
  - 三省六部 agents   : > 3 天（heartbeat 每 30 分钟一个）
  - main / rongcui    : > 7 天（保留一周历史对话）

用法:
  python3 session_cleaner.py              # 执行清理
  python3 session_cleaner.py --dry-run    # 只统计，不删除

集成到 run_loop.sh 中，每 N 小时执行一次。
"""

import os
import pathlib
import time
import json
import logging

log = logging.getLogger('session_cleaner')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

# ── 配置 ──

OPENCLAW_HOME = pathlib.Path.home() / '.openclaw'
SESSIONS_ROOT = OPENCLAW_HOME / 'agents'

# 清理策略: agent_id_prefix -> (文件类型, 天数)
# 支持 prefix 匹配（如 "openmoss-" 匹配所有 openmoss-* agent）
CLEANUP_POLICY = {
    # (文件名 glob, 修改时间 > N 天)
    'ld-r':             [('*.jsonl', 1), ('*.trajectory*.json', 1)],
    'openmoss-':        [('*.jsonl', 1), ('*.trajectory*.json', 1)],
    # 三省六部
    'daima':            [('*.jsonl', 3), ('*.trajectory*.json', 3)],
    'guihua':           [('*.jsonl', 3), ('*.trajectory*.json', 3)],
    'huizong':          [('*.jsonl', 3), ('*.trajectory*.json', 3)],
    'paifa':            [('*.jsonl', 3), ('*.trajectory*.json', 3)],
    'sheji':            [('*.jsonl', 3), ('*.trajectory*.json', 3)],
    'shencha':          [('*.jsonl', 3), ('*.trajectory*.json', 3)],
    'shenyi':           [('*.jsonl', 3), ('*.trajectory*.json', 3)],
    'wenan':            [('*.jsonl', 3), ('*.trajectory*.json', 3)],
    # main + rongcui 保留更久
    'main':             [('*.jsonl', 7), ('*.trajectory*.json', 7)],
    'rongcui':          [('*.jsonl', 7), ('*.trajectory*.json', 7)],
}

# 默认策略（未在策略中列出的 agent）
DEFAULT_POLICY = [('*.jsonl', 3), ('*.trajectory*.json', 3)]

CLEANUP_INTERVAL_HOURS = 4  # run_loop 中的清理间隔


def get_policy(agent_id: str):
    """根据 agent_id 查找匹配的清理策略"""
    # 精确匹配
    if agent_id in CLEANUP_POLICY:
        return CLEANUP_POLICY[agent_id]
    # 前缀匹配（如 openmoss-executor -> openmoss-）
    for prefix, policy in CLEANUP_POLICY.items():
        if prefix.endswith('-') and agent_id.startswith(prefix):
            return policy
    return DEFAULT_POLICY


def clean_sessions(dry_run=False):
    """执行清理，返回统计信息"""
    stats = {
        'deleted_files': 0,
        'freed_bytes': 0,
        'scanned_agents': 0,
        'details': {},
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
    }

    if not SESSIONS_ROOT.exists():
        log.warning('sessions 目录不存在: %s', SESSIONS_ROOT)
        return stats

    now = time.time()

    for agent_dir in SESSIONS_ROOT.iterdir():
        if not agent_dir.is_dir():
            continue
        agent_id = agent_dir.name
        sessions_dir = agent_dir / 'sessions'
        if not sessions_dir.exists():
            continue

        stats['scanned_agents'] += 1
        policy = get_policy(agent_id)
        agent_deleted = 0
        agent_freed = 0

        for pattern, max_days in policy:
            max_age = max_days * 86400  # 秒
            for f in sessions_dir.glob(pattern):
                if not f.is_file():
                    continue
                try:
                    mtime = f.stat().st_mtime
                except OSError:
                    continue
                if (now - mtime) > max_age:
                    try:
                        fsize = f.stat().st_size
                        if not dry_run:
                            f.unlink()
                        agent_deleted += 1
                        agent_freed += fsize
                    except OSError as e:
                        log.debug('删除失败 %s: %s', f, e)

        if agent_deleted > 0:
            stats['details'][agent_id] = {
                'deleted': agent_deleted,
                'freed_mb': round(agent_freed / 1048576, 1),
                'policy': f'{max_days}d',
            }
            stats['deleted_files'] += agent_deleted
            stats['freed_bytes'] += agent_freed

    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description='OpenClaw Session Cleaner')
    parser.add_argument('--dry-run', action='store_true', help='只统计不删除')
    parser.add_argument('--json', action='store_true', help='输出 JSON 格式')
    args = parser.parse_args()

    prefix = '[DRY RUN] ' if args.dry_run else ''
    log.info('%s开始清理 session 文件...', prefix)

    stats = clean_sessions(dry_run=args.dry_run)

    if stats['deleted_files'] == 0:
        log.info('%s无需清理（扫描 %d 个 agent 目录）', prefix, stats['scanned_agents'])
    else:
        log.info(
            '%s清理完成：删除 %d 个文件，释放 %.1fMB',
            prefix, stats['deleted_files'],
            stats['freed_bytes'] / 1048576
        )
        for agent_id, detail in stats['details'].items():
            log.info('  %s: -%d files, -%.1fMB (>%s)', agent_id, detail['deleted'], detail['freed_mb'], detail['policy'])

    if args.json:
        stats['freed_mb'] = round(stats['freed_bytes'] / 1048576, 1)
        print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
