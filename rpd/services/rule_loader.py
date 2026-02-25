"""Load and apply critical fields rule pack."""

from pathlib import Path
from typing import Any

import yaml


def load_rule_pack(path: str | Path | None = None) -> dict[str, Any]:
    """Load critical fields rule pack from YAML."""
    if path is None:
        path = Path(__file__).parent.parent.parent / "rule_packs" / "critical_fields.yaml"
    path = Path(path)
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_critical_fields_for_type(rule_pack: dict, document_type: str) -> list[dict]:
    """Get critical field definitions for a document type."""
    types = rule_pack.get("document_types", {})
    if document_type not in types:
        return []
    cfg = types[document_type]
    # Handle extends
    extends = cfg.get("extends")
    base_fields = []
    if extends and extends in types:
        base_fields = get_critical_fields_for_type(rule_pack, extends)
    fields = cfg.get("critical_fields", [])
    return base_fields + fields


def get_severity_for_path(rule_pack: dict, document_type: str, path: str) -> str:
    """Get severity for a field path from rule pack. Default: low."""
    defaults = rule_pack.get("defaults", {})
    default = defaults.get("unspecified_field_severity", "low")
    fields = get_critical_fields_for_type(rule_pack, document_type)
    for f in fields:
        if f.get("path") == path:
            return f.get("severity_on_conflict", default)
    return default
