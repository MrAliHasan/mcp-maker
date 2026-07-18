# Excel Connector

Connect to Excel (`.xlsx`) files and auto-generate MCP tools for every sheet.

```bash
pip install mcp-maker[excel]
```

---

## Quick Start

```bash
mcp-maker init ./my_data.xlsx
mcp-maker serve
```

Every sheet in your workbook now has list, search, count, and schema tools.

---

## URI Format

```
excel:///path/to/file.xlsx        # Explicit scheme
./my_data.xlsx                     # Direct file path (auto-detected)
/absolute/path/to/data.xlsx        # Absolute path
```

Supported extensions: `.xlsx`, `.xlsm`, `.xltx`, `.xltm`

---

## What Gets Generated

### New in 0.2.7

- `filter_{sheet}(field, value, operator)` — eq/ne/gt/gte/lt/lte/contains filtering
- `aggregate_{sheet}(group_by, agg_function, agg_column)` — count/sum/avg/min/max
- `distinct_{sheet}(field)` — distinct values of a column
- Date/datetime cells are now typed as `date`/`datetime` instead of strings
- Duplicate headers are de-duplicated; large sheets are sampled instead of fully loaded during inspection

Each sheet in your Excel file becomes a table. The **first row** is used as column headers.

### Read Tools (always generated)

```
list_sheet1(limit=50, offset=0)     → {results, total, has_more, next_offset}
search_sheet1(query="alice")         → Text search across all text columns
count_sheet1()                       → Total row count
schema_sheet1()                      → Column names & inferred types
export_sheet1_csv()                  → Export as CSV string
export_sheet1_json()                 → Export as JSON string
```

### Advanced List Features

```
list_sheet1(fields="name,email")     → Column selection
list_sheet1(sort_field="name", sort_direction="desc")  → Sorting
```

---

## Example: Complete Walkthrough

### 1. You have an Excel file

`sales_data.xlsx` with two sheets: `Q1 Sales`, `Products`

### 2. Generate the server

```bash
mcp-maker init ./sales_data.xlsx
```

```
⚒️ MCP-Maker                                         v0.3.0

  ✅ Connected to excel source

  ┌────────────────────────────────────────────────────┐
  │ 📊 Discovered Tables (2)                           │
  ├──────────┬──────────────────────────┬──────┬───────┤
  │ Table    │ Columns                  │ Rows │ PK    │
  ├──────────┼──────────────────────────┼──────┼───────┤
  │ q1_sales │ date, product, amount    │  150 │  —    │
  │ products │ sku, name, price, stock  │   45 │  —    │
  └──────────┴──────────────────────────┴──────┴───────┘

  🎉 Generated: mcp_server.py
```

### 3. Run and connect

```bash
mcp-maker serve
mcp-maker config --install
```

### 4. Ask Claude

> **You:** "What products are in stock?"
>
> **Claude:** *calls `search_products(query="in stock")`*

> **You:** "Show me the first 10 sales"
>
> **Claude:** *calls `list_q1_sales(limit=10)`*

---

## Type Inference

MCP-Maker samples the first 100 data rows to infer types:

| Python Type | Mapped To | Example |
|-------------|-----------|---------|
| `int` | Integer | `1`, `42` |
| `float` | Float | `3.14`, `99.9` |
| `bool` | Boolean | `True`, `False` |
| `str` (and everything else) | String | `"hello"` |

---

## Tips

- **Sheet names are sanitized** — spaces and special characters become underscores (e.g., `Q1 Sales` → `q1_sales`).
- **Empty rows are skipped** — rows where all cells are `None` are filtered out.
- **Empty sheets are skipped** — sheets with no data or no headers are ignored.
- **Data is pre-loaded** — the entire file is loaded into memory at startup for fast access. Best for files under ~100MB.

---

## Troubleshooting

### "openpyxl is required"

```
ImportError: openpyxl is required for Excel support.
```

**Fix:** Install the Excel extra:

```bash
pip install mcp-maker[excel]
```

### "Unsupported file format"

MCP-Maker only supports `.xlsx` files. For `.xls` (legacy Excel), convert it first:
- Open in Excel/LibreOffice → Save As → `.xlsx`
