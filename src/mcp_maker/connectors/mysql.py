"""
MCP-Maker MySQL Connector — Inspect MySQL databases.
"""

from urllib.parse import unquote, urlparse

from ..core.schema import (
    Column,
    DataSourceSchema,
    ForeignKey,
    Table,
    map_sql_type,
)
from .base import BaseConnector, register_connector


class MySQLConnector(BaseConnector):
    """Connector for MySQL databases.

    Inspects all tables, columns, types, primary keys, and row counts
    from a MySQL database.

    URI format: mysql://user:pass@host:port/dbname
    """

    @property
    def source_type(self) -> str:
        return "mysql"

    def _parse_uri(self) -> dict:
        """Parse MySQL URI into connection parameters.

        Credentials are URL-decoded so passwords containing special
        characters (@, %, /, …) work when percent-encoded in the URI.
        """
        parsed = urlparse(self.uri)
        database = unquote(parsed.path.lstrip("/"))
        if not database:
            raise ValueError(
                "MySQL URI must include a database name. "
                "Example: mysql://user:pass@localhost:3306/mydb"
            )
        return {
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 3306,
            "user": unquote(parsed.username) if parsed.username else "root",
            "password": unquote(parsed.password) if parsed.password else "",
            "database": database,
            "charset": "utf8mb4",
        }

    @staticmethod
    def _quote_ident(name: str) -> str:
        """Safely quote a MySQL identifier (escapes embedded backticks)."""
        return "`" + name.replace("`", "``") + "`"

    def validate(self) -> bool:
        """Check that the MySQL database is accessible."""
        try:
            import pymysql
        except ImportError:
            raise ImportError(
                "MySQL support requires pymysql.\n"
                "Install it with: pip install mcp-maker[mysql]"
            )

        params = self._parse_uri()
        try:
            conn = pymysql.connect(**params)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            raise ConnectionError(f"Cannot connect to MySQL: {e}")

    def inspect(self) -> DataSourceSchema:
        """Inspect the MySQL database and return its schema."""
        import pymysql
        import pymysql.cursors

        params = self._parse_uri()
        db_name = params["database"]
        conn = pymysql.connect(
            **params,
            cursorclass=pymysql.cursors.DictCursor,
        )
        cursor = conn.cursor()

        tables = []

        # Get all tables and views
        cursor.execute(
            """
            SELECT TABLE_NAME, TABLE_COMMENT, TABLE_TYPE
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s
              AND TABLE_TYPE IN ('BASE TABLE', 'VIEW')
            ORDER BY TABLE_NAME
            """,
            (db_name,),
        )
        table_rows = cursor.fetchall()
        table_names = [r["TABLE_NAME"] for r in table_rows if r["TABLE_TYPE"] == "BASE TABLE"]
        view_names = [r["TABLE_NAME"] for r in table_rows if r["TABLE_TYPE"] == "VIEW"]
        table_comments = {row["TABLE_NAME"]: row["TABLE_COMMENT"] for row in table_rows if row["TABLE_COMMENT"]}

        for table_name in table_names + view_names:
            # Get columns with primary key info
            cursor.execute(
                """
                SELECT
                    COLUMN_NAME,
                    DATA_TYPE,
                    IS_NULLABLE,
                    COLUMN_KEY,
                    COLUMN_DEFAULT,
                    COLUMN_COMMENT
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s
                  AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
                """,
                (db_name, table_name),
            )

            columns = []
            for col in cursor.fetchall():
                columns.append(Column(
                    name=col["COLUMN_NAME"],
                    type=map_sql_type(col["DATA_TYPE"]),
                    nullable=col["IS_NULLABLE"] == "YES",
                    primary_key=col["COLUMN_KEY"] == "PRI",
                    description=col["COLUMN_COMMENT"] if col["COLUMN_COMMENT"] else None,
                ))

            # Get row count
            try:
                cursor.execute(
                    f"SELECT COUNT(*) as cnt FROM {self._quote_ident(table_name)}"
                )
                row_count = cursor.fetchone()["cnt"]
            except Exception:
                row_count = None

            description = table_comments.get(table_name)
            if table_name in view_names:
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
                    TABLE_NAME AS from_table,
                    COLUMN_NAME AS from_column,
                    REFERENCED_TABLE_NAME AS to_table,
                    REFERENCED_COLUMN_NAME AS to_column
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = %s
                  AND REFERENCED_TABLE_NAME IS NOT NULL
                """,
                (db_name,),
            )
            for row in cursor.fetchall():
                foreign_keys.append(ForeignKey(
                    from_table=row["from_table"],
                    from_column=row["from_column"],
                    to_table=row["to_table"],
                    to_column=row["to_column"],
                ))
        except Exception:
            pass

        cursor.close()
        conn.close()

        return DataSourceSchema(
            source_type="mysql",
            source_uri=self.uri,
            tables=tables,
            foreign_keys=foreign_keys,
            metadata={
                "database": db_name,
                "host": params["host"],
                "port": params["port"],
                "views": view_names,
            },
        )


# Register this connector
register_connector("mysql", MySQLConnector)
