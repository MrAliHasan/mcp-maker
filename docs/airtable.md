# Airtable Connector

Connect to any Airtable base and auto-generate powerful MCP tools — including native formula filtering, view-based queries, sorting, and full CRUD.

---

## Installation

```bash
pip install mcp-maker[airtable]
```

---

## Setup (Step by Step)

### Step 1: Create an Airtable API Token

1. Go to [https://airtable.com/create/tokens](https://airtable.com/create/tokens)
2. Click **"Create new token"**
3. Give it a name (e.g., `mcp-maker`)
4. **Add scopes:**
   - `data.records:read` — required for all read operations
   - `data.records:write` — only if you'll use `--read-write`
   - `schema.bases:read` — required for schema inspection
5. **Add access** — select the base(s) you want to connect
6. Click **"Create token"**
7. **Copy the token** (starts with `pat_`) — you won't see it again!

### Step 2: Set the Environment Variable

```bash
export AIRTABLE_API_KEY=pat_xxxxxxxxxxxxxxxxxxxx.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Add this to your `~/.zshrc` or `~/.bashrc` to make it permanent:

```bash
echo 'export AIRTABLE_API_KEY=pat_xxxxxxxxxxxx' >> ~/.zshrc
source ~/.zshrc
```

### Step 3: Find Your Base ID

**Option A — Use the discovery command:**

```bash
mcp-maker bases
```

```
🗂️  Airtable Base Discovery                          v0.2.3

  ┌─────────────────────────────────────────────────────────────────┐
  │ 📋 Accessible Bases (3)                                        │
  ├──────────────────┬─────────────────┬───────────────────────────┤
  │ Base ID          │ Name            │ Command                   │
  ├──────────────────┼─────────────────┼───────────────────────────┤
  │ appABC123def456  │ CRM             │ mcp-maker init airtable://appABC123def456 │
  │ appXYZ789ghi012  │ Project Tracker │ mcp-maker init airtable://appXYZ789ghi012 │
  │ app345JKL678mno  │ Inventory       │ mcp-maker init airtable://app345JKL678mno │
  └──────────────────┴─────────────────┴───────────────────────────┘

  Run any command above to generate an MCP server for that base.
```

**Option B — From the Airtable URL:**

Open your base in the browser. The URL looks like:

```
https://airtable.com/appABC123def456/tblXXXXXX/...
                     ^^^^^^^^^^^^^^^^
                     This is your Base ID
```

### Step 4: Generate the Server

```bash
# Read-only (default)
mcp-maker init airtable://appABC123def456

# With write operations
mcp-maker init airtable://appABC123def456 --read-write
```

---

## Generated Tools

### New in 0.2.7

- `distinct_{table}(field, limit)` — distinct values of a field
- `aggregate_{table}(group_by, agg_function, agg_field)` — count/sum/avg/min/max
- Fixed: `search_{table}` crashed at runtime (it iterated the wrong data structure)
- Row counts during `init` are capped at 1,000 records to protect your API quota

For a base with tables `Contacts` and `Projects`, you'll get:

### Standard Tools (every table)

| Tool | Example | What It Does |
|------|---------|-------------|
| `list_contacts(limit, offset, sort_field, sort_direction, fields)` | `list_contacts(limit=10, sort_field="name")` | → `{results, total, has_more, next_offset}` |
| `get_contacts_by_record_id(record_id)` | `get_contacts_by_record_id("recXXXXXXXX")` | Get by Airtable record ID |
| `search_contacts(query, limit)` | `search_contacts(query="alice")` | Full-text search across all fields |
| `count_contacts()` | `count_contacts()` | Total record count |
| `schema_contacts()` | `schema_contacts()` | Field names, types, and select options |
| `export_contacts_csv()` | `export_contacts_csv()` | Export as CSV string |
| `export_contacts_json()` | `export_contacts_json()` | Export as JSON string |

**Advanced list features:**
- `list_contacts(fields="name,email")` → Field selection

### Airtable-Specific Tools

| Tool | Example | What It Does |
|------|---------|-------------|
| `filter_contacts(formula, limit)` | `filter_contacts(formula='{Status} = "Active"')` | **Native Airtable formula queries** |
| `list_contacts_views()` | `list_contacts_views()` | List all views for this table |
| `list_contacts_by_view(view_name, limit)` | `list_contacts_by_view("active_clients")` | Query through a specific view |

### Write Tools (with `--read-write`)

| Tool | Example | What It Does |
|------|---------|-------------|
| `create_contacts(name, email, ...)` | `create_contacts(name="Alice", email="a@co.com")` | Create a new record |
| `update_contacts(record_id, ...)` | `update_contacts(record_id="recXX", status="Active")` | Update specific fields |
| `delete_contacts(record_id)` | `delete_contacts(record_id="recXXXXXXXX")` | Delete a record |

---

## Formula Filtering — The Killer Feature

The `filter` tool uses [Airtable's native formula language](https://support.airtable.com/docs/formula-field-reference). This is the most powerful way to query Airtable data:

### Basic Comparisons

```python
# Equals
filter_contacts(formula='{Status} = "Active"')

# Not equals
filter_contacts(formula='{Status} != "Inactive"')

# Greater/less than (numbers and dates)
filter_contacts(formula='{Age} > 25')
filter_contacts(formula='{Created} > "2024-01-01"')
```

### Combining Conditions

```python
# AND — all conditions must match
filter_contacts(formula='AND({Status} = "Active", {City} = "NYC")')

# OR — any condition matches
filter_contacts(formula='OR({Priority} = "High", {Priority} = "Critical")')

# Complex nesting
filter_contacts(formula='AND({Status} = "Active", OR({City} = "NYC", {City} = "London"))')
```

### Text Functions

```python
# Contains text (case-insensitive)
filter_contacts(formula='FIND("python", LOWER({Skills}))')

# Starts with
filter_contacts(formula='LEFT({Name}, 1) = "A"')

# Is not empty
filter_contacts(formula='NOT({Email} = BLANK())')

# Is empty
filter_contacts(formula='{Phone} = BLANK()')
```

### Date Functions

```python
# Records from today
filter_contacts(formula='IS_SAME({Due Date}, TODAY(), "day")')

# Records from this month
filter_contacts(formula='IS_SAME({Created}, TODAY(), "month")')

# Records in the last 7 days
filter_contacts(formula='DATETIME_DIFF(TODAY(), {Created}, "days") <= 7')
```

> **Important:** Use the **original Airtable field names** in formulas (e.g., `{First Name}`), not the safe Python names (e.g., `first_name`). The `schema` tool shows you the mapping.

---

## Views

Airtable views are pre-configured filters and sorts. MCP-Maker auto-discovers them:

```python
# See available views
list_contacts_views()
# Returns: [
#   {"name": "grid_view", "airtable_name": "Grid view", "type": "grid"},
#   {"name": "active_clients", "airtable_name": "Active Clients", "type": "grid"},
#   {"name": "kanban", "airtable_name": "Kanban", "type": "kanban"},
# ]

# Query through a view
list_contacts_by_view("active_clients", limit=50)
```

---

## Sorting

The `list` tool supports sorting:

```python
# Sort by name A-Z
list_contacts(sort_field="name", sort_direction="asc")

# Sort by created date, newest first
list_contacts(sort_field="created", sort_direction="desc")

# Sort + limit
list_contacts(sort_field="priority", sort_direction="desc", limit=10)
```

---

## Example: Complete CRM Workflow

### Your Airtable base has a `Contacts` table

| Name | Email | Company | Status | Priority |
|------|-------|---------|--------|----------|
| Alice | alice@acme.com | Acme Corp | Active | High |
| Bob | bob@globex.com | Globex Inc | Inactive | Low |
| Carol | carol@initech.com | Initech | Active | Medium |

### Ask Claude

> **You:** "Show me all active contacts"
>
> **Claude:** *calls `filter_contacts(formula='{Status} = "Active"')`*
> "You have 2 active contacts: Alice (Acme Corp) and Carol (Initech)."

> **You:** "Find high priority contacts at Acme Corp"
>
> **Claude:** *calls `filter_contacts(formula='AND({Priority} = "High", {Company} = "Acme Corp")')`*
> "Alice Johnson is your high-priority contact at Acme Corp."

> **You:** "Add a new contact: Dave at Globex, status Active"
>
> **Claude:** *calls `create_contacts(name="Dave", company="Globex Inc", status="Active")`*
> "Created new contact Dave at Globex Inc with Active status. Record ID: recXXXXXX."

> **You:** "Mark Bob as Active"
>
> **Claude:** First *calls `search_contacts(query="Bob")`* to find the record ID, then *calls `update_contacts(record_id="recYYYYYY", status="Active")`*
> "Updated Bob's status to Active."

---

## Field Name Mapping

Airtable field names often contain spaces and special characters. MCP-Maker converts them to safe Python names:

| Airtable Name | Safe Name | Used In |
|---------------|-----------|---------|
| `First Name` | `first_name` | Tool parameters, results |
| `Email Address` | `email_address` | Tool parameters, results |
| `Created (Date)` | `created_date` | Tool parameters, results |
| `2024 Revenue` | `_2024_revenue` | Tool parameters, results |

The `schema` tool shows you this mapping:

```python
schema_contacts()
# Returns:
# {
#   "first_name": {"type": "STRING", "airtable_name": "First Name"},
#   "email_address": {"type": "STRING", "airtable_name": "Email Address"},
#   "status": {"type": "STRING", "airtable_name": "Status", "options": ["Active", "Inactive"]},
# }
```

---

## Troubleshooting

### "AIRTABLE_API_KEY not found"

```bash
export AIRTABLE_API_KEY=pat_xxxxxxxxxxxx
```

### "Cannot connect to Airtable base"

- Check that your token has `schema.bases:read` scope
- Make sure the base is in the token's access list
- Token might have expired — create a new one

### "403 Forbidden on write operations"

Your token needs `data.records:write` scope. Edit the token at [airtable.com/create/tokens](https://airtable.com/create/tokens).

### Formula errors

- Use `{Field Name}` with curly braces for field names in formulas
- Use **original** Airtable names, not safe Python names
- String values need double quotes inside: `'{Status} = "Active"'`
