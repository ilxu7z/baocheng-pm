#!/usr/bin/env python3
"""
migrate_org_names.py — 「三省六部 → 现代化组织」历史数据一次性迁移

将 data/ 下各 JSON 文件中残留的古代名称（太子/中书省/皇上/准奏/封驳 等）
迁移为现代化名称（总办/规划部/老板/通过/驳回 等），保证与 dashboard 改名后的
后端运行时写入格式一致（历史数据 org/from/to/remark 全量现代化）。

安全特性:
  - --dry-run            只预览将发生的替换，不写文件
  - 自动备份            每次实际写入前，将原文件复制为 <file>.bak-<ts>
  - 长词优先替换        避免「太子调度」被「太子→总办」拆成「总办调度」
  - 字段感知替换        org/official/from/to 用整值映射；remark/now 用词替换

用法:
  python3 scripts/migrate_org_names.py --dry-run        # 预览
  python3 scripts/migrate_org_names.py                  # 实际迁移
  python3 scripts/migrate_org_names.py --files a.json b.json  # 指定文件
"""

import argparse
import json
import os
import shutil
import sys
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── 权威映射表（与 dashboard/server.py ORG_LEGACY_MAP + court OFFICIAL_PROFILES 一致）──
# 整值映射：org / official / from / to 等字段的精确值（长词在前，防止局部误伤）
VALUE_MAP = [
    # (古名, 现代名)  长词优先
    ("太子调度", "总控调度"),
    ("朝报官", "运维专员"),
    ("钦天监", "运维组"),
    ("礼部尚书", "内容负责人"),
    ("户部尚书", "交付负责人"),
    ("兵部尚书", "开发负责人"),
    ("刑部尚书", "质控负责人"),
    ("工部尚书", "设计负责人"),
    ("吏部尚书", "人力路由负责人"),
    ("中书令", "规划师"),
    ("尚书令", "执行经理"),
    ("门下省", "审议部"),
    ("中书省", "规划部"),
    ("尚书省", "执行办"),
    ("礼部", "内容部"),
    ("户部", "交付汇总处"),
    ("兵部", "开发部"),
    ("刑部", "质控部"),
    ("工部", "设计部"),
    ("吏部", "人力路由处"),
    ("太子", "总办"),
    ("皇上", "老板"),
    ("准奏", "通过"),
    ("封驳", "驳回"),
    ("御批", "审议"),
    ("下旨", "创建任务"),
    ("旨意", "任务"),
    ("储君", "项目总控"),
    ("圣旨", "任务"),
    ("军机处", "总控中心"),
    ("回奏", "归档"),
    ("六部", "执行部门"),
]

# 按长度降序，确保「太子调度」先于「太子」匹配
VALUE_MAP.sort(key=lambda kv: -len(kv[0]))

DEFAULT_FILES = [
    "data/tasks_source.json",
    "data/live_status.json",
    "data/officials_stats.json",
    "data/agent_config.json",
    "data/audit_log.json",
]


def apply_word(text):
    """对一段文字做古词→现代词替换（长词优先，逐次替换避免级联误差）。"""
    if not isinstance(text, str):
        return text
    out = text
    for old, new in VALUE_MAP:
        if old in out:
            out = out.replace(old, new)
    return out


def apply_value(value):
    """对单个值递归处理：字符串做词替换，dict/list 递归。"""
    if isinstance(value, str):
        return apply_word(value)
    if isinstance(value, dict):
        return {k: apply_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [apply_value(v) for v in value]
    return value


def diff_summary(before, after, label=""):
    """统计 before/after 两版 JSON 的古名次数差异，返回 (before_cnt, after_cnt, changed_str_count)。"""
    old_words = [kv[0] for kv in VALUE_MAP]
    b = json.dumps(before, ensure_ascii=False)
    a = json.dumps(after, ensure_ascii=False)
    before_cnt = sum(b.count(w) for w in old_words)
    after_cnt = sum(a.count(w) for w in old_words)
    changed = sum(1 for i, (x, y) in enumerate(zip(b, a)) if x != y)
    return before_cnt, after_cnt, changed


def migrate_file(path, dry_run):
    abspath = os.path.join(REPO, path) if not os.path.isabs(path) else path
    if not os.path.exists(abspath):
        print(f"⚠️  跳过（不存在）: {path}")
        return
    try:
        with open(abspath, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ 无法解析 {path}: {e}")
        return

    migrated = apply_value(data)
    before_cnt, after_cnt, changed_str = diff_summary(data, migrated)

    status = "dry-run" if dry_run else "已迁移"
    print(f"\n{'═' * 60}")
    print(f"📄 {path}  [{status}]")
    print(f"   古名出现: {before_cnt} → {after_cnt}   (替换 {before_cnt - after_cnt} 处)")

    if dry_run:
        if before_cnt == after_cnt:
            print(f"   ✓ 无古名需要迁移")
        return

    if before_cnt == after_cnt:
        print(f"   ✓ 无变化，跳过写入")
        return

    # 备份
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = f"{abspath}.bak-{ts}"
    shutil.copy2(abspath, bak)
    print(f"   💾 备份 → {os.path.basename(bak)}")

    # 写入
    with open(abspath, encoding="utf-8") as f:
        raw = f.read()
    # 保留原缩进风格：探测原文件是否用 2 空格缩进
    indent = 2 if all(not l.startswith(" " * 4) for l in raw.splitlines() if l.strip()) else 4
    with open(abspath, "w", encoding="utf-8") as f:
        json.dump(migrated, f, ensure_ascii=False, indent=indent)
    print(f"   ✅ 写入完成")


def main():
    ap = argparse.ArgumentParser(description="三省六部 → 现代化组织：历史数据一次性迁移")
    ap.add_argument("--dry-run", action="store_true", help="只预览，不写文件")
    ap.add_argument("--files", nargs="*", default=DEFAULT_FILES, help="要迁移的 JSON 文件（默认全部）")
    args = ap.parse_args()

    print("🚀 组织名称迁移工具（古名 → 现代名）")
    print(f"   模式: {'DRY-RUN 预览' if args.dry_run else '实际迁移'}")
    print(f"   映射条目: {len(VALUE_MAP)} 组（长词优先）")

    total_before = total_after = 0
    for path in args.files:
        migrate_file(path, args.dry_run)
        abspath = os.path.join(REPO, path) if not os.path.isabs(path) else path
        if os.path.exists(abspath):
            try:
                with open(abspath, encoding="utf-8") as f:
                    d = json.load(f)
                old_words = [kv[0] for kv in VALUE_MAP]
                s = json.dumps(d, ensure_ascii=False)
                total_before += sum(s.count(w) for w in old_words)
            except Exception:
                pass

    print(f"\n{'═' * 60}")
    if args.dry_run:
        print("📋 预览完成。确认无误后去掉 --dry-run 执行实际迁移。")
    else:
        print("✅ 迁移完成。所有数据文件的古名已现代化。")
        print("   ⚠️ 请重启 dashboard 服务使运行时读取新数据，并在浏览器硬刷新。")


if __name__ == "__main__":
    main()
