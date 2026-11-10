# codex-chat-cleanup

Codex 桌面端的聊天遗留文件清理技能。扫描本机聊天与目录归属，将**有明确会话归属、且已无现有或归档会话引用**的独立目录移入 macOS 废纸篓。

删除侧边栏聊天后，本地生成的文件可能仍然存在。本技能按需检查这些目录，保留仍被使用的内容。它不在后台监听，也不负责删除聊天记录。

## 适用环境

| 项目 | 要求 |
|---|---|
| 客户端 | Codex 桌面端，能取得本机完整的现有聊天、归档聊天和项目清单 |
| 系统 | macOS 支持扫描及移入废纸篓；其他系统仅扫描 |
| Python | Python 3.9 或更新版本；执行脚本仅使用标准库 |
| 数据位置 | 默认 `~/.codex`，设置 `CODEX_HOME` 时读取该目录 |
| 权限 | 可读取本机 Codex 状态及待检查目录；清理时可更新归属索引并访问 `~/.Trash` |

本实现于 **2026-11-10** 在 macOS、Python 3.9 与 `state_5.sqlite` 本地数据结构下验证。它依赖 Codex 内部字段；格式变化或会话清单不完整时会停止清理。仅有终端执行能力、缺少桌面端清单工具时，不能完成自动清理。

## 安装

按 [Codex 官方文档](https://learn.chatgpt.com/docs/build-skills)，新安装可放在用户级 `~/.agents/skills/`：

```bash
git clone https://github.com/TheShyWR/skills.git
mkdir -p ~/.agents/skills
cp -R skills/codex-chat-cleanup ~/.agents/skills/
```

本技能也已在 `${CODEX_HOME:-$HOME/.codex}/skills/` 的既有安装中验证。按客户端能发现的位置选择一处安装，避免两处同时出现同名技能。安装位置与脚本读取的 Codex 数据目录是两回事；后者仍由 `CODEX_HOME` 决定。

安装整个技能目录，保留 `SKILL.md`、`agents/` 和 `scripts/` 的相对位置。已有同名目录时，先检查再更新，避免覆盖自己的修改。

安装后在新对话中使用 `$codex-chat-cleanup`。如果客户端没有发现新技能，重启客户端后再试。

## 使用

### 只扫描

```text
$codex-chat-cleanup 只扫描聊天遗留文件，先不要清理
```

Codex 会列出待清理目录、占用字节数、文件列表，以及其他目录被保留的原因。扫描会更新一份仅含目录与会话 ID 的归属索引，供后续识别使用；不会移动目录。

### 扫描并清理

```text
$codex-chat-cleanup 扫描并清理聊天遗留文件
```

调用即授权把符合条件的目录移入废纸篓。清理前会展示范围，并重新检查目录指纹与数据库引用；文件发生变化或出现新引用时停止处理。

**不会永久删除文件或清空废纸篓。** 移入废纸篓也不等于立即释放磁盘空间。

## 处理范围

只考虑以下两类目录，并要求有明确的 projectless 聊天归属：

```text
~/Documents/Codex/YYYY-MM-DD/<聊天工作目录>/
$CODEX_HOME/visualizations/YYYY/MM/DD/<会话ID>/
```

符合条件的目录会整体移动，包括其 `work/` 和 `outputs/`。**如果其中有需要保留的交付文件，请使用“只扫描”，先将文件保存到其他位置。**

以下情况会保留：

- 本机数据库或完整会话清单中仍有现有、归档或子会话引用。
- 当前工作目录、其他会话共用的目录，以及项目根目录或其关联路径。
- 含 `.git` 的目录、符号链接，以及归属无法确认的目录。
- Codex 管理的 worktree 和上述处理范围之外的任何路径。

其他应用的配置、API 密钥、Codex 认证文件、聊天数据库、会话日志与记忆文件均不处理。

## 如何判断

技能交叉检查三类信息：

1. 桌面端的本机完整聊天清单，包含所有分页及归档聊天，同时读取项目目录。
2. 以只读方式查询本地 `state_*.sqlite` 中的 `threads` 和 `project_roots`。
3. `.codex-global-state.json` 中的 `thread-projectless-output-directories`，以及历次扫描保存的目录归属索引。

“侧边栏没看到”“目录日期很旧”或“某个查询找不到聊天”都不能单独作为清理依据。即使某条会话不出现在界面中，只要数据库还引用其目录，就保留。

目前没有使用可靠的删除墓碑，因此报告中的“已无引用”**不代表能确认具体删除时间**。首次扫描前如果归属映射已消失，只能列出归属不明的目录，不能自动判断其属于哪条已删除聊天。归属索引也只记录已扫描到的映射，不保证找回全部历史遗留文件。

## 报告与恢复

| 文件 | 内容 |
|---|---|
| 当前聊天目录的 `work/chat-cleanup-inventory.json` | 本次取得的完整会话与项目清单 |
| 当前聊天目录的 `work/chat-cleanup-report.json` | 扫描结果、文件元数据、保留原因及候选目录 |
| `$CODEX_HOME/chat-cleanup/ownership.json` | 目录与会话 ID 的历史对应关系 |
| `$CODEX_HOME/chat-cleanup/last-cleanup.json` | 最近一次成功移动的原路径、废纸篓路径及字节数 |

清理结果会给出废纸篓中的具体路径。需要恢复时，让 Codex 根据最近一次清理记录将目录移回原位置；**原位置已存在文件时停止，避免覆盖**。清空废纸篓后，本技能无法保证恢复。

脚本不读取待清理文件的正文，也不调用网络。Codex 本身会查询会话清单，路径、文件名和扫描结果可能显示在对话中；这不是完全离线的隐私处理方案。

## 验证

在仓库根目录运行：

```bash
python3 -m unittest discover -s codex-chat-cleanup/tests -v
```

测试使用临时的假 HOME、数据库与废纸篓，不处理真实用户目录。覆盖孤立目录移动、现有和归档会话保护、共享目录与项目保护、符号链接、归属缺失、清单不足，以及扫描后发生文件变化或新增引用的情况。

## 目录结构

```text
codex-chat-cleanup/
├── SKILL.md
├── README.md
├── agents/openai.yaml
├── scripts/cleanup.py
└── tests/test_cleanup.py
```

## 许可

[MIT](../LICENSE)
