"""
MCP-Maker Supabase Connector — Inspect Supabase databases.

Built on Postgres but uses the Supabase Python client for a richer experience.
Requires SUPABASE_URL and SUPABASE_KEY environment variables.
"""

import os

from ..core.schema import (
    Column,
    ColumnType,
    DataSourceSchema,
    Table,
)
from .base import BaseConnector, register_connector


class SupabaseConnector(BaseConnector):
    """Connector for Supabase databases.

    Uses the Supabase Python client to inspect tables and generate tools
    that include Supabase-specific features (auth, storage).

    URI format: supabase://PROJECT_REF
    Requires: SUPABASE_URL and SUPABASE_KEY environment variables.
    """

    @property
    def source_type(self) -> str:
        return "supabase"

    def _get_config(self) -> tuple[str, str]:
        """Get Supabase URL and key from environment."""
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))

        if not url:
            # Try to construct from project ref in URI
            ref = self.uri
            if ref.startswith("supabase://"):
                ref = ref[len("supabase://"):]
            if ref:
                url = f"https://{ref}.supabase.co"

        if not url:
            raise ValueError(
                "SUPABASE_URL environment variable is required. "
                "Example: https://your-project.supabase.co"
            )
        if not key:
            raise ValueError(
                "SUPABASE_KEY or SUPABASE_ANON_KEY environment variable is required. "
                "Find it in your Supabase dashboard under Settings > API."
            )
        return url, key

    def validate(self) -> bool:
        """Check that the Supabase project is accessible.

        Hits the PostgREST root endpoint and verifies the response status,
        so a wrong URL or key fails here instead of during inspect().
        """
        try:
            import httpx
        except ImportError:
            raise ImportError(
                "httpx is required for Supabase support. "
                "Install it with: pip install mcp-maker[supabase]"
            )

        url, key = self._get_config()
        try:
            resp = httpx.get(
                f"{url}/rest/v1/",
                headers={"apikey": key, "Authorization": f"Bearer {key}"},
                timeout=15,
            )
        except Exception as e:
            raise ConnectionError(f"Cannot reach Supabase at {url}: {e}")

        if resp.status_code in (401, 403):
            raise ConnectionError(
                "Supabase rejected the API key (HTTP "
                f"{resp.status_code}). Check SUPABASE_KEY / SUPABASE_ANON_KEY."
            )
        if resp.status_code != 200:
            raise ConnectionError(
                f"Supabase REST API returned HTTP {resp.status_code} for {url}."
            )
        return True

    def inspect(self) -> DataSourceSchema:
        """Inspect the Supabase database and return its schema."""
        import httpx

        url, key = self._get_config()

        # Use PostgREST endpoint to get table schema
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
        }

        # Get table list from PostgREST OpenAPI endpoint
        resp = httpx.get(f"{url}/rest/v1/", headers=headers, timeout=30)
        if resp.status_code != 200:
            raise ConnectionError(f"Cannot reach Supabase REST API: {resp.status_code}")

        openapi_spec = resp.json()
        definitions = openapi_spec.get("definitions", {})

        tables = []
        for table_name, schema_def in sorted(definitions.items()):
            properties = schema_def.get("properties", {})
            required_fields = set(schema_def.get("required", []))

            columns = []
            for col_name, col_schema in sorted(properties.items()):
                col_format = col_schema.get("format", "")
                col_schema.get("type", "string")

                # Map Supabase/PostgREST types
                if col_format in ("bigint", "integer", "smallint"):
                    col_type = ColumnType.INTEGER
                elif col_format in ("double precision", "real", "numeric"):
                    col_type = ColumnType.FLOAT
                elif col_format == "boolean":
                    col_type = ColumnType.BOOLEAN
                elif col_format in ("timestamp with time zone", "timestamp without time zone"):
                    col_type = ColumnType.DATETIME
                elif col_format == "date":
                    col_type = ColumnType.DATE
                elif col_format == "jsonb" or col_format == "json":
                    col_type = ColumnType.JSON
                else:
                    col_type = ColumnType.STRING

                # Detect primary key from description
                description = col_schema.get("description", "")
                is_pk = "primary key" in description.lower()

                columns.append(Column(
                    name=col_name,
                    type=col_type,
                    nullable=col_name not in required_fields,
                    primary_key=is_pk,
                    description=col_format,
                ))

            # Get row count via the REST API
            try:
                count_resp = httpx.get(
                    f"{url}/rest/v1/{table_name}",
                    headers={**headers, "Range": "0-0", "Prefer": "count=exact"},
                    timeout=15,
                )
                content_range = count_resp.headers.get("Content-Range", "")
                row_count = int(content_range.split("/")[-1]) if "/" in content_range else None
            except Exception:
                row_count = None

            tables.append(Table(
                name=table_name,
                columns=columns,
                row_count=row_count,
            ))

        return DataSourceSchema(
            source_type="supabase",
            source_uri=self.uri,
            tables=tables,
            metadata={
                "supabase_url": url,
                "project_ref": url.split("//")[1].split(".")[0] if "//" in url else "",
            },
        )


# Register this connector
register_connector("supabase", SupabaseConnector)
