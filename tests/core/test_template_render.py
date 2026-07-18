"""Render every connector's template with a synthetic schema and verify the
generated server is syntactically valid Python.

This is the test that would have caught the Notion template's unbalanced
Jinja blocks, which made Notion generation crash with TemplateSyntaxError.
"""

import ast

import pytest

from mcp_maker.core.generator import generate_server_code
from mcp_maker.core.schema import Column, ColumnType, DataSourceSchema, ForeignKey, Table


def _cols():
    return [
        Column(name="id", type=ColumnType.INTEGER, primary_key=True, nullable=False, description="ID"),
        Column(name="name", type=ColumnType.STRING, nullable=True, description="Full Name"),
        Column(name="score", type=ColumnType.FLOAT, nullable=True, description="Score"),
        Column(name="created", type=ColumnType.DATETIME, nullable=True),
    ]


def _sql_schema(source_type, metadata):
    tables = [
        Table(name="users", columns=_cols(), row_count=5),
        Table(name="orders", columns=_cols(), row_count=5),
    ]
    fks = [ForeignKey(from_table="orders", from_column="id", to_table="users", to_column="id")]
    return DataSourceSchema(
        source_type=source_type, source_uri=f"{source_type}://x",
        tables=tables, foreign_keys=fks, metadata=metadata,
    )


def _api_schema(source_type, metadata):
    return DataSourceSchema(
        source_type=source_type, source_uri=f"{source_type}://x",
        tables=[Table(name="users", columns=_cols(), row_count=5, description="Users Sheet")],
        metadata=metadata,
    )


SCHEMAS = {
    "sqlite": _sql_schema("sqlite", {"db_path": "/tmp/x.db", "views": []}),
    "postgres": _sql_schema("postgres", {"database": "d", "schema": "public", "host": "h", "port": 5432, "views": []}),
    "mysql": _sql_schema("mysql", {"database": "d", "host": "h", "port": 3306, "views": []}),
    "files": _api_schema("files", {"file_map": {"users": "Users Data.csv"}, "is_single_file": False}),
    "excel": _api_schema("excel", {"file_path": "/tmp/x.xlsx", "sheet_count": 1}),
    "mongodb": _api_schema("mongodb", {"database": "d", "collection_name_map": {"users": "user-docs"}}),
    "hubspot": _api_schema("hubspot", {"select_options_map": {}, "object_type_map": {"users": "p1_user-obj"}}),
    "supabase": _api_schema("supabase", {"supabase_url": "https://x.supabase.co", "project_ref": "x"}),
    "gsheet": _api_schema("gsheet", {"spreadsheet_id": "abc", "spreadsheet_title": "T", "sheet_name_map": {"users": "Users Sheet"}}),
    "notion": _api_schema("notion", {"database_map": {"users": "db1"}, "title_map": {"users": "U"}, "select_options_map": {"users": {}}}),
    "airtable": _api_schema("airtable", {"base_id": "app1", "table_name_map": {"users": "Users Sheet"}, "table_views_map": {"users": []}, "field_options_map": {"users": {}}}),
    "redis": DataSourceSchema(
        source_type="redis", source_uri="redis://x",
        tables=[
            Table(name="cache", columns=[Column(name="key", type=ColumnType.STRING, primary_key=True), Column(name="value", type=ColumnType.STRING)], row_count=3, description="cache (string)"),
            Table(name="sessions", columns=[Column(name="key", type=ColumnType.STRING, primary_key=True)], row_count=2, description="sessions (hash)"),
        ],
        metadata={"db_size": 5, "key_groups": 2},
    ),
    "openapi": DataSourceSchema(
        source_type="openapi", source_uri="openapi:///x.json",
        tables=[Table(name="get_users", columns=[
            Column(name="_method", type=ColumnType.STRING, nullable=False, description="GET"),
            Column(name="_path", type=ColumnType.STRING, nullable=False, description="/users/{uid}"),
            Column(name="uid", type=ColumnType.INTEGER, nullable=False, description="path param"),
            Column(name="q", type=ColumnType.STRING, nullable=True, description="query param"),
            Column(name="payload", type=ColumnType.JSON, nullable=True, description="body field"),
        ], description="List users")],
        metadata={"base_url": "https://api.example.com", "spec_title": "T", "spec_version": "1", "endpoint_count": 1},
    ),
}


@pytest.mark.parametrize("source_type", sorted(SCHEMAS))
@pytest.mark.parametrize("ops", [["read"], ["read", "insert", "update", "delete"]], ids=["read", "full"])
def test_template_renders_valid_python(source_type, ops):
    server, autogen = generate_server_code(SCHEMAS[source_type], ops=ops)
    ast.parse(server)
    ast.parse(autogen)


@pytest.mark.parametrize("source_type", sorted(SCHEMAS))
def test_consolidated_mode_renders(source_type):
    schema = SCHEMAS[source_type]
    server, autogen = generate_server_code(schema, ops=["read"], consolidate_threshold=0)
    ast.parse(server)
    ast.parse(autogen)
