from typing import Dict, TypedDict


class IndicatorSchema(TypedDict):
    id: str
    name: str
    inputs: Dict[str, dict]
