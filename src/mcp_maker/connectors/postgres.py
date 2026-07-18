"""
MCP-Maker PostgreSQL Connector — Inspect PostgreSQL databases.
"""

from urllib.parse import urlparse

from ..core.schema import (
    Column,
    DataSourceSchema,
    ForeignKey,
    Table,
    map_sql_type,
)
from .base import BaseConnector, register_connector


class PostgresConnector(BaseConnector):
    """Connector for PostgreSQL databases.

    Inspects all tables, columns, types, primary keys, and row counts
    from a PostgreSQL database.

    URI format: postgres://user:pass@host:port/dbname
                postgresql://user:pass@host:port/dbname
    """

    @property
    def source_type(self) -> str:
        return "postgres"

    def _get_dsn(self) -> str:
        """Return a psycopg2-compatible DSN from the URI.

        Strips the mcp-maker-specific ?schema= parameter, which libpq
        would otherwise reject as an unknown connection option.
        """
        uri = self.uri
        # Normalize scheme for psycopg2
        if uri.startswith("postgres://"):
            uri = "postgresql://" + uri[len("postgres://"):]
        parsed = urlparse(uri)
        if parsed.query:
            kept = [
                p for p in parsed.query.split("&")
                if not p.lower().startswith("schema=")
            ]
            uri = uri.split("?")[0] + (("?" + "&".join(kept)) if kept else "")
        return uri

    def _parse_schema(self) -> str:
        """Extract the schema name from the URI query string, default 'public'."""
        parsed = urlparse(self.uri)
        # Check for ?schema=xxx in query params
        if parsed.query:
            params = dict(p.split("=", 1) for p in parsed.query.split("&") if "=" in p)
            return params.get("schema", "public")
        return "public"

    @staticmethod
    def _quote_ident(name: str) -> str:
        """Safely quote a PostgreSQL identifier (escapes embedded double quotes)."""
        return '"' + name.replace('"', '""') + '"'

    def validate(self) -> bool:
        """Check that the PostgreSQL database is accessible."""
        try:
            import psycopg2
        except ImportError:
            raise ImportError(
                "PostgreSQL support requires psycopg2.\n"
                "Install it with: pip install mcp-maker[postgres]"
            )

        try:
            conn = psycopg2.connect(self._get_dsn())
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            raise ConnectionError(f"Cannot connect to PostgreSQL: {e}")

    def inspect(self) -> DataSourceSchema:
        """Inspect the PostgreSQL database and return its schema."""
        import psycopg2
        import psycopg2.extras

        dsn = self._get_dsn()
        schema_name = self._parse_schema()
        conn = psycopg2.connect(dsn)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        tables = []

        # Get all tables and views in the schema
        cursor.execute(
            """
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type IN ('BASE TABLE', 'VIEW')
            ORDER BY table_name
            """,
            (schema_name,),
        )
        rows = cursor.fetchall()
        table_names = [r["table_name"] for r in rows if r["table_type"] == "BASE TABLE"]
        view_names = [r["table_name"] for r in rows if r["table_type"] == "VIEW"]

        # Materialized views (not in information_schema.tables)
        cursor.execute(
            "SELECT matviewname FROM pg_matviews WHERE schemaname = %s ORDER BY matviewname",
            (schema_name,),
        )
        view_names += [r["matviewname"] for r in cursor.fetchall()]

        # Get table comments
        cursor.execute(
            """
            SELECT c.relname as table_name, obj_description(c.oid, 'class') as table_comment
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s
            """,
            (schema_name,),
        )
        table_comments = {row["table_name"]: row["table_comment"] for row in cursor.fetchall() if row["table_comment"]}

        # Get all column comments for the schema
        cursor.execute(
            """
            SELECT c.relname as table_name, a.attname as column_name, col_description(c.oid, a.attnum) as column_comment
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON c.oid = a.attrelid
            WHERE n.nspname = %s AND a.attnum > 0 AND NOT a.attisdropped
            """,
            (schema_name,),
        )
        col_comments = {}
        for row in cursor.fetchall():
            if row["column_comment"]:
                col_comments.setdefault(row["table_name"], {})[row["column_name"]] = row["column_comment"]

        # Get primary keys for all tables at once
        cursor.execute(
            """
            SELECT
                kcu.table_name,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = %s
            """,
            (schema_name,),
        )
        pk_map: dict[str, set[str]] = {}
        for row in cursor.fetchall():
            pk_map.setdefault(row["table_name"], set()).add(row["column_name"])

        for table_name in table_names + view_names:
            is_view = table_name in view_names
            # Get columns
            cursor.execute(
                """
                SELECT
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                (schema_name, table_name),
            )
            col_rows = cursor.fetchall()

            # Materialized views aren't in information_schema.columns — use pg_attribute
            if not col_rows:
                cursor.execute(
                    """
                    SELECT
                        a.attname AS column_name,
                        format_type(a.atttypid, a.atttypmod) AS data_type,
                        CASE WHEN a.attnotnull THEN 'NO' ELSE 'YES' END AS is_nullable,
                        NULL AS column_default
                    FROM pg_attribute a
                    JOIN pg_class c ON c.oid = a.attrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = %s AND c.relname = %s
                      AND a.attnum > 0 AND NOT a.attisdropped
                    ORDER BY a.attnum
                    """,
                    (schema_name, table_name),
                )
                col_rows = cursor.fetchall()

            pk_columns = pk_map.get(table_name, set())
            tb_col_comments = col_comments.get(table_name, {})
            columns = []
            for col in col_rows:
                columns.append(Column(
                    name=col["column_name"],
                    type=map_sql_type(col["data_type"]),
                    nullable=col["is_nullable"] == "YES",
                    primary_key=col["column_name"] in pk_columns,
                    description=tb_col_comments.get(col["column_name"]),
                ))

            # Get row count
            try:
                cursor.execute(
                    f"SELECT COUNT(*) as cnt FROM "
                    f"{self._quote_ident(schema_name)}.{self._quote_ident(table_name)}"
                )
                row_count = cursor.fetchone()["cnt"]
            except Exception:
                row_count = None
                conn.rollback()

            description = table_comments.get(table_name)
            if is_view:
                description = description or "view (read-only)"

            tables.append(Table(
                name=table_name,
                columns=columns,
                row_count=row_count,
                description=description,
            ))

        # Discover foreign key relationships
        foreign_keys = []
        try:
            cursor.execute(
                """
                SELECT
                    kcu.table_name AS from_table,
                    kcu.column_name AS from_column,
                    ccu.table_name AS to_table,
                    ccu.column_name AS to_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage ccu
                    ON tc.constraint_name = ccu.constraint_name
                    AND tc.table_schema = ccu.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = %s
                """,
                (schema_name,),
            )
            for row in cursor.fetchall():
                foreign_keys.append(ForeignKey(
                    from_table=row["from_table"],
                    from_column=row["from_column"],
                    to_table=row["to_table"],
                    to_column=row["to_column"],
                ))
        except Exception:
            conn.rollback()

        cursor.close()
        conn.close()

        # Extract database name for metadata
        parsed = urlparse(dsn)
        db_name = parsed.path.lstrip("/") if parsed.path else "unknown"

        return DataSourceSchema(
            source_type="postgres",
            source_uri=self.uri,
            tables=tables,
            foreign_keys=foreign_keys,
            metadata={
                "database": db_name,
                "schema": schema_name,
                "host": parsed.hostname or "localhost",
                "port": parsed.port or 5432,
                "views": view_names,
            },
        )


# Register this connector for both schemes
register_connector("postgres", PostgresConnector)
register_connector("postgresql", PostgresConnector)
