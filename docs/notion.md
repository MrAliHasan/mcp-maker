# Notion Connector

Connect to Notion databases and auto-generate MCP tools. Supports multiple databases in a single server.

---

## Installation

```bash
pip install mcp-maker[notion]
```

---

## Setup (Step by Step)

### Step 1: Create a Notion Integration

1. Go to [https://www.notion.so/my-integrations](https://www.notion.so/my-integrations)
2. Click **"New integration"**
3. Fill in:
   - **Name:** `mcp-maker` (or whatever you prefer)
   - **Associated workspace:** Select your workspace
4. Under **Capabilities**, enable:
   - ✅ **Read content** — required for all read operations
   - ✅ **Insert content** — if you'll use `--read-write`
   - ✅ **Update content** — if you'll use `--read-write`
   - ❌ **No user information** is needed
5. Click **Submit**
6. **Copy the Internal Integration Secret** — it starts with `ntn_`

### Step 2: Connect the Integration to Your Database

**This is the step most people miss.** Notion integrations don't get automatic access to anything — you must explicitly connect them.

1. Open your Notion database page in the browser
2. Click the **⋯** menu (top-right corner of the page)
3. Scroll down to **"Connections"**
4. Click **"Connect to"** → search for your integration name
5. Click **Confirm**

> **Repeat this for every database** you want to include in your MCP server.

### Step 3: Set the Environment Variable

```bash
export NOTION_API_KEY=ntn_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

For permanent setup:

```bash
echo 'export NOTION_API_KEY=ntn_xxxxxxxxxxxx' >> ~/.zshrc
source ~/.zshrc
```

### Step 4: Find Your Database ID

Open your Notion database in the browser. The URL looks like:

```
https://www.notion.so/myworkspace/abc123def456789012345678abcdef01?v=...
                                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                  This is your Database ID
```

It's the 32-character hex string before the `?`.

> **Tip:** The database ID sometimes has dashes — both `abc-123-def` and `abc123def` work.

### Step 5: Generate the Server

```bash
# Single database
mcp-maker init notion://abc123def456789012345678abcdef01

# Multiple databases in one server!
mcp-maker init notion://DB_ID_1,DB_ID_2,DB_ID_3

# With write operations
mcp-maker init notion://abc123def456 --read-write
```

---

## Generated Tools

### New in 0.2.7

- `distinct_{db}(property_name, limit)` — distinct values of a property
- `count_{db}` is capped at 10,000 pages and reports whether the count is exact
- Fixed: **server generation for Notion previously crashed with a template error** — it now works

For a Notion workspace with databases `Tasks` and `Contacts`:

### Read Tools (always generated)

| Tool | Example | What It Does |
|------|---------|-------------|
| `list_tasks(limit, start_cursor, fields)` | `list_tasks(limit=20)` | → `{results, has_more, next_cursor}` |
| `get_tasks_by_page_id(page_id)` | `get_tasks_by_page_id("abc-123...")` | Get a specific page |
| `search_tasks(query, limit)` | `search_tasks(query="urgent")` | Full-text search |
| `filter_tasks(property_name, value)` | `filter_tasks(property_name="status", value="Done")` | Server-side filtering |
| `count_tasks()` | `count_tasks()` | Total page count |
| `schema_tasks()` | `schema_tasks()` | Property names, types, select options |
| `export_tasks_csv()` | `export_tasks_csv()` | Export as CSV string |
| `export_tasks_json()` | `export_tasks_json()` | Export as JSON string |

**Advanced list features:**
- `list_tasks(fields="task,status")` → Property selection

### Write Tools (with `--read-write`)

| Tool | Example | What It Does |
|------|---------|-------------|
| `create_tasks(title, status, ...)` | `create_tasks(title="Fix bug", status="In Progress")` | Create a new page |

---

## Pagination — How It Works

Notion uses **cursor-based pagination**, not page numbers. Here's how it works:

### First request

```python
list_tasks(limit=50)
```

Returns:

```json
{
  "results": [
    {"page_id": "abc-123", "title": "Fix login bug", "status": "In Progress"},
    {"page_id": "def-456", "title": "Update docs", "status": "Done"}
  ],
  "next_cursor": "eyJsYXN0X2lkIjoiZGVmLTQ1NiJ9",
  "has_more": true
}
```

### Getting the next page

```python
list_tasks(limit=50, start_cursor="eyJsYXN0X2lkIjoiZGVmLTQ1NiJ9")
```

The AI handles this automatically — when Claude needs more results, it reads `next_cursor` from the response and passes it in the next call.

---

## Property Types

MCP-Maker maps all Notion property types:

| Notion Type | Mapped To | Example Value |
|-------------|-----------|--------------|
| Title | String | `"My Task"` |
| Rich Text | String | `"Some description"` |
| Number | Float | `42.5` |
| Checkbox | Boolean | `true` |
| Select | String | `"In Progress"` |
| Multi-select | JSON (list) | `["Bug", "Urgent"]` |
| Status | String | `"Done"` |
| Date | DateTime | `"2024-01-15"` |
| URL | String | `"https://example.com"` |
| Email | String | `"alice@co.com"` |
| Phone | String | `"+1-555-0123"` |
| People | JSON (list) | `["Alice", "Bob"]` |
| Files | JSON (list) | `["document.pdf"]` |
| Relation | JSON (list) | `["page-id-1", "page-id-2"]` |
| Formula | String | Computed value |
| Rollup | varies | Aggregated value |
| Created time | DateTime | `"2024-01-15T10:30:00"` |
| Last edited time | DateTime | `"2024-01-16T14:00:00"` |
| Created by | String | `"Alice"` |
| Last edited by | String | `"Bob"` |
| Unique ID | Integer | `"TASK-42"` |

---

## Example: Project Management Workflow

### Your Notion database: "Tasks"

| Task | Status | Priority | Assignee | Due Date |
|------|--------|----------|----------|----------|
| Fix login bug | In Progress | High | Alice | 2024-02-15 |
| Update docs | Done | Medium | Bob | 2024-02-10 |
| Add notifications | To Do | High | Carol | 2024-02-20 |
| Refactor API | In Progress | Low | Alice | 2024-03-01 |

### Generate and run

```bash
export NOTION_API_KEY=ntn_xxxxxxxxxxxx
mcp-maker init notion://YOUR_DATABASE_ID --read-write
mcp-maker serve
```

### Ask Claude

> **You:** "What tasks are in progress?"
>
> **Claude:** *calls `filter_tasks(property_name="status", value="In Progress")`*
> "There are 2 tasks in progress: 'Fix login bug' (High priority, assigned to Alice) and 'Refactor API' (Low priority, also assigned to Alice)."

> **You:** "Show me all high priority tasks"
>
> **Claude:** *calls `filter_tasks(property_name="priority", value="High")`*
> "2 high priority tasks: 'Fix login bug' (In Progress, due Feb 15) and 'Add notifications' (To Do, due Feb 20)."

> **You:** "What's the task count?"
>
> **Claude:** *calls `count_tasks()`*
> "You have 4 tasks total."

> **You:** "Create a new task: Design landing page, status To Do, priority Medium"
>
> **Claude:** *calls `create_tasks(task="Design landing page", status="To Do", priority="Medium")`*
> "Created new task 'Design landing page' with To Do status and Medium priority."

> **You:** "Show me the database schema"
>
> **Claude:** *calls `schema_tasks()`*
> "The Tasks database has 5 properties:
> - task (String) — Title
> - status (String) — Options: To Do, In Progress, Done
> - priority (String) — Options: Low, Medium, High
> - assignee (JSON) — People
> - due_date (DateTime)"

---

## Multiple Databases in One Server

This is a unique MCP-Maker feature. Combine related databases:

```bash
# Comma-separated database IDs
mcp-maker init notion://TASKS_DB_ID,CONTACTS_DB_ID,PROJECTS_DB_ID
```

This generates one MCP server with tools for all three databases:

```
list_tasks()       search_tasks()       count_tasks()
list_contacts()    search_contacts()    count_contacts()
list_projects()    search_projects()    count_projects()
```

> **Remember:** Each database must have the integration connected (Step 2 in setup).

---

## Claude Desktop Configuration

For Notion, pass the API key via env vars:

```json
{
  "mcpServers": {
    "my-notion": {
      "command": "/usr/bin/python3",
      "args": ["/full/path/to/mcp_server.py"],
      "env": {
        "NOTION_API_KEY": "ntn_xxxxxxxxxxxxxxxxxxxx"
      }
    }
  }
}
```

---

## Troubleshooting

### "NOTION_API_KEY not found"

```bash
export NOTION_API_KEY=ntn_xxxxxxxxxxxx
```

### "Cannot access database"

**Most common cause:** You forgot to connect the integration to the database.

1. Open the Notion database
2. Click **⋯** → **Connections** → Connect your integration

### "Integration not showing in Connections"

- Make sure the integration is in the same workspace as the database
- Try refreshing the Notion page

### "Properties not showing up"

- Hidden properties in Notion are still visible via the API
- If a property was renamed, re-run `mcp-maker init` to update

### "Filter not working"

The `filter` tool uses a simple equals filter by default. For complex filters, the tool falls back to client-side filtering. Use the safe property names (from `schema`) for `property_name`.
