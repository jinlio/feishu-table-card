# Feishu Table Patch — 开发记录

> 分支: `feat/table-component-verify`  
> 日期: 2026-05-30 ~ 2026-06-01  
> 作者: iqjiy

---

## 目标

将 Hermes Agent 飞书适配器的 Markdown 表格渲染从 `post + tag: md` 升级为 `interactive card + 原生 tag: table 组件`，实现**自适应列宽**，解决列少但单列内容长时列宽被平均挤压、可读性差的问题。

---

## 核心改动

### 文件: `install.sh`

**唯一修改的文件**（patch 注入逻辑）。改动内容：

| 项目 | 旧 (`v10.0.0`) | 新 (`v11.0.0`) |
|------|---------------|---------------|
| 注入方法 | `_build_post_with_md()` | `_build_table_card()` |
| 消息类型 | `msg_type: post` | `msg_type: interactive` |
| 表格渲染 | `tag: md`（飞书 Markdown 渲染器，列宽不可控） | `tag: table`（飞书原生表格组件 + 自适应列宽） |
| 文字渲染 | 整段 post + md | `tag: markdown`（GFM 全保留） |

**处理流程:**

```
_build_outbound_payload(content)
  ├── 检测到表格？
  │   ├── 是 → _build_table_card(content)
  │   │       1. 拆分文字段落和表格段落
  │   │       2. 文字 → {"tag": "markdown", "content": "..."}
  │   │       3. 表格 → parse → 自适应列宽 → {"tag": "table", ...}
  │   │       4. 组装 schema 2.0 interactive card
  │   │       5. return ("interactive", card_json)
  │   └── 否 → 走 Hermes 原始逻辑（不变）
```

### 新增文件: `scripts/verify_table_component.py`

飞书原生 table 组件验证脚本。用于测试:
- `tag: table` 是否能在当前飞书客户端正常渲染
- `width` 字段是否被 API 接受
- 与 `post + tag: md` 对照组对比

---

## 关键发现

### 1. 飞书 `tag: table` 组件格式

经过多轮 API 测试，确认正确的 JSON 格式：

```json
{
  "tag": "table",
  "columns": [
    {"name": "c0", "width": "30%"},
    {"name": "c1", "width": "70%"}
  ],
  "rows": [
    {"c0": "表头1", "c1": "表头2"},
    {"c0": "数据1", "c1": "数据2"}
  ]
}
```

**关键规则:**
- `columns[].name` 必须是**纯字符串**（不能是 `{"tag": "plain_text", "content": "..."}` 对象，旧文档格式已废弃）
- `rows` 是**对象数组**，key 必须与 `columns[].name` 匹配（不是 `[["val1", "val2"]]` 数组格式）
- `columns[].width` 支持百分比格式（`"35%"`），范围约 12%-75%

### 2. 表头显示问题（Plan B）

**问题:** `columns[].name` 仅用于数据绑定（row 对象的 key 映射），**不作为可视表头显示**。即使 API 接受中文列名，飞书客户端只渲染分隔线 `--`。

**解决方案（Plan B）:**
- 使用通用列名 `c0, c1, c2...` 做内部绑定
- 将 Markdown 表格的真实表头作为 `rows` 的第一行数据
- 列宽计算仍基于表头内容

### 3. 历史 Bug 已修复

| 旧记录 | 实际情况 |
|--------|---------|
| `tag: table` 客户端空白 | **已修复**，当前飞书客户端正常渲染 |
| `column.width` 不支持 | **已支持**，`"35%"` 格式生效 |

---

## 自适应列宽算法

```python
def _display_width(text):
    """中文字符权重 2，英文/数字权重 1"""
    w = 0
    for ch in text:
        if '一' <= ch <= '鿿' or '　' <= ch <= '〿' or '＀' <= ch <= '￯':
            w += 2  # CJK
        else:
            w += 1
    return max(w, 1)

def _calc_column_widths(headers, rows):
    """按内容最长行计算每列显示宽度，转换为百分比"""
    widths = []
    for i, h in enumerate(headers):
        w = _display_width(h)
        for row in rows:
            if i < len(row):
                w = max(w, _display_width(row[i]))
        widths.append(w)
    total = sum(widths)
    if total == 0:
        return [f"{100 // len(headers)}%" for _ in headers]
    pcts = [max(12, min(75, round(w / total * 100))) for w in widths]
    diff = 100 - sum(pcts)
    if diff != 0:
        widest_idx = pcts.index(max(pcts))
        pcts[widest_idx] += diff
    return [f"{p}%" for p in pcts]
```

**效果示例:**

| 表格类型 | 列宽分配 |
|----------|---------|
| 2列（发现 / 说明） | 27% / 73% |
| 3列（项目 / 结论 / 依据） | 17% / 37% / 46% |
| 4列（项目 / Stars / 验证方式 / 核心借鉴点） | 12% / 12% / 26% / 50% |

---

## Markdown 单元格清洗

表格单元格中的 Markdown 格式符会被自动清除，避免 `**粗体**` 原样显示：

| 输入 | 输出 |
|------|------|
| `**快速排序**` | 快速排序 |
| `*斜体文字*` | 斜体文字 |
| `~~删除线~~` | 删除线 |
| `` `O(n log n)` `` | O(n log n) |
| `[链接](url)` | 链接 |

---

## 边界情况处理

1. **空表头**: `| | 列A | 列B |` → 空列名自动替换为 `列N`
2. **无表格消息**: 返回 `None`，走 Hermes 原始逻辑
3. **解析失败**: 表格解析失败时降级为 `tag: markdown` 渲染
4. **混合内容**: 文字+表格+文字 → 正确拆分为多个 card elements

---

## 已知限制

1. 表格单元格为**纯文本**，不支持粗体/斜体/链接等格式
2. 表头与数据行在视觉上**无区分**（Plan B 的副作用）
3. 单张卡片最多 5 个表格组件（飞书平台限制）
4. 卡片 JSON 2.0 需要客户端 ≥ v7.20

---

## 提交历史

```
f7f5728 fix: use generic column keys + headers as first data row (Plan B)
9fb24bf fix: handle empty markdown table column headers
288cca9 feat: native table component with adaptive column width
```

## 验证清单

- [x] 2 列表格自适应列宽（27%/73%）
- [x] 3 列表格自适应列宽（17%/37%/46%）
- [x] 4 列表格自适应列宽（12%/12%/26%/50%）
- [x] 混合内容（文字 + 表格 + 文字）正确拆分渲染
- [x] 文字部分 GFM 全部保留（粗体、斜体、代码块、标题、引用块）
- [x] 无表格消息走原始逻辑不受影响
- [x] 空列名自动替换
- [x] 单元格 Markdown 格式符清洗
- [x] 表头正确显示（Plan B: 作为第一行数据）
- [x] 卸载 → 重装 → 检查全流程闭环
- [x] 多 profile 兼容（default / code-assistant / research-bot）

## 安装与使用

```bash
cd feishu-table-patch
HERMES_DIR=~/.hermes/hermes-agent bash install.sh

# 重启 gateway
hermes gateway stop --all
hermes gateway start
# 多 profile:
hermes --profile code-assistant gateway start
hermes --profile research-bot gateway start
```
