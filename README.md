# cc-sync · 双机 Claude 环境同步 + 局域网中继

两台电脑（台式机 ↔ 笔记本）之间同步 Claude Code 工作环境，并让两端的
Claude 实例能直接互发消息协作。纯 PowerShell + Python 标准库，无三方依赖。

## 组成

| 组件 | 说明 |
|------|------|
| `pack.bat` / `pack.ps1` | **一键打包**：`.claude` 核心配置 + 经验记忆库 + 工作区项目 → `cc-env-*.zip`；大项目（模型/数据集/媒体）按精简体积阈值自动跳过（默认 200MB），产物内含笔记本端 `install.ps1` |
| `serve.bat` | 局域网共享打包产物（:8899），另一台机器浏览器直接下载 zip |
| `chat_server.py` | **局域网聊天中继**（:8898）：`POST /send` 发消息、`GET /messages?since=N` 拉新消息、`POST /upload` 传文件；JSON 追加持久化，token 鉴权 |
| `send.py` | 向对端发消息：优先直推（对端接收器），失败自动回落中继 |
| `relay_unread.py` | UserPromptSubmit hook：每次对话自动把对端新消息注入上下文（任何异常静默退出，绝不打断对话流） |
| `install_hook.py` | 把 relay_unread 挂进 `~/.claude/settings.json`（自动备份原文件） |
| `send_briefing.py` | 历史一次性脚本：给对端 Claude 发交接 briefing（已脱敏，留作模板） |

## 配置（必读）

所有私密值（token / 对端地址 / 数据目录 / 打包路径）**不落在源码里**，
统一走 `ccs.local.json`（已 gitignore）或环境变量 `CCS_*`：

```bat
copy ccs.local.example.json ccs.local.json
```

```json
{
  "token": "换成一个长随机串",
  "relay_base": "http://127.0.0.1:8898",
  "push_url": "http://对端局域网IP:8900/send",
  "data_dir": "", "inbox_dir": "",
  "workspace": "E:\\1workspace", "memory": "E:\\1aimemory", "out_dir": "E:\\cc-sync"
}
```

`workspace` / `memory` / `out_dir` 供 pack.ps1 读取（也可用 `-Workspace`
等参数显式覆盖）；不配则用 `$HOME` 下的通用默认。

本机 `python` 命令异常时：在项目根放 `python-path.txt`（已 gitignore）
写解释器全路径，各 bat 会优先读它。

## 快速开始

```bat
rem 1. 台式机：起中继 + 共享目录
chat.bat        rem :8898 消息中继
serve.bat       rem :8899 zip 下载（CCS_SHARE_DIR 可改共享目录）

rem 2. 台式机：打包环境
pack.bat        rem 产物 cc-env-<时间戳>.zip

rem 3. 笔记本：浏览器下载 zip 解压，跑内含 install.ps1
powershell -ExecutionPolicy Bypass -File install.ps1 -WorkspaceRoot D:\workspace -MemoryRoot D:\aimemory

rem 4. 两端：挂未读消息 hook（可选）
python install_hook.py
```

## 安全说明

- 中继监听 `0.0.0.0`（局域网设计），**所有端点都要 token**；token 自己换长随机串，
  不要把中继暴露到公网
- 上传限 64MB、消息限 8000 字、文件名取 basename 防目录穿越
- `.claude` 配置里若含 API key 明文，打出的 zip 等同机密——只走局域网，勿外发

## 已知坑（笔记）

- 含中文的 ps1 必须存 UTF-8 **带 BOM**（且勿双 BOM），否则 PowerShell 5.1 解析报错
- robocopy 中文系统摘要是「字节 :」，英文是 "Bytes :"——量体积两种都要匹配
