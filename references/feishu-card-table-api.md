# Feishu Card Table API — Debugging Notes

This file captures the trial-and-error discovery of the correct Feishu card `tag: table` format. Useful when debugging table rendering failures.

## What Failed

| Attempt | Error | Root Cause |
|---------|-------|-----------|
| `{"tag": "column", "title": "Name"}` | `table column name is empty` (idx:1) | Wrong field name |
| `{"tag": "column", "name": "Name"}` (string) | `table column name is empty` (idx:1) | `name` must be object, not string |
| `{"tag": "column", "name": {"tag": "plain_text", "content": "Name"}, "width": 100}` | `mismatched type with value` at index 266 | `width` is not a valid column field |
| `data: [[...], [...]]` | `table rows is empty` | Wrong field name (should be `rows`) |
| `rows: [...]` with `title` object in columns | `table rows is invalid` (idx:1) | Column field was still wrong |
| `columns: ["Name", "Value"]` (array of strings) | `mismatched type with value` | Columns structure was completely wrong |

## What Worked

### Correct format
```python
{
  "tag": "table",
  "columns": [
    {"tag": "column", "name": {"tag": "plain_text", "content": "列名"}},
    {"tag": "column", "name": {"tag": "plain_text", "content": "列名"}}
  ],
  "rows": [
    ["值1", "值2", "值3"],
    ["值4", "值5", "值6"]
  ]
}
```

**Key rules:**
- `columns[].name` must be `{"tag": "plain_text", "content": "HeaderName"}` — an object, NOT a plain string
- Row data field is `rows` (not `data`, not `cells`)
- `rows` is a flat list of lists of strings: `[[str, str, ...], [str, str, ...]]`
- No `width` field on columns (not supported by this app's card version)
- No `title` field on columns (use `name` instead)

## Quick Diagnostic Pattern

When a card send fails with a Feishu card parse error, try the minimal test:
```python
test_card = {
    "schema": "2.0",
    "config": {"width_mode": "fill"},
    "header": {"title": {"tag": "plain_text", "content": "Test"}, "template": "blue"},
    "body": {
        "elements": [{"tag": "table", "columns": [
            {"tag": "column", "name": {"tag": "plain_text", "content": "A"}}
        ], "rows": [["b"]]}]
    }
}
```
If this fails, the issue is the column/row structure. If it succeeds, the issue is in your data.

## Markdown vs Table Tag

| Approach | Tag | Renders as |
|----------|-----|-----------|
| Markdown in card | `{"tag": "markdown", "content": "\| A \| B \|..."}` | GFM table (limited support) |
| Native table element | `{"tag": "table", "columns": [...], "rows": [...]}` | Real Feishu table grid |

The native `tag: table` is preferred for proper grid rendering. Use markdown only as fallback.