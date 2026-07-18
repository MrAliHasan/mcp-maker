"""
MCP-Maker OpenAPI Connector — Generate MCP tools from an OpenAPI/Swagger spec.

Each API endpoint becomes a tool. Supports OpenAPI 3.x and Swagger 2.x specs.
"""

import os

from ..core.schema import (
    Column,
    ColumnType,
    DataSourceSchema,
    Table,
)
from .base import BaseConnector, register_connector


def _openapi_type_to_column_type(param_schema: dict) -> ColumnType:
    """Map OpenAPI param types to ColumnType."""
    type_str = param_schema.get("type", "string")
    format_str = param_schema.get("format", "")
    mapping = {
        "integer": ColumnType.INTEGER,
        "number": ColumnType.FLOAT,
        "boolean": ColumnType.BOOLEAN,
        "array": ColumnType.JSON,
        "object": ColumnType.JSON,
    }
    if type_str in mapping:
        return mapping[type_str]
    if format_str in ("date", "date-time"):
        return ColumnType.DATETIME
    return ColumnType.STRING


def _sanitize_operation_id(method: str, path: str) -> str:
    """Create a safe function name from HTTP method + path."""
    # /users/{id}/posts → users_id_posts
    clean_path = path.strip("/").replace("{", "").replace("}", "")
    clean_path = clean_path.replace("/", "_").replace("-", "_")
    return f"{method}_{clean_path}"


def _resolve_ref(node, spec: dict, _depth: int = 0):
    """Resolve local $ref pointers ('#/components/…', '#/definitions/…').

    Returns the node with any top-level $ref replaced by its target.
    Nested refs inside the returned object are resolved lazily by callers
    that pass their sub-schemas back through this function.
    """
    while isinstance(node, dict) and "$ref" in node and _depth < 20:
        ref = node["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            break  # external/remote refs are not supported
        target = spec
        for part in ref[2:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            if not isinstance(target, dict) or part not in target:
                return node  # dangling ref — return as-is
            target = target[part]
        node = target
        _depth += 1
    return node


class OpenAPIConnector(BaseConnector):
    """Connector for OpenAPI/Swagger specs.

    Parses an OpenAPI 3.x or Swagger 2.x spec and generates MCP tools
    for each endpoint.

    URI format:
        openapi:///path/to/spec.yaml
        openapi:///path/to/spec.json
        openapi://https://api.example.com/openapi.json
    """

    @property
    def source_type(self) -> str:
        return "openapi"

    def _get_spec_path(self) -> str:
        """Extract the spec file path or URL from the URI."""
        path = self.uri
        if path.startswith("openapi:///"):
            path = path[len("openapi:///"):]
        elif path.startswith("openapi://"):
            path = path[len("openapi://"):]
        return path

    def _load_spec(self) -> dict:
        """Load the OpenAPI spec from file or URL."""
        import json

        spec_path = self._get_spec_path()

        # Check if it's a URL
        if spec_path.startswith("http://") or spec_path.startswith("https://"):
            import httpx
            resp = httpx.get(spec_path, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            if spec_path.endswith(".yaml") or spec_path.endswith(".yml"):
                import yaml
                return yaml.safe_load(resp.text)
            try:
                return resp.json()
            except ValueError:
                # Some servers serve YAML without a .yaml extension
                import yaml
                return yaml.safe_load(resp.text)

        # Local file
        spec_path = os.path.expanduser(spec_path)
        with open(spec_path, encoding="utf-8") as f:
            content = f.read()

        ext = os.path.splitext(spec_path)[1].lower()
        if ext in (".yaml", ".yml"):
            import yaml
            return yaml.safe_load(content)
        return json.loads(content)

    def validate(self) -> bool:
        """Check that the spec file exists and is valid."""
        try:
            spec = self._load_spec()
        except Exception as e:
            raise ValueError(f"Cannot load OpenAPI spec: {e}")

        # Basic structure validation
        if "openapi" not in spec and "swagger" not in spec:
            raise ValueError("Not a valid OpenAPI/Swagger spec: missing 'openapi' or 'swagger' key")

        if "paths" not in spec:
            raise ValueError("OpenAPI spec has no 'paths' defined")

        return True

    def inspect(self) -> DataSourceSchema:
        """Inspect the OpenAPI spec and return its schema.

        Each endpoint path becomes a "table" with:
        - Table name = sanitized operation ID
        - Columns = path params + query params + request body fields
        """
        spec = self._load_spec()
        paths = spec.get("paths", {})
        base_url = ""

        # Extract base URL
        if "servers" in spec:  # OpenAPI 3.x
            base_url = spec["servers"][0].get("url", "")
        elif "host" in spec:  # Swagger 2.x
            scheme = (spec.get("schemes") or ["https"])[0]
            base_url = f"{scheme}://{spec['host']}{spec.get('basePath', '')}"

        tables = []
        used_names: dict[str, int] = {}

        for path, methods in sorted(paths.items()):
            if not isinstance(methods, dict):
                continue
            # Path-level parameters are shared by every operation on the path
            shared_params = [
                _resolve_ref(p, spec) for p in methods.get("parameters", [])
            ]

            for method, endpoint in sorted(methods.items()):
                if method.lower() not in ("get", "post", "put", "patch", "delete"):
                    continue
                endpoint = _resolve_ref(endpoint, spec)

                operation_id = endpoint.get("operationId", _sanitize_operation_id(method, path))
                summary = endpoint.get("summary", f"{method.upper()} {path}")

                columns = []

                # Add HTTP method and path as metadata columns
                columns.append(Column(
                    name="_method",
                    type=ColumnType.STRING,
                    nullable=False,
                    description=method.upper(),
                ))
                columns.append(Column(
                    name="_path",
                    type=ColumnType.STRING,
                    nullable=False,
                    description=path,
                ))

                # Parse parameters (path-level + operation-level)
                params = shared_params + [
                    _resolve_ref(p, spec) for p in endpoint.get("parameters", [])
                ]
                body_schema = None
                for param in params:
                    if not isinstance(param, dict) or "name" not in param:
                        continue
                    # Swagger 2.x body params carry a schema instead of a type
                    if param.get("in") == "body":
                        body_schema = _resolve_ref(param.get("schema", {}), spec)
                        continue
                    param_schema = _resolve_ref(param.get("schema", param), spec)
                    columns.append(Column(
                        name=param["name"],
                        type=_openapi_type_to_column_type(param_schema),
                        nullable=not param.get("required", False),
                        description=f"{param.get('in', 'query')} param",
                    ))

                # Parse request body (OpenAPI 3.x), falling back to the
                # Swagger 2.x body param schema captured above
                request_body = _resolve_ref(endpoint.get("requestBody", {}), spec)
                if request_body:
                    content = request_body.get("content", {})
                    body_schema = _resolve_ref(
                        content.get("application/json", {}).get("schema", {}), spec
                    )
                if body_schema:
                    properties = body_schema.get("properties", {})
                    required = set(body_schema.get("required", []))
                    for prop_name, prop_schema in sorted(properties.items()):
                        prop_schema = _resolve_ref(prop_schema, spec)
                        columns.append(Column(
                            name=prop_name,
                            type=_openapi_type_to_column_type(prop_schema),
                            nullable=prop_name not in required,
                            description="body field",
                        ))

                safe_name = operation_id.replace("-", "_").replace(".", "_").lower()
                # De-duplicate colliding operation IDs
                if safe_name in used_names:
                    used_names[safe_name] += 1
                    safe_name = f"{safe_name}_{used_names[safe_name]}"
                else:
                    used_names[safe_name] = 1

                tables.append(Table(
                    name=safe_name,
                    columns=columns,
                    description=summary,
                ))

        return DataSourceSchema(
            source_type="openapi",
            source_uri=self.uri,
            tables=tables,
            metadata={
                "base_url": base_url,
                "spec_title": spec.get("info", {}).get("title", ""),
                "spec_version": spec.get("info", {}).get("version", ""),
                "endpoint_count": len(tables),
            },
        )


# Register this connector
register_connector("openapi", OpenAPIConnector)
