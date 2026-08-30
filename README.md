# Feishu Table Patch

> [!IMPORTANT]
> **本项目已归档（2026-08-30）**：Hermes 官方更新已包含原生表格渲染支持，本项目的使命完成，不再维护。
> 感谢 [@iqjiy](https://github.com/iqjiy) 的两个贡献（bug 修复 + 原生 table 组件，见 [PR #1](https://github.com/jinlio/feishu-table-patch/pull/1) / [PR #2](https://github.com/jinlio/feishu-table-patch/pull/2)），最终版本 v11.0.0 已合并。
> 仍在使用旧版 Hermes 的用户可继续 fork 使用。

> 让 Hermes Agent 的飞书适配器正确渲染 Markdown 表格。

Hermes 的飞书适配器检测到 Markdown 表格时，会强制用纯文本 `msg_type: text` 发送，导致表格在飞书中无法正确渲染。本工具通过 patch 适配器，让检测到表格时改用 `msg_type: post` + `tag: md` 发送富文本消息，表格完美渲染。

**核心优势：** 一行命令安装 patch，自动生效，无需 LLM 参与，零 token 消耗。

## 功能特性

| 模式 | 说明 | 触发方式 |
|------|------|----------|
| **Card（推荐）** | `msg_type: interactive` + 原生 `tag: table` 组件，**自适应列宽** | 自动（patch） |
| **Post（旧版）** | `msg_type: post` + `tag: md`，支持所有 GFM 语法 | 自动（降级） |
| **Card（旧版）** | Schema 2.0 卡片 + `tag: markdown` | `--card` |
| **Text（兜底）** | 转为纯文本列表 | `--text` |

### 自适应列宽

Patch 自动检测 Markdown 表格，解析后转为飞书原生 table 组件，并按内容长度自动计算列宽：

- 中文字符权重 ×2，英文/数字权重 ×1
- 列宽范围约束 12%–75%
- 自动修正总和为 100%
- 表格单元格中的 Markdown 格式符（`**粗体**`、`*斜体*` 等）自动清洗为纯文本
- 文字部分保留 `tag: markdown`，支持全部 GFM 语法（粗体、斜体、代码块、列表等）

## 安装

```bash
git clone git@github.com:jinlio/feishu-table-patch.git
cd feishu-table-patch

# 安装依赖
pip install requests

# 安装 patch（自动修改 Hermes 飞书适配器）
bash install.sh

# 检查 patch 状态
bash install.sh --check

# 卸载 patch（还原 Hermes 原始代码）
bash install.sh --uninstall
```

> **注意：** `install.sh` 会自动 patch Hermes Agent 的飞书适配器。此 patch 是幂等的（重复运行不会重复注入），且可逆（`--uninstall` 还原）。Hermes 升级后需重新运行 `install.sh`。

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
  "header_template": "blue"
}
```

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `card_title` | `null` | 卡片标题栏文字（仅 --card 模式）。`null` 表示不显示 |
| `header_template` | `"blue"` | 标题栏颜色（仅 --card 模式） |

## 快速使用

### 命令行（独立使用）

```bash
cd feishu-table-patch/scripts

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
    send_markdown_as_post,      # 发送 markdown 为 post 消息（主模式）
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

1. 在 `FeishuAdapter` 类中注入 `_build_table_card()` 方法
2. 在 `_build_outbound_payload` 方法开头插入表格检测逻辑
3. 检测到表格时：
   - 拆分文字段落和表格段落
   - 文字 → `tag: markdown`（保留全部 GFM 语法）
   - 表格 → 解析 → 计算自适应列宽 → 原生 `tag: table` 组件
   - 组装为 `msg_type: interactive` card 发送
4. 未检测到表格时，走原始逻辑不变

**整个过程不经过 LLM**，直接在适配器层完成转换，零 token 消耗。

## 已知问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| ~~飞书卡片 `tag: table` 空白~~ | ~~飞书客户端 Bug~~ | **已修复**（v11.0.0），原生 table 组件正常渲染 |
| `tag: lark_md` 报错 | 错误的 tag 名称 | 使用 `tag: md` |

## 项目结构

```
feishu-table-patch/
├── README.md                       # 本文件
├── install.sh                      # Patch 安装脚本（注入 _build_table_card）
├── scripts/
│   ├── config.json                # 消息配置（标题栏）
│   ├── feishu_table_card.py        # 核心脚本（独立 CLI 使用）
│   └── verify_table_component.py  # 原生 table 组件验证脚本
└── references/
    ├── feishu-table-rendering-issue.md
    ├── feishu-card-table-api.md
    └── openclaw-post-md-approach.md
```

## 关于

由 **[jinlio](https://github.com/jinlio)** 开发维护。

版本历史：
- **v11.0.0** — 主模式改为 interactive card + 原生 table 组件，自适应列宽，文字保留 GFM
- **v10.0.0** — 主模式改为 post+tag:md；直接 patch _build_outbound_payload（跳过 LLM）
- **v9.2.0** — 新增 outgoing:feishu hook + install.sh patch 脚本
- **v9.1.0** — 卡片标题栏可选；新增 config.json
- **v9.0.0** — 添加 header 字段；移除泄露凭证
