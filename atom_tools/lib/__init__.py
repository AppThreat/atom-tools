"""
Common dataclasses
"""
from dataclasses import dataclass


@dataclass
class HttpRoute:
    url_pattern: str
    method: str
