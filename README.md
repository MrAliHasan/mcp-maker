# MCP Maker - MCP Server Generator for Any Data Source

[![PyPI version](https://img.shields.io/pypi/v/mcp-maker.svg)](https://pypi.org/project/mcp-maker/)
[![Tests](https://github.com/MrAliHasan/mcp-maker/actions/workflows/tests.yml/badge.svg)](https://github.com/MrAliHasan/mcp-maker/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/MrAliHasan/mcp-maker/branch/main/graph/badge.svg)](https://codecov.io/gh/MrAliHasan/mcp-maker)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/mcp-maker.svg)](https://pypi.org/project/mcp-maker/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/MrAliHasan/mcp-maker/blob/main/LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/mcp-maker.svg)](https://pypi.org/project/mcp-maker/)
[![MCPWorld](https://img.shields.io/badge/MCPWorld-A%20·%20High%20Quality-2ea44f)](https://www.mcpworld.com/zh/detail/e387fc9987c2a7da5b970c77ec14de99)

**Connect Claude, Cursor, ChatGPT, Grok & DeepSeek to your data in under 60 seconds.**

One command. No code. No MCP knowledge required. Generate an [MCP](https://modelcontextprotocol.io/) server for any MCP client — or chat with your database right in the terminal using OpenAI, Grok, DeepSeek, or 500+ models via OpenRouter.

```bash
pip install mcp-maker
mcp-maker init postgres://user:pass@host/mydb
mcp-maker config --install    # wires it into Claude Desktop
```

Restart Claude - it can now query your database.

**Works with:**

| Databases  | Spreadsheets & SaaS | Files & APIs                |
| ---------- | ------------------- | --------------------------- |
| PostgreSQL | Airtable            | CSV / TSV / JSON / JSONL    |
| MySQL      | Notion              | Excel                       |
| SQLite     | Google Sheets       | REST APIs (OpenAPI/Swagger) |
| MongoDB    | HubSpot             |                             |
| Redis      | Supabase            |                             |

**379 tests · MIT licensed · Zero runtime dependency on MCP-Maker · Rated [A – High Quality on MCPWorld](https://www.mcpworld.com/zh/detail/e387fc9987c2a7da5b970c77ec14de99)** ("rigorously validated, comprehensive functionality, high-quality user experience")

---

## Why not just ask Claude or Cursor to write an MCP server?

You can — for one table and four tools. MCP-Maker exists for everything after that:

- **20+ correct tools per table** — pagination, sorting, column selection, date-range filters, full-text search, operator filters, aggregations, distinct values, batch inserts, foreign-key joins, CSV/JSON export. Hand-prompted servers rarely get pagination and SQL quoting right, let alone all of it.
- **Schema-aware, not prompt-aware** — it *inspects* your actual database: primary keys, foreign keys, views, column comments, select-field options. Nothing is hallucinated.
- **Safe by default** — read-only unless you pass `--ops insert,update,delete`; per-table RBAC; identifier escaping everywhere; batch limits.
- **Auto-configures Claude Desktop** — `mcp-maker config --install` and you're done.
- **A standalone file you own** — the generated server has zero runtime dependency on MCP-Maker. Uninstall it; your server keeps working.
- **379 tests** stand behind the generated code — every connector's output is rendered and verified in CI.

> **What is MCP?** The [Model Context Protocol](https://modelcontextprotocol.io/) is the open standard for connecting AI to external tools and data. MCP-Maker auto-generates a complete MCP server from your data source — you don't write a single line of code.

---

## Quick Start

### Generate an MCP Server (for Claude, Cursor, ChatGPT)

```bash
pip install mcp-maker

# Generate from your database
mcp-maker init sqlite:///mydata.db

# Connect to Claude Desktop
mcp-maker config --install

# Restart Claude — your AI can now query your data
```

### Chat directly in your terminal

No Claude needed — talk to your **SQLite** database right from the terminal:

```bash
pip install "mcp-maker[chat]"

# Chat with any SQLite database (no init required)
mcp-maker chat sqlite:///mydata.db
```

> **💡 `init` vs `chat`:** `init` generates a server file for AI clients (Claude, Cursor) and supports **all 13 connectors**. `chat` lets you query directly from the terminal — currently supports **SQLite only** (PostgreSQL and MySQL coming soon).

```
╭──────────────────────────────────╮
│ 💬 MCP-Maker Chat                │
╰──────────── v0.2.7 ─────────────╯
📊 Connected: 3 tables (users, orders, products)
🔧 12 tools available (read-only)
🧠 Provider: OpenAI (gpt-4o-mini)

You > How many orders were placed this month?
🔧 count_orders(date_from='2026-03-01')
There were 47 orders placed this month.

You > Who is our top customer?
🔧 list_orders(order_by='total', order_dir='desc', limit=1)
Your top customer is Sarah Chen with $12,450 in orders.
```

**LLM Providers:** `chat` supports **OpenAI**, **Grok (xAI)**, **DeepSeek**, and **OpenRouter** (500+ models including Claude, Gemini, Llama):

```bash
# OpenAI (default)
mcp-maker chat sqlite:///data.db --api-key sk-xxx

# Grok — auto-detected from the xai- key prefix
mcp-maker chat sqlite:///data.db --api-key xai-xxx --model grok-3-mini

# DeepSeek — use --provider (DeepSeek keys share OpenAI's sk- prefix)
mcp-maker chat sqlite:///data.db --provider deepseek --api-key sk-xxx

# OpenRouter — auto-detected from the sk-or- key prefix
mcp-maker chat sqlite:///data.db --api-key sk-or-xxx --model anthropic/claude-sonnet-4
mcp-maker chat sqlite:///data.db --api-key sk-or-xxx --model google/gemini-2.5-flash
```

Environment variables also work: `OPENAI_API_KEY`, `XAI_API_KEY`, `DEEPSEEK_API_KEY`, `OPENROUTER_API_KEY` (the variable a key comes from selects the provider).

---

## How It Works

```
Your Data Source          MCP-Maker              Output
┌──────────────┐    ┌──────────────────┐    ┌─────────────────────────┐
│ SQLite       │    │                  │    │ 📄 mcp_server.py        │
│ PostgreSQL   │    │                  │    │   ↳ Editable, yours     │
│ MySQL        │───▶│  mcp-maker init  │───▶│                         │
│ Airtable     │    │                  │    │ ⚙️  _autogen_tools.py    │
│ Google Sheets│    │  (auto-inspect)  │    │   ↳ list_users()        │
│ Notion       │    │  (auto-generate) │    │   ↳ search_orders()     │
│ CSV/JSON     │    │                  │    │   ↳ join_tasks_users()   │
│ +6 more      │    └──────────────────┘    └─────────────────────────┘
└──────────────┘                            Standalone Python file ✅
                                            Works forever, even after
                                            uninstalling MCP-Maker
```

MCP-Maker generates a **standalone Python file**. No runtime dependency on MCP-Maker — uninstall it after generation and your server keeps running.

---

## Supported Connectors (13)

| Connector                            | URI Format                                       | Auth         | Install                               |
| ------------------------------------ | ------------------------------------------------ | ------------ | ------------------------------------- |
| **SQLite**                     | `sqlite:///my.db`                              | —           | Built-in                              |
| **Files** (CSV/TSV/JSON/JSONL) | `./data/` or `./users.csv`                   | —           | Built-in                              |
| **PostgreSQL**                 | `postgres://user:pass@host/db`                 | DB creds     | `pip install "mcp-maker[postgres]"` |
| **MySQL**                      | `mysql://user:pass@host/db`                    | DB creds     | `pip install "mcp-maker[mysql]"`    |
| **Airtable**                   | `airtable://appXXXX`                           | API key      | `pip install "mcp-maker[airtable]"` |
| **Google Sheets**              | `gsheet://SPREADSHEET_ID`                      | Service acct | `pip install "mcp-maker[gsheets]"`  |
| **Notion**                     | `notion://DATABASE_ID`                         | Integration  | `pip install "mcp-maker[notion]"`   |
| **Excel**                      | `excel:///path.xlsx`                           | —           | `pip install "mcp-maker[excel]"`    |
| **MongoDB**                    | `mongodb://…` or `mongodb+srv://…` (Atlas) | DB creds     | `pip install "mcp-maker[mongodb]"`  |
| **Supabase**                   | `supabase://PROJECT_REF`                       | API key      | `pip install "mcp-maker[supabase]"` |
| **REST API**                   | `openapi:///spec.yaml`                         | API token    | `pip install "mcp-maker[openapi]"`  |
| **Redis**                      | `redis://host:6379/0`                          | Password     | `pip install "mcp-maker[redis]"`    |
| **HubSpot**                    | `hubspot://pat=TOKEN`                          | PAT          | `pip install "mcp-maker[hubspot]"`  |

```bash
# Install all connectors at once
pip install "mcp-maker[all]"
```

---

## Generated Tools

For each table/collection, MCP-Maker generates:

| Tool                      | Description                                                                      |
| ------------------------- | -------------------------------------------------------------------------------- |
| `list_{table}`          | Paginated listing with filters, sorting, field selection, date ranges            |
| `get_{table}`           | Lookup by primary key                                                            |
| `search_{table}`        | Full-text search across string columns                                           |
| `count_{table}`         | Count with optional filters                                                      |
| `insert_{table}`        | Insert a single record*(with`--ops insert`)*                                   |
| `update_{table}`        | Update by ID*(with`--ops update`)*                                             |
| `delete_{table}`        | Delete by ID*(with`--ops delete`)*                                             |
| `batch_insert_{table}`  | Bulk insert up to 1,000 records in a transaction                                 |
| `batch_delete_{table}`  | Bulk delete by IDs                                                               |
| `aggregate_{table}`     | GROUP BY aggregations (count, sum, avg, min, max)                                |
| `distinct_{table}`      | Distinct values of any column                                                    |
| `filter_{table}`        | Operator-based filtering (eq, gt, lt, contains, …) for file/Excel/Mongo sources |
| `join_{from}_with_{to}` | Cross-table queries via auto-discovered foreign keys                             |
| `call_api`              | Generic escape-hatch call for any endpoint (OpenAPI sources)                     |
| `export_{table}_csv`    | Export to CSV                                                                    |
| `export_{table}_json`   | Export to JSON                                                                   |

Additional tools based on flags: `--semantic` (vector search), `--webhooks` (event hooks), `--audit` (structured logging).

---

## CLI Reference

```bash
# Core
mcp-maker init <source>                       # Generate MCP server
mcp-maker chat <source>                       # Chat with your database (NEW)
mcp-maker serve                               # Run the generated server
mcp-maker inspect <source>                    # Dry run — preview what would be generated

# Configuration
mcp-maker config --install                    # Auto-configure Claude Desktop
mcp-maker env set KEY VALUE                   # Store API keys in .env
mcp-maker env list                            # List stored keys (masked)
mcp-maker list-connectors                     # Show available connectors

# Deployment
mcp-maker deploy --platform railway           # Generate Railway deployment files
mcp-maker deploy --platform render            # Render deployment
mcp-maker deploy --platform fly               # Fly.io deployment

# Generation Options
mcp-maker init <source> --ops read,insert     # Control what the LLM can do
mcp-maker init <source> --tables users,orders # Only expose specific tables
mcp-maker init <source> --async               # Async tools (aiosqlite/asyncpg)
mcp-maker init <source> --auth api-key        # Require MCP_API_KEY for access
mcp-maker init <source> --semantic            # Enable ChromaDB vector search
mcp-maker init <source> --webhooks            # Real-time event notifications
mcp-maker init <source> --audit               # Structured JSON audit logging
mcp-maker init <source> --cache 60            # Cache reads for N seconds
mcp-maker init <source> --no-ssl              # Disable SSL (local dev only)
mcp-maker init <source> --consolidate-threshold 10  # Consolidate large schemas

# Chat Options
mcp-maker chat <source> --api-key sk-xxx      # OpenAI key
mcp-maker chat <source> --api-key sk-or-xxx   # OpenRouter key (auto-detected)
mcp-maker chat <source> --model gpt-4o        # Choose model
mcp-maker chat <source> --provider openrouter # Explicit provider
mcp-maker chat <source> --tables users        # Limit to specific tables
```

---

## Architecture & Security

### Non-Destructive Generation

MCP-Maker generates two files:

- **`mcp_server.py`** — Your editable entry point. Add custom tools, business logic, middleware. Never overwritten on re-generation.
- **`_autogen_mcp_server.py`** — Auto-generated tools. Regenerated safely when you run `init` again.

### Security Features

| Feature                            | Description                                                                                    |
| ---------------------------------- | ---------------------------------------------------------------------------------------------- |
| **Credential Isolation**     | Connection strings and API keys loaded from`.env` — never embedded in generated code        |
| **Granular Permissions**     | `--ops read` (default) prevents writes. Explicitly enable `insert`, `update`, `delete` |
| **API Key Auth**             | `--auth api-key` gates every tool call behind `MCP_API_KEY` validation                     |
| **SSL/TLS by Default**       | PostgreSQL and MySQL connections enforce encrypted transport                                   |
| **SQL Injection Prevention** | Column whitelist validation on all dynamic queries                                             |
| **Batch Limits**             | Bulk operations capped at 1,000 records to prevent resource exhaustion                         |
| **Rate Limiting**            | Built-in token bucket throttling for cloud APIs (Airtable, Notion, Sheets)                     |

### Schema Versioning

MCP-Maker generates a `.mcp-maker.lock` file tracking your schema fingerprint. On re-generation, it detects changes (added/removed tables and columns) and displays a color-coded migration diff before updating tools.

### Large Schema Handling

For schemas with 20+ tables, the `--consolidate-threshold` flag switches from per-table tools to consolidated generic tools (e.g., `query_database`), preventing LLM context window overflow.

---

## MCP Client Compatibility

The generated server works with any MCP-compatible client:

| Client                       | Setup                                         |
| ---------------------------- | --------------------------------------------- |
| **Claude Desktop**     | `mcp-maker config --install` (automatic)    |
| **Cursor**             | Add to Cursor Settings → MCP Servers         |
| **Windsurf**           | Add to`~/.codeium/windsurf/mcp_config.json` |
| **VS Code + Continue** | Add to Continue's MCP config                  |
| **ChatGPT Desktop**    | OpenAI MCP support (rolling out)              |
| **Any MCP client**     | Run`mcp-maker serve` and point to it        |

---

## Installation

```bash
# Core (SQLite + Files + CLI)
pip install mcp-maker

# With chat support (OpenAI / Grok / DeepSeek / OpenRouter)
pip install "mcp-maker[chat]"

# With specific connectors
pip install "mcp-maker[postgres]"
pip install "mcp-maker[airtable]"
pip install "mcp-maker[gsheets]"
pip install "mcp-maker[notion]"

# With async support
pip install "mcp-maker[async-sqlite]"
pip install "mcp-maker[async-postgres]"
pip install "mcp-maker[async-mysql]"

# Everything
pip install "mcp-maker[all]"
```

**Requirements:** Python 3.10+

---

## 📖 Documentation

| Guide                                                          | Description                                      |
| -------------------------------------------------------------- | ------------------------------------------------ |
| **[Getting Started](docs/getting-started.md)**            | Installation, first server, Claude Desktop setup |
| **[CLI &amp; Architecture Reference](docs/reference.md)** | All commands, env vars, security details         |

### Connector Guides

Each guide includes step-by-step setup, examples, and troubleshooting:

| Connector          | Guide                                             |
| ------------------ | ------------------------------------------------- |
| SQLite             | [docs/sqlite.md](docs/sqlite.md)                   |
| Files (CSV/JSON)   | [docs/files.md](docs/files.md)                     |
| PostgreSQL         | [docs/postgresql.md](docs/postgresql.md)           |
| MySQL              | [docs/mysql.md](docs/mysql.md)                     |
| Airtable           | [docs/airtable.md](docs/airtable.md)               |
| Google Sheets      | [docs/google-sheets.md](docs/google-sheets.md)     |
| Notion             | [docs/notion.md](docs/notion.md)                   |
| Excel              | [docs/excel.md](docs/excel.md)                     |
| MongoDB            | [docs/mongodb.md](docs/mongodb.md)                 |
| Supabase           | [docs/supabase.md](docs/supabase.md)               |
| REST API (OpenAPI) | [docs/openapi.md](docs/openapi.md)                 |
| Redis              | [docs/redis.md](docs/redis.md)                     |
| HubSpot            | [docs/hubspot.md](docs/hubspot.md)                 |
| Semantic Search    | [docs/semantic-search.md](docs/semantic-search.md) |

---

## Contributing

MCP-Maker is designed for community contributions — each connector is a self-contained PR.

See **[CONTRIBUTING.md](CONTRIBUTING.md)** for a step-by-step guide.

```bash
git clone https://github.com/MrAliHasan/mcp-maker.git
cd mcp-maker
make install    # Set up dev environment
make check      # Run lint + tests (379 tests)
```

## Security

Found a vulnerability? Please report it privately via **[SECURITY.md](SECURITY.md)**.

## License

[MIT License](LICENSE) · [Code of Conduct](CODE_OF_CONDUCT.md)
