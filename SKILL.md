---
name: feishu-table-card
version: 9.1.0
description: >
  Convert Markdown (tables + rich text) to Feishu card messages.
  **Primary: schema 2.0 interactive card + `tag: markdown` in `body.elements`** — renders as a proper
  full-card. Supports ALL markdown syntax: tables, bold, italic, code blocks, blockquotes, lists.
  Fallback: plain text bullet list when card fails.
  Triggers: "send table", "render table", "feishu table", "表格发飞书", "发表格",
  "render markdown", "send markdown", "markdown table".
tags: [feishu, lark, table, markdown, card, productivity, chinese]
env:
  FEISHU_APP_ID: "Feishu app ID (from open.feishu.cn)"
  FEISHU_APP_SECRET: "Feishu app secret"
---

# Feishu Table Card Skill

Converts Markdown (tables + rich text) to Feishu card messages.

## ✅ Primary: Schema 2.0 Card + `tag: markdown` in `body.elements`

Uses a schema 2.0 interactive card with `tag: markdown` inside `body.elements`.
Renders as a **proper full-card** (not text-embedded). Supports ALL markdown syntax.

**Card structure (with header):**
```json
{
  "schema": "2.0",
  "config": {"width_mode": "fill"},
  "header": {
    "title": {"tag": "plain_text", "content": "Card Title"},
    "template": "blue"
  },
  "body": {
    "elements": [{
      "tag": "markdown",
      "content": "**Title**\n\n| Col1 | Col2 |\n|------|------|\n| A    | B    |"
    }]
  }
}
```

**Card structure (without header):**
```json
{
  "schema": "2.0",
  "config": {"width_mode": "fill"},
  "body": {
    "elements": [{
      "tag": "markdown",
      "content": "**Title**\n\n| Col1 | Col2 |\n|------|------|\n| A    | B    |"
    }]
  }
}
```

Header is optional. Set `card_title` in `scripts/config.json` or pass `--title` to enable it.

**Must use `body.elements`** — top-level `elements` (no `body`) fails with `unknown property elements`.

**Supported markdown syntax:** tables, bold (`**`), italics (`*`),
inline code (`` ` ``), code blocks (```` ``` ````), headers (`#`), lists, blockquotes (`>`), `---`.

## ⚠️ `tag: lark_md` Returns Error

Use `tag: md` instead.

## ⚠️ `tag: table` Has Client Bug

Feishu's interactive card `tag: table` has a confirmed client bug — API returns `code: 0`
but the table body is blank. Use `tag: markdown` instead.

## Usage

```bash
cd ~/.hermes/skills/productivity/feishu-table-card/scripts

# Primary: raw markdown (text + table) → schema 2.0 card (no header by default)
python3 feishu_table_card.py "oc_xxxx" "| Model | Price |
| RTX 5090 | ¥16,999 |
| RTX 4090 | ¥12,499 |"

# With custom title (shows header bar)
python3 feishu_table_card.py --title "GPU Price" "oc_xxxx" "| Model | Price | ..."

# Text fallback: plain bullet list (last resort)
python3 feishu_table_card.py --text "oc_xxxx" "| Model | Price |
..."
```

### Python API

```python
from feishu_table_card import (
    build_feishu_card,          # build schema 2.0 card
    send_markdown_as_card,      # send markdown as card (primary)
    send_table_as_text_fallback, # text bullet list (fallback)
    send_table_with_fallback,   # card -> text fallback chain
)

# Primary: pass raw markdown string (no header)
result = send_markdown_as_card("oc_xxxx", "| Col1 | Col2 |\n|---|---|\n| A | B |")

# With header
result = send_markdown_as_card("oc_xxxx", "| Col1 | Col2 |\n|---|---|\n| A | B |", title="My Card")

# Fallback chain: try card, then text
result = send_table_with_fallback("oc_xxxx", "| Col1 | Col2 |", title="My Card")
```

## Configuration

Edit `scripts/config.json` to customize defaults:

```json
{
  "card_title": null,
  "header_template": "blue"
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `card_title` | `null` | Default card header title. `null` = no header. |
| `header_template` | `"blue"` | Header color template (blue/green/red/orange/etc.) |

Environment variable overrides: `FEISHU_CARD_CARD_TITLE`, `FEISHU_CARD_HEADER_TEMPLATE`.

## Dependencies

```bash
pip install requests
```

## Version History

| Version | Changes |
|---------|---------|
| v9.1.0 | Card header is now optional (default: no header). Added `config.json` for customization. Env var overrides. |
| v9.0.0 | Added `header` field (fixes card rendering without header); `send_markdown_as_card` supports `title`; lazy `_session`; removed leaked credentials. |
| v8.0.0 | Removed Image mode (matplotlib CJK font issues). Card is now the only mode. Fallback chain: card → text. |
| v7.0.0 | OpenCode review: added retry, unified timeout, CJK width, MAX_ROWS protection, fixed critical bugs. |
| v6.0.0 | Fixed `body.elements` structure. Card mode works properly. |
- `body.elements` missing `body` wrapper → `unknown property elements` API error

## Implementation Details

- `DEFAULT_TIMEOUT = 15` — unified timeout (all HTTP calls)
- `MAX_ROWS = 200` — table row truncation protection
- `_build_session()` — `requests.Session` with `HTTPAdapter` + `Retry` (429/5xx exponential backoff, 3 retries)
- `_send_message()` — unified internal sender used by `send_card` and `send_text_message`
- `table_to_bullet_list` — `title_emoji` parameter (default 📊), can be set to any emoji or empty string
- `get_tenant_token()` — validates `FEISHU_APP_ID`/`FEISHU_APP_SECRET` before requesting token
- `parse_markdown_table()` — strips separator rows, truncates to `MAX_ROWS`, raises `ValueError` if table is malformed

## References

- `references/feishu-table-rendering-issue.md` — Full debugging log: API format attempts,
  error codes, root cause analysis for tag:table blank bug.
- `references/feishu-card-table-api.md` — Correct (but non-rendering) `tag: table` format.
- `references/openclaw-post-md-approach.md` — OpenClaw's `buildFeishuPostMessagePayload`
  implementation. Source: `.openclaw/npm/node_modules/@openclaw/feishu/dist/send-DowxxbpH.js` lines ~1034.
- `references/body-elements-fix.md` — Root cause: top-level `elements` without `body` wrapper
  causes API error 200621; fix is `body.elements` structure.