"""
MCP-Maker MongoDB Connector — Inspect MongoDB databases.

Each collection becomes a table. Schema is inferred by sampling documents.
"""


from ..core.schema import (
    Column,
    ColumnType,
    DataSourceSchema,
    Table,
)
from .base import BaseConnector, register_connector
from .utils import sanitize_name as _sanitize_name

# Map BSON/Python types to our universal types
_BSON_TYPE_MAP = {
    "str": ColumnType.STRING,
    "int": ColumnType.INTEGER,
    "float": ColumnType.FLOAT,
    "bool": ColumnType.BOOLEAN,
    "datetime": ColumnType.DATETIME,
    "ObjectId": ColumnType.STRING,
    "list": ColumnType.JSON,
    "dict": ColumnType.JSON,
    "NoneType": ColumnType.UNKNOWN,
}


def _python_type_to_column_type(value) -> ColumnType:
    """Map a Python value to a ColumnType."""
    type_name = type(value).__name__
    return _BSON_TYPE_MAP.get(type_name, ColumnType.STRING)


class MongoDBConnector(BaseConnector):
    """Connector for MongoDB databases.

    Inspects all collections, sampling documents to infer schema.

    URI format: mongodb://user:pass@host:27017/dbname
                mongodb+srv://user:pass@cluster.example.mongodb.net/dbname
    """

    @property
    def source_type(self) -> str:
        return "mongodb"

    def _get_database_name(self) -> str:
        """Extract the database name from the MongoDB URI."""
        from urllib.parse import urlparse
        parsed = urlparse(self.uri)
        db_name = parsed.path.lstrip("/")
        if not db_name:
            raise ValueError(
                "MongoDB URI must include a database name. "
                "Example: mongodb://localhost:27017/mydb"
            )
        return db_name

    def validate(self) -> bool:
        """Check that the MongoDB server is accessible."""
        try:
            import pymongo  # noqa: F401
        except ImportError:
            raise ImportError(
                "pymongo is required for MongoDB support. "
                "Install it with: pip install mcp-maker[mongodb]"
            )

        from pymongo import MongoClient
        client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
        try:
            client.server_info()
            return True
        except Exception as e:
            raise ConnectionError(f"Cannot connect to MongoDB: {e}")
        finally:
            client.close()

    def inspect(self) -> DataSourceSchema:
        """Inspect the MongoDB database and return its schema."""
        from pymongo import MongoClient

        client = MongoClient(self.uri, serverSelectionTimeoutMS=10000)
        db_name = self._get_database_name()
        db = client[db_name]

        tables = []
        collection_name_map = {}  # safe table name -> actual collection name

        for collection_name in sorted(db.list_collection_names()):
            # Skip system collections
            if collection_name.startswith("system."):
                continue

            collection = db[collection_name]
            row_count = collection.estimated_document_count()

            # Sample documents to infer schema
            sample = list(collection.find().limit(100))

            # Aggregate all field names and their types. A null in an early
            # document must not lock the field to UNKNOWN — later non-null
            # values refine the type.
            field_types: dict[str, ColumnType] = {}
            field_order: list[str] = []
            for doc in sample:
                for key, value in doc.items():
                    if key not in field_types:
                        field_order.append(key)
                        field_types[key] = _python_type_to_column_type(value)
                    elif field_types[key] == ColumnType.UNKNOWN:
                        field_types[key] = _python_type_to_column_type(value)

            # _id first, then remaining fields in first-seen order
            if "_id" in field_order:
                field_order.remove("_id")
                field_order.insert(0, "_id")

            columns = []
            for field_name in field_order:
                col_type = field_types[field_name]
                columns.append(Column(
                    name=field_name,
                    type=ColumnType.STRING if col_type == ColumnType.UNKNOWN else col_type,
                    nullable=True,
                    primary_key=(field_name == "_id"),
                ))

            safe_name = _sanitize_name(collection_name)
            if safe_name in collection_name_map:
                safe_name = f"{safe_name}_{len(collection_name_map)}"
            collection_name_map[safe_name] = collection_name
            tables.append(Table(
                name=safe_name,
                columns=columns,
                row_count=row_count,
                description=collection_name if collection_name != safe_name else None,
            ))

        client.close()

        return DataSourceSchema(
            source_type="mongodb",
            source_uri=self.uri,
            tables=tables,
            metadata={
                "database": db_name,
                "collection_count": len(tables),
                "collection_name_map": collection_name_map,
            },
        )


# Register this connector (plain and Atlas SRV schemes)
register_connector("mongodb", MongoDBConnector)
register_connector("mongodb+srv", MongoDBConnector)
