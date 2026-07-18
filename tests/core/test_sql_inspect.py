"""Mock-based tests for MySQL and PostgreSQL connector inspect methods."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from mcp_maker.connectors.mysql import MySQLConnector
from mcp_maker.connectors.postgres import PostgresConnector


class TestMySQLInspect:
    def test_validate_success(self):
        mock_pymysql = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pymusql_cls = MagicMock(return_value=mock_conn)
        mock_pymysql.connect = mock_pymusql_cls

        with patch.dict(sys.modules, {"pymysql": mock_pymysql}):
            c = MySQLConnector("mysql://user:pass@localhost:3306/mydb")
            assert c.validate() is True
            mock_cursor.execute.assert_called_with("SELECT 1")

    def test_validate_connection_error(self):
        mock_pymysql = MagicMock()
        mock_pymysql.connect.side_effect = Exception("Access denied")

        with patch.dict(sys.modules, {"pymysql": mock_pymysql}):
            c = MySQLConnector("mysql://user:pass@localhost:3306/mydb")
            with pytest.raises(ConnectionError, match="Cannot connect"):
                c.validate()

    def test_inspect(self):
        mock_pymysql = MagicMock()
        mock_cursors = MagicMock()
        mock_pymysql.cursors = mock_cursors

        mock_cursor = MagicMock()

        # Sequence of fetchall calls: tables, columns, row_count, fk
        tables_result = [{"TABLE_NAME": "users", "TABLE_COMMENT": "user table", "TABLE_TYPE": "BASE TABLE"}]
        columns_result = [
            {"COLUMN_NAME": "id", "DATA_TYPE": "int", "IS_NULLABLE": "NO", "COLUMN_KEY": "PRI", "COLUMN_DEFAULT": None, "COLUMN_COMMENT": "id col"},
            {"COLUMN_NAME": "name", "DATA_TYPE": "varchar", "IS_NULLABLE": "YES", "COLUMN_KEY": "", "COLUMN_DEFAULT": None, "COLUMN_COMMENT": None},
        ]
        fk_result = [
            {"from_table": "orders", "from_column": "user_id", "to_table": "users", "to_column": "id"},
        ]

        call_count = [0]
        def mock_fetchall():
            results = [tables_result, columns_result, fk_result]
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(results):
                return results[idx]
            return []

        def mock_fetchone():
            return {"cnt": 42}

        mock_cursor.fetchall = mock_fetchall
        mock_cursor.fetchone = mock_fetchone

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pymysql.connect.return_value = mock_conn

        with patch.dict(sys.modules, {"pymysql": mock_pymysql, "pymysql.cursors": mock_cursors}):
            c = MySQLConnector("mysql://user:pass@localhost:3306/mydb")
            schema = c.inspect()
            assert schema.source_type == "mysql"
            assert len(schema.tables) == 1
            assert schema.tables[0].name == "users"
            assert schema.metadata["database"] == "mydb"


class TestPostgresInspect:
    def test_validate_success(self):
        mock_psycopg2 = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        with patch.dict(sys.modules, {"psycopg2": mock_psycopg2}):
            c = PostgresConnector("postgres://user:pass@localhost:5432/mydb")
            assert c.validate() is True
            mock_cursor.execute.assert_called_with("SELECT 1")

    def test_validate_connection_error(self):
        mock_psycopg2 = MagicMock()
        mock_psycopg2.connect.side_effect = Exception("Connection refused")

        with patch.dict(sys.modules, {"psycopg2": mock_psycopg2}):
            c = PostgresConnector("postgres://user:pass@localhost:5432/mydb")
            with pytest.raises(ConnectionError, match="Cannot connect"):
                c.validate()

    def test_inspect(self):
        mock_psycopg2 = MagicMock()
        mock_extras = MagicMock()
        mock_psycopg2.extras = mock_extras

        mock_cursor = MagicMock()

        # Sequence of fetchall calls: tables, matviews, table_comments, col_comments, pks, columns, fks
        tables_result = [{"table_name": "users", "table_type": "BASE TABLE"}]
        matviews_result = []
        table_comments_result = [{"table_name": "users", "table_comment": "user table"}]
        col_comments_result = [{"table_name": "users", "column_name": "id", "column_comment": "id col"}]
        pk_result = [{"table_name": "users", "column_name": "id"}]
        columns_result = [
            {"column_name": "id", "data_type": "integer", "is_nullable": "NO", "column_default": None},
            {"column_name": "email", "data_type": "varchar", "is_nullable": "YES", "column_default": None},
        ]
        fk_result = []

        call_count = [0]
        def mock_fetchall():
            results = [tables_result, matviews_result, table_comments_result, col_comments_result, pk_result, columns_result, fk_result]
            idx = call_count[0]
            call_count[0] += 1
            if idx < len(results):
                return results[idx]
            return []

        def mock_fetchone():
            return {"cnt": 100}

        mock_cursor.fetchall = mock_fetchall
        mock_cursor.fetchone = mock_fetchone

        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_psycopg2.connect.return_value = mock_conn

        with patch.dict(sys.modules, {"psycopg2": mock_psycopg2, "psycopg2.extras": mock_extras}):
            c = PostgresConnector("postgres://user:pass@localhost:5432/mydb")
            schema = c.inspect()
            assert schema.source_type == "postgres"
            assert len(schema.tables) == 1
            assert schema.tables[0].name == "users"
            assert schema.metadata["database"] == "mydb"
