"""Field-by-field conflict resolution; Python replica of packages/domain/src/conflict.ts (R6).

The op arriving last wins a contested field. Device clocks are never read.
"""
from typing import Any


def resolve_field_conflicts(record: dict[str, Any], op: dict[str, Any]) -> dict[str, Any]:
    server_version = record["server_version"] + 1
    fields = dict(record["fields"])
    field_versions = dict(record["field_versions"])
    conflicts: list[dict[str, Any]] = []

    for field, value in op["changes"].items():
        if field_versions.get(field, 0) > op["base_version"]:
            conflicts.append(
                {
                    "field": field,
                    "discarded_value": record["fields"].get(field),
                    "kept_value": value,
                    "discarded_by": op["author_id"],
                    "base_version": op["base_version"],
                    "server_version": server_version,
                }
            )
        fields[field] = value
        field_versions[field] = server_version

    return {
        "fields": fields,
        "field_versions": field_versions,
        "server_version": server_version,
        "has_conflict": bool(conflicts),
        "conflicts": conflicts,
    }
