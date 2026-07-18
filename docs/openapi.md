# REST API (OpenAPI) Connector

Pass an OpenAPI or Swagger spec to auto-generate MCP tools for every API endpoint.

```bash
pip install mcp-maker[openapi]
```

---

## Quick Start

```bash
# From a local spec file
mcp-maker init openapi:///path/to/api-spec.yaml

# From a remote URL
mcp-maker init openapi://https://petstore3.swagger.io/api/v3/openapi.json

mcp-maker serve
```

Every API endpoint becomes an MCP tool that your AI can call.

---

## URI Format

```
openapi:///path/to/spec.yaml              # Local YAML file
openapi:///path/to/spec.json              # Local JSON file
openapi://https://api.example.com/openapi.json  # Remote spec URL
```

Supports:
- **OpenAPI 3.x** (recommended)
- **Swagger 2.x** (legacy)

---

## What Gets Generated

### New in 0.2.7

- `call_api(method, path, query_params, body)` — generic escape hatch for any endpoint
- **`$ref` schemas are now resolved** — request bodies defined via `#/components/schemas/...` produce full typed parameters
- Swagger 2.x `in: body` parameters and path-level shared parameters are now supported
- Three auth styles via env vars: `API_TOKEN` (Bearer), `API_KEY` + `API_KEY_HEADER` (custom header), `API_KEY` + `API_KEY_QUERY` (query param)
- HTTP errors return structured `{error, status, body}` results instead of raising

Each endpoint in your API spec becomes a tool:

```
GET  /users          →  get_users(limit, offset)
GET  /users/{id}     →  get_users_id(id)
POST /users          →  post_users(name, email)
PUT  /users/{id}     →  put_users_id(id, name, email)
DELETE /users/{id}   →  delete_users_id(id)
```

Parameters are extracted from:
- **Path parameters** (`/users/{id}` → `id` argument)
- **Query parameters** (`?limit=10` → `limit` argument)
- **Request body** (JSON body → individual arguments)

---

## Example: Complete Walkthrough

### 1. You have an API spec

The [Petstore](https://petstore3.swagger.io/) OpenAPI spec:

```bash
mcp-maker init openapi://https://petstore3.swagger.io/api/v3/openapi.json
```

```
⚒️ MCP-Maker                                         v0.3.0

  ✅ Connected to openapi source

  ┌────────────────────────────────────────────────────────┐
  │ 📊 Discovered Endpoints (15)                           │
  ├──────────────────┬─────────────────────────────────────┤
  │ Tool             │ Description                         │
  ├──────────────────┼─────────────────────────────────────┤
  │ get_pet_petid    │ GET /pet/{petId}                    │
  │ post_pet         │ POST /pet                           │
  │ get_store_inv    │ GET /store/inventory                │
  │ ...              │ ...                                 │
  └──────────────────┴─────────────────────────────────────┘

  🎉 Generated: mcp_server.py
```

### 2. Set API authentication (if needed)

```bash
export API_TOKEN="your-bearer-token"
# or
export API_KEY="your-api-key"
```

### 3. Run and connect

```bash
mcp-maker serve
mcp-maker config --install
```

### 4. Ask Claude

> **You:** "Get the pet with ID 1"
>
> **Claude:** *calls `get_pet_petid(petId=1)`*

> **You:** "Create a new pet named Max"
>
> **Claude:** *calls `post_pet(name="Max", status="available")`*

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `API_TOKEN` | Optional | Bearer token for API authentication |
| `API_KEY` | Optional | Alternative API key variable |

The generated server checks both variables and sends the token as a `Bearer` authorization header.

---

## How It Works

1. **Parse**: Reads the OpenAPI/Swagger spec (YAML or JSON)
2. **Map**: Each endpoint path + HTTP method → one MCP tool function
3. **Generate**: Uses `httpx` for HTTP calls with connection pooling
4. **Serve**: Tools call the real API when invoked

```
OpenAPI Spec → MCP-Maker → MCP Tool → httpx → Your API
```

---

## Tips

- **Operation IDs**: If your spec has `operationId` fields, those are used as tool names. Otherwise, MCP-Maker generates names from the HTTP method and path.
- **Base URL**: Extracted from the spec's `servers` (OpenAPI 3.x) or `host` + `basePath` (Swagger 2.x).
- **Connection pooling**: The generated server uses a persistent `httpx.Client` for efficient connection reuse.
- **Error handling**: Non-2xx responses raise `httpx.HTTPStatusError` with the full response.

---

## Troubleshooting

### "Cannot load OpenAPI spec"

Make sure your spec file is valid YAML or JSON:
```bash
# Validate locally
python -c "import yaml; yaml.safe_load(open('spec.yaml'))"
```

### "Not a valid OpenAPI/Swagger spec"

The spec must have either an `openapi` key (3.x) or `swagger` key (2.x) at the top level.

### "pyyaml is required"

For YAML specs, install the YAML parser:
```bash
pip install mcp-maker[openapi]
```
