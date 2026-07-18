"""
MCP-Maker HubSpot Connector — Inspect HubSpot CRM.

Features:
    - Object discovery (Contacts, Companies, Deals)
    - Custom property schema mapping with exact UI labels
    - Private App Token authentication

URI format: hubspot://pat=YOUR_TOKEN
Auth: Extract from URI or HUBSPOT_ACCESS_TOKEN env var
"""

import os
import urllib.parse

from ..core.schema import (
    Column,
    ColumnType,
    DataSourceSchema,
    Table,
)
from .base import BaseConnector, register_connector
from .utils import sanitize_name as _sanitize_name

HUBSPOT_TYPE_MAP = {
    "string": ColumnType.STRING,
    "number": ColumnType.FLOAT,
    "date": ColumnType.DATETIME,
    "datetime": ColumnType.DATETIME,
    "enumeration": ColumnType.STRING,
    "bool": ColumnType.BOOLEAN,
    "phone_number": ColumnType.STRING,
}

# The objects we will discover by default
DEFAULT_OBJECTS = [
    "contacts", "companies", "deals", "tickets", "products", "quotes",
    "notes", "tasks", "meetings", "emails", "calls"
]

class HubSpotConnector(BaseConnector):
    """Connector for HubSpot CRM databases.

    Authentication:
        Provide `pat=` in the URI, or set the `HUBSPOT_ACCESS_TOKEN` env var.
    """

    @property
    def source_type(self) -> str:
        return "hubspot"

    def _get_api_key(self) -> str:
        """Get API key from URI or environment."""
        uri = self.uri
        if uri.startswith("hubspot://pat="):
            return uri[len("hubspot://pat="):]

        parsed = urllib.parse.urlparse(uri)
        if parsed.password:
            return parsed.password

        query = urllib.parse.parse_qs(parsed.query)
        if "pat" in query:
            return query["pat"][0]

        token = os.environ.get("HUBSPOT_ACCESS_TOKEN")
        if not token:
            raise ValueError(
                "HubSpot Private App Token not found.\n"
                "Provide it in the URI (hubspot://pat=YOUR_TOKEN) or set HUBSPOT_ACCESS_TOKEN."
            )
        return token

    def _sanitize_uri(self) -> str:
        """Return URI with token redacted for safe use in error messages."""
        uri = self.uri
        if uri.startswith("hubspot://pat="):
            return "hubspot://pat=***REDACTED***"
        return uri.split("?")[0] + "?***"

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._get_api_key()}",
            "Content-Type": "application/json",
        }

    def validate(self) -> bool:
        """Validate connection by fetching the current PAT metadata."""
        try:
            import requests
        except ImportError:
            raise ImportError(
                "HubSpot support requires the requests library.\n"
                "Install it with: pip install mcp-maker[hubspot]"
            )

        resp = requests.get(
            "https://api.hubapi.com/crm/v3/properties/contacts",
            headers=self._get_headers(),
            timeout=10,
        )
        if resp.status_code == 401:
            raise ConnectionError("Invalid HubSpot Private App Token.")
        resp.raise_for_status()
        return True

    def inspect(self) -> DataSourceSchema:
        """Inspect HubSpot objects and return their custom properties."""
        import requests

        tables = []
        headers = self._get_headers()

        # Dynamically discover Custom Objects if the token allows it
        objects_to_inspect = list(DEFAULT_OBJECTS)
        try:
            schemas_resp = requests.get(
                "https://api.hubapi.com/crm/v3/schemas",
                headers=headers,
                timeout=10,
            )
            if schemas_resp.status_code == 200:
                for schema in schemas_resp.json().get("results", []):
                    fq_name = schema.get("fullyQualifiedName")
                    if fq_name and fq_name not in objects_to_inspect:
                        objects_to_inspect.append(fq_name)
        except Exception:
            pass  # Silently skip custom object discovery if scopes are missing

        # The mapping of internal name to its options/metadata for Jinja
        select_options_map = {}
        object_type_map = {}  # safe table name -> actual HubSpot object type

        for obj_type in objects_to_inspect:
            try:
                resp = requests.get(
                    f"https://api.hubapi.com/crm/v3/properties/{obj_type}",
                    headers=headers,
                    timeout=15,
                )
                if resp.status_code in [401, 403, 404]:
                    continue  # Gracefully skip objects this PAT lacks access to
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                continue  # Skip gracefully on random network or API errors

            columns = []
            field_opts = {}

            for prop in data.get("results", []):
                if prop.get("hidden"):
                    continue

                prop_name = prop["name"]
                prop_label = prop.get("label", prop_name)
                prop_type = prop.get("type", "string")

                # The LLM needs the "label" to understand the field context
                desc = f"{prop_label}"

                # Expose enumeration (select) options
                if prop_type == "enumeration" and prop.get("options"):
                    opts = [opt["label"] for opt in prop["options"] if not opt.get("hidden")]
                    field_opts[prop_name] = opts
                    desc += f" (Options: {', '.join(opts[:5])}{'...' if len(opts)>5 else ''})"

                col_type = HUBSPOT_TYPE_MAP.get(prop_type, ColumnType.STRING)

                columns.append(Column(
                    name=prop_name,
                    type=col_type,
                    nullable=True,
                    primary_key=prop.get("hasUniqueValue", False),
                    description=desc,
                ))

            select_options_map[_sanitize_name(obj_type)] = field_opts

            # HubSpot object row_count requires a POST to the search endpoint.
            # A failed search must report "unknown", not a fake 0.
            try:
                search_resp = requests.post(
                    f"https://api.hubapi.com/crm/v3/objects/{obj_type}/search",
                    headers=headers,
                    json={"limit": 1},
                    timeout=10,
                )
                if search_resp.status_code == 200:
                    row_count = search_resp.json().get("total")
                else:
                    row_count = None
            except Exception:
                row_count = None

            safe_name = _sanitize_name(obj_type)
            object_type_map[safe_name] = obj_type
            tables.append(Table(
                name=safe_name,
                columns=columns,
                row_count=row_count,
                description=f"HubSpot {obj_type} object",
            ))

        return DataSourceSchema(
            source_type="hubspot",
            source_uri=self.uri,
            tables=tables,
            metadata={
                "select_options_map": select_options_map,
                "object_type_map": object_type_map,
            },
        )

# Register this connector
register_connector("hubspot", HubSpotConnector)
