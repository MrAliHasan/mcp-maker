# Supabase Connector

Connect to a Supabase project and auto-generate MCP tools for every table, plus Supabase-specific auth and storage tools.

```bash
pip install mcp-maker[supabase]
```

---

## Quick Start

```bash
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_KEY="your-anon-or-service-role-key"

mcp-maker init supabase://your-project-ref
mcp-maker serve
```

---

## URI Format

```
supabase://PROJECT_REF     # Project reference (from Supabase dashboard URL)
```

The connector uses `SUPABASE_URL` and `SUPABASE_KEY` environment variables for authentication.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | ✅ | Your project URL (e.g., `https://xxxx.supabase.co`) |
| `SUPABASE_KEY` | ✅ | Anon key (read-only) or service_role key (full access) |

Find these in your Supabase dashboard: **Settings → API**.

> **Tip:** Use the **anon key** for read-only access, or the **service_role key** for full CRUD + auth tools.

---

## What Gets Generated

### New in 0.2.7

- `distinct_{table}(field, limit)` — distinct values of a column (sampled from up to 1,000 rows)
- Fixed: `search_{table}` now matches when ANY text column contains the query (it previously required every column to match)
- `validate` now genuinely checks your URL and API key instead of always passing

### Per-Table Tools

For each table in your Supabase database:

```
list_users(limit=50, offset=0)              → {results, total, has_more, next_offset}
get_users_by_id(id=1)                       → Get by primary key
search_users(query="alice")                 → ILIKE text search
count_users()                               → Exact row count
schema_users()                              → Column names & types
export_users_csv()                          → Export as CSV string
export_users_json()                         → Export as JSON string
```

### Advanced List Features

```
list_users(fields="name,email")             → Column selection (via PostgREST select)
list_users(sort_field="name", sort_direction="desc")  → Sorting
```

### Write Tools (with `--ops read,insert,update,delete`)

```
insert_users(data={...})                    → Insert via REST API
update_users_by_id(id=1, data={...})        → Update via REST API
delete_users_by_id(id=1)                    → Delete via REST API
batch_insert_users(records=[{...}, {...}])   → Batch insert via REST
batch_delete_users(ids=[1, 2, 3])            → Batch delete via REST
```

### Supabase-Specific Tools (always generated)

```
supabase_auth_list_users(limit=50)          → List auth users (requires service_role key)
supabase_storage_list_buckets()             → List storage buckets
supabase_storage_list_files(bucket, path)   → List files in a bucket
```

---

## Example: Complete Walkthrough

### 1. Set environment variables

```bash
export SUPABASE_URL="https://myproject.supabase.co"
export SUPABASE_KEY="eyJhbGciOiJIUzI1NiIsInR5..."
```

Or use `mcp-maker env`:

```bash
mcp-maker env set SUPABASE_URL "https://myproject.supabase.co"
mcp-maker env set SUPABASE_KEY "eyJhbGci..."
source .env
```

### 2. Generate the server

```bash
mcp-maker init supabase://myproject --ops read,insert
```

### 3. Ask Claude

> **You:** "How many users are in the database?"
>
> **Claude:** *calls `count_users()`*

> **You:** "List all storage buckets"
>
> **Claude:** *calls `supabase_storage_list_buckets()`*

> **You:** "Show me auth users"
>
> **Claude:** *calls `supabase_auth_list_users()`*

---

## How It Works

Unlike the PostgreSQL connector (which connects via `psycopg2`), the Supabase connector uses the **PostgREST API** for all operations. This means:

- ✅ Works with Supabase's Row Level Security (RLS)
- ✅ No direct database connection needed
- ✅ Works with Supabase Auth and Storage APIs
- ⚠️ Only tables exposed via PostgREST are visible (check your API settings)

---

## Tips

- **Row Level Security:** If RLS is enabled, the tools respect your policies. Use the service_role key to bypass RLS.
- **Schema discovery** uses the PostgREST OpenAPI endpoint to detect tables and column types.
- **Auth tools** require a `service_role` key. The anon key will get permission errors.
- **Real-time** and **Edge Functions** are not currently supported — generated tools use REST only.

---

## Troubleshooting

### "SUPABASE_URL is required"

**Fix:** Set the environment variable:
```bash
export SUPABASE_URL="https://your-project.supabase.co"
```

### "No tables found"

Supabase only exposes tables that are in the `public` schema and have PostgREST access enabled. Check **Settings → API → Exposed Schemas** in your Supabase dashboard.

### "Permission denied" on auth tools

Auth admin tools require the `service_role` key, not the anon key:
```bash
export SUPABASE_KEY="your-service-role-key"
```
