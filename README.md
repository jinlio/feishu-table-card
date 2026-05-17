# Feishu Table Card — Hermes Skill

> 一个 [Hermes](https://github.com/anomalyco/hermes) 技能插件，把 Markdown 表格渲染为飞书富文本消息。

**核心用法：** 一行命令，把带表格的 Markdown 文本发送为飞书富文本，表格不再空白！

## 功能特性

| 模式 | 说明 | 触发方式 |
|------|------|----------|
| **Post（推荐）** | `msg_type: post` + `tag: md`，支持所有 GFM 语法，页脚显示 Agent/模型信息 | 默认 |
| **Card（旧版）** | Schema 2.0 卡片 + `tag: markdown` | `--card` |
| **Text（兜底）** | 转为纯文本列表，最后兜底方案 | `--text` |

## 安装

```bash
# 克隆到 skills 目录
cp -r feishu-table-card ~/.hermes/skills/productivity/

# 安装依赖
pip install requests

# 安装 hook patch（自动拦截含表格的飞书消息并转为富文本）
cd ~/.hermes/skills/productivity/feishu-table-card
bash install.sh

# 卸载 patch（还原 Hermes 原始代码）
bash install.sh --uninstall

# 检查 patch 状态
bash install.sh --check
```

> **注意：** `install.sh` 会自动 patch Hermes Agent 的飞书适配器，注入 `outgoing:feishu` hook 点。此 patch 是幂等的（重复运行不会重复注入），且可逆（`--uninstall` 还原）。Hermes 升级后需重新运行 `install.sh`。

## 配置

### 飞书应用凭证

从 [open.feishu.cn](https://open.feishu.cn) 创建应用获取：

```bash
export FEISHU_APP_ID="cli_xxxxx"
export FEISHU_APP_SECRET="xxxxx"
```

### 消息配置

编辑 `scripts/config.json` 自定义：

```json
{
  "card_title": null,
  "header_template": "blue",
  "footer_agent": "Hermes Agent",
  "footer_model": null
}
```

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `card_title` | `null` | 卡片标题栏文字（仅 --card 模式）。`null` 表示不显示标题栏 |
| `header_template` | `"blue"` | 标题栏颜色（仅 --card 模式） |
| `footer_agent` | `"Hermes Agent"` | 页脚显示的 Agent 名称。`null` 表示不显示 |
| `footer_model` | `null` | 页脚显示的模型名称。`null` 表示不显示 |

环境变量覆盖：`FEISHU_CARD_FOOTER_AGENT`、`FEISHU_CARD_FOOTER_MODEL`、`HERMES_AGENT_NAME`、`HERMES_MODEL_NAME`。

## 快速使用

### 命令行

```bash
cd ~/.hermes/skills/productivity/feishu-table-card/scripts

# Post 模式（默认，无标题，页脚显示 Agent/模型信息）
python3 feishu_table_card.py "oc_xxxx" "| Model | Price |
| RTX 5090 | ¥16,999 |
| RTX 4090 | ¥12,499 |"

# 旧版 Card 模式
python3 feishu_table_card.py --card "oc_xxxx" "| Model | Price | ..."

# Text 兜底模式
python3 feishu_table_card.py --text "oc_xxxx" "| Model | Price | ..."

# 不自动降级
python3 feishu_table_card.py --no-fallback "oc_xxxx" "| Model | Price | ..."
```

### Python API

```python
from feishu_table_card import (
    build_feishu_post,          # 构建 post+tag:md payload
    send_markdown_as_post,     # 发送 markdown 为 post 消息（主模式）
    build_feishu_card,          # 构建 schema 2.0 卡片（旧版）
    send_markdown_as_card,      # 发送 markdown 为卡片（旧版）
    send_with_fallback,         # post -> card -> text 降级链
    send_table_as_text_fallback,
)

# Post 模式（主模式）
result = send_markdown_as_post("oc_xxxx", "| Col1 | Col2 |\n|---|---|\n| A | B |")

# 降级链：post -> card -> text
result = send_with_fallback("oc_xxxx", "| Col1 | Col2 |")
```

## 支持的 Markdown 语法

Post 模式（`tag: md`）支持 GFM 全部语法：

- [x] **加粗** `**text**`
- [x] *斜体* `*text*`
- [x] ~~删除线~~ `~~text~~`
- [x] `行内代码` `` `code` ``
- [x] 代码块 ```` ```language ... ``` ````
- [x] `# 标题` / `## 二级标题`
- [x] `> 引用块`
- [x] 有序列表 `1. 2. 3.`
- [x] 无序列表 `- item`
- [x] 分隔线 `---`
- [x] 链接 `[text](url)`
- [x] 表格 `| Col1 | Col2 |`

## 自动触发机制

`install.sh` 会在 Hermes 的飞书适配器中注入 `outgoing:feishu` hook 点。Hook handler 自动检测出站消息中的 markdown 表格，直接通过 CLI 调用脚本转换为 post 消息，**无需 LLM 参与**，节省 token 和时间。

## 已知问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 飞书卡片 `tag: table` 空白 | 飞书客户端 Bug，API 返回成功但表格身为空 | 使用 `tag: md` 模式 |
| `tag: lark_md` 报错 | 错误的 tag 名称 | 使用 `tag: md` |
| `elements` 报 `unknown property` | 结构少了 `body` 层 | 使用 `body.elements` 结构 |

## 项目结构

```
feishu-table-card/
├── SKILL.md                        # Hermes Skill 定义（v10.0.0）
├── README.md                       # 本文件
├── install.sh                      # Hook patch 安装脚本（幂等、可逆）
├── scripts/
│   ├── config.json                # 消息配置（页脚、标题栏、颜色模板）
│   └── feishu_table_card.py        # 核心脚本
├── hooks/
│   └── feishu-table-card-hook/
│       ├── HOOK.yaml               # Hook 定义（outgoing:feishu 事件）
│       └── handler.py              # Hook handler（subprocess CLI 调用）
└── references/
    ├── feishu-table-rendering-issue.md  # 完整调试日志
    ├── feishu-card-table-api.md          # tag:table 格式文档
    └── openclaw-post-md-approach.md      # OpenClaw 实现参考
```

## 关于

本技能由 **[jinlio](https://github.com/jinlio)** 开发维护，基于 OpenClaw 的飞书卡片方案改进。

版本历史：
- **v10.0.0** — 主模式改为 post+tag:md；hook handler 改用 subprocess CLI 调用（跳过 LLM）；页脚显示 Agent/模型信息
- **v9.2.0** — 新增 `outgoing:feishu` hook + `install.sh` patch 脚本，自动拦截含表格的飞书消息并转为卡片
- **v9.1.0** — 卡片标题栏改为可选（默认不显示）；新增 `config.json` 配置文件；环境变量覆盖支持
- **v9.0.0** — 添加 `header` 字段；`send_markdown_as_card` 支持 `title` 参数；`_session` 懒加载；移除泄露的测试凭证
- **v8.0.0** — 移除 Image 模式（matplotlib CJK 字体问题），Card 为唯一主模式，降级链 card → text
- **v7.0.0** — 添加 retry、统一 timeout、CJK width、MAX_ROWS 保护、修复关键 bug
- **v6.0.0** — 修复 `body.elements` 结构，Card 模式正常工作