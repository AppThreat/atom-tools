"""
Ruby semantic utils
"""
import re
from typing import List

from atom_tools.lib import HttpRoute


def _get_dangling_routes(i, kind, code, code_parts, url_prefix="/"):
    routes = []
    url_pattern = f"{url_prefix}{re.sub('^:', '', code_parts[i + 1])}"
    if kind == "resources":
        routes.append(HttpRoute(url_pattern=url_pattern, method="GET"))
    if "only: [" not in code and "shallow:" not in code:
        routes.append(HttpRoute(url_pattern=f"{url_pattern}/new", method="GET"))
        routes.append(HttpRoute(url_pattern=url_pattern, method="POST"))
        routes.append(HttpRoute(url_pattern=f"{url_pattern}/:id", method="GET"))
        routes.append(HttpRoute(url_pattern=f"{url_pattern}/:id/edit", method="GET"))
        routes.append(HttpRoute(url_pattern=f"{url_pattern}/:id", method="PUT"))
        routes.append(HttpRoute(url_pattern=f"{url_pattern}/:id", method="DELETE"))
    return routes


def code_to_routes(code: str, file_name: str | None = None, method_full_name: str | None = None) -> List[HttpRoute]:
    routes = []
    if not code:
        return []
    keyword_found = False
    for keyword in (
            "namespace", "scope", "concern", "resource", "resources", "get", "post", "patch", "delete", "put", "head",
            "options"):
        if f"{keyword} " in code:
            keyword_found = True
            break
    if not keyword_found:
        return []
    code_parts = code.strip().replace("...", "").split()
    # Dangling resources - leads to many kinds of automatic routes
    has_resources = "resources " in code or "resource " in code
    url_prefix = ""
    for i, part in enumerate(code_parts):
        if part in ("resource", "resources", "namespace") and len(code_parts) >= i + 1 and code_parts[i + 1].startswith(
                ":"):
            url_pattern = f"/{re.sub('^:', '', code_parts[i + 1])}"
            url_pattern = re.sub('[,/]$', '', url_pattern)
            if len(code_parts) > i + 2 and code_parts[i + 2] in ("resources", "resource"):
                routes += _get_dangling_routes(i, code_parts[i + 2], code, code_parts, f"{url_prefix}/")
            elif i == len(code_parts) - 2 and part in ("resource", "resources"):
                routes += _get_dangling_routes(i, part, code, code_parts, f"{url_prefix}/")
            else:
                url_prefix = f"{url_prefix}{url_pattern}"
            continue
        if part in ("collection", "concern", "do") or part.startswith(":") or part.startswith('"'):
            continue
        if part == "end" and url_prefix:
            url_prefix = "/".join(url_prefix.split("/")[:-1])
        for m in ("get", "post", "delete", "patch", "put", "head", "options"):
            if part == m and len(code_parts) > i + 1 and code_parts[i + 1].startswith('"'):
                routes.append(
                    HttpRoute(url_pattern=f"{url_prefix}/{code_parts[i + 1].replace('"', "")}",
                              method=m.upper() if m != "patch" else "PUT"))
                break
    if has_resources:
        if not routes:
            for i, part in enumerate(code_parts):
                for m in ("resource", "resources"):
                    if part == m and code_parts[i + 1].startswith(':') and (
                            i == len(code_parts) - 2 or (len(code_parts) > i + 2 and code_parts[i + 1] != "do")):
                        routes += _get_dangling_routes(i, m, code, code_parts, "/")

    return routes
