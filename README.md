# Feishu Table Card — Hermes Skill

> 一个 [Hermes](https://github.com/anomalyco/hermes) 技能插件，把 Markdown 表格渲染为飞书富文本消息。

**核心用法：** 一行命令安装 patch，Hermes 发送含表格的消息时自动转为飞书富文本，无需 LLM 参与！

## 问题背景

Hermes 的飞书适配器 `FeishuAdapter._build_outbound_payload` 检测到 Markdown 表格时，会强制用纯文本 `msg_type: text` 发送，导致表格在飞书中无法正确渲染。

本技能通过 patch 该方法，让检测到表格时改用 `msg_type: post` + `tag: md` 发送富文本消息，表格完美渲染，并在页脚显示 Agent/模型信息。

## 功能特性

| 模式 | 说明 | 触发方式 |
|------|------|----------|
| **Post（推荐）** | `msg_type: post` + `tag: md`，支持所有 GFM 语法，页脚显示 Agent/模型信息 | 自动（patch） |
| **Card（旧版）** | Schema 2.0 卡片 + `tag: markdown` | `--card` |
| **Text（兜底）** | 转为纯文本列表 | `--text` |

## 安装

```bash
# 克隆到 skills 目录
cp -r feishu-table-card ~/.hermes/skills/productivity/

# 安装依赖
pip install requests

# 安装 patch（自动修改 Hermes 飞书适配器，检测表格时用 post+tag:md 发送）
cd ~/.hermes/skills/productivity/feishu-table-card
bash install.sh

# 检查 patch 状态
bash install.sh --check

# 卸载 patch（还原 Hermes 原始代码）
bash install.sh --uninstall
```

> **注意：** `install.sh` 会自动 patch Hermes Agent 的飞书适配器 `FeishuAdapter._build_outbound_payload` 方法。此 patch 是幂等的（重复运行不会重复注入），且可逆（`--uninstall` 还原）。Hermes 升级后需重新运行 `install.sh`。

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
| `footer_agent` | `"Hermes Agent"` | 页脚显示的 Agent 名称。`null` 表示不显示 |
| `footer_model` | `null` | 页脚显示的模型名称。`null` 表示不显示 |

环境变量覆盖：`FEISHU_CARD_FOOTER_AGENT`、`FEISHU_CARD_FOOTER_MODEL`、`HERMES_AGENT_NAME`、`HERMES_MODEL_NAME`。

## 快速使用

### 命令行（独立使用）

```bash
cd ~/.hermes/skills/productivity/feishu-table-card/scripts

# Post 模式（默认）
python3 feishu_table_card.py "oc_xxxx" "| Model | Price |
| RTX 5090 | ¥16,999 |
| RTX 4090 | ¥12,499 |"

# 旧版 Card 模式
python3 feishu_table_card.py --card "oc_xxxx" "| Model | Price | ..."

# Text 兜底模式
python3 feishu_table_card.py --text "oc_xxxx" "| Model | Price | ..."
```

### Python API

```python
from feishu_table_card import (
    build_feishu_post,          # 构建 post+tag:md payload
    send_markdown_as_post,     # 发送 markdown 为 post 消息（主模式）
    build_feishu_card,          # 构建 schema 2.0 卡片（旧版）
    send_markdown_as_card,      # 发送 markdown 为卡片（旧版）
    send_with_fallback,         # post -> card -> text 降级链
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

## 工作原理

`install.sh` patch Hermes 的 `FeishuAdapter._build_outbound_payload` 方法：

1. 在 `FeishuAdapter` 类中注入 `_MARKDOWN_TABLE_RE` 正则和 `_build_post_with_md()` 方法
2. 在 `_build_outbound_payload` 方法开头插入表格检测逻辑
3. 检测到表格时，调用 `_build_post_with_md()` 构建 `post + tag:md` payload 并返回
4. 未检测到表格时，走原始逻辑不变

**整个过程不经过 LLM**，直接在适配器层完成转换，零 token 消耗。

## 已知问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 飞书卡片 `tag: table` 空白 | 飞书客户端 Bug | 使用 `tag: md` 模式 |
| `tag: lark_md` 报错 | 错误的 tag 名称 | 使用 `tag: md` |

## 项目结构

```
feishu-table-card/
├── SKILL.md                        # Hermes Skill 定义（v10.0.0）
├── README.md                       # 本文件
├── install.sh                      # Patch 安装脚本（修改 _build_outbound_payload）
├── scripts/
│   ├── config.json                # 消息配置（页脚、标题栏）
│   └── feishu_table_card.py        # 核心脚本（独立 CLI 使用）
└── references/
    ├── feishu-table-rendering-issue.md
    ├── feishu-card-table-api.md
    └── openclaw-post-md-approach.md
```

## 关于

本技能由 **[jinlio](https://github.com/jinlio)** 开发维护。

版本历史：
- **v10.0.0** — 主模式改为 post+tag:md；直接 patch _build_outbound_payload（跳过 LLM）；页脚显示 Agent/模型信息；移除 hook 机制
- **v9.2.0** — 新增 outgoing:feishu hook + install.sh patch 脚本
- **v9.1.0** — 卡片标题栏可选；新增 config.json
- **v9.0.0** — 添加 header 字段；移除泄露凭证