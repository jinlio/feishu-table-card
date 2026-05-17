---
name: feishu-table-card
version: 10.0.0
description: >
  Convert Markdown (tables + rich text) to Feishu post messages.
  **Primary: msg_type: post + tag: md** — renders as rich text with full GFM support.
  Fallback: Schema 2.0 interactive card + tag: markdown, then plain text bullet list.
  Auto-triggered by patching Hermes FeishuAdapter (no LLM needed).
tags: [feishu, lark, table, markdown, post, card, productivity, chinese]
env:
  FEISHU_APP_ID: "Feishu app ID (from open.feishu.cn)"
  FEISHU_APP_SECRET: "Feishu app secret"
---

# Feishu Table Card Skill

Converts Markdown (tables + rich text) to Feishu post messages.

## How It Works

Hermes's `FeishuAdapter._build_outbound_payload` detects markdown tables
and forces plain text, which breaks table rendering. This skill patches
that method to send tables as `msg_type: post` + `tag: md` instead,
with full GFM markdown support.

**No LLM invocation required** — the patch runs at the adapter level,
intercepting outbound messages before they are sent.

## Primary: Post Message + `tag: md`

```json
{
  "msg_type": "post",
  "content": {
    "zh_cn": {
      "title": "",
      "content": [
        [{"tag": "md", "text": "| Col1 | Col2 |\n|---|---|\n| A | B |"}]
      ]
    }
  }
}
```

## Installation

```bash
cd ~/.hermes/skills/productivity/feishu-table-card
bash install.sh          # Install patch
bash install.sh --check  # Verify patch status
bash install.sh --uninstall  # Remove patch (restores original)
```

The patch is idempotent and reversible. After patching, restart Hermes.

## Configuration

Edit `scripts/config.json`:

```json
{
  "card_title": null,
  "header_template": "blue"
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `card_title` | `null` | Card header title (legacy --card mode). `null` = no header. |
| `header_template` | `"blue"` | Header color template (legacy --card mode). |

## CLI Usage (Standalone)

```bash
cd ~/.hermes/skills/productivity/feishu-table-card/scripts

# Post + tag:md (default)
python3 feishu_table_card.py "oc_xxxx" "| Model | Price |
| RTX 5090 | ¥16,999 |"

# Legacy: interactive card
python3 feishu_table_card.py --card "oc_xxxx" "| Model | Price | ..."

# Text fallback
python3 feishu_table_card.py --text "oc_xxxx" "| Model | Price | ..."
```

## Python API

```python
from feishu_table_card import (
    build_feishu_post,          # build post+tag:md payload
    send_markdown_as_post,     # send markdown as post (primary)
    build_feishu_card,          # build schema 2.0 card (legacy)
    send_markdown_as_card,      # send markdown as card (legacy)
    send_with_fallback,         # post -> card -> text
)
```

## Version History

| Version | Changes |
|---------|---------|
| v10.0.0 | Primary mode: post+tag:md. Patch _build_outbound_payload directly (no hook/LLM). |
| v9.2.0 | Added outgoing:feishu hook + install.sh patch. |
| v9.1.0 | Card header optional. config.json. Env var overrides. |
| v9.0.0 | Added header field. Lazy _session. Removed leaked credentials. |