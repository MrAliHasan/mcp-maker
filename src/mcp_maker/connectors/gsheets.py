"""
MCP-Maker Google Sheets Connector — Inspect Google Spreadsheets.

Features:
    - Worksheet discovery (each sheet tab → a table)
    - Column type inference from data
    - Row counts
    - Service account or API key authentication

URI format: gsheet://SPREADSHEET_ID
Auth: GOOGLE_SERVICE_ACCOUNT_FILE env var pointing to credentials JSON
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
from .utils import sanitize_name as _sanitize_name


def _infer_type(values: list) -> ColumnType:
    """Infer a column type from sample values."""
    if not values:
        return ColumnType.STRING

    # Sample up to 20 non-empty values
    samples = [v for v in values[:20] if v is not None and str(v).strip()]
    if not samples:
        return ColumnType.STRING

    # Check if all are booleans
    bool_vals = {"true", "false", "yes", "no", "1", "0"}
    if all(str(v).lower() in bool_vals for v in samples):
        return ColumnType.BOOLEAN

    # Check if all are integers
    try:
        for v in samples:
            if isinstance(v, bool):
                continue
            if isinstance(v, int):
                continue
            int(str(v))
        return ColumnType.INTEGER
    except (ValueError, TypeError):
        pass

    # Check if all are floats
    try:
        for v in samples:
            if isinstance(v, (int, float)):
                continue
            float(str(v))
        return ColumnType.FLOAT
    except (ValueError, TypeError):
        pass

    return ColumnType.STRING


class GoogleSheetsConnector(BaseConnector):
    """Connector for Google Spreadsheets.

    Inspects all worksheets (tabs) in a Google Sheet, treating each as a table.
    The first row of each worksheet is used as column headers.

    Authentication:
        Set GOOGLE_SERVICE_ACCOUNT_FILE to the path of your service account JSON,
        OR set GOOGLE_CREDENTIALS_JSON to the JSON content directly.

    URI format: gsheet://SPREADSHEET_ID
    """

    @property
    def source_type(self) -> str:
        return "gsheet"

    def _get_spreadsheet_id(self) -> str:
        """Extract spreadsheet ID from URI."""
        uri = self.uri
        if uri.startswith("gsheet://"):
            return uri[len("gsheet://"):]
        # Handle full Google Sheets URLs
        if "docs.google.com/spreadsheets" in uri:
            # Extract ID from URL like /d/SPREADSHEET_ID/
            match = re.search(r"/d/([a-zA-Z0-9_-]+)", uri)
            if match:
                return match.group(1)
        return uri

    def _get_client(self):
        """Get an authenticated gspread client."""
        import gspread

        # Try service account file
        sa_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE")
        if sa_file and os.path.isfile(sa_file):
            return gspread.service_account(filename=sa_file)

        # Try JSON content directly
        sa_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
        if sa_json:
            import json
            import tempfile
            creds = json.loads(sa_json)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(creds, f)
                tmp_path = f.name
            try:
                client = gspread.service_account(filename=tmp_path)
                return client
            finally:
                os.unlink(tmp_path)

        # Try default credentials (e.g., on GCP)
        try:
            return gspread.service_account()
        except Exception:
            pass

        raise ValueError(
            "Google Sheets credentials not found.\n"
            "Set one of these environment variables:\n"
            "  GOOGLE_SERVICE_ACCOUNT_FILE=path/to/credentials.json\n"
            "  GOOGLE_CREDENTIALS_JSON='{...json content...}'\n"
            "Get credentials from: https://console.cloud.google.com/iam-admin/serviceaccounts"
        )

    def validate(self) -> bool:
        """Check that gspread is installed and credentials work."""
        try:
            import gspread  # noqa: F401
        except ImportError:
            raise ImportError(
                "Google Sheets support requires gspread.\n"
                "Install it with: pip install mcp-maker[gsheets]"
            )

        client = self._get_client()
        spreadsheet_id = self._get_spreadsheet_id()

        try:
            client.open_by_key(spreadsheet_id)
            return True
        except Exception as e:
            raise ConnectionError(
                f"Cannot access spreadsheet {spreadsheet_id}: {e}\n"
                "Make sure the spreadsheet is shared with your service account email."
            )

    def inspect(self) -> DataSourceSchema:
        """Inspect the Google Sheet and return its schema."""

        client = self._get_client()
        spreadsheet_id = self._get_spreadsheet_id()
        spreadsheet = client.open_by_key(spreadsheet_id)

        tables = []
        sheet_name_map = {}  # safe_name -> original_name

        for worksheet in spreadsheet.worksheets():
            original_name = worksheet.title
            safe_name = _sanitize_name(original_name)
            sheet_name_map[safe_name] = original_name

            # Get all values (first row = headers). get_all_values tolerates
            # duplicate/empty headers, unlike get_all_records which raises
            # and previously caused such sheets to be silently skipped.
            try:
                values = worksheet.get_all_values()
            except Exception:
                continue

            if not values or not any(h.strip() for h in values[0]):
                continue

            headers = [h.strip() for h in values[0]]
            data_rows = values[1:]

            # Sanitize + de-duplicate column names
            safe_headers: list[str] = []
            used: dict[str, int] = {}
            for h in headers:
                safe = _sanitize_name(h) if h else "_unnamed"
                if safe in used:
                    used[safe] += 1
                    safe = f"{safe}_{used[safe]}"
                else:
                    used[safe] = 1
                safe_headers.append(safe)

            columns = []
            for idx, (h, safe) in enumerate(zip(headers, safe_headers)):
                if not h:
                    continue  # skip truly empty header columns
                col_values = [row[idx] if idx < len(row) else None for row in data_rows]
                col_type = _infer_type(col_values) if data_rows else ColumnType.STRING
                columns.append(Column(
                    name=safe,
                    type=col_type,
                    nullable=True,
                    primary_key=False,
                    description=h,
                ))

            tables.append(Table(
                name=safe_name,
                columns=columns,
                row_count=len(data_rows),
                description=original_name,
            ))

        return DataSourceSchema(
            source_type="gsheet",
            source_uri=self.uri,
            tables=tables,
            metadata={
                "spreadsheet_id": spreadsheet_id,
                "spreadsheet_title": spreadsheet.title,
                "sheet_name_map": sheet_name_map,
            },
        )


# Register this connector
register_connector("gsheet", GoogleSheetsConnector)
