# HubSpot Connector

Connect MCP-Maker to your HubSpot CRM to auto-generate tools for contacts, companies, deals, tickets, and custom objects.

## Prerequisites

- A HubSpot account with a [Private App](https://developers.hubspot.com/docs/api/private-apps) created
- A Private App Token (PAT) with the required scopes

### Required Scopes

| Scope | Used For |
|-------|----------|
| `crm.objects.contacts.read` | Reading contacts |
| `crm.objects.contacts.write` | Creating/updating contacts |
| `crm.objects.companies.read` | Reading companies |
| `crm.objects.companies.write` | Creating/updating companies |
| `crm.objects.deals.read` | Reading deals and pipelines |
| `crm.objects.deals.write` | Creating/updating deals |
| `crm.schemas.contacts.read` | Discovering custom properties |
| `crm.schemas.companies.read` | Discovering custom properties |
| `crm.schemas.deals.read` | Discovering custom properties |

> **Tip:** Grant all `crm.objects.*.read` and `crm.schemas.*.read` scopes to allow MCP-Maker to fully discover your CRM schema.

## Installation

```bash
pip install "mcp-maker[hubspot]"
```

## Quick Start

### Step 1: Store your token

```bash
mcp-maker env set HUBSPOT_ACCESS_TOKEN pat-na1-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Or pass it directly in the URI:

```bash
mcp-maker init "hubspot://pat=YOUR_TOKEN"
```

### Step 2: Generate the server

```bash
# Using environment variable (recommended)
mcp-maker init hubspot://

# Using inline token
mcp-maker init "hubspot://pat=pat-na1-xxxxxxxx"

# With write operations
mcp-maker init hubspot:// --ops read,insert,update

# Only specific objects
mcp-maker init hubspot:// --tables contacts,deals
```

### Step 3: Connect to Claude Desktop

```bash
mcp-maker config --install
```

## Generated Tools

### New in 0.2.7

- Custom objects with special characters in their names now generate valid tools that call the correct API endpoints
- Failed record counts report "unknown" instead of a misleading 0

For each CRM object type discovered, MCP-Maker generates:

| Tool | Description |
|------|-------------|
| `list_{object}` | List records with pagination and filters |
| `get_{object}_by_id` | Get a single record by HubSpot ID |
| `search_{object}` | Full-text search across all properties |
| `insert_{object}` | Create a new record (requires `--ops insert`) |
| `update_{object}` | Update an existing record (requires `--ops update`) |
| `export_{object}_csv` | Export records as CSV |
| `export_{object}_json` | Export records as JSON |

### Example: Contacts

```python
# Auto-generated tool signatures
list_contacts(limit=100, offset=0)
get_contacts_by_id(id: str)
search_contacts(query: str)
insert_contacts(email: str, firstname: str, lastname: str, ...)
```

## Features

### Custom Property Discovery

MCP-Maker automatically discovers all custom properties in your HubSpot portal. Properties are mapped to MCP tool parameters with appropriate types:

| HubSpot Type | MCP Type |
|-------------|----------|
| `string`, `phonenumber`, `enumeration` | `STRING` |
| `number` | `FLOAT` |
| `bool` | `BOOLEAN` |
| `date`, `datetime` | `DATETIME` |

### Deal Pipeline Mapping

Deal pipelines and stages are automatically discovered and mapped. The generated tools include pipeline-aware filtering:

```bash
# Ask Claude:
"Show me all deals in the Sales Pipeline at the Proposal stage"
```

### Owner ID Resolution

HubSpot stores owners as numeric IDs. MCP-Maker resolves `owner_id` fields to human-readable names in the generated schema, so Claude can display "John Smith" instead of "12345678".

### Batch Operations

With `--ops insert`, batch upsert tools are generated for bulk data import:

```bash
mcp-maker init hubspot:// --ops read,insert
# Generates: batch_insert_contacts, batch_insert_companies, etc.
```

## Authentication

### Option 1: Environment Variable (Recommended)

```bash
export HUBSPOT_ACCESS_TOKEN="pat-na1-xxxxxxxx"
mcp-maker init hubspot://
```

### Option 2: URI Parameter

```bash
mcp-maker init "hubspot://pat=pat-na1-xxxxxxxx"
```

> **Security Note:** When using URI parameters, the token is never logged or included in error messages. MCP-Maker automatically redacts tokens in all output.

### Option 3: .env File

```bash
mcp-maker env set HUBSPOT_ACCESS_TOKEN pat-na1-xxxxxxxx
source .env
mcp-maker init hubspot://
```

## Example Claude Conversations

**User:** "How many contacts do we have?"

**Claude:** Uses `list_contacts(limit=1)` → reads `total` from response → "You have 2,847 contacts."

---

**User:** "Find all deals worth more than $50,000 in the Enterprise pipeline"

**Claude:** Uses `list_deals(limit=100)` with filters → returns matching deals with amounts and stages.

---

**User:** "Add a new contact: Jane Smith, jane@example.com, VP of Engineering"

**Claude:** Uses `insert_contacts(email="jane@example.com", firstname="Jane", lastname="Smith", jobtitle="VP of Engineering")` → confirms creation.

## Troubleshooting

### "HubSpot Private App Token not found"

Your token wasn't found. Either:
1. Set `HUBSPOT_ACCESS_TOKEN` environment variable
2. Pass it in the URI: `hubspot://pat=YOUR_TOKEN`

### "403 Forbidden" errors

Your Private App doesn't have the required scopes. Go to **HubSpot → Settings → Integrations → Private Apps** and add the missing scopes listed above.

### "429 Too Many Requests"

MCP-Maker includes built-in rate limiting for HubSpot's API (100 requests per 10 seconds). If you still hit limits, you may have other integrations consuming your quota.

### Only some objects appear

MCP-Maker discovers objects based on your token's scopes. If `tickets` don't appear, ensure your Private App has `crm.objects.tickets.read` scope.

## Limitations

- **Association discovery** is limited to standard associations (contact→company, deal→contact). Custom associations require manual tool additions.
- **Custom objects** require `crm.schemas.custom.read` scope and may not be discovered on all HubSpot plans.
- **File/attachment properties** are returned as URLs, not downloaded.
