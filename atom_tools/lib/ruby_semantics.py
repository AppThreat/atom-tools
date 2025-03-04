"""
Ruby semantic utils
"""
import re
from typing import List

from atom_tools.lib import HttpRoute


def _get_dangling_routes(i, kind, code, code_parts, url_prefix="/"):
    """
    Internal method

    Args:
        i:
        kind:
        code:
        code_parts:
        url_prefix:

    Returns:

    """
    routes = []
    url_pattern = _clean_url(f"{url_prefix}{re.sub('^:', '', code_parts[i + 1])}")
    if kind == "resources":
        routes.append(HttpRoute(url_pattern=url_pattern, method="GET"))
    if ("match " in code and "via: :all" in code) or ("only: [" not in code and "shallow:" not in code):
        routes.append(HttpRoute(url_pattern=f"{url_pattern}/new", method="GET"))
        routes.append(HttpRoute(url_pattern=url_pattern, method="POST"))
        routes.append(HttpRoute(url_pattern=f"{url_pattern}" + "/{id}", method="GET"))
        routes.append(HttpRoute(url_pattern=f"{url_pattern}" + "/{id}/edit", method="GET"))
        routes.append(HttpRoute(url_pattern=f"{url_pattern}" + "/{id}", method="PUT"))
        routes.append(HttpRoute(url_pattern=f"{url_pattern}" + "/{id}", method="DELETE"))
    return routes


def _clean_url(url_pattern):
    return re.sub('[,/]$', '', url_pattern)


def fix_url_params(path_str):
    if path_str == "*":
        return "/"
    s = []
    for p in path_str.split("/"):
        if p.startswith(":"):
            s.append("{" + p.removeprefix(":") + "}")
        elif p in ("*", "*.*", ".*"):
            s.append("{extra_path}")
        else:
            s.append(p)
    return "/".join(s)


def code_to_routes(code: str) -> List[HttpRoute]:
    """
    Convert code string to routes
    Args:
        code: Code snippet

    Returns:
        List of http routes
    """
    routes = []
    if not code:
        return []
    keyword_found = False
    for keyword in (
            "namespace", "scope", "concern", "resource", "resources", "get",
            "post", "patch", "delete", "put", "head", "match",
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
    has_scope = False
    for i, part in enumerate(code_parts):
        if not part or len(part) < 2:
            continue
        if part in ("scope",) or part.startswith("scope("):
            has_scope = True
            if len(code_parts) >= i + 1 and code_parts[i + 1].startswith('":'):
                url_prefix = f"""/{re.sub('[:",]', '', code_parts[i + 1])}"""
                continue
        if (part in ("resource", "resources", "namespace", "member")
                and len(code_parts) >= i + 1
                and code_parts[i + 1].startswith(":")):
            url_pattern = _clean_url(f"/{re.sub('^:', '', code_parts[i + 1])}")
            # Is there an alias for this patten
            if len(code_parts) > i + 3 and code_parts[i + 2] in ("path:", "path", "path("):
                url_pattern = _clean_url(code_parts[i + 3].replace('"', ""))
                routes += _get_dangling_routes(i, part, code, code_parts,
                                               f"{url_prefix}/{url_pattern}/")
                continue
            if len(code_parts) > i + 2 and code_parts[i + 2] in ("resources", "resource"):
                routes += _get_dangling_routes(i, code_parts[i + 2], code, code_parts, f"{url_prefix}/")
            elif i == len(code_parts) - 2 and part in ("resource", "resources"):
                routes += _get_dangling_routes(i, part, code, code_parts, f"{url_prefix}/")
            else:
                url_prefix = f"{url_prefix}{url_pattern}"
            continue
        if part in ("collection", "member", "concern", "do", "as:", "constraints:") or part.startswith(
                ":") or part.startswith('"'):
            continue
        if part == "end" and url_prefix:
            url_prefix = "/".join(url_prefix.split("/")[:-1])
        for m in ("get", "post", "delete", "patch", "put", "head", "options"):
            if part == m and len(code_parts) > i + 1 and (code_parts[i + 1].startswith('"') or code_parts[i + 1].startswith("'")):
                fmt_path = fix_url_params(code_parts[i + 1].replace('"', "").replace("'", ""))
                full_path = fmt_path if not url_prefix and fmt_path in ("/", "*") else f"""{url_prefix}/{fmt_path.removeprefix("/")}"""
                # * is not allowed by swagger
                if m == "options" and full_path == "*":
                    full_path = "/"
                routes.append(
                    HttpRoute(url_pattern=full_path,
                              method=m.upper() if m != "patch" else "PUT"))
                break
    if has_resources:
        if not routes:
            for i, part in enumerate(code_parts):
                for m in ("resource", "resources"):
                    if part == m and code_parts[i + 1].startswith(':') and (
                            i == len(code_parts) - 2 or (len(code_parts) > i + 2 and code_parts[i + 1] != "do")):
                        routes += _get_dangling_routes(i, m, code, code_parts, f"{url_prefix}/" if has_scope else "/")

    return routes
