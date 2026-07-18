"""
MCP-Maker Redis Connector — Inspect Redis databases.

Discovers keys by type and groups them into logical "tables":
- String keys → key-value pairs
- Hash keys → structured records
- List keys → ordered collections
- Set keys → unique value sets
- Sorted Set keys → scored value sets
"""


from ..core.schema import (
    Column,
    ColumnType,
    DataSourceSchema,
    Table,
)
from .base import BaseConnector, register_connector


class RedisConnector(BaseConnector):
    """Connector for Redis databases.

    Scans keys, groups them by type, and generates tools for
    reading and writing key-value data.

    URI format: redis://host:6379/0
    """

    @property
    def source_type(self) -> str:
        return "redis"

    def _get_url(self) -> str:
        """Normalize the URI to a redis:// URL.

        Using redis.from_url preserves username (ACL), password, db number,
        and TLS — the previous manual parse silently dropped the username.
        """
        uri = self.uri
        if not uri.startswith("redis://") and not uri.startswith("rediss://"):
            uri = f"redis://{uri}"
        return uri

    def validate(self) -> bool:
        """Check that the Redis server is accessible."""
        try:
            import redis as redis_lib  # noqa: F401
        except ImportError:
            raise ImportError(
                "redis is required for Redis support. "
                "Install it with: pip install mcp-maker[redis]"
            )

        import redis as redis_lib
        client = redis_lib.from_url(self._get_url(), socket_connect_timeout=5)
        try:
            client.ping()
            return True
        except Exception as e:
            raise ConnectionError(f"Cannot connect to Redis: {e}")
        finally:
            client.close()

    def inspect(self) -> DataSourceSchema:
        """Inspect the Redis database and return its schema.

        Groups keys by their prefix (before the first ':' or '.') and type.
        Each group becomes a "table".
        """
        import redis as redis_lib

        client = redis_lib.from_url(self._get_url(), decode_responses=True)

        # Scan all keys and group by prefix + type
        key_groups: dict[str, dict] = {}
        cursor = 0
        sample_limit = 1000  # Limit scanning for large databases

        scanned = 0
        while scanned < sample_limit:
            cursor, keys = client.scan(cursor=cursor, count=100)
            for key in keys:
                key_type = client.type(key)
                # Extract prefix (group name)
                prefix = key.split(":")[0].split(".")[0] if (":" in key or "." in key) else key

                group_key = f"{prefix}_{key_type}"
                if group_key not in key_groups:
                    key_groups[group_key] = {
                        "prefix": prefix,
                        "type": key_type,
                        "count": 0,
                        "sample_keys": [],
                        "fields": set(),
                    }

                group = key_groups[group_key]
                group["count"] += 1

                if len(group["sample_keys"]) < 10:
                    group["sample_keys"].append(key)

                # For hash keys, sample fields
                if key_type == "hash" and len(group["fields"]) < 50:
                    try:
                        fields = client.hkeys(key)
                        group["fields"].update(fields)
                    except Exception:
                        pass

                scanned += 1
                if scanned >= sample_limit:
                    break

            if cursor == 0:
                break

        tables = []
        for group_key, group in sorted(key_groups.items()):
            columns = [
                Column(name="key", type=ColumnType.STRING, primary_key=True),
            ]

            key_type = group["type"]

            if key_type == "string":
                columns.append(Column(name="value", type=ColumnType.STRING))
            elif key_type == "hash":
                for field in sorted(group["fields"]):
                    columns.append(Column(name=field, type=ColumnType.STRING, nullable=True))
            elif key_type == "list":
                columns.append(Column(name="values", type=ColumnType.JSON))
                columns.append(Column(name="length", type=ColumnType.INTEGER))
            elif key_type == "set":
                columns.append(Column(name="members", type=ColumnType.JSON))
                columns.append(Column(name="cardinality", type=ColumnType.INTEGER))
            elif key_type == "zset":
                columns.append(Column(name="members_with_scores", type=ColumnType.JSON))
                columns.append(Column(name="cardinality", type=ColumnType.INTEGER))

            safe_name = group["prefix"].replace("-", "_").replace(".", "_").lower()
            if not safe_name.isidentifier():
                safe_name = f"redis_{safe_name}"

            tables.append(Table(
                name=safe_name,
                columns=columns,
                row_count=group["count"],
                description=f"{group['prefix']} ({key_type})",
            ))

        # Add a meta table for overall DB info
        db_size = client.dbsize()
        client.close()

        # Note: no connection params in metadata — the URI may contain a
        # password and metadata can be persisted into generated artifacts.
        return DataSourceSchema(
            source_type="redis",
            source_uri=self.uri,
            tables=tables,
            metadata={
                "db_size": db_size,
                "key_groups": len(tables),
            },
        )


# Register this connector
register_connector("redis", RedisConnector)
register_connector("rediss", RedisConnector)
