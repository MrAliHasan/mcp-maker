"""
MCP-Maker Notion Connector — Inspect Notion databases.

Features:
    - Database property discovery (maps Notion prop types to ColumnType)
    - Page/record querying
    - Rich property type mapping
    - Internal integration token authentication

URI format: notion://DATABASE_ID
Auth: NOTION_API_KEY env var (internal integration token)
"""

import os
import re

from ..core.schema import (
    Column,
    ColumnType,
    DataSourceSchema,
    Table,
)
from .base import BaseConnector, register_connector

# Map Notion property types to our universal ColumnType
NOTION_TYPE_MAP = {
    # Text
    "title": ColumnType.STRING,
    "rich_text": ColumnType.STRING,
    "url": ColumnType.STRING,
    "email": ColumnType.STRING,
    "phone_number": ColumnType.STRING,
    # Numbers
    "number": ColumnType.FLOAT,
    "unique_id": ColumnType.INTEGER,
    # Boolean
    "checkbox": ColumnType.BOOLEAN,
    # Dates
    "date": ColumnType.DATETIME,
    "created_time": ColumnType.DATETIME,
    "last_edited_time": ColumnType.DATETIME,
    # Select
    "select": ColumnType.STRING,
    "status": ColumnType.STRING,
    # Multi/complex
    "multi_select": ColumnType.JSON,
    "people": ColumnType.JSON,
    "files": ColumnType.JSON,
    "relation": ColumnType.JSON,
    "rollup": ColumnType.JSON,
    "formula": ColumnType.STRING,
    # Created/edited by
    "created_by": ColumnType.JSON,
    "last_edited_by": ColumnType.JSON,
}


from .utils import sanitize_name as _sanitize_name  # noqa: E402


def _extract_property_value(prop: dict) -> any:
    """Extract a plain Python value from a Notion property object."""
    prop_type = prop.get("type", "")

    if prop_type == "title":
        parts = prop.get("title", [])
        return "".join(p.get("plain_text", "") for p in parts)

    elif prop_type == "rich_text":
        parts = prop.get("rich_text", [])
        return "".join(p.get("plain_text", "") for p in parts)

    elif prop_type == "number":
        return prop.get("number")

    elif prop_type == "checkbox":
        return prop.get("checkbox", False)

    elif prop_type == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else None

    elif prop_type == "multi_select":
        return [s.get("name", "") for s in prop.get("multi_select", [])]

    elif prop_type == "status":
        status = prop.get("status")
        return status.get("name", "") if status else None

    elif prop_type == "date":
        date_obj = prop.get("date")
        if date_obj:
            return date_obj.get("start")
        return None

    elif prop_type == "url":
        return prop.get("url")

    elif prop_type == "email":
        return prop.get("email")

    elif prop_type == "phone_number":
        return prop.get("phone_number")

    elif prop_type == "created_time":
        return prop.get("created_time")

    elif prop_type == "last_edited_time":
        return prop.get("last_edited_time")

    elif prop_type == "people":
        return [p.get("name", p.get("id", "")) for p in prop.get("people", [])]

    elif prop_type == "files":
        files = prop.get("files", [])
        return [f.get("name", f.get("external", {}).get("url", "")) for f in files]

    elif prop_type == "relation":
        return [r.get("id", "") for r in prop.get("relation", [])]

    elif prop_type == "formula":
        formula = prop.get("formula", {})
        f_type = formula.get("type", "")
        return formula.get(f_type)

    elif prop_type == "rollup":
        rollup = prop.get("rollup", {})
        r_type = rollup.get("type", "")
        if r_type == "array":
            return rollup.get("array", [])
        return rollup.get(r_type)

    elif prop_type == "unique_id":
        uid = prop.get("unique_id", {})
        prefix = uid.get("prefix", "")
        number = uid.get("number", 0)
        return f"{prefix}-{number}" if prefix else str(number)

    elif prop_type in ("created_by", "last_edited_by"):
        user = prop.get(prop_type, {})
        return user.get("name", user.get("id", ""))

    return str(prop.get(prop_type, ""))


class NotionConnector(BaseConnector):
    """Connector for Notion databases.

    Inspects a Notion database's properties and discovers page structure.

    Authentication:
        Set NOTION_API_KEY to your internal integration token.
        Create one at: https://www.notion.so/my-integrations

    URI format:
        notion://DATABASE_ID
        notion://DATABASE_ID,DATABASE_ID2  (multiple databases)
    """

    @property
    def source_type(self) -> str:
        return "notion"

    def _get_database_ids(self) -> list[str]:
        """Extract database ID(s) from URI."""
        uri = self.uri
        if uri.startswith("notion://"):
            raw = uri[len("notion://"):]
        else:
            raw = uri

        # Handle comma-separated IDs
        ids = [db_id.strip() for db_id in raw.split(",") if db_id.strip()]

        # Clean up IDs — remove dashes if present (Notion IDs can be with or without)
        cleaned = []
        for db_id in ids:
            # If it looks like a URL, extract the ID
            if "notion.so" in db_id or "notion.site" in db_id:
                match = re.search(r"([a-f0-9]{32})", db_id.replace("-", ""))
                if match:
                    cleaned.append(match.group(1))
            else:
                cleaned.append(db_id.replace("-", ""))
        return cleaned if cleaned else ids

    def _get_api_key(self) -> str:
        """Get the Notion API key from environment."""
        key = os.environ.get("NOTION_API_KEY") or os.environ.get("NOTION_TOKEN")
        if not key:
            raise ValueError(
                "Notion API key not found.\n"
                "Set the NOTION_API_KEY environment variable:\n"
                "  export NOTION_API_KEY=ntn_xxxxxxxxxxxx\n"
                "Create an integration at: https://www.notion.so/my-integrations"
            )
        return key

    def _get_client(self):
        """Get a Notion client."""
        from notion_client import Client
        return Client(auth=self._get_api_key())

    def validate(self) -> bool:
        """Check that notion-client is installed and credentials work."""
        try:
            from notion_client import Client  # noqa: F401
        except ImportError:
            raise ImportError(
                "Notion support requires notion-client.\n"
                "Install it with: pip install mcp-maker[notion]"
            )

        client = self._get_client()
        db_ids = self._get_database_ids()

        for db_id in db_ids:
            try:
                client.databases.retrieve(database_id=db_id)
            except Exception as e:
                raise ConnectionError(
                    f"Cannot access Notion database {db_id}: {e}\n"
                    "Make sure the database is connected to your integration."
                )
        return True

    def inspect(self) -> DataSourceSchema:
        """Inspect Notion database(s) and return schema."""

        client = self._get_client()
        db_ids = self._get_database_ids()

        tables = []
        db_name_map = {}  # safe_name -> database_id
        db_title_map = {}  # safe_name -> original_title
        select_options_map = {}  # safe_table -> {safe_field: [options]}

        for db_id in db_ids:
            db_info = client.databases.retrieve(database_id=db_id)

            # Get database title
            title_parts = db_info.get("title", [])
            original_title = "".join(p.get("plain_text", "") for p in title_parts)
            if not original_title:
                original_title = db_id[:8]
            safe_name = _sanitize_name(original_title)

            # Avoid name collisions
            if safe_name in db_name_map:
                safe_name = f"{safe_name}_{db_id[:6]}"

            db_name_map[safe_name] = db_id
            db_title_map[safe_name] = original_title

            # Discover properties
            properties = db_info.get("properties", {})
            columns = []
            field_opts = {}

            for prop_name, prop_info in properties.items():
                prop_type = prop_info.get("type", "rich_text")
                col_type = NOTION_TYPE_MAP.get(prop_type, ColumnType.STRING)
                safe_field = _sanitize_name(prop_name)

                # Extract select/multi_select/status options
                if prop_type in ("select", "multi_select", "status"):
                    opts_container = prop_info.get(prop_type, {})
                    if isinstance(opts_container, dict):
                        options = opts_container.get("options", [])
                        if options:
                            field_opts[safe_field] = [
                                o.get("name", "") for o in options
                            ]

                columns.append(Column(
                    name=safe_field,
                    type=col_type,
                    nullable=True,
                    primary_key=False,
                    description=prop_name,
                ))

            select_options_map[safe_name] = field_opts

            # Get row count via paginated query, capped at 10 pages (1,000
            # records) so huge databases don't hammer the API. Beyond the
            # cap the count is reported as unknown.
            try:
                row_count = 0
                has_more = True
                start_cursor = None
                pages_fetched = 0
                while has_more and pages_fetched < 10:
                    query_result = client.databases.query(
                        database_id=db_id,
                        page_size=100,
                        **({"start_cursor": start_cursor} if start_cursor else {}),
                    )
                    row_count += len(query_result.get("results", []))
                    has_more = query_result.get("has_more", False)
                    start_cursor = query_result.get("next_cursor")
                    pages_fetched += 1
                if has_more:
                    row_count = None
            except Exception:
                row_count = None

            tables.append(Table(
                name=safe_name,
                columns=columns,
                row_count=row_count,
                description=original_title,
            ))

        return DataSourceSchema(
            source_type="notion",
            source_uri=self.uri,
            tables=tables,
            metadata={
                "database_map": db_name_map,
                "title_map": db_title_map,
                "select_options_map": select_options_map,
            },
        )


# Register this connector
register_connector("notion", NotionConnector)
