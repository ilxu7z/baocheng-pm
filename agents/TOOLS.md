<!-- version:v2.0.0-system -->
# TOOLS.md · 研发主管工具配置

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## 本机网络
- **内网 IP**: `192.168.3.180`（自动检测: `ipconfig getifaddr en0`）
- **看板服务器**: http://192.168.3.180:7891
- **OC-MACS 项目**: /Users/chee/Projects/oc-macs

## 常用路径
- **Workspace**: /Users/chee/.openclaw/workspace-daima
- **项目产出**: projects/oc-macs/
- **核心库**: lib/core.sh
- **Agent 配置**: /Users/chee/Projects/oc-macs/registry.json

## 常用命令
- `ipconfig getifaddr en0` → 获取本机 IP（macOS 有线网卡）
- `ipconfig getifaddr en1` → 获取本机 IP（macOS 无线网卡）
- `npm root -g` → npm 全局安装目录
- `file -I <file>` → 检测文件编码

## 相关
- [Agent workspace](/concepts/agent-workspace)
- [OC-MACS 项目](file:///Users/chee/Projects/oc-macs)