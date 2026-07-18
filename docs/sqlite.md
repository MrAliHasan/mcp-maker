# SQLite Connector

Connect to any SQLite database and auto-generate MCP tools for every table.

**No extra installation needed** — SQLite support is built into the core `mcp-maker` package.

---

## Quick Start

```bash
mcp-maker init sqlite:///path/to/your/database.db
mcp-maker serve
```

That's it. Every table in your database now has list, search, count, and schema tools.

---

## URI Format

```
sqlite:///path/to/database.db          # Relative path
sqlite:////absolute/path/to/database.db  # Absolute path (note: 4 slashes)
```

You can also pass a `.db` file directly:

```bash
mcp-maker init ./my_data.db
```

---

## What Gets Generated

### New in 0.2.7

- `distinct_{table}(field, limit)` — distinct values of any column
- **Views are now discovered** and get read tools (`list_`, `search_`, `count_`, `aggregate_`, `distinct_`)
- Inspection opens the database **read-only** — it can never lock or mutate your file
- Table/column names containing quotes are now safely escaped

For each table in your SQLite database, MCP-Maker generates:

### Read Tools (always generated)

```
list_contacts(limit=50, offset=0)     → Paginated listing → {results, total, has_more, next_offset}
get_contacts_by_id(id=1)              → Get by primary key
search_contacts(query="alice")         → Full-text search
count_contacts()                       → Total row count
schema_contacts()                      → Column names & types
export_contacts_csv()                  → Export as CSV string
export_contacts_json()                 → Export as JSON string
```

### Advanced List Features

```
list_contacts(fields="name,email")              → Column selection
list_contacts(sort_field="name", sort_direction="desc")  → Sorting
list_contacts(created_at_from="2024-01-01")     → Date range filter (auto-detected)
```

### Write Tools (with `--read-write`)

```bash
mcp-maker init sqlite:///my.db --read-write
```

```
insert_contacts(name="Frank", email="frank@co.com")      → Insert a row
update_contacts_by_id(id=1, name="Alice Updated")         → Update by PK
delete_contacts_by_id(id=1)                                → Delete by PK
batch_insert_contacts(records=[{...}, {...}])               → Batch insert
batch_delete_contacts(ids=[1, 2, 3])                        → Batch delete
```

### Relationship Tools

When foreign keys are detected between tables (e.g., `posts.user_id → users.id`), MCP-Maker auto-generates:

```
join_posts_with_users(limit=50, offset=0)  → Pre-built JOIN query
```

---

## Example: Complete Walkthrough

### 1. You have a SQLite database

Let's say you have a `chinook.db` music database with tables: `artists`, `albums`, `tracks`, `customers`.

### 2. Generate the server

```bash
mcp-maker init sqlite:///chinook.db
```

```
⚒️ MCP-Maker                                         v0.2.3

  ✅ Connected to sqlite source

  ┌──────────────────────────────────────────────────────────────┐
  │ 📊 Discovered Tables (4)                                    │
  ├───────────┬─────────────────────────────────┬──────┬────────┤
  │ Table     │ Columns                         │ Rows │ PK     │
  ├───────────┼─────────────────────────────────┼──────┼────────┤
  │ artists   │ ArtistId, Name                  │  275 │ArtistId│
  │ albums    │ AlbumId, Title, ArtistId        │  347 │AlbumId │
  │ tracks    │ TrackId, Name, AlbumId, ...     │ 3503 │TrackId │
  │ customers │ CustomerId, FirstName, ...      │   59 │CustomerId│
  └───────────┴─────────────────────────────────┴──────┴────────┘

  🎉 Generated: mcp_server.py
```

### 3. Preview what was generated (optional)

```bash
mcp-maker inspect sqlite:///chinook.db
```

This shows you all the tools that would be generated without creating any files.

### 4. Run and connect

```bash
mcp-maker serve
mcp-maker config --install   # Connect to Claude Desktop
```

### 5. Ask Claude

> **You:** "What tables are in the database?"
>
> **Claude:** *calls `schema_artists()`, `schema_albums()`, etc.*
> "Your database has 4 tables: artists (275 rows), albums (347), tracks (3503), and customers (59)."

> **You:** "Show me 5 rock tracks"
>
> **Claude:** *calls `search_tracks(query="Rock", limit=5)`*
> "Here are 5 rock tracks: 1. 'For Those About To Rock' by AC/DC..."

> **You:** "How many customers are from Brazil?"
>
> **Claude:** *calls `search_customers(query="Brazil")`*
> "There are 5 customers from Brazil."

---

## Supported Column Types

MCP-Maker maps SQLite types automatically:

| SQLite Type | Mapped To | Example |
|-------------|-----------|---------|
| `INTEGER` | Integer | `1`, `42`, `1000` |
| `TEXT`, `VARCHAR`, `CHAR` | String | `"hello"` |
| `REAL`, `FLOAT`, `DOUBLE` | Float | `3.14`, `99.9` |
| `BOOLEAN` | Boolean | `true`, `false` |
| `DATE` | Date | `"2024-01-15"` |
| `DATETIME`, `TIMESTAMP` | DateTime | `"2024-01-15T10:30:00"` |
| `BLOB` | Binary | Binary data |
| `JSON` | JSON | `{"key": "value"}` |

---

## Tips

- **Primary keys are auto-detected.** MCP-Maker finds the primary key of each table and generates a `get_by_{pk}` tool for it.
- **Composite primary keys** are supported — the first PK column is used for the get tool.
- **Views are included** as read-only tables.
- **Foreign keys** are auto-detected and generate `join_` tools for cross-table queries.
- **Date columns** auto-generate `_from`/`_to` filter params on `list_` tools.

---

## Troubleshooting

### "File not found"

```
Validation failed: Database file not found: ./my.db
```

**Fix:** Make sure the path is correct. Use absolute paths if relative paths aren't working:

```bash
mcp-maker init sqlite:////Users/you/data/my.db
```

### "No tables found"

Your database exists but has no tables. Check it with:

```bash
sqlite3 my.db ".tables"
```
