"""
Tests for MCP-Maker Chat CLI — cli/chat.py

Covers:
- API key validation (missing, env vars, OpenRouter fallback)
- Provider auto-detection from key prefix
- _resolve_db_path and _print_schema helpers
- Connection errors, missing tables, non-SQLite sources
- OpenAI import error handling
"""

import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from mcp_maker.cli import app
from mcp_maker.cli.chat import _print_schema, _resolve_db_path
from mcp_maker.core.schema import (
    Column,
    ColumnType,
    DataSourceSchema,
    Table,
)

runner = CliRunner()


# ──── Fixtures ────


@pytest.fixture
def sample_schema():
    return DataSourceSchema(
        source_type="sqlite",
        source_uri="sqlite:///test.db",
        tables=[
            Table(
                name="users",
                columns=[
                    Column(name="id", type=ColumnType.INTEGER, nullable=False, primary_key=True),
                    Column(name="name", type=ColumnType.STRING, nullable=False),
                ],
                row_count=5,
            ),
        ],
    )


@pytest.fixture
def test_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO users VALUES (1, 'Ali')")
    conn.commit()
    conn.close()
    yield db_path
    os.unlink(db_path)


# ──── _resolve_db_path Tests ────


def _simple_schema(test_db):
    return DataSourceSchema(
        source_type="sqlite",
        source_uri=f"sqlite:///{test_db}",
        tables=[
            Table(
                name="users",
                columns=[
                    Column(name="id", type=ColumnType.INTEGER, nullable=False, primary_key=True),
                    Column(name="name", type=ColumnType.STRING, nullable=False),
                ],
                row_count=1,
            ),
        ],
    )


class TestResolveDbPath:

    def test_sqlite_triple_slash(self, sample_schema):
        result = _resolve_db_path("sqlite:///path/to/db.db", sample_schema)
        assert result == "path/to/db.db"

    def test_sqlite_double_slash(self, sample_schema):
        result = _resolve_db_path("sqlite://path/to/db.db", sample_schema)
        assert result == "path/to/db.db"

    def test_sqlite_no_prefix(self, sample_schema):
        result = _resolve_db_path("mydb.db", sample_schema)
        assert result == "mydb.db"

    def test_sqlite_tilde_expansion(self, sample_schema):
        result = _resolve_db_path("sqlite:///~/mydb.db", sample_schema)
        assert result == os.path.expanduser("~/mydb.db")

    def test_files_source_returns_none(self):
        schema = DataSourceSchema(
            source_type="files",
            source_uri="./data/",
            tables=[],
        )
        assert _resolve_db_path("./data/", schema) is None

    def test_postgres_returns_none(self):
        schema = DataSourceSchema(
            source_type="postgresql",
            source_uri="postgres://localhost/db",
            tables=[],
        )
        assert _resolve_db_path("postgres://localhost/db", schema) is None


# ──── _print_schema Tests ────


class TestPrintSchema:

    def test_prints_without_error(self, sample_schema, capsys):
        # Should not raise
        _print_schema(sample_schema)

    def test_handles_none_row_count(self):
        schema = DataSourceSchema(
            source_type="sqlite",
            source_uri="sqlite:///test.db",
            tables=[
                Table(
                    name="products",
                    columns=[
                        Column(name="id", type=ColumnType.INTEGER, nullable=False, primary_key=True),
                    ],
                    row_count=None,
                ),
            ],
        )
        # Should not raise even with None row_count
        _print_schema(schema)


# ──── CLI Chat Command Tests ────


class TestChatCommand:

    def test_missing_api_key(self, test_db):
        env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "OPENROUTER_API_KEY")}
        result = runner.invoke(app, ["chat", f"sqlite:///{test_db}"], env=env)
        assert result.exit_code != 0
        assert "No API key" in result.output

    def test_invalid_source(self):
        result = runner.invoke(
            app,
            ["chat", "sqlite:///nonexistent_db_file.db", "--api-key", "sk-test"],
        )
        assert result.exit_code != 0

    def test_non_sqlite_source_rejected(self):
        """Chat should reject non-SQLite sources with a clear message."""
        with patch("mcp_maker.cli.chat.get_connector") as mock_conn:
            mock_connector = MagicMock()
            mock_conn.return_value = mock_connector
            schema = DataSourceSchema(
                source_type="postgresql",
                source_uri="postgres://localhost/db",
                tables=[
                    Table(
                        name="users",
                        columns=[
                            Column(name="id", type=ColumnType.INTEGER, nullable=False, primary_key=True),
                        ],
                        row_count=10,
                    ),
                ],
            )
            mock_connector.inspect.return_value = schema
            result = runner.invoke(
                app,
                ["chat", "postgres://localhost/db", "--api-key", "sk-test"],
            )
            assert result.exit_code != 0
            assert "SQLite" in result.output

    def test_openrouter_autodetect_from_key(self, test_db):
        """sk-or- prefix should auto-detect OpenRouter provider."""
        with (
            patch("mcp_maker.cli.chat.get_connector") as mock_conn,
            patch.dict("sys.modules", {"openai": MagicMock()}),
        ):
            mock_connector = MagicMock()
            mock_conn.return_value = mock_connector
            schema = DataSourceSchema(
                source_type="sqlite",
                source_uri=f"sqlite:///{test_db}",
                tables=[
                    Table(
                        name="users",
                        columns=[
                            Column(name="id", type=ColumnType.INTEGER, nullable=False, primary_key=True),
                            Column(name="name", type=ColumnType.STRING, nullable=False),
                        ],
                        row_count=1,
                    ),
                ],
            )
            mock_connector.inspect.return_value = schema
            # Simulate immediate EOF to exit the REPL
            result = runner.invoke(
                app,
                ["chat", f"sqlite:///{test_db}", "--api-key", "sk-or-test123"],
                input="\x04",  # Ctrl+D / EOF
            )
            assert "OpenRouter" in result.output

    def test_openai_default_provider(self, test_db):
        """Regular sk- key should default to OpenAI."""
        with (
            patch("mcp_maker.cli.chat.get_connector") as mock_conn,
            patch.dict("sys.modules", {"openai": MagicMock()}),
        ):
            mock_connector = MagicMock()
            mock_conn.return_value = mock_connector
            schema = DataSourceSchema(
                source_type="sqlite",
                source_uri=f"sqlite:///{test_db}",
                tables=[
                    Table(
                        name="users",
                        columns=[
                            Column(name="id", type=ColumnType.INTEGER, nullable=False, primary_key=True),
                            Column(name="name", type=ColumnType.STRING, nullable=False),
                        ],
                        row_count=1,
                    ),
                ],
            )
            mock_connector.inspect.return_value = schema
            result = runner.invoke(
                app,
                ["chat", f"sqlite:///{test_db}", "--api-key", "sk-test123"],
                input="\x04",
            )
            assert "OpenAI" in result.output

    def test_grok_autodetect_from_key(self, test_db):
        """xai- prefix should auto-detect the Grok provider."""
        with (
            patch("mcp_maker.cli.chat.get_connector") as mock_conn,
            patch.dict("sys.modules", {"openai": MagicMock()}),
        ):
            mock_connector = MagicMock()
            mock_conn.return_value = mock_connector
            mock_connector.inspect.return_value = _simple_schema(test_db)
            result = runner.invoke(
                app,
                ["chat", f"sqlite:///{test_db}", "--api-key", "xai-test123"],
                input="\x04",
            )
            assert "Grok" in result.output
            assert "grok-3-mini" in result.output

    def test_deepseek_provider_flag(self, test_db):
        """--provider deepseek selects DeepSeek even with an sk- key."""
        with (
            patch("mcp_maker.cli.chat.get_connector") as mock_conn,
            patch.dict("sys.modules", {"openai": MagicMock()}),
        ):
            mock_connector = MagicMock()
            mock_conn.return_value = mock_connector
            mock_connector.inspect.return_value = _simple_schema(test_db)
            result = runner.invoke(
                app,
                ["chat", f"sqlite:///{test_db}", "--api-key", "sk-test123", "--provider", "deepseek"],
                input="\x04",
            )
            assert "DeepSeek" in result.output
            assert "deepseek-chat" in result.output

    def test_deepseek_env_var_fallback(self, test_db):
        """DEEPSEEK_API_KEY env var selects the DeepSeek provider."""
        with (
            patch("mcp_maker.cli.chat.get_connector") as mock_conn,
            patch.dict("sys.modules", {"openai": MagicMock()}),
            patch.dict("os.environ", {"DEEPSEEK_API_KEY": "sk-ds-test"}, clear=False),
        ):
            import os as _os
            _os.environ.pop("OPENAI_API_KEY", None)
            _os.environ.pop("OPENROUTER_API_KEY", None)
            _os.environ.pop("XAI_API_KEY", None)
            _os.environ.pop("GROK_API_KEY", None)
            mock_connector = MagicMock()
            mock_conn.return_value = mock_connector
            mock_connector.inspect.return_value = _simple_schema(test_db)
            result = runner.invoke(
                app,
                ["chat", f"sqlite:///{test_db}"],
                input="\x04",
            )
            assert "DeepSeek" in result.output

    def test_invalid_provider_rejected(self, test_db):
        """An unknown --provider value exits with an error."""
        with (
            patch("mcp_maker.cli.chat.get_connector") as mock_conn,
            patch.dict("sys.modules", {"openai": MagicMock()}),
        ):
            mock_conn.return_value = MagicMock()
            result = runner.invoke(
                app,
                ["chat", f"sqlite:///{test_db}", "--api-key", "sk-x", "--provider", "gemini"],
            )
            assert result.exit_code != 0
            assert "Unknown provider" in result.output

    def test_empty_tables_rejected(self, test_db):
        """Should fail if no tables found."""
        with patch("mcp_maker.cli.chat.get_connector") as mock_conn:
            mock_connector = MagicMock()
            mock_conn.return_value = mock_connector
            schema = DataSourceSchema(
                source_type="sqlite",
                source_uri=f"sqlite:///{test_db}",
                tables=[],
            )
            mock_connector.inspect.return_value = schema
            result = runner.invoke(
                app,
                ["chat", f"sqlite:///{test_db}", "--api-key", "sk-test"],
            )
            assert result.exit_code != 0
            assert "No tables" in result.output

    def test_openrouter_env_var_fallback(self, test_db):
        """OPENROUTER_API_KEY env var should be used when no --api-key given."""
        env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY",)}
        env["OPENROUTER_API_KEY"] = "sk-or-envtest"

        with (
            patch("mcp_maker.cli.chat.get_connector") as mock_conn,
            patch.dict("sys.modules", {"openai": MagicMock()}),
        ):
            mock_connector = MagicMock()
            mock_conn.return_value = mock_connector
            schema = DataSourceSchema(
                source_type="sqlite",
                source_uri=f"sqlite:///{test_db}",
                tables=[
                    Table(
                        name="users",
                        columns=[
                            Column(name="id", type=ColumnType.INTEGER, nullable=False, primary_key=True),
                        ],
                        row_count=1,
                    ),
                ],
            )
            mock_connector.inspect.return_value = schema
            result = runner.invoke(
                app,
                ["chat", f"sqlite:///{test_db}"],
                input="\x04",
                env=env,
            )
            assert "OpenRouter" in result.output

    def test_connection_failure(self, test_db):
        """Should show error when connector fails."""
        with patch("mcp_maker.cli.chat.get_connector") as mock_conn:
            mock_conn.return_value.validate.side_effect = Exception("Connection refused")
            result = runner.invoke(
                app,
                ["chat", f"sqlite:///{test_db}", "--api-key", "sk-test"],
            )
            assert result.exit_code != 0
            assert "Connection failed" in result.output
