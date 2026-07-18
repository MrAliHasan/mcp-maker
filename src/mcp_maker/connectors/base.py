"""
MCP-Maker Base Connector — Abstract interface for all data source connectors.
"""

from abc import ABC, abstractmethod

from ..core.schema import DataSourceSchema


class BaseConnector(ABC):
    """Abstract base class for data source connectors.

    Every connector must implement:
    - `inspect()`: Analyze the data source and return its schema.
    - `validate()`: Check if the connection/path is valid.

    To add a new connector, subclass this and implement both methods.
    Then register it in the connector registry.
    """

    def __init__(self, uri: str):
        """Initialize the connector with a data source URI.

        Args:
            uri: Connection string, file path, or URL for the data source.
        """
        self.uri = uri

    @abstractmethod
    def validate(self) -> bool:
        """Validate that the data source is accessible.

        Returns:
            True if the data source can be connected to.

        Raises:
            ConnectionError: If the data source cannot be reached.
            FileNotFoundError: If the file/path doesn't exist.
        """

    @abstractmethod
    def inspect(self) -> DataSourceSchema:
        """Inspect the data source and return its schema.

        Returns:
            DataSourceSchema describing all tables, columns,
            and resources found in the data source.
        """

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the type identifier for this connector (e.g., 'sqlite')."""


# ──── Connector Registry ────

_CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {}


def register_connector(scheme: str, connector_class: type[BaseConnector]):
    """Register a connector class for a URI scheme."""
    _CONNECTOR_REGISTRY[scheme.lower()] = connector_class


def get_connector(uri: str) -> BaseConnector:
    """Get the appropriate connector for a given URI.

    Determines the connector type from the URI scheme or file extension.

    Args:
        uri: The data source URI (e.g., 'sqlite:///my.db', './data/')

    Returns:
        An initialized connector instance.

    Raises:
        ValueError: If no connector matches the URI.
    """
    import os

    # Check for explicit scheme (sqlite:///, postgres://, etc.)
    if "://" in uri:
        scheme = uri.split("://")[0].lower()
        if scheme in _CONNECTOR_REGISTRY:
            return _CONNECTOR_REGISTRY[scheme](uri)

        # Dependency hints — keys must match actual URI schemes
        hints = {
            "postgres": "pip install mcp-maker[postgres]",
            "postgresql": "pip install mcp-maker[postgres]",
            "mysql": "pip install mcp-maker[mysql]",
            "airtable": "pip install mcp-maker[airtable]",
            "gsheet": "pip install mcp-maker[gsheets]",
            "gsheets": "pip install mcp-maker[gsheets]",
            "notion": "pip install mcp-maker[notion]",
            "excel": "pip install mcp-maker[excel]",
            "mongodb": "pip install mcp-maker[mongodb]",
            "mongodb+srv": "pip install mcp-maker[mongodb]",
            "supabase": "pip install mcp-maker[supabase]",
            "openapi": "pip install mcp-maker[openapi]",
            "redis": "pip install mcp-maker[redis]",
            "rediss": "pip install mcp-maker[redis]",
            "hubspot": "pip install mcp-maker[hubspot]",
        }
        if scheme in hints:
            raise ValueError(f"Missing dependencies for {scheme}. Please install them: {hints[scheme]}")

    # Check if it's a directory → FileConnector
    if os.path.isdir(uri):
        if "files" in _CONNECTOR_REGISTRY:
            return _CONNECTOR_REGISTRY["files"](uri)

    # Check file extension for known single-file formats
    if os.path.isfile(uri):
        ext = os.path.splitext(uri)[1].lower()
        if ext in (".db", ".sqlite", ".sqlite3"):
            if "sqlite" in _CONNECTOR_REGISTRY:
                return _CONNECTOR_REGISTRY["sqlite"](f"sqlite:///{uri}")
        if ext in (".xlsx", ".xlsm", ".xltx", ".xltm"):
            if "excel" in _CONNECTOR_REGISTRY:
                return _CONNECTOR_REGISTRY["excel"](f"excel:///{uri}")
        if ext in (".csv", ".tsv", ".json", ".jsonl"):
            if "files" in _CONNECTOR_REGISTRY:
                return _CONNECTOR_REGISTRY["files"](uri)

    raise ValueError(
        f"No connector found for URI: {uri}\n"
        f"Available connectors: {', '.join(_CONNECTOR_REGISTRY.keys())}\n"
        f"Examples:\n"
        f"  mcp-maker init sqlite:///my.db\n"
        f"  mcp-maker init ./data/\n"
        f"  mcp-maker init postgres://user:pass@localhost/mydb"
    )
