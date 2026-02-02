from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.util
import os
from typing import Dict, Iterable, List, Optional

from core.hot_reload import start_generic_watcher, GenericHotReloadWorker
from core.strategies.schema import validate_schema


@dataclass
class StrategyInfo:
    strategy_id: str
    name: str
    inputs: Dict[str, dict]
    path: str
    module_hash: str
    module: object


def discover_strategies(root_paths: str | Iterable[str]) -> List[StrategyInfo]:
    strategies: List[StrategyInfo] = []
    paths = [root_paths] if isinstance(root_paths, str) else list(root_paths)

    for root_path in paths:
        if not root_path or not os.path.isdir(root_path):
            continue
        for entry in os.listdir(root_path):
            if not entry.endswith(".py"):
                continue
            if entry.startswith("_"):
                continue
            path = os.path.join(root_path, entry)
            module = _load_module_from_path(path)
            if module is None:
                continue
            schema = _safe_schema(module)
            if not schema:
                continue
            ok, _ = validate_schema(schema)
            if not ok:
                continue
            strategy_id = str(schema.get("id") or os.path.splitext(entry)[0])
            name = str(schema.get("name") or strategy_id)
            inputs = schema.get("inputs") or {}
            module_hash = _hash_file(path)
            strategies.append(
                StrategyInfo(
                    strategy_id=strategy_id,
                    name=name,
                    inputs=inputs,
                    path=path,
                    module_hash=module_hash,
                    module=module,
                )
            )

    strategies.sort(key=lambda info: info.name.lower())
    return strategies


def start_strategy_watcher(
    root_paths: str | Iterable[str],
    on_change,
    on_error,
    poll_interval: float = 1.0,
) -> Optional[GenericHotReloadWorker]:
    return start_generic_watcher(discover_strategies, root_paths, on_change, on_error, poll_interval=poll_interval)


def _load_module_from_path(path: str) -> Optional[object]:
    try:
        spec = importlib.util.spec_from_file_location(f"strategy_{os.path.basename(path)}", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


def _safe_schema(module: object) -> Optional[Dict[str, dict]]:
    try:
        schema_fn = getattr(module, "schema", None)
        if schema_fn is None:
            return None
        schema = schema_fn()
        if not isinstance(schema, dict):
            return None
        return schema
    except Exception:
        return None


def _hash_file(path: str) -> str:
    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(8192)
                if not chunk:
                    break
                hasher.update(chunk)
    except Exception:
        return ""
    return hasher.hexdigest()
