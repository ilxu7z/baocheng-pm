#!/usr/bin/env python3
"""
同步 openclaw.json 中的 agent 配置 → data/agent_config.json
支持自动发现 agent workspace 下的 Skills 目录

Changelog v2 (2026-06-02):
- _collect_openclaw_models(): 修复 providers 路径 (cfg.providers → cfg.models.providers)，修复自定义 provider 模型不出现
- get_skills(): 加 workspace 目录存在性校验
- allowAgents: 兼容 ag.subagents.allowAgents 和 ag.allowAgents 两种位置
"""
import json, os, pathlib, datetime, logging
from file_lock import atomic_json_write
from utils import get_openclaw_home

log = logging.getLogger('sync_agent_config')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

# Auto-detect project root (parent of scripts/)
BASE = pathlib.Path(__file__).parent.parent
DATA = BASE / 'data'
OPENCLAW_HOME = get_openclaw_home()
OPENCLAW_CFG = OPENCLAW_HOME / 'openclaw.json'

ID_LABEL = {
    'main':     {'label': '鲍澄',   'role': '项目负责人', 'duty': '需求分析、调度决策、最终交付', 'emoji': '🏛️'},
    'ld-r':     {'label': 'Ld.r',   'role': '执行经理',   'duty': '项目管理、方案执行、督办推进', 'emoji': '📮'},
    'guihua':   {'label': '筹微',   'role': '规划师',     'duty': '需求拆解、生成TASK.md',          'emoji': '📜'},
    'shenyi':   {'label': '审微',   'role': '审议官',     'duty': '独立审查、通过或驳回',            'emoji': '🔍'},
    'paifa':    {'label': '驿使',   'role': '派发官',     'duty': '任务路由、派发到执行部门',        'emoji': '📮'},
    'wenan':    {'label': '墨卿',   'role': '文案策划',   'duty': '网站文案、品牌故事、SEO、翻译',   'emoji': '📝'},
    'daima':    {'label': '锋铸',   'role': '代码开发',   'duty': '前端开发、功能实现、性能优化',    'emoji': '⚔️'},
    'sheji':    {'label': '绘象',   'role': '视觉设计',   'duty': '视觉规范、UI设计、生图',          'emoji': '🎨'},
    'shencha':  {'label': '镜衡',   'role': '质量审查',   'duty': '独立质量验收、对照标准评分',      'emoji': '⚖️'},
    'huizong':  {'label': '归藏',   'role': '项目汇总',   'duty': '整合交付、生成交付报告',          'emoji': '📋'},
    'rongcui':  {'label': '溶萃',   'role': '全能工程师', 'duty': '运维部署、技术支持、特殊任务',    'emoji': '🔧'},
}

# 不再维护硬编码模型列表。所有可用模型从 openclaw.json 的 defaults.models 读取，
# 这是 OpenClaw 实际使用的模型列表，是唯一真相源。


def normalize_model(model_value, fallback='unknown'):
    if isinstance(model_value, str) and model_value:
        return model_value
    if isinstance(model_value, dict):
        return model_value.get('primary') or model_value.get('id') or fallback
    return fallback


def _parse_skill_front_matter(md_path: pathlib.Path):
    """解析 SKILL.md 的 YAML front matter，返回 name 和 description。"""
    name = md_path.parent.name
    desc = ''
    if not md_path.exists():
        return name, desc
    try:
        lines = md_path.read_text(encoding='utf-8', errors='ignore').splitlines()
        in_front = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped == '---':
                if not in_front:
                    in_front = True
                    continue
                else:
                    break  # end front matter
            if in_front:
                if stripped.startswith('name:'):
                    v = stripped[len('name:'):].strip().strip("'\"")
                    if v:
                        name = v
                elif stripped.startswith('description:'):
                    v = stripped[len('description:'):].strip().strip("'\"")
                    if v:
                        desc = v
        if not desc:
            # 兜底：用第一行非空正文
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and not stripped.startswith('---'):
                    desc = stripped[:100]
                    break
    except Exception:
        pass
    return name, desc


GLOBAL_SKILLS_PATH = OPENCLAW_HOME / 'skills'


def _scan_global_skills():
    """扫描 ~/.openclaw/skills/ 目录，返回所有全局技能列表。"""
    skills = []
    try:
        if GLOBAL_SKILLS_PATH.is_dir():
            for d in sorted(GLOBAL_SKILLS_PATH.iterdir()):
                if d.is_dir():
                    md = d / 'SKILL.md'
                    sname, sdesc = _parse_skill_front_matter(md)
                    skills.append({
                        'name': d.name,
                        'title': sname,
                        'path': str(md),
                        'exists': md.exists(),
                        'description': sdesc or '(无描述)',
                        'isGlobal': True,
                    })
    except PermissionError:
        pass
    return skills


def get_skills(workspace: str):
    """获取 Agent 私有技能（workspace-{agent}/skills/ 目录下）。
    5.28+ 兼容：先校验 workspace 目录是否实际存在。"""
    ws_path = pathlib.Path(workspace)
    if not ws_path.exists():
        log.info(f'workspace does not exist: {workspace}')
        return []
    skills_dir = ws_path / 'skills'
    skills = []
    try:
        if skills_dir.exists():
            for d in sorted(skills_dir.iterdir()):
                if d.is_dir():
                    md = d / 'SKILL.md'
                    sname, sdesc = _parse_skill_front_matter(md)
                    skills.append({
                        'name': d.name,
                        'title': sname,
                        'path': str(md),
                        'exists': md.exists(),
                        'description': sdesc or '(无描述)',
                        'isGlobal': False,
                    })
    except PermissionError as e:
        log.warning(f'Skills 目录访问受限: {e}')
    return skills


def _merge_skills(global_skills, agent_specific_skills, agent_id):
    """合并全局技能和 Agent 私有技能。全局技能默认 disabled，可在 dashboard 中启用。"""
    # 加载已有的 enabled 状态
    existing_path = DATA / 'agent_config.json'
    existing_enabled = {}
    if existing_path.exists():
        try:
            existing = json.loads(existing_path.read_text())
            for a in existing.get('agents', []):
                if a.get('id') == agent_id:
                    for s in a.get('skills', []):
                        if s.get('isGlobal'):
                            existing_enabled[s['name']] = s.get('enabled', False)
        except Exception:
            pass

    merged = []
    for gs in global_skills:
        s = dict(gs)
        s['enabled'] = existing_enabled.get(gs['name'], False)
        merged.append(s)
    for cs in agent_specific_skills:
        s = dict(cs)
        s['enabled'] = True
        merged.append(s)
    return merged


def _collect_openclaw_models(cfg):
    """从 openclaw.json 的 defaults.models 收集所有可用模型。
    
    defaults.models 是 OpenClaw 实际使用的模型列表，是唯一真相源。
    格式: {"ProviderName/model-id": {}, ...}
    
    同时兜底收集 agents.list 中各 agent 的 model 字段，确保已分配给 agent
    的模型即使不在 defaults.models 中也能出现在下拉列表。
    """
    result = []
    seen_ids = set()

    agents_cfg = cfg.get('agents', {})

    # 主源：defaults.models（OpenClaw 实际启用的模型）
    defaults_models = agents_cfg.get('defaults', {}).get('models', {})
    if isinstance(defaults_models, dict):
        for full_id in defaults_models.keys():
            if not full_id or full_id in seen_ids:
                continue
            seen_ids.add(full_id)
            # full_id 格式: "ProviderName/model-id" 如 "火山/deepseek-v4-flash-260425"
            parts = full_id.split('/', 1)
            provider = parts[0] if len(parts) > 1 else 'OpenClaw'
            model_name = parts[1] if len(parts) > 1 else full_id
            result.append({
                'id': full_id,
                'label': model_name,
                'provider': provider,
            })

    # 兜底：agents.list 中各 agent 的 model（可能不在 defaults.models 中）
    for ag in agents_cfg.get('list', []):
        m = normalize_model(ag.get('model', ''), '')
        if m and m not in seen_ids:
            seen_ids.add(m)
            parts = m.split('/', 1)
            provider = parts[0] if len(parts) > 1 else 'OpenClaw'
            model_name = parts[1] if len(parts) > 1 else m
            result.append({
                'id': m,
                'label': model_name,
                'provider': provider,
            })

    return result


def main():
    cfg = {}
    try:
        cfg = json.loads(OPENCLAW_CFG.read_text(encoding='utf-8'))
    except Exception as e:
        log.warning(f'cannot read openclaw.json: {e}')
        return

    agents_cfg = cfg.get('agents', {})
    default_model = normalize_model(agents_cfg.get('defaults', {}).get('model', {}), 'unknown')
    agents_list = agents_cfg.get('list', [])
    merged_models = _collect_openclaw_models(cfg)

    global_skills = _scan_global_skills()

    result = []
    seen_ids = set()
    for ag in agents_list:
        ag_id = ag.get('id', '')
        if ag_id not in ID_LABEL:
            continue
        meta = ID_LABEL[ag_id]
        workspace = ag.get('workspace', str(OPENCLAW_HOME / f'workspace-{ag_id}'))
        # 5.28+ 兼容：allowAgents 可能在 ag.allowAgents 或 ag.subagents.allowAgents
        if 'allowAgents' in ag:
            allow_agents = ag.get('allowAgents', []) or []
        else:
            allow_agents = (ag.get('subagents') or {}).get('allowAgents', []) if isinstance(ag.get('subagents'), dict) else []
            if not isinstance(allow_agents, list):
                allow_agents = []
        agent_skills = get_skills(workspace)
        merged = _merge_skills(global_skills, agent_skills, ag_id)
        result.append({
            'id': ag_id,
            'label': meta['label'], 'role': meta['role'], 'duty': meta['duty'], 'emoji': meta['emoji'],
            'model': normalize_model(ag.get('model', default_model), default_model),
            'defaultModel': default_model,
            'workspace': workspace,
            'skills': merged,
            'allowAgents': allow_agents,
        })
        seen_ids.add(ag_id)

    # 补充不在 openclaw.json agents list 中的 agent（主会话鲍澄）
    EXTRA_AGENTS = {
        'main':    {'model': default_model, 'workspace': str(OPENCLAW_HOME / 'workspace-main'),
                    'allowAgents': ['guihua','shenyi','paifa','wenan','daima','sheji','shencha','huizong']},
    }
    for ag_id, extra in EXTRA_AGENTS.items():
        if ag_id in seen_ids or ag_id not in ID_LABEL:
            continue
        meta = ID_LABEL[ag_id]
        agent_skills = get_skills(extra['workspace'])
        merged = _merge_skills(global_skills, agent_skills, ag_id)
        result.append({
            'id': ag_id,
            'label': meta['label'], 'role': meta['role'], 'duty': meta['duty'], 'emoji': meta['emoji'],
            'model': extra['model'],
            'defaultModel': default_model,
            'workspace': extra['workspace'],
            'skills': merged,
            'allowAgents': extra['allowAgents'],
            'isDefaultModel': True,
        })

    # 保留已有的 dispatchChannel 配置 (Fix #139)
    existing_cfg = {}
    cfg_path = DATA / 'agent_config.json'
    if cfg_path.exists():
        try:
            existing_cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    payload = {
        'generatedAt': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'defaultModel': default_model,
        'knownModels': merged_models,
        'dispatchChannel': existing_cfg.get('dispatchChannel') or os.getenv('DEFAULT_DISPATCH_CHANNEL', ''),
        'agents': result,
        'globalSkillsPool': global_skills,
    }
    DATA.mkdir(exist_ok=True)
    atomic_json_write(DATA / 'agent_config.json', payload)
    log.info(f'{len(result)} agents synced')

    # 自动部署 SOUL.md 到 workspace（如果项目里有更新）
    deploy_soul_files()
    # 同步 scripts/ 到各 workspace（保持 kanban_update.py 等最新）
    sync_scripts_to_workspaces()


# 项目 agents/ 目录名 → 运行时 agent_id 映射
_SOUL_DEPLOY_MAP = {
    'guihua': 'guihua',
    'shenyi': 'shenyi',
    'paifa': 'paifa',
    'wenan': 'wenan',
    'daima': 'daima',
    'sheji': 'sheji',
    'shencha': 'shencha',
    'huizong': 'huizong',
}

def _sync_script_symlink(src_file: pathlib.Path, dst_file: pathlib.Path) -> bool:
    """Create a symlink dst_file → src_file (resolved).

    Using symlinks instead of physical copies ensures that ``__file__`` in
    each script always resolves back to the project ``scripts/`` directory,
    so relative-path computations like ``Path(__file__).resolve().parent.parent``
    point to the correct project root regardless of which workspace runs the
    script.  (Fixes #56 — kanban data-path split)

    Returns True if the link was (re-)created, False if already up-to-date.
    """
    src_resolved = src_file.resolve()
    # Guard: skip if dst resolves to the same real path as src.
    # This happens when ws_scripts is itself a directory-level symlink pointing
    # to the project scripts/ dir (created by install.sh link_resources).
    # Without this check the function would unlink the real source file and
    # then create a self-referential symlink (foo.py -> foo.py).
    try:
        dst_resolved = dst_file.resolve()
    except OSError:
        dst_resolved = None
    if dst_resolved == src_resolved:
        return False
    # Already a correct symlink?
    if dst_file.is_symlink() and dst_resolved == src_resolved:
        return False
    # Remove stale file / old physical copy / broken symlink
    if dst_file.exists() or dst_file.is_symlink():
        dst_file.unlink()
    os.symlink(src_resolved, dst_file)
    return True


def sync_scripts_to_workspaces():
    """将项目 scripts/ 目录同步到各 agent workspace（保持 kanban_update.py 等最新）

    Uses symlinks so that ``__file__`` in workspace copies resolves to the
    project ``scripts/`` directory, keeping path-derived constants like
    ``TASKS_FILE`` pointing to the canonical ``data/`` folder.
    """
    scripts_src = BASE / 'scripts'
    if not scripts_src.is_dir():
        return
    synced = 0
    for proj_name, runtime_id in _SOUL_DEPLOY_MAP.items():
        ws_scripts = OPENCLAW_HOME / f'workspace-{runtime_id}' / 'scripts'
        ws_scripts.mkdir(parents=True, exist_ok=True)
        for src_file in scripts_src.iterdir():
            if src_file.suffix not in ('.py', '.sh') or src_file.stem.startswith('__'):
                continue
            dst_file = ws_scripts / src_file.name
            try:
                if _sync_script_symlink(src_file, dst_file):
                    synced += 1
            except Exception:
                continue
    # also sync to workspace-main for legacy compatibility
    ws_main_scripts = OPENCLAW_HOME / 'workspace-main' / 'scripts'
    ws_main_scripts.mkdir(parents=True, exist_ok=True)
    for src_file in scripts_src.iterdir():
        if src_file.suffix not in ('.py', '.sh') or src_file.stem.startswith('__'):
            continue
        dst_file = ws_main_scripts / src_file.name
        try:
            if _sync_script_symlink(src_file, dst_file):
                synced += 1
        except Exception:
            pass
    if synced:
        log.info(f'{synced} script symlinks synced to workspaces')


def deploy_soul_files():
    """将项目 agents/xxx/SOUL.md 部署到 ~/.openclaw/workspace-xxx/SOUL.md"""
    agents_dir = BASE / 'agents'
    deployed = 0
    for proj_name, runtime_id in _SOUL_DEPLOY_MAP.items():
        src = agents_dir / proj_name / 'SOUL.md'
        if not src.exists():
            continue
        ws_dst = OPENCLAW_HOME / f'workspace-{runtime_id}' / 'SOUL.md'
        ws_dst.parent.mkdir(parents=True, exist_ok=True)
        # 只在内容不同时更新（避免不必要的写入）
        src_text = src.read_text(encoding='utf-8', errors='ignore')
        try:
            dst_text = ws_dst.read_text(encoding='utf-8', errors='ignore')
        except FileNotFoundError:
            dst_text = ''
        if src_text != dst_text:
            ws_dst.write_text(src_text, encoding='utf-8')
            deployed += 1
        # 总办兼容：同步一份到 legacy main agent 目录
        if runtime_id == 'taizi':
            ag_dst = OPENCLAW_HOME / 'agents' / 'main' / 'SOUL.md'
            ag_dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                ag_text = ag_dst.read_text(encoding='utf-8', errors='ignore')
            except FileNotFoundError:
                ag_text = ''
            if src_text != ag_text:
                ag_dst.write_text(src_text, encoding='utf-8')
        # 确保 sessions 目录存在
        sess_dir = OPENCLAW_HOME / 'agents' / runtime_id / 'sessions'
        sess_dir.mkdir(parents=True, exist_ok=True)
    if deployed:
        log.info(f'{deployed} SOUL.md files deployed')


if __name__ == '__main__':
    main()
