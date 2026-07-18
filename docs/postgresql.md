# PostgreSQL Connector

Connect to any PostgreSQL database and auto-generate MCP tools for every table.

---

## Installation

```bash
pip install mcp-maker[postgres]
```

---

## Quick Start

```bash
mcp-maker init postgres://username:password@hostname:5432/database_name
mcp-maker serve
```

---

## URI Format

```
postgres://username:password@hostname:port/database_name
postgresql://username:password@hostname:port/database_name
```

Both `postgres://` and `postgresql://` work.

### Examples

```bash
# Local database
mcp-maker init postgres://myuser:mypass@localhost:5432/myapp

# Remote database
mcp-maker init postgres://admin:secret@db.example.com:5432/production

# With specific schema
mcp-maker init "postgres://user:pass@host:5432/db?schema=analytics"

# Default port (5432)
mcp-maker init postgres://user:pass@localhost/mydb
```

### Custom Schema

By default, MCP-Maker inspects the `public` schema. To use a different schema:

```bash
mcp-maker init "postgres://user:pass@localhost:5432/mydb?schema=analytics"
```

---

## Generated Tools

### New in 0.2.7

- `distinct_{table}(field, limit)` — distinct values of any column
- **Views and materialized views are now discovered** and get read tools
- Fixed: `?schema=myschema` in the URI no longer breaks the connection

Same as SQLite — for each table you get:

### Read Tools

```
list_users(limit=50, offset=0)       → {results, total, has_more, next_offset}
get_users_by_id(id=1)                → Get by primary key
search_users(query="alice")           → Full-text search (ILIKE)
count_users()                         → Row count
schema_users()                        → Column info
export_users_csv()                    → Export as CSV string
export_users_json()                   → Export as JSON string
```

### Advanced List Features

```
list_users(fields="name,email")              → Column selection
list_users(sort_field="name", sort_direction="desc")  → Sorting
list_orders(placed_at_from="2024-01-01")     → Date range filter (auto-detected)
```

### Write Tools (with `--read-write`)

```bash
mcp-maker init postgres://user:pass@host/db --read-write
```

```
insert_users(name="Frank", email="frank@co.com")
update_users_by_id(id=1, name="Updated Name")
delete_users_by_id(id=1)
batch_insert_users(records=[{...}, {...}])
batch_delete_users(ids=[1, 2, 3])
```

### Relationship Tools

```
join_orders_with_users(limit=50, offset=0)  → Auto-detected FK joins
```

---

## Example

### Your PostgreSQL database

```
production_db
├── users (5,000 rows)          → id, name, email, role, created_at
├── orders (15,000 rows)        → id, user_id, total, status, placed_at
├── products (200 rows)         → id, name, price, category, in_stock
└── reviews (8,000 rows)        → id, product_id, user_id, rating, body
```

### Generate and run

```bash
mcp-maker init postgres://admin:secret@localhost:5432/production_db
mcp-maker serve
```

### Ask Claude

> **You:** "How many orders do we have?"
>
> **Claude:** *calls `count_orders()`*
> "You have 15,000 orders."

> **You:** "Find orders with status 'pending'"
>
> **Claude:** *calls `search_orders(query="pending", limit=10)`*
> "Here are 10 pending orders..."

> **You:** "What does the products table look like?"
>
> **Claude:** *calls `schema_products()`*
> "The products table has 5 columns: id (integer, PK), name (text), price (float), category (text), in_stock (boolean)."

---

## Supported PostgreSQL Types

| PostgreSQL Type | Mapped To |
|----------------|----------|
| `integer`, `bigint`, `smallint`, `serial` | Integer |
| `real`, `double precision`, `numeric`, `decimal` | Float |
| `text`, `varchar`, `char`, `citext` | String |
| `boolean` | Boolean |
| `date` | Date |
| `timestamp`, `timestamptz` | DateTime |
| `json`, `jsonb` | JSON |
| `uuid` | String |
| `bytea` | Binary |
| `array` | JSON |
| `inet`, `cidr`, `macaddr` | String |

---

## Troubleshooting

### "psycopg2 not installed"

```bash
pip install mcp-maker[postgres]
```

### "Connection refused"

- Check that PostgreSQL is running: `pg_isready`
- Verify hostname, port, username, and password
- Make sure the database allows remote connections (check `pg_hba.conf`)

### "Permission denied"

The database user needs at least `SELECT` privilege on the tables. For write mode, it needs `INSERT`, `UPDATE`, `DELETE` too.

### SSL connections

Some hosted databases (like Supabase, Neon) require SSL:

```bash
mcp-maker init "postgres://user:pass@host:5432/db?sslmode=require"
```
