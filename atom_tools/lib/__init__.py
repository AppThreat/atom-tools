"""
Common dataclasses
"""
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class HttpRoute:
    url_pattern: str
    method: str
    servers: Optional[List[str]] = None
