#!/usr/bin/env python3
"""
knowledge_bridge.py — 记忆系统双向桥接

打通两套经验积累系统：
  MACS agent_memory (data/agent_memory/{agent_id}.json)
  ↔ shared-knowledge/ (lessons/ methods/ preferences/ INDEX.md)

用法:
  # MACS → shared-knowledge（将 Agent 写的记忆同步到共享知识库）
  python3 knowledge_bridge.py sync

  # shared-knowledge → MACS（将共享知识库条目写回 Agent 记忆，供查询）
  python3 knowledge_bridge.py backfill <agent_id>

  # 查看桥接统计
  python3 knowledge_bridge.py status

自动化:
  建议在 run_loop.sh 中加入此脚本，每次 sync 后自动执行。
"""
import json, pathlib, datetime, logging, re, sys, os

# 导入公共工具函数
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from utils import get_openclaw_home

log = logging.getLogger('knowledge_bridge')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

BASE = pathlib.Path(os.environ.get('EDICT_HOME', str(pathlib.Path(__file__).resolve().parent.parent)))
DATA = BASE / 'data'
AGENT_MEMORY_DIR = DATA / 'agent_memory'
TASK_MEMORY_DIR = DATA / 'task_memory'
SHARED_MEMORY_FILE = DATA / 'shared_memory.json'

OCLAW_HOME = get_openclaw_home()
SHARED_KNOWLEDGE_DIR = OCLAW_HOME / 'workspace-main' / 'shared-knowledge'

# ── 工具函数 ──

def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

def today_str():
    return datetime.datetime.now().strftime('%Y-%m-%d')

def slugify(text, max_len=40):
    """将文本转为文件名友好的 slug"""
    text = re.sub(r'[^\w\u4e00-\u9fff\s-]', '', text)
    text = re.sub(r'\s+', '-', text.strip())
    return text[:max_len]


# ── MACS → shared-knowledge ──

def sync_agent_memories_to_shared_knowledge():
    """将 Agent 写的经验同步到共享知识库。"""
    if not AGENT_MEMORY_DIR.is_dir():
        log.info('agent_memory 目录为空，跳过同步')
        return {'synced': 0, 'skipped': 0}

    results = {'synced': 0, 'skipped': 0}

    for mem_file in sorted(AGENT_MEMORY_DIR.glob('*.json')):
        try:
            data = json.loads(mem_file.read_text(encoding='utf-8'))
        except Exception:
            continue

        agent_id = data.get('agent_id', mem_file.stem)
        memories = data.get('memories', [])

        for mem in memories:
            mem_type = mem.get('type', 'experience')
            content = mem.get('content', '')
            mem_id = mem.get('id', '')
            source_task = mem.get('source_task', '')
            created_at = mem.get('created_at', '')

            if not content or len(content) < 10:
                continue

            # 根据类型路由到不同目录
            if mem_type == 'lesson' or mem_type == 'experience':
                _write_lesson(agent_id, content, source_task, created_at, results)
            elif mem_type == 'method':
                _write_method(agent_id, content, source_task, created_at, results)
            elif mem_type == 'preference' or mem_type == 'feedback':
                _write_preference(agent_id, content, source_task, created_at, results)

    _update_index()
    return results


def _write_lesson(agent_id, content, source_task, created_at, results):
    target_dir = SHARED_KNOWLEDGE_DIR / 'lessons'
    target_dir.mkdir(parents=True, exist_ok=True)

    date_str = created_at[:10] if created_at else today_str()
    slug = slugify(content)
    filename = f'{date_str}-{slug}.md'

    filepath = target_dir / filename
    if filepath.exists():
        results['skipped'] += 1
        return

    filepath.write_text(f"""# {content[:60]}

- **日期**: {created_at[:10] if created_at else '未知'}
- **来源 Agent**: {agent_id}
- **关联任务**: {source_task or '无'}

## 问题
{content}

## 预防
（待 Agent 补充）
""", encoding='utf-8')
    log.info(f'📝 lesson: {filename}')
    results['synced'] += 1


def _write_method(agent_id, content, source_task, created_at, results):
    target_dir = SHARED_KNOWLEDGE_DIR / 'methods'
    target_dir.mkdir(parents=True, exist_ok=True)

    date_str = created_at[:10] if created_at else today_str()
    slug = slugify(content)
    filename = f'{date_str}-{slug}.md'

    filepath = target_dir / filename
    if filepath.exists():
        results['skipped'] += 1
        return

    filepath.write_text(f"""# {content[:60]}

- **日期**: {created_at[:10] if created_at else '未知'}
- **来源 Agent**: {agent_id}
- **关联任务**: {source_task or '无'}

## 方法描述
{content}

## 适用场景
（待 Agent 补充）

## 步骤
（待 Agent 补充）
""", encoding='utf-8')
    log.info(f'📝 method: {filename}')
    results['synced'] += 1


def _write_preference(agent_id, content, source_task, created_at, results):
    target_dir = SHARED_KNOWLEDGE_DIR / 'preferences'
    target_dir.mkdir(parents=True, exist_ok=True)

    date_str = created_at[:10] if created_at else today_str()
    filename = f'{date_str}-{slugify(content)}.md'

    filepath = target_dir / filename
    if filepath.exists():
        results['skipped'] += 1
        return

    filepath.write_text(f"""# {content[:60]}

- **日期**: {created_at[:10] if created_at else '未知'}
- **来源 Agent**: {agent_id}

{content}
""", encoding='utf-8')
    log.info(f'📝 preference: {filename}')
    results['synced'] += 1


def _update_index():
    """更新 shared-knowledge/INDEX.md"""
    idx_path = SHARED_KNOWLEDGE_DIR / 'INDEX.md'
    if not idx_path.exists():
        return

    existing = idx_path.read_text(encoding='utf-8')

    # 扫描各目录
    lessons = _list_md_files('lessons')
    methods = _list_md_files('methods')
    preferences = _list_md_files('preferences')

    # 生成新的索引段落
    index_entries = []
    for cat, entries in [('lessons/', lessons), ('methods/', methods), ('preferences/', preferences)]:
        index_entries.append(f'### {cat}')
        if entries:
            for name, title in entries:
                index_entries.append(f'- [{title}]({cat}{name})')
        else:
            index_entries.append('*(暂无条目)*')
        index_entries.append('')

    # 替换现有索引（保留文件头和进化协议部分）
    header_end = existing.find('## 📋 知识条目')
    protocol_start = existing.find('## 🔄 进化协议')

    if header_end >= 0 and protocol_start > header_end:
        new_content = existing[:header_end]
        new_content += '## 📋 知识条目\n\n'
        new_content += '\n'.join(index_entries)
        new_content += '\n' + existing[protocol_start:]
        idx_path.write_text(new_content, encoding='utf-8')
        log.info('📋 INDEX.md 已更新')


def _list_md_files(subdir):
    """列出子目录中的 md 文件，返回 [(filename, title), ...]"""
    d = SHARED_KNOWLEDGE_DIR / subdir
    if not d.is_dir():
        return []
    results = []
    for f in sorted(d.glob('*.md')):
        try:
            lines = f.read_text(encoding='utf-8').splitlines()
            title = f.name
            for line in lines:
                if line.startswith('# '):
                    title = line[2:].strip()
                    break
            results.append((f.name, title))
        except Exception:
            results.append((f.name, f.name))
    return results


# ── shared-knowledge → MACS ──

def backfill_to_agent(agent_id):
    """将共享知识库中的相关条目写回 Agent 记忆（供 Agent 查询）。"""
    if not SHARED_KNOWLEDGE_DIR.is_dir():
        log.warning('shared-knowledge 目录不存在')
        return 0

    # 读共享知识库中的 lessons 和 methods
    entries = []
    for cat_dir in ['lessons', 'methods']:
        d = SHARED_KNOWLEDGE_DIR / cat_dir
        if not d.is_dir():
            continue
        for f in sorted(d.glob('*.md')):
            try:
                content = f.read_text(encoding='utf-8')
                # 取前 200 字作为摘要
                summary = content[:200].replace('\n', ' ')
                entries.append({
                    'type': 'shared_knowledge',
                    'source': f'{cat_dir}/{f.name}',
                    'content': summary,
                    'created_at': now_iso(),
                    'pinned': True,  # 共享知识条目不淘汰
                })
            except Exception:
                continue

    if not entries:
        return 0

    AGENT_MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    mem_file = AGENT_MEMORY_DIR / f'{agent_id}.json'

    existing = {}
    if mem_file.exists():
        try:
            existing = json.loads(mem_file.read_text(encoding='utf-8'))
        except Exception:
            pass

    memories = existing.get('memories', [])
    existing_sources = {m.get('source', '') for m in memories}

    added = 0
    for entry in entries:
        if entry['source'] not in existing_sources:
            memories.append(entry)
            added += 1

    existing['agent_id'] = agent_id
    existing['memories'] = memories

    mem_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding='utf-8')
    log.info(f'backfill {agent_id}: +{added} shared knowledge entries')
    return added


# ── 状态查询 ──

def show_status():
    """展示桥接状态。"""
    lines = ['📊 记忆系统桥接状态', '=' * 40]

    # MACS 侧
    lines.append('\n📮 MACS agent_memory:')
    if AGENT_MEMORY_DIR.is_dir():
        for f in sorted(AGENT_MEMORY_DIR.glob('*.json')):
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
                count = len(data.get('memories', []))
                pinned = sum(1 for m in data.get('memories', []) if m.get('pinned'))
                lines.append(f'  {f.stem}: {count} 条记忆 ({pinned} pinned)')
            except Exception:
                lines.append(f'  {f.stem}: 读取失败')
    else:
        lines.append('  (空)')

    # shared-knowledge 侧
    lines.append('\n📚 shared-knowledge:')
    for cat in ['lessons', 'methods', 'preferences']:
        d = SHARED_KNOWLEDGE_DIR / cat
        if d.is_dir():
            files = list(d.glob('*.md'))
            lines.append(f'  {cat}/: {len(files)} 个条目')
        else:
            lines.append(f'  {cat}/: (不存在)')

    # 任务记忆
    lines.append('\n📝 task_memory:')
    if TASK_MEMORY_DIR.is_dir():
        files = list(TASK_MEMORY_DIR.glob('*.json'))
        lines.append(f'  {len(files)} 个任务的记忆')
    else:
        lines.append('  (空)')

    # 共享记忆
    lines.append('\n🌐 shared_memory:')
    if SHARED_MEMORY_FILE.exists():
        try:
            data = json.loads(SHARED_MEMORY_FILE.read_text(encoding='utf-8'))
            lines.append(f'  {len(data.get("rules", []))} 条全局规则')
        except Exception:
            lines.append('  读取失败')
    else:
        lines.append('  (空)')

    print('\n'.join(lines))


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'

    if cmd == 'sync':
        result = sync_agent_memories_to_shared_knowledge()
        print(f'✅ 同步完成: {result["synced"]} 新增, {result["skipped"]} 跳过')

    elif cmd == 'backfill':
        agent_id = sys.argv[2] if len(sys.argv) > 2 else 'all'
        if agent_id == 'all':
            total = 0
            if AGENT_MEMORY_DIR.is_dir():
                for f in AGENT_MEMORY_DIR.glob('*.json'):
                    total += backfill_to_agent(f.stem)
            print(f'✅ backfill all: {total} entries')
        else:
            added = backfill_to_agent(agent_id)
            print(f'✅ backfill {agent_id}: {added} entries')

    elif cmd == 'status':
        show_status()

    else:
        print(__doc__)
