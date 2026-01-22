from dataclasses import dataclass
from typing import Dict, List


@dataclass
class IndicatorInfo:
    indicator_id: str
    name: str
    inputs: Dict[str, dict]
    path: str
    module_hash: str


def discover_indicators(root_path: str) -> List[IndicatorInfo]:
    _ = root_path
    return []
