"""Tests for connector audit fixes: JSONL/TSV parsing, single-file mode,
sanitized names, SQLite views/read-only, $ref resolution, scheme registration."""

import json
import sqlite3

import pytest

from mcp_maker.connectors.base import _CONNECTOR_REGISTRY, get_connector
from mcp_maker.connectors.files import FileConnector
from mcp_maker.connectors.openapi import OpenAPIConnector, _resolve_ref
from mcp_maker.connectors.sqlite import SQLiteConnector
from mcp_maker.core.schema import ColumnType


class TestFileConnectorFixes:
    def test_jsonl_parsed_as_table(self, tmp_path):
        f = tmp_path / "events.jsonl"
        f.write_text(
            '{"id": 1, "event": "signup"}\n{"id": 2, "event": "login"}\n'
        )
        schema = FileConnector(str(tmp_path)).inspect()
        assert len(schema.tables) == 1
        table = schema.tables[0]
        assert table.name == "events"
        assert table.row_count == 2
        col_names = [c.name for c in table.columns]
        assert col_names == ["id", "event"]
        assert table.columns[0].primary_key

    def test_tsv_supported(self, tmp_path):
        f = tmp_path / "people.tsv"
        f.write_text("name\tage\nAlice\t30\nBob\t25\n")
        schema = FileConnector(str(tmp_path)).inspect()
        assert len(schema.tables) == 1
        assert [c.name for c in schema.tables[0].columns] == ["name", "age"]
        assert schema.tables[0].columns[1].type == ColumnType.INTEGER

    def test_csv_headers_sanitized(self, tmp_path):
        f = tmp_path / "my-data.csv"
        f.write_text("First Name,email@address\nAlice,a@x.com\n")
        schema = FileConnector(str(tmp_path)).inspect()
        table = schema.tables[0]
        assert table.name == "my_data"
        assert [c.name for c in table.columns] == ["first_name", "email_address"]

    def test_duplicate_headers_deduped(self, tmp_path):
        f = tmp_path / "dup.csv"
        f.write_text("a,A!,a\n1,2,3\n")
        schema = FileConnector(str(tmp_path)).inspect()
        names = [c.name for c in schema.tables[0].columns]
        assert len(names) == len(set(names))

    def test_single_file_mode(self, tmp_path):
        f = tmp_path / "users.csv"
        f.write_text("id,name\n1,Alice\n")
        connector = get_connector(str(f))
        assert isinstance(connector, FileConnector)
        assert connector.validate()
        schema = connector.inspect()
        assert schema.tables[0].name == "users"

    def test_mixed_int_float_column_is_float(self, tmp_path):
        f = tmp_path / "nums.csv"
        f.write_text("v\n1\n2.5\n")
        schema = FileConnector(str(tmp_path)).inspect()
        assert schema.tables[0].columns[0].type == ColumnType.FLOAT


class TestSQLiteFixes:
    @pytest.fixture
    def db(self, tmp_path):
        path = tmp_path / "t.db"
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO users VALUES (1, 'a'), (2, 'b')")
        conn.execute("CREATE VIEW adults AS SELECT * FROM users")
        conn.commit()
        conn.close()
        return str(path)

    def test_views_discovered(self, db):
        schema = SQLiteConnector(f"sqlite:///{db}").inspect()
        names = {t.name for t in schema.tables}
        assert names == {"users", "adults"}
        view = next(t for t in schema.tables if t.name == "adults")
        assert "view" in (view.description or "")
        assert schema.metadata["views"] == ["adults"]

    def test_quoted_identifier_table(self, tmp_path):
        path = tmp_path / "q.db"
        conn = sqlite3.connect(path)
        conn.execute('CREATE TABLE "we""ird" (id INTEGER)')
        conn.commit()
        conn.close()
        schema = SQLiteConnector(f"sqlite:///{path}").inspect()
        assert schema.tables[0].row_count == 0  # count query survived quoting

    def test_validate_missing_db_no_file_created(self, tmp_path):
        missing = tmp_path / "nope.db"
        with pytest.raises(FileNotFoundError):
            SQLiteConnector(f"sqlite:///{missing}").validate()
        assert not missing.exists()


class TestOpenAPIRefResolution:
    def test_resolve_ref(self):
        spec = {"components": {"schemas": {"User": {"type": "object"}}}}
        node = {"$ref": "#/components/schemas/User"}
        assert _resolve_ref(node, spec) == {"type": "object"}

    def test_body_ref_expanded(self, tmp_path):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "t", "version": "1"},
            "paths": {
                "/users": {
                    "post": {
                        "operationId": "createUser",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            }
                        },
                    }
                }
            },
            "components": {
                "schemas": {
                    "User": {
                        "type": "object",
                        "required": ["name"],
                        "properties": {
                            "name": {"type": "string"},
                            "age": {"type": "integer"},
                        },
                    }
                }
            },
        }
        f = tmp_path / "spec.json"
        f.write_text(json.dumps(spec))
        schema = OpenAPIConnector(f"openapi:///{f}").inspect()
        cols = {c.name: c for c in schema.tables[0].columns}
        assert cols["name"].type == ColumnType.STRING
        assert not cols["name"].nullable
        assert cols["age"].type == ColumnType.INTEGER

    def test_swagger2_body_and_path_params(self, tmp_path):
        spec = {
            "swagger": "2.0",
            "info": {"title": "t", "version": "1"},
            "host": "api.example.com",
            "paths": {
                "/pets/{petId}": {
                    "parameters": [
                        {"name": "petId", "in": "path", "required": True, "type": "integer"}
                    ],
                    "put": {
                        "operationId": "updatePet",
                        "parameters": [
                            {
                                "name": "body",
                                "in": "body",
                                "schema": {
                                    "type": "object",
                                    "properties": {"nickname": {"type": "string"}},
                                },
                            }
                        ],
                    },
                }
            },
        }
        f = tmp_path / "spec.json"
        f.write_text(json.dumps(spec))
        schema = OpenAPIConnector(f"openapi:///{f}").inspect()
        cols = [c.name for c in schema.tables[0].columns]
        assert "petId" in cols  # path-level shared param
        assert "nickname" in cols  # swagger 2 body schema


class TestRegistryFixes:
    def test_mongodb_srv_registered_when_available(self):
        # Registered only if pymongo importable — mirror mongodb registration
        if "mongodb" in _CONNECTOR_REGISTRY:
            assert "mongodb+srv" in _CONNECTOR_REGISTRY

    def test_hint_for_unavailable_scheme(self):
        if "hubspot" in _CONNECTOR_REGISTRY:
            pytest.skip("hubspot connector installed")
        with pytest.raises(ValueError, match=r"mcp-maker\[hubspot\]"):
            get_connector("hubspot://pat=x")
