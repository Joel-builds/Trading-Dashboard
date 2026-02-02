from __future__ import annotations

import re
from typing import Any, Dict, Tuple


ID_RE = re.compile(r"^[a-z0-9_]+$")


def validate_schema(schema: Dict[str, Any]) -> Tuple[bool, str]:
    if not isinstance(schema, dict):
        return False, "schema must be a dict"
    strategy_id = schema.get("id")
    name = schema.get("name")
    inputs = schema.get("inputs")
    if not strategy_id or not isinstance(strategy_id, str):
        return False, "schema.id is required"
    if not ID_RE.match(strategy_id):
        return False, "schema.id must match [a-z0-9_]+"
    if not name or not isinstance(name, str):
        return False, "schema.name is required"
    if inputs is None or not isinstance(inputs, dict):
        return False, "schema.inputs must be a dict"
    for key, spec in inputs.items():
        if not isinstance(spec, dict):
            return False, f"input {key} must be a dict"
        field_type = spec.get("type")
        if field_type not in ("int", "float", "bool", "select"):
            return False, f"input {key} has invalid type"
        if "default" not in spec:
            return False, f"input {key} missing default"
        if field_type in ("int", "float"):
            if "min" not in spec or "max" not in spec:
                return False, f"input {key} missing min/max"
        if field_type == "select":
            options = spec.get("options")
            if not isinstance(options, list) or not options:
                return False, f"input {key} missing options"
    return True, ""


def resolve_params(schema: Dict[str, Any], user_values: Dict[str, Any]) -> Dict[str, Any]:
    resolved: Dict[str, Any] = {}
    inputs = schema.get("inputs") or {}
    for key, spec in inputs.items():
        field_type = spec.get("type")
        if key in user_values:
            value = user_values[key]
        else:
            value = spec.get("default")
        if field_type == "int":
            try:
                value = int(value)
            except Exception:
                value = int(spec.get("default", 0))
            min_v = int(spec.get("min", -999999))
            max_v = int(spec.get("max", 999999))
            value = max(min_v, min(max_v, value))
        elif field_type == "float":
            try:
                value = float(value)
            except Exception:
                value = float(spec.get("default", 0.0))
            min_v = float(spec.get("min", -1e12))
            max_v = float(spec.get("max", 1e12))
            value = max(min_v, min(max_v, value))
        elif field_type == "bool":
            value = bool(value)
        elif field_type == "select":
            options = spec.get("options") or []
            if value not in options:
                value = options[0] if options else value
        resolved[key] = value
    return resolved
