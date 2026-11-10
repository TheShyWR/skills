# AI Agent Skills

个人维护的 AI 助手技能集合，收录思考协议、会话续接、本地文件处理和工具维护等工作流。目前包含面向 **WorkBuddy** 和 **Codex** 的技能，每个技能独立安装、互不依赖。

不同技能依赖的工具、目录和记忆机制不同，适用平台与安装方法以各自 README 为准。

## 技能目录

| Skill | 作用 | 适用平台 |
|---|---|---|
| [codex-chat-cleanup](codex-chat-cleanup/) | 扫描已无引用的 Codex 聊天专属目录，将符合条件的遗留目录移入废纸篓 | Codex 桌面端 · macOS |
| [steel-man](steel-man/) | 决策挑战：双向钢人论证，找出关键分歧，再给明确判断与行动 | WorkBuddy |
| [deep-thinking](deep-thinking/) | 开放探索：拆解隐含假设、缺失信息和常见错误，先把问题想清楚 | WorkBuddy |
| [session-recall](session-recall/) | 跨会话记忆与续接：区分项目和普通会话，按作用域保存、读取进度 | WorkBuddy |
| [local-file-privacy](local-file-privacy/) | 本地文件隐私处理：通过本地脚本处理敏感文件，正文不进入对话，结果另存 | WorkBuddy；本地脚本可独立使用 |

> 原有 WorkBuddy 技能保留其平台说明。其中的思考协议可作为适配其他助手的起点；安装方式、工具调用和记忆规则需要按目标平台调整，尚未逐个平台验证。

## 安装

先克隆仓库，再将需要的**单个技能子目录**复制到对应平台的 skills 目录。

```bash
git clone https://github.com/TheShyWR/skills.git
```

### Codex

以 `codex-chat-cleanup` 为例，按 [Codex 官方文档](https://learn.chatgpt.com/docs/build-skills)安装到用户级技能目录：

```bash
mkdir -p ~/.agents/skills
cp -R skills/codex-chat-cleanup ~/.agents/skills/
```

如果已安装同名技能，请先检查现有内容，再更新对应目录。安装后在新对话中输入：

```text
$codex-chat-cleanup 只扫描聊天遗留文件，先不要清理
```

完整要求与清理方式见 [codex-chat-cleanup 使用说明](codex-chat-cleanup/README.md)。

### WorkBuddy

以 `steel-man` 为例：

```bash
mkdir -p ~/.workbuddy/skills
cp -R skills/steel-man ~/.workbuddy/skills/
```

安装其他 WorkBuddy 技能时，将 `steel-man` 替换为目录中的对应名称。项目级安装与额外依赖见各技能 README。

## 仓库约定

- `SKILL.md`：供 AI 助手读取的触发条件、执行步骤与边界。
- `README.md`：供使用者阅读的功能、安装方法、示例与限制。
- `scripts/`、`agents/`、`tests/`：按需要提供执行脚本、界面元数据与验证用例。
- 涉及本地文件修改的技能应说明处理范围、保留条件和恢复方式；具体行为以技能文档为准。

## 许可

[MIT](LICENSE)
