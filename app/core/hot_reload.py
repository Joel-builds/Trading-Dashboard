from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class ReloadEvent:
    path: str
    module_hash: str


def start_watcher(root_path: str, on_change: Callable[[ReloadEvent], None], debounce_ms: int = 500) -> Optional[object]:
    _ = (root_path, on_change, debounce_ms)
    return None
