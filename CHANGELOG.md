# Changelog

## v2.0.0 (2026-07-30)

### Added

- **`install.sh` v2 全面重写**（1806 行）
  - 全新安装模式（`./install.sh` 或 `./install.sh install`）
  - 升级模式（`./install.sh --mode update` 或 `./install.sh update`）
  - 版本标记协议：文件头部 `<!-- version:MAJOR.MINOR.PATCH-layer -->` 标记
  - 版本比对引擎 `version_compare()`：MAJOR 覆盖 / MINOR 增量追加 / 版本相同跳过
  - 增量追加算法 `append_incremental()`：逐段比对、大文件预检、编码检测
  - 自动备份机制：覆盖/追加前创建 `*.bak.YYYYMMDD-HHMMSS` 备份文件

- **`uninstall.sh` v2 新增**（395 行）
  - 四模式卸载体系：
    - `--mode clean` — 清理子 Agent workspace（保留 main）
    - `--mode clean-all` — 清理所有 Agent workspace（含 main）
    - `--mode clean-update` — 清理 deprecated 标记段落
    - `--mode uninstall` — 完全卸载（删除 Agent 注册 + 配置文件 + workspace）
  - 卸载前自动备份 `openclaw.json` 到 `*.bak.pre-uninstall-*`

- **Bootstrap 三层文件体系**
  - `bootstrap_layer1()` — main Agent 核心文件（GOVERNANCE.md、AGENTS.md、SOUL.md 等）
  - `bootstrap_layer2()` — 子 Agent 公共文件（AGENTS.md、GOVERNANCE.md）
  - `bootstrap_layer3()` — 子 Agent 专属文件（SOUL.md、GOVERNANCE.md 模板）
  - 每层支持 install/update 双模式，update 模式自动版本比对

- **OCR 集成**
  - `Phase 4: OCR 集成` 安装阶段
  - 自动安装/升级 OCR CLI（`npm install -g @alibaba-group/open-code-review`）
  - 最低版本要求 1.8.0
  - 安装后自动验证 `ocr --version`
  - 规则文件 `.github/ocr-rules.md` 版本化管理
  - GitHub Actions CI 工作流集成

- **升级模式差异报告**
  - update 模式完整输出：哪些文件跳过、覆盖、增量追加、创建
  - 清晰的状态标识（跳过/覆盖/增量追加/创建）

### Changed

- 安装脚本从 v1 单模式重构为 v2 双模式（install/update）
- 文件处理函数 `handle_bootstrap_file()` 统一为三层模式
- 所有受管文件增加版本标记头部注释
- 升级模式不再全量覆盖，改为智能增量写入
- Agent 注册流程改为幂等（已注册则跳过，不重复注册）

### Removed

- 废止 v1 的全局覆盖升级策略，替换为版本标记协议
- 移除旧版 `install.sh` 中的硬编码版本号，统一使用 `extract_version()` 函数

### Fixed

- 升级操作不再覆盖用户自定义配置（通过版本比对 + 增量追加实现）
- 非 UTF-8 编码文件跳过增量追加，避免乱码写入
- 大文件（>5MB）跳过增量追加，提示手动处理
- 卸载时自动备份配置文件，支持回滚