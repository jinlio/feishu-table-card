# Feishu Table Rendering — Final Working Solution

**Date resolved:** 2026-05-17
**Status:** CONFIRMED WORKING — tested with full rich text + table card

## ✅ Working Approach: Schema 2.0 Card + `tag: markdown` in `body.elements` WITH header

```python
card = {
    "schema": "2.0",
    "config": {"width_mode": "fill"},
    "header": {
        "title": {"tag": "plain_text", "content": "Card Title"},
        "template": "blue"
    },
    "body": {
        "elements": [{
            "tag": "markdown",
            "content": "**Title in markdown**\n\n| Col1 | Col2 |\n|------|------|\n| A    | B    |"
        }]
    }
}
```

**Key design decisions:**
- `header` with `template: blue` IS required — card renders correctly with it
- Without `header`: API returns `code: 0` but body shows "请升级至最新版本客户端" (card structure rejected)
- Single `tag: markdown` element in `body.elements` contains entire markdown (title + table + rich text)
- `width_mode: fill` makes card span full message width

**Critical structure (learned from debugging 2026-05-17):**
- ❌ `elements` at root level (no `body`) → `unknown property elements` error
- ❌ No `header` → renders but shows "请升级至最新版本客户端" (invalid card structure rejected)
- ✅ `body.elements` + `header` → works perfectly

---

## ❌ What Does NOT Work

| Attempt | Error | Root Cause |
|---------|-------|-----------|
| `tag: table` in card | `code=0` but body blank | Feishu client bug — table body never renders |
| `tag: column.title` | `column name is empty` | Must use `name` not `title` |
| `tag: column.name` as string | `column name is empty` | Must be `{"tag": "plain_text", "content": "..."}` object |
| `column.width` | `mismatched type` | Not a valid column field |
| `rows.data` | `table rows is empty` | Must use `rows`, not `data` |
| `tag: lark_md` | `wrong tag:{lark_md}` | Use `tag: md` instead |
| Top-level `elements` | `unknown property elements` | Must use `body.elements` |
| Card without `header` | "请升级至最新版本客户端" | `header` is required for valid card structure |
| `msg_type: post` + `tag: md` | text-embedded style | Not proper full-card rendering |

## Test Credentials

- App ID: `<your FEISHU_APP_ID>` (set via environment variable)
- Test chat_id: `<your chat_id>`
- Send: `POST https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id`