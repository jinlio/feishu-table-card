# OpenClaw `post` + `tag: md` Approach

## Source

OpenClaw's Feishu integration uses `msg_type: post` with `tag: md` to send markdown tables.
Source: `.openclaw/npm/node_modules/@openclaw/feishu/dist/send-DowxxbpH.js` lines ~1034.

## Key Implementation

```javascript
// buildFeishuPostMessagePayload — sends markdown as Feishu post message
function buildFeishuPostMessagePayload(params) {
    const { messageText } = params;
    return {
        content: JSON.stringify({ zh_cn: { content: [[{
            tag: "md",
            text: messageText
        }]] } }),
        msgType: "post"
    };
}
```

## Payload Structure

```json
{
  "msg_type": "post",
  "content": {
    "zh_cn": {
      "title": "Optional Title",
      "content": [
        [{"tag": "md", "text": "| Col1 | Col2 |\n|---|---|---|\n| A | B |"}],
        [{"tag": "md", "text": "Some **bold** text"}]
      ]
    }
  }
}
```

- `content` is an array of blocks (each block = array of tags)
- Each tag can be `md` (raw markdown), `text` (plain text with styling), `at`, etc.
- `tag: md` supports GFM — tables, bold, code blocks, headers, links

## Why Not `interactive` Card?

Feishu `interactive` cards have limited element support:
- `tag: table` is broken (blank body on API success)
- `tag: markdown` in cards renders as plain text, not proper markdown
- Cards are better for buttons/forms; post messages are better for rich text

## `tag: lark_md` vs `tag: md`

- `tag: lark_md` → returns `wrong tag:{lark_md}` error in post messages
- `tag: md` → correct, renders GFM markdown natively

## Tested Verification

Manual test to `<your chat_id>`:
```python
payload = {
    "msg_type": "post",
    "content": {
        "zh_cn": {
            "title": "M5 TOPS 估算",
            "content": [[{"tag": "md", "text": "| Component | Value | Note |\n|---|---|---|\n| NPU | 50 TOPS | ..."}]]
        }
    }
}
# Result: {'code': 0, 'msg': 'success'}
```

## Supported Markdown Features (GFM)

- Tables: `| Col1 | Col2 |`, `|---|---|`
- Headers: `# H1`, `## H2`, etc.
- Bold: `**text**`
- Italics: `*text*`
- Inline code: `` `code` ``
- Code blocks: ```` ```python ... ``` ````
- Links: `[text](url)`
- Lists: `- item`, `1. item`

## OpenClaw Repo Access Issues

- GitHub path `https://github.com/nickarora01/openclaw/blob/main/plugins/feishu/send.ts` returned 404
- The npm package has compiled JS, not TypeScript source
- Local path `.openclaw/npm/node_modules/@openclaw/feishu/dist/send-DowxxbpH.js` worked for reading source