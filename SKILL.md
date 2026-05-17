---
name: feishu-table-card
version: 10.0.0
description: >
  Convert Markdown (tables + rich text) to Feishu post messages.
  **Primary: msg_type: post + tag: md** — renders as rich text with full GFM support.
  Fallback: Schema 2.0 interactive card + tag: markdown, then plain text bullet list.
  Auto-triggered by outgoing:feishu hook (no LLM needed).
tags: [feishu, lark, table, markdown, post, card, productivity, chinese]
env:
  FEISHU_APP_ID: "Feishu app ID (from open.feishu.cn)"
  FEISHU_APP_SECRET: "Feishu app secret"
---

# Feishu Table Card Skill

Converts Markdown (tables + rich text) to Feishu post messages.

## Primary: Post Message + `tag: md`

Uses `msg_type: post` with `tag: md` inside `zh_cn.content`.
Renders as **rich text** with full GFM markdown support (tables, bold, code blocks, etc.).
No title. Footer with agent/model info if configured.

**Post structure:**
```json
{
  "msg_type": "post",
  "content": {
    "zh_cn": {
      "title": "",
      "content": [
        [{"tag": "md", "text": "| Col1 | Col2 |\n|---|---|\n| A | B |"}],
        [{"tag": "md", "text": "---\n🤖 Hermes Agent | Model: gpt-4o"}]
      ]
    }
  }
}
```

**Supported markdown syntax (GFM):** tables, bold (`**`), italics (`*`),
inline code (`` ` ``), code blocks (```` ``` ````), headers (`#`), links (`[]()`),
lists (`- item`, `1. item`), blockquotes (`>`), `---`.

## Auto-Trigger via Hook (No LLM Required)

The `outgoing:feishu` hook automatically detects markdown tables in outbound
messages and converts them to post messages. The handler calls the script
via CLI subprocess — no LLM invocation, no token waste.

## Legacy: Schema 2.0 Card + `tag: markdown`

Still available via `--card` flag. Uses schema 2.0 interactive card with
`tag: markdown` inside `body.elements`. Header is optional.

## Usage

```bash
cd ~/.hermes/skills/productivity/feishu-table-card/scripts

# Primary: post + tag:md (default)
python3 feishu_table_card.py "oc_xxxx" "| Model | Price |
| RTX 5090 | ¥16,999 |
| RTX 4090 | ¥12,499 |"

# Legacy: interactive card
python3 feishu_table_card.py --card "oc_xxxx" "| Model | Price | ..."

# Text fallback: plain bullet list
python3 feishu_table_card.py --text "oc_xxxx" "| Model | Price | ..."

# No fallback (only try selected mode)
python3 feishu_table_card.py --no-fallback "oc_xxxx" "| Model | Price | ..."
```

### Python API

```python
from feishu_table_card import (
    build_feishu_post,          # build post+tag:md payload
    send_markdown_as_post,     # send markdown as post message (primary)
    build_feishu_card,          # build schema 2.0 card (legacy)
    send_markdown_as_card,      # send markdown as card (legacy)
    send_with_fallback,         # post -> card -> text fallback chain
    send_table_as_text_fallback,
)

# Primary: post + tag:md
result = send_markdown_as_post("oc_xxxx", "| Col1 | Col2 |\n|---|---|\n| A | B |")

# Fallback chain: post -> card -> text
result = send_with_fallback("oc_xxxx", "| Col1 | Col2 |")
```

## Configuration

Edit `scripts/config.json` to customize defaults:

```json
{
  "card_title": null,
  "header_template": "blue",
  "footer_agent": "Hermes Agent",
  "footer_model": null
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `card_title` | `null` | Card header title (legacy --card mode). `null` = no header. |
| `header_template` | `"blue"` | Header color template (legacy --card mode) |
| `footer_agent` | `"Hermes Agent"` | Agent name shown in footer. `null` = hide. |
| `footer_model` | `null` | Model name shown in footer. `null` = hide. |

Environment variable overrides:
- `FEISHU_CARD_CARD_TITLE`, `FEISHU_CARD_HEADER_TEMPLATE`
- `FEISHU_CARD_FOOTER_AGENT`, `FEISHU_CARD_FOOTER_MODEL`
- `HERMES_AGENT_NAME` (fallback for footer_agent)
- `HERMES_MODEL_NAME` (fallback for footer_model)

## Dependencies

```bash
pip install requests
```

## Version History

| Version | Changes |
|---------|---------|
| v10.0.0 | Primary mode changed to post+tag:md. Hook handler uses subprocess CLI (no LLM). Footer with agent/model info. |
| v9.2.0 | Added `outgoing:feishu` hook + `install.sh` patch script for auto-intercepting table messages. |
| v9.1.0 | Card header is now optional (default: no header). Added `config.json` for customization. Env var overrides. |
| v9.0.0 | Added `header` field; `send_markdown_as_card` supports `title`; lazy `_session`; removed leaked credentials. |

## Implementation Details

- `DEFAULT_TIMEOUT = 15` — unified timeout (all HTTP calls)
- `MAX_ROWS = 200` — table row truncation protection
- `_build_session()` — `requests.Session` with `HTTPAdapter` + `Retry` (429/5xx exponential backoff, 3 retries)
- `_send_message()` — unified internal sender used by `send_card` and `send_text_message`
- `build_feishu_post()` — builds post+tag:md payload with optional footer
- `send_markdown_as_post()` — primary send method, no title, footer with agent/model
- `send_with_fallback()` — fallback chain: post -> card -> text
- Handler uses `subprocess.run()` to call script CLI, no Python import coupling

## References

- `references/openclaw-post-md-approach.md` — OpenClaw's `buildFeishuPostMessagePayload`
  implementation with `tag: md`.
- `references/feishu-table-rendering-issue.md` — Full debugging log for tag:table blank bug.
- `references/feishu-card-table-api.md` — Correct (but non-rendering) `tag: table` format.
- `references/body-elements-fix.md` — Root cause: top-level `elements` without `body` wrapper.