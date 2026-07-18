"""
MCP-Maker SQLite Connector — Inspect SQLite databases.
"""

import os
import sqlite3

from ..core.schema import (
    Column,
    DataSourceSchema,
    ForeignKey,
    Table,
    map_sql_type,
)
from .base import BaseConnector, register_connector


class SQLiteConnector(BaseConnector):
    """Connector for SQLite databases.

    Inspects all tables, columns, types, primary keys, and row counts.

    URI format: sqlite:///path/to/database.db
    """

    @property
    def source_type(self) -> str:
        return "sqlite"

    @staticmethod
    def _quote_ident(name: str) -> str:
        """Safely quote an SQLite identifier (escapes embedded double quotes)."""
        return '"' + name.replace('"', '""') + '"'

    def _connect_readonly(self, db_path: str) -> sqlite3.Connection:
        """Open the database in read-only mode so inspection can never mutate it."""
        from urllib.parse import quote
        return sqlite3.connect(f"file:{quote(db_path)}?mode=ro", uri=True)

    def _get_db_path(self) -> str:
        """Extract the file path from the SQLite URI."""
        path = self.uri
        if path.startswith("sqlite:///"):
            path = path[len("sqlite:///"):]
        elif path.startswith("sqlite://"):
            path = path[len("sqlite://"):]
        return os.path.expanduser(path)

    def validate(self) -> bool:
        """Check that the SQLite database file exists and is readable."""
        db_path = self._get_db_path()
        if not os.path.isfile(db_path):
            raise FileNotFoundError(f"Database not found: {db_path}")
        # Try opening the database (read-only — validation must not create/lock files)
        try:
            conn = self._connect_readonly(db_path)
            conn.execute("SELECT 1")
            conn.close()
            return True
        except sqlite3.Error as e:
            raise ConnectionError(f"Cannot open database: {e}")

    def inspect(self) -> DataSourceSchema:
        """Inspect the SQLite database and return its schema.

        Discovers tables and views (views are marked in their description
        and excluded from write-tool generation downstream).
        """
        db_path = self._get_db_path()
        conn = self._connect_readonly(db_path)
        conn.row_factory = sqlite3.Row

        tables = []

        # Get all tables and views (exclude SQLite internal tables)
        cursor = conn.execute(
            "SELECT name, type FROM sqlite_master "
            "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
        rows = cursor.fetchall()
        table_names = [row["name"] for row in rows if row["type"] == "table"]
        view_names = [row["name"] for row in rows if row["type"] == "view"]

        for table_name in table_names + view_names:
            is_view = table_name in view_names
            quoted = self._quote_ident(table_name)

            col_cursor = conn.execute(f"PRAGMA table_info({quoted})")
            columns = []
            for col in col_cursor.fetchall():
                columns.append(Column(
                    name=col["name"],
                    type=map_sql_type(col["type"] or "text"),
                    nullable=not col["notnull"],
                    primary_key=bool(col["pk"]),
                ))

            # Get row count
            try:
                count_cursor = conn.execute(
                    f"SELECT COUNT(*) as cnt FROM {quoted}"
                )
                row_count = count_cursor.fetchone()["cnt"]
            except sqlite3.Error:
                row_count = None

            tables.append(Table(
                name=table_name,
                columns=columns,
                row_count=row_count,
                description="view (read-only)" if is_view else None,
            ))

        # Discover foreign key relationships
        foreign_keys = []
        for table_name in table_names:
            try:
                fk_cursor = conn.execute(
                    f"PRAGMA foreign_key_list({self._quote_ident(table_name)})"
                )
                for fk in fk_cursor.fetchall():
                    foreign_keys.append(ForeignKey(
                        from_table=table_name,
                        from_column=fk["from"],
                        to_table=fk["table"],
                        to_column=fk["to"],
                    ))
            except sqlite3.Error:
                pass

        conn.close()

        return DataSourceSchema(
            source_type="sqlite",
            source_uri=self.uri,
            tables=tables,
            foreign_keys=foreign_keys,
            metadata={
                "db_path": db_path,
                "file_size_bytes": os.path.getsize(db_path),
                "views": view_names,
            },
        )


# Register this connector
register_connector("sqlite", SQLiteConnector)
