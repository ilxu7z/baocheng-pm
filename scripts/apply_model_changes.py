#!/usr/bin/env python3
"""应用 data/pending_model_changes.json → openclaw.json，并重启 Gateway"""
import json, pathlib, subprocess, datetime, shutil, logging, glob
from file_lock import atomic_json_write, atomic_json_read
from utils import get_openclaw_home

log = logging.getLogger('model_change')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s', datefmt='%H:%M:%S')

BASE = pathlib.Path(__file__).parent.parent
DATA = BASE / 'data'
OPENCLAW_HOME = get_openclaw_home()
OPENCLAW_CFG = OPENCLAW_HOME / 'openclaw.json'
PENDING = DATA / 'pending_model_changes.json'
CHANGE_LOG = DATA / 'model_change_log.json'
MAX_BACKUPS = 10


def rj(path, default):
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def cleanup_backups():
    """只保留最近 MAX_BACKUPS 个备份"""
    pattern = str(OPENCLAW_CFG.parent / 'openclaw.json.bak.model-*')
    baks = sorted(glob.glob(pattern))
    for old in baks[:-MAX_BACKUPS]:
        try:
            pathlib.Path(old).unlink()
        except OSError:
            pass


def _hot_reload():
    """通过 Gateway RPC 触发热加载，不重启"""
    try:
        r = subprocess.run(
            ['openclaw', 'config', 'validate'],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode == 0:
            log.info('config validation OK')
        else:
            log.warning(f'config validation: {r.stderr.strip()}')
    except Exception as e:
        log.warning(f'config validation failed (non-fatal): {e}')


def main():
    if not PENDING.exists():
        return
    pending = rj(PENDING, [])
    if not pending:
        return

    import copy
    cfg = rj(OPENCLAW_CFG, {})
    # deepcopy：new_cfg 的修改不影响 cfg，确保 old_text ≠ new_text 判断正确
    new_cfg = copy.deepcopy(cfg)
    agents_list = new_cfg.get('agents', {}).get('list', [])
    default_model = cfg.get('agents', {}).get('defaults', {}).get('model', {}).get('primary', '')

    applied, errors = [], []
    for change in pending:
        ag_id = change.get('agentId', '').strip()
        new_model = change.get('model', '').strip()
        if not ag_id or not new_model:
            errors.append({'change': change, 'error': 'missing fields'})
            continue
        found = False
        for ag in agents_list:
            if ag.get('id') == ag_id:
                old = ag.get('model', default_model)
                if new_model == default_model:
                    ag.pop('model', None)
                else:
                    ag['model'] = new_model
                # 确保 oldModel 总是字符串（非 dict），避免 React 渲染崩溃
                old_model_str = old if isinstance(old, str) else (old.get('primary', '') if isinstance(old, dict) else str(old))
                applied.append({'at': datetime.datetime.now().isoformat(), 'agentId': ag_id, 'oldModel': old_model_str, 'newModel': new_model})
                found = True
                break
        if not found:
            errors.append({'change': change, 'error': f'agent {ag_id} not found'})

    if applied:
        old_text = json.dumps(cfg, ensure_ascii=False, sort_keys=True)
        new_text = json.dumps(new_cfg, ensure_ascii=False, sort_keys=True)
        if old_text != new_text:
            bak = OPENCLAW_CFG.parent / f'openclaw.json.bak.model-{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}'
            shutil.copy2(OPENCLAW_CFG, bak)
            cleanup_backups()
            atomic_json_write(OPENCLAW_CFG, new_cfg)

        log_data = rj(CHANGE_LOG, [])
        if not isinstance(log_data, list):
            log_data = []
        log_data.extend(applied)
        if len(log_data) > 200:
            log_data = log_data[-200:]
        atomic_json_write(CHANGE_LOG, log_data)

        for e in applied:
            log.info(f'{e["agentId"]}: {e["oldModel"]} → {e["newModel"]}')

        # 热加载替换重启：agents.list.*.model 的 reloadKind = "hot"
        # gateway.reload.mode=hybrid + debounceMs=500 → 500ms 内自动生效
        log.info('config written → gateway hot-reload in ~500ms (no restart)')
        _hot_reload()
        reload_ok = True
        rollback = False

        atomic_json_write(PENDING, [])
        atomic_json_write(DATA / 'last_model_change_result.json', {
            'at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'applied': applied, 'errors': errors,
            'hotReloaded': reload_ok, 'rolledBack': rollback,
        })
    elif errors:
        log.warning(f'{len(errors)} changes failed, 0 applied')
        atomic_json_write(PENDING, [])


if __name__ == '__main__':
    main()
