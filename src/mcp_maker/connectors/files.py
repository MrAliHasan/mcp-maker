"""
MCP-Maker File Connector — Inspect CSV, TSV, JSON, and other file-based data sources.
"""

import csv
import json
import os
from pathlib import Path

from ..core.schema import (
    Column,
    ColumnType,
    DataSourceSchema,
    Resource,
    Table,
)
from .base import BaseConnector, register_connector
from .utils import infer_type as _infer_type
from .utils import sanitize_name as _sanitize_name

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".json": "application/json",
    ".jsonl": "application/jsonl",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".yaml": "text/yaml",
    ".yml": "text/yaml",
    ".xml": "text/xml",
}

# Extensions that can be inspected as structured tables
TABULAR_EXTENSIONS = (".csv", ".tsv", ".json", ".jsonl")


def _dedupe(names: list[str]) -> list[str]:
    """Make sanitized names unique by appending _2, _3, … to duplicates."""
    seen: dict[str, int] = {}
    result = []
    for name in names:
        if name in seen:
            seen[name] += 1
            result.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 1
            result.append(name)
    return result


def _columns_from_records(records: list[dict], fieldnames: list[str]) -> list[Column]:
    """Build sanitized, de-duplicated columns with types inferred from records."""
    safe_names = _dedupe([_sanitize_name(f) for f in fieldnames])
    columns = []
    for field_name, safe_name in zip(fieldnames, safe_names):
        # Infer from a consensus of sampled values, not just the first one
        seen_types = set()
        sampled = 0
        for row in records:
            value = row.get(field_name)
            if value is None or value == "":
                continue
            seen_types.add(_infer_type(value))
            sampled += 1
            if sampled >= 20:
                break
        seen_types.discard(ColumnType.UNKNOWN)
        if not seen_types:
            col_type = ColumnType.STRING
        elif len(seen_types) == 1:
            col_type = seen_types.pop()
        elif seen_types == {ColumnType.INTEGER, ColumnType.FLOAT}:
            col_type = ColumnType.FLOAT
        else:
            col_type = ColumnType.STRING
        columns.append(Column(
            name=safe_name,
            type=col_type,
            description=field_name if field_name != safe_name else None,
        ))

    # Set first column as primary key if it looks like an ID
    if columns and columns[0].name.lower() in ("id", "uuid", "key", "_id"):
        columns[0].primary_key = True
    return columns


def _inspect_delimited(filepath: str, delimiter: str = ",") -> Table:
    """Inspect a CSV/TSV file and return its schema as a Table."""
    name = _sanitize_name(Path(filepath).stem)

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        fieldnames = reader.fieldnames or []

        # Read a sample to infer types, then count remaining records
        sample_rows = []
        row_count = 0
        for row in reader:
            if row_count < 100:
                sample_rows.append(row)
            row_count += 1

    columns = _columns_from_records(sample_rows, list(fieldnames))
    return Table(name=name, columns=columns, row_count=row_count)


def _inspect_json(filepath: str) -> Table | None:
    """Inspect a JSON file and return its schema as a Table."""
    name = _sanitize_name(Path(filepath).stem)

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    # Handle both array of objects and single object
    if isinstance(data, list) and data and isinstance(data[0], dict):
        records = data
    elif isinstance(data, dict):
        records = [data]
    else:
        # Not a structured dataset — treat as a resource instead
        return None

    # Infer columns from sampled records (union of keys, preserving order)
    fieldnames: list[str] = []
    for record in records[:100]:
        for key in record:
            if key not in fieldnames:
                fieldnames.append(key)

    columns = _columns_from_records(records[:100], fieldnames)
    return Table(
        name=name,
        columns=columns,
        row_count=len(records) if isinstance(data, list) else 1,
    )


def _inspect_jsonl(filepath: str) -> Table | None:
    """Inspect a JSON Lines file (one JSON object per line)."""
    name = _sanitize_name(Path(filepath).stem)

    records = []
    row_count = 0
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row_count += 1
            if len(records) < 100:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    return None
                records.append(obj)

    if not records:
        return None

    fieldnames: list[str] = []
    for record in records:
        for key in record:
            if key not in fieldnames:
                fieldnames.append(key)

    columns = _columns_from_records(records, fieldnames)
    return Table(name=name, columns=columns, row_count=row_count)


class FileConnector(BaseConnector):
    """Connector for file-based data sources (CSV, TSV, JSON, JSONL, etc.).

    Inspects a directory of files — or a single file — and generates:
    - Tables for structured data (CSV, TSV, JSON arrays, JSONL)
    - Resources for unstructured data (text, markdown, etc.)

    URI format: a directory path (./data/) or a single file (./users.csv)
    """

    @property
    def source_type(self) -> str:
        return "files"

    def _get_path(self) -> str:
        return os.path.expanduser(self.uri)

    def validate(self) -> bool:
        """Check that the path exists and contains (or is) a supported file."""
        path = self._get_path()

        if os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                return True
            raise ValueError(
                f"Unsupported file type: {ext}. "
                f"Supported: {', '.join(SUPPORTED_EXTENSIONS.keys())}"
            )

        if not os.path.isdir(path):
            raise FileNotFoundError(f"Path not found: {path}")
        # Check for at least one supported file
        for f in os.listdir(path):
            ext = os.path.splitext(f)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                return True
        raise ValueError(
            f"No supported files found in {path}. "
            f"Supported: {', '.join(SUPPORTED_EXTENSIONS.keys())}"
        )

    def _inspect_file(
        self,
        filepath: str,
        tables: list[Table],
        resources: list[Resource],
        table_files: list[str],
    ):
        """Inspect a single file, appending to tables or resources."""
        filename = os.path.basename(filepath)
        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return
        mime_type = SUPPORTED_EXTENSIONS[ext]

        try:
            table = None
            if ext == ".csv":
                table = _inspect_delimited(filepath, delimiter=",")
            elif ext == ".tsv":
                table = _inspect_delimited(filepath, delimiter="\t")
            elif ext == ".json":
                table = _inspect_json(filepath)
            elif ext == ".jsonl":
                table = _inspect_jsonl(filepath)

            if table is not None:
                tables.append(table)
                table_files.append(filename)
            else:
                resources.append(Resource(
                    name=_sanitize_name(Path(filename).stem),
                    uri=filepath,
                    mime_type=mime_type,
                ))
        except Exception:
            # If a file can't be inspected, add as resource
            resources.append(Resource(
                name=_sanitize_name(Path(filename).stem),
                uri=filepath,
                mime_type=mime_type,
                description=f"Could not inspect: {filename}",
            ))

    def inspect(self) -> DataSourceSchema:
        """Inspect the file or directory and return the schema."""
        path = self._get_path()
        tables: list[Table] = []
        resources: list[Resource] = []
        table_files: list[str] = []  # source filename per table, parallel to tables

        if os.path.isfile(path):
            self._inspect_file(path, tables, resources, table_files)
        else:
            for filename in sorted(os.listdir(path)):
                filepath = os.path.join(path, filename)
                if os.path.isfile(filepath):
                    self._inspect_file(filepath, tables, resources, table_files)

        # De-duplicate table names (e.g. users.csv + users.json), then
        # map each final table name to its source file
        for table, unique in zip(tables, _dedupe([t.name for t in tables])):
            table.name = unique
        file_map = {t.name: f for t, f in zip(tables, table_files)}

        return DataSourceSchema(
            source_type="files",
            source_uri=path,
            tables=tables,
            resources=resources,
            metadata={
                "file_count": len(tables) + len(resources),
                "file_map": file_map,
                "is_single_file": os.path.isfile(path),
            },
        )


# Register this connector
register_connector("files", FileConnector)
