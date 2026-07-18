# Google Sheets Connector

Connect to any Google Spreadsheet. Each sheet tab becomes a table with auto-generated tools.

---

## Installation

```bash
pip install mcp-maker[gsheets]
```

---

## Setup (Step by Step)

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown (top left) → **New Project**
3. Name it (e.g., `mcp-maker`) → **Create**

### Step 2: Enable the APIs

1. In your project, go to **APIs & Services → Library**
2. Search for **Google Sheets API** → click → **Enable**
3. Search for **Google Drive API** → click → **Enable**

### Step 3: Create a Service Account

1. Go to **IAM & Admin → Service Accounts**
2. Click **Create Service Account**
3. Name it (e.g., `mcp-maker-bot`) → **Create and Continue**
4. Skip the role selection → **Continue** → **Done**
5. Click on your new service account
6. Go to the **Keys** tab
7. **Add Key → Create new key → JSON → Create**
8. A JSON file downloads — **save it somewhere safe** (e.g., `~/credentials/gsheets-sa.json`)

### Step 4: Share Your Spreadsheet

1. Open the downloaded JSON file
2. Find the `client_email` field — it looks like:
   ```
   mcp-maker-bot@your-project.iam.gserviceaccount.com
   ```
3. Open your Google Spreadsheet in the browser
4. Click **Share** (top right)
5. Paste the service account email
6. Set permission to **Viewer** (or **Editor** if using `--read-write`)
7. Click **Send**

> **This step is critical!** The service account is treated as a separate user. It can only access spreadsheets explicitly shared with it.

### Step 5: Set the Environment Variable

```bash
export GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/your-credentials.json
```

For permanent setup:

```bash
echo 'export GOOGLE_SERVICE_ACCOUNT_FILE=~/credentials/gsheets-sa.json' >> ~/.zshrc
source ~/.zshrc
```

**Alternative — JSON content directly** (useful for deployment):

```bash
export GOOGLE_CREDENTIALS_JSON='{"type":"service_account","project_id":"my-project",...}'
```

### Step 6: Find Your Spreadsheet ID

From the URL of your Google Sheet:

```
https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjiSfghkH/edit
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                       This is your Spreadsheet ID
```

### Step 7: Generate the Server

```bash
mcp-maker init gsheet://1BxiMVs0XRA5nFMdKvBdBZjiSfghkH
```

---

## Generated Tools

### New in 0.2.7

- `filter_{sheet}(field, value, operator)` — eq/ne/gt/gte/lt/lte/contains filtering
- `aggregate_{sheet}(group_by, agg_function, agg_column)` — count/sum/avg/min/max
- `distinct_{sheet}(field)` — distinct values of a column
- `list_{sheet}` now supports `sort_field`/`sort_direction` (numeric-aware)
- Fixed: sheets with duplicate or empty headers no longer break reads
- Fixed: `count_{sheet}` counts actual data rows (it previously returned the grid size, often 1000)

For a spreadsheet with tabs `Clients` and `Invoices`:

### Read Tools (always generated)

| Tool | Example | What It Does |
|------|---------|-------------|
| `list_clients(limit, offset, fields)` | `list_clients(limit=20)` | → `{results, total, has_more, next_offset}` |
| `search_clients(query, limit)` | `search_clients(query="Acme")` | Search across all columns |
| `count_clients()` | `count_clients()` | Total row count |
| `schema_clients()` | `schema_clients()` | Column headers and inferred types |
| `export_clients_csv()` | `export_clients_csv()` | Export as CSV string |
| `export_clients_json()` | `export_clients_json()` | Export as JSON string |

**Advanced list features:**
- `list_clients(fields="name,email")` → Column selection

### Write Tools (with `--read-write`)

| Tool | Example | What It Does |
|------|---------|-------------|
| `append_clients(name, email, ...)` | `append_clients(name="Alice", email="a@co.com")` | Add a new row at the bottom |
| `update_clients_cell(row_number, field, value)` | `update_clients_cell(row_number=5, field="status", value="Active")` | Update a single cell |

---

## How Sheet Tabs Become Tables

Each tab/sheet in your spreadsheet becomes a separate table:

```
Your Google Spreadsheet
├── Tab: "Clients"         → Table: clients
├── Tab: "Invoices"        → Table: invoices
├── Tab: "2024 Revenue"    → Table: _2024_revenue
└── Tab: "Settings"        → Table: settings
```

- **Row 1 = column headers.** The first row of each tab is used as field names.
- **Row 2 onwards = data.** These are your records.
- **Tab names are sanitized** — spaces become underscores, special chars are removed.

---

## Example: Complete Walkthrough

### Your Google Sheet

**Tab: "Clients"**

| Name | Email | Company | Status |
|------|-------|---------|--------|
| Alice Johnson | alice@acme.com | Acme Corp | Active |
| Bob Smith | bob@globex.com | Globex Inc | Inactive |
| Carol Williams | carol@initech.com | Initech | Active |

**Tab: "Invoices"**

| Invoice # | Client | Amount | Paid |
|-----------|--------|--------|------|
| INV-001 | Acme Corp | 5000 | Yes |
| INV-002 | Globex Inc | 3200 | No |
| INV-003 | Initech | 7500 | Yes |

### Generate and run

```bash
export GOOGLE_SERVICE_ACCOUNT_FILE=~/credentials/service-account.json
mcp-maker init gsheet://1BxiMVs0XRA5nFMdKvBdBZji --read-write
mcp-maker serve
```

### Ask Claude

> **You:** "What clients do we have?"
>
> **Claude:** *calls `list_clients()`*
> "You have 3 clients: Alice Johnson (Active), Bob Smith (Inactive), and Carol Williams (Active)."

> **You:** "Show me unpaid invoices"
>
> **Claude:** *calls `search_invoices(query="No")`*
> "There's 1 unpaid invoice: INV-002 for Globex Inc, $3,200."

> **You:** "Add a new client: Dave Brown at MegaCorp, status Active"
>
> **Claude:** *calls `append_clients(name="Dave Brown", email="dave@megacorp.com", company="MegaCorp", status="Active")`*
> "Added Dave Brown to the Clients sheet."

> **You:** "Mark Bob as Active"
>
> **Claude:** First *calls `list_clients()`* to find Bob's row number (row 3), then *calls `update_clients_cell(row_number=3, field="status", value="Active")`*
> "Updated Bob's status to Active."

---

## Row Numbers

Each record in results includes a `row_number` field:

```json
[
  {"row_number": 2, "name": "Alice Johnson", "email": "alice@acme.com", ...},
  {"row_number": 3, "name": "Bob Smith", "email": "bob@globex.com", ...},
  {"row_number": 4, "name": "Carol Williams", "email": "carol@initech.com", ...}
]
```

- Row 1 is the header row
- Row 2 is the first data row
- Use `row_number` with `update_cell` to update specific rows

---

## Type Inference

MCP-Maker infers column types from your data:

| Data Pattern | Inferred Type | Example Values |
|-------------|--------------|---------------|
| Integers only | Integer | `1`, `42`, `1000` |
| Decimals | Float | `9.99`, `3.14` |
| true/false/yes/no | Boolean | `TRUE`, `FALSE` |
| Everything else | String | `"hello"`, dates, etc. |

---

## Claude Desktop Configuration

For Google Sheets, you need to pass the credentials env var to Claude Desktop:

```json
{
  "mcpServers": {
    "my-sheets": {
      "command": "/usr/bin/python3",
      "args": ["/full/path/to/mcp_server.py"],
      "env": {
        "GOOGLE_SERVICE_ACCOUNT_FILE": "/full/path/to/credentials.json"
      }
    }
  }
}
```

---

## Troubleshooting

### "Cannot access spreadsheet"

- Did you share the spreadsheet with the service account email?
- Open the JSON credentials file → copy `client_email` → Share the sheet with that email

### "Google Sheets API is not enabled"

Go to [Google Cloud Console → APIs & Services](https://console.cloud.google.com/apis/library) and enable both the **Google Sheets API** and **Google Drive API**.

### "File not found: credentials.json"

Make sure `GOOGLE_SERVICE_ACCOUNT_FILE` points to the actual file:

```bash
ls -la $GOOGLE_SERVICE_ACCOUNT_FILE   # Should show the file
```

### "Permission denied" on write operations

Make sure the spreadsheet is shared with **Editor** access (not just Viewer) for the service account.

### Empty results from a sheet

- Make sure your sheet has data starting from row 1 (headers) and row 2 (data)
- Completely empty sheets are skipped
