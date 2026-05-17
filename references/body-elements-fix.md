# Body Elements Fix — Root Cause Analysis

**Date:** 2026-05-17
**Problem:** Feishu interactive card API returns error 200621: `unknown property, property: elements, path:`

## Root Cause

Schema 2.0 card structure must nest elements under `body`, not at top level.

## Wrong (top-level `elements`)

```json
{
  "schema": "2.0",
  "config": {"width_mode": "fill"},
  "elements": [{ "tag": "markdown", "content": "..." }]  // ❌ FAILS
}
```

**API Response:**
```json
{"code": 200621, "msg": "[parse card json err...] unknown property, property: elements, path: "}
```

## Correct (`body.elements`)

```json
{
  "schema": "2.0",
  "config": {"width_mode": "fill"},
  "body": {
    "elements": [{ "tag": "markdown", "content": "..." }]  // ✅ WORKS
  }
}
```

**API Response:** `{"code": 0, "msg": "success"}`

## Key Lesson

Feishu schema 2.0 card uses `body.elements`, not `elements` at root level.
The OpenClaw reference implementation uses the same structure:
```javascript
// from @openclaw/feishu/dist/send-DowxxbpH.js
const payload = {
  schema: "2.0",
  config: { width_mode: "fill" },
  body: { elements: [{ tag: "markdown", content }] }
}
```

## Files Affected

- `feishu_table_card.py`: `build_feishu_card()` — fixed to use `body.elements`
- **Tested 2026-05-17:** Card sends successfully, renders properly in Feishu client.