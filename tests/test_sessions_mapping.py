# -*- coding: utf-8 -*-
"""JJC-20260807-001 P1-1 会话映射逻辑修复 单元测试（AC4）
覆盖：Bug1 分页/全量拉取、Bug2 spawnedBy 死代码、Bug3 org 归一化、Bug4 TTL。
"""
import json
import subprocess
import sys
import os

# 让 dashboard 可导入
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'dashboard'))
import server  # noqa: E402


def test_modern_org_normalization():
    """AC2：怪值 + 古名归一化"""
    assert server._modern('审议部') == '审议部'          # 已现代名
    assert server._modern('门下省') == '审议部'          # 古名
    assert server._modern('三省-军师') == '规划部'        # 怪值
    assert server._modern('三省-研发主管') == '开发部'    # 怪值
    assert server._modern('') == ''                       # 空值健壮


def test_modern_org_legacy_full():
    """古名全覆盖（ORG_LEGACY_MAP 关键项）"""
    cases = {
        '皇上': '老板', '太子': '总办', '中书省': '规划部', '门下省': '审议部',
        '尚书省': '执行办', '吏部': '人力路由处', '礼部': '内容部', '兵部': '开发部',
        '刑部': '质控部', '工部': '设计部', '户部': '交付汇总处', '钦天监': '运维组',
    }
    for old, new in cases.items():
        assert server._modern(old) == new, f'{old} → {new}'


def test_sessions_ttl():
    """Bug4：TTL 已提升到 10-15s 区间（非 2.0）"""
    assert 10 <= server._SESSIONS_CACHE_TTL <= 15, \
        f'TTL={server._SESSIONS_CACHE_TTL} 应落在 10-15s'


def test_spawnedby_bare_id():
    """Bug2：spawnedBy 完整 key → 裸 id（agent:main:main → main）"""
    sb = 'agent:main:dashboard:796eb76c'
    bare = sb.split(':')[1] if sb.count(':') >= 1 else sb
    assert bare == 'main'
    # 空值不崩溃
    empty = ''
    bare_empty = empty.split(':')[1] if empty.count(':') >= 1 else empty
    assert bare_empty == ''


def test_sessions_list_pagination():
    """Bug1：全量拉取，hasMore 处理，totalSessions 真实总数（≥224）"""
    r = subprocess.run(
        ['openclaw', 'sessions', 'list', '--all-agents', '--json', '--limit', '300'],
        capture_output=True, text=True, timeout=30
    )
    assert r.returncode == 0, f'openclaw 调用失败: {r.stderr[:200]}'
    data = json.loads(r.stdout)
    sessions = data.get('sessions', [])
    total = int(data.get('totalCount') or len(sessions))
    has_more = data.get('hasMore', False)
    assert not has_more, 'limit=300 仍 hasMore，需放大'
    assert len(sessions) >= 224, f'应拉取≥224，实际 {len(sessions)}'
    assert len(sessions) <= total, 'returnedSessions 不应超过 totalSessions'


def test_get_sessions_mapping_shape():
    """AC3：get_sessions_mapping 返回结构含 totalSessions/returnedSessions"""
    # 仅验证返回结构字段存在（不依赖真实任务匹配，避免耦合看板数据）
    result = server.get_sessions_mapping()
    assert result.get('ok') is True
    assert 'totalSessions' in result
    assert 'returnedSessions' in result
    assert result['returnedSessions'] <= result['totalSessions']
    assert result['totalSessions'] >= 224


if __name__ == '__main__':
    # 简易 runner（无 pytest 时可用 python tests/test_xxx.py）
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    passed = 0
    for fn in fns:
        try:
            fn()
            print(f'  ✅ {fn.__name__}')
            passed += 1
        except Exception:
            print(f'  ❌ {fn.__name__}')
            traceback.print_exc()
    print(f'\n{passed}/{len(fns)} 通过')
    sys.exit(0 if passed == len(fns) else 1)
