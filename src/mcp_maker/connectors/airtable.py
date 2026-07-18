"""
MCP-Maker Airtable Connector — Inspect Airtable bases.

Features:
    - Table discovery with full field type mapping
    - View discovery for each table
    - Safe Python identifier generation for tables/fields
    - Row count via lightweight record fetch
"""

import os

from ..core.schema import (
    Column,
    ColumnType,
    DataSourceSchema,
    Table,
)
from .base import BaseConnector, register_connector

# Map Airtable field types to our universal ColumnType
AIRTABLE_TYPE_MAP = {
    # Text
    "singleLineText": ColumnType.STRING,
    "multilineText": ColumnType.STRING,
    "richText": ColumnType.STRING,
    "email": ColumnType.STRING,
    "url": ColumnType.STRING,
    "phoneNumber": ColumnType.STRING,
    # Numbers
    "number": ColumnType.FLOAT,
    "currency": ColumnType.FLOAT,
    "percent": ColumnType.FLOAT,
    "rating": ColumnType.INTEGER,
    "duration": ColumnType.INTEGER,
    "count": ColumnType.INTEGER,
    "autoNumber": ColumnType.INTEGER,
    # Boolean
    "checkbox": ColumnType.BOOLEAN,
    # Dates
    "date": ColumnType.DATE,
    "dateTime": ColumnType.DATETIME,
    "createdTime": ColumnType.DATETIME,
    "lastModifiedTime": ColumnType.DATETIME,
    # Select
    "singleSelect": ColumnType.STRING,
    # Complex/JSON
    "multipleSelects": ColumnType.JSON,
    "singleCollaborator": ColumnType.JSON,
    "multipleCollaborators": ColumnType.JSON,
    "multipleRecordLinks": ColumnType.JSON,
    "multipleAttachments": ColumnType.JSON,
    "lookup": ColumnType.JSON,
    "button": ColumnType.JSON,
    # Computed
    "barcode": ColumnType.STRING,
    "formula": ColumnType.STRING,
    "rollup": ColumnType.STRING,
    "externalSyncSource": ColumnType.STRING,
    "aiText": ColumnType.STRING,
    "lastModifiedBy": ColumnType.JSON,
    "createdBy": ColumnType.JSON,
}


from .utils import sanitize_name as _sanitize_name  # noqa: E402


class AirtableConnector(BaseConnector):
    """Connector for Airtable bases.

    Inspects all tables, fields, field types, and views from an Airtable base.
    Requires the AIRTABLE_API_KEY environment variable to be set
    (a Personal Access Token from https://airtable.com/create/tokens).

    URI format: airtable://BASE_ID

    Generated servers include:
        - list, search, count, schema, get_by_record_id tools
        - filter_by_formula tool for Airtable formula-based queries
        - list_by_view tool for view-based listing
        - create, update, delete tools (with --read-write flag)
    """

    @property
    def source_type(self) -> str:
        return "airtable"

    def _get_base_id(self) -> str:
        """Extract the base ID from the URI."""
        uri = self.uri
        if uri.startswith("airtable://"):
            return uri[len("airtable://"):]
        return uri

    def _get_api_key(self) -> str:
        """Get the Airtable API key from environment."""
        key = os.environ.get("AIRTABLE_API_KEY") or os.environ.get("AIRTABLE_TOKEN")
        if not key:
            raise ValueError(
                "Airtable API key not found.\n"
                "Set the AIRTABLE_API_KEY environment variable:\n"
                "  export AIRTABLE_API_KEY=pat_xxxxxxxxxxxx\n"
                "Get a token from: https://airtable.com/create/tokens"
            )
        return key

    def validate(self) -> bool:
        """Check that the Airtable base is accessible."""
        try:
            from pyairtable import Api
        except ImportError:
            raise ImportError(
                "Airtable support requires pyairtable.\n"
                "Install it with: pip install mcp-maker[airtable]"
            )

        api_key = self._get_api_key()
        base_id = self._get_base_id()

        try:
            api = Api(api_key)
            base = api.base(base_id)
            # Fetch schema to validate the base exists
            base.schema()
            return True
        except Exception as e:
            raise ConnectionError(f"Cannot connect to Airtable base {base_id}: {e}")

    def inspect(self) -> DataSourceSchema:
        """Inspect the Airtable base and return its schema.

        Discovers:
            - All tables and their fields (with type mapping)
            - All views for each table
            - Row counts
            - Select field options (for single/multi-select fields)
        """
        from pyairtable import Api

        api_key = self._get_api_key()
        base_id = self._get_base_id()
        api = Api(api_key)
        base = api.base(base_id)

        # Get schema (table names, fields, views)
        schema_info = base.schema()

        tables = []
        table_name_map = {}  # safe_name -> original_name
        table_views_map = {}  # safe_name -> [{"name": safe, "original": orig}, ...]
        field_options_map = {}  # safe_table -> {safe_field: [option, ...]}

        for tbl in schema_info.tables:
            original_name = tbl.name
            safe_name = _sanitize_name(original_name)
            table_name_map[safe_name] = original_name

            # Discover views
            views = []
            if hasattr(tbl, 'views') and tbl.views:
                for view in tbl.views:
                    views.append({
                        "name": _sanitize_name(view.name),
                        "original": view.name,
                        "type": getattr(view, 'type', 'grid'),
                    })
            table_views_map[safe_name] = views

            # Discover fields (de-duplicating names that collide after sanitization)
            columns = []
            field_opts = {}
            used_names: dict[str, int] = {}
            for field in tbl.fields:
                field_type = AIRTABLE_TYPE_MAP.get(field.type, ColumnType.STRING)
                safe_field = _sanitize_name(field.name)
                if safe_field in used_names:
                    used_names[safe_field] += 1
                    safe_field = f"{safe_field}_{used_names[safe_field]}"
                else:
                    used_names[safe_field] = 1

                # Extract select options if available
                if field.type in ("singleSelect", "multipleSelects"):
                    if hasattr(field, 'options') and field.options:
                        choices = getattr(field.options, 'choices', None)
                        if choices:
                            field_opts[safe_field] = [
                                c.name for c in choices if hasattr(c, 'name')
                            ]

                columns.append(Column(
                    name=safe_field,
                    type=field_type,
                    nullable=True,
                    primary_key=False,
                    description=field.name,  # Store original name
                ))
            field_options_map[safe_name] = field_opts

            # Get row count — capped so huge bases don't burn API quota.
            # Up to 1,000 records are fetched (id-only); beyond that the
            # count is reported as unknown rather than paginating the base.
            try:
                airtable_table = base.table(original_name)
                records = airtable_table.all(fields=[], max_records=1001)
                row_count = len(records) if len(records) <= 1000 else None
            except Exception:
                row_count = None

            tables.append(Table(
                name=safe_name,
                columns=columns,
                row_count=row_count,
                description=original_name,  # Store original name
            ))

        return DataSourceSchema(
            source_type="airtable",
            source_uri=self.uri,
            tables=tables,
            metadata={
                "base_id": base_id,
                "table_name_map": table_name_map,
                "table_views_map": table_views_map,
                "field_options_map": field_options_map,
            },
        )


# Register this connector
register_connector("airtable", AirtableConnector)
