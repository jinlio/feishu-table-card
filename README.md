# 🐑 Feishu Table Card

> 把 Markdown 表格（以及所有 Markdown 语法）渲染为飞书卡片的技能插件。

**核心用法：** 一行命令，把带表格的 Markdown 文本发送为飞书卡片，表格不再空白！

## 📌 功能特性

| 模式 | 说明 | 触发方式 |
|------|------|----------|
| **Card（推荐）** | Schema 2.0 卡片 + `tag: markdown`，支持所有 Markdown 语法（表格、加粗、斜体、代码块、列表等） | 默认 |
| **Text（文本）** | 转为纯文本列表，最后兜底方案 | `--text` |

## 🔧 安装

```bash
# 克隆或解压到 skills 目录
cp -r feishu-table-card ~/.hermes/skills/productivity/

# 安装依赖
pip install requests
```

## ⚙️ 配置

需要设置飞书应用凭证（从 [open.feishu.cn](https://open.feishu.cn) 创建应用获取）：

```bash
export FEISHU_APP_ID="cli_xxxxx"
export FEISHU_APP_SECRET="xxxxx"
```

或在调用时直接修改脚本顶部的默认值。

## 🚀 快速使用

### 命令行

```bash
cd ~/.hermes/skills/productivity/feishu-table-card/scripts

# Card 模式（默认，自动降级 card → text）
python3 feishu_table_card.py "oc_xxxx" "| Model | Price |
| RTX 5090 | ¥16,999 |
| RTX 4090 | ¥12,499 |"

# 指定卡片标题
python3 feishu_table_card.py --title "GPU 价格表" "oc_xxxx" "| Model | Price |
| RTX 5090 | ¥16,999 |
| RTX 4090 | ¥12,499 |"

# 仅 Card 模式（不自动降级）
python3 feishu_table_card.py --no-fallback "oc_xxxx" "| Model | Price |
| RTX 5090 | ¥16,999 |
| RTX 4090 | ¥12,499 |"

# Text 模式（兜底）
python3 feishu_table_card.py --text "oc_xxxx" "| Model | Price |
..."
```

### Python API

```python
from feishu_table_card import (
    build_feishu_card,          # 构建卡片 payload
    send_markdown_as_card,     # 发送任意 Markdown（文本+表格）为卡片
    send_table_as_text_fallback,
    send_table_with_fallback,  # 自动降级 card → text
)

# Card 模式：传入原始 Markdown 字符串
card = build_feishu_card("**标题**\n\n| Col1 | Col2 |\n|------|------|\n| A    | B    |", title="My Card")
result = send_markdown_as_card("oc_xxxx", "| Col1 | Col2 |\n|---|---|\n| A | B |", title="My Card")

# 自动降级：card 失败后自动尝试 text
result = send_table_with_fallback("oc_xxxx", "| Col1 | Col2 |\n|---|---|\n| A | B |", title="My Card")
```

## 📄 支持的 Markdown 语法

在 Card 模式下，`tag: markdown` 支持以下所有语法：

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
- [x] 表格 `| Col1 | Col2 |`

## 🐛 已知问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 飞书卡片 `tag: table` 空白 | 飞书客户端 Bug，API 返回成功但表格身为空 | 使用 `tag: markdown` 模式 |
| `tag: lark_md` 报错 | 错误的 tag 名称 | 使用 `tag: md` |
| `elements` 报 `unknown property` | 结构少了 `body` 层 | 使用 `body.elements` |

## 📁 项目结构

```
feishu-table-card/
├── SKILL.md                        # Hermes Skill 定义（v9.0.0）
├── README.md                       # 本文件
├── scripts/
│   └── feishu_table_card.py        # 核心脚本（含 tuple 返回值修复）
└── references/
    ├── feishu-table-rendering-issue.md  # 完整调试日志
    ├── feishu-card-table-api.md          # tag:table 格式文档
    └── openclaw-post-md-approach.md      # OpenClaw 实现参考
```

## 🐑 关于

本技能由 **小羊** 开发维护，基于 OpenClaw 的飞书卡片方案改进。

版本历史：
- **v9.0.0** — 添加 `header` 字段（修复无 header 卡片渲染失败）；`send_markdown_as_card` 支持 `title` 参数；`_session` 懒加载；移除泄露的测试凭证
- **v8.0.0** — 移除 Image 模式（matplotlib CJK 字体问题），Card 为唯一主模式，降级链 card → text
- **v7.0.0** — 添加 retry、统一 timeout、CJK width、MAX_ROWS 保护、修复关键 bug
- **v6.0.0** — 修复 `body.elements` 结构，Card 模式正常工作