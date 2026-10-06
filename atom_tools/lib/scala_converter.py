"""
Scala converter helper
"""

from atom_tools.lib.slices import AtomSlice
from atom_tools.lib.utils import extract_params


def extract_pattern(route_pattern):
    parts = []
    for part in route_pattern.split("/"):
        if part.startswith(":"):
            parts.append("{" + part.replace(":", "") + "}")
        elif part.endswith("*") or part.startswith("*"):
            parts.append("{extra_path}")
            continue
        else:
            parts.append(part)
    route_pattern = "/".join(parts)
    params = extract_params(route_pattern)
    return route_pattern, params


def convert(usages: AtomSlice | None, semantics: AtomSlice):
    result = {}
    if not semantics or not semantics.content:
        return result
    content = semantics.content
    if content.get("_meta", {}).get("schemaVersion") == "scalasem/2":
        return convert_endpoints(content)
    return convert_routes(content)


def convert_endpoints(content: dict):
    """Version 2 scalasem reports carry every framework's routes in
    ``endpoints[]``, with the resolved path pattern, the handler and the file
    and line it was declared at."""
    result = {}
    for endpoint in content.get("endpoints", []):
        route_pattern, params = extract_pattern(endpoint.get("path", ""))
        handler = endpoint.get("handler")
        method = str(endpoint.get("method", "GET")).lower()
        amethod = {
            "operationId": handler or method,
            "responses": {"200": {"description": ""}},
        }
        if handler:
            amethod["x-atom-usages"] = {
                "method": handler,
                "file": endpoint.get("file"),
                "line": endpoint.get("line"),
            }
        if params:
            amethod["parameters"] = params
        if endpoint.get("authenticated"):
            amethod["security"] = [{"bearerAuth": []}]
        result.setdefault(route_pattern, {})
        result[route_pattern].setdefault(method, amethod)
    return result


def convert_routes(content: dict):
    """Version 1 semantics slices carry the Play route file only."""
    result = {}
    routes = content.get("config", {}).get("routes")
    if not routes:
        return result
    i = 0
    for route in routes:
        i = i + 1
        route_pattern, params = extract_pattern(route.get("pattern"))
        controller_method = route.get("controllerMethod")
        amethod = {
            "operationId": f"{controller_method if controller_method else route.get('method')}-{str(i)}",
            "responses": {"200": {"description": ""}},
        }
        if controller_method:
            amethod["x-atom-usages"] = {"method": controller_method}
        if params:
            amethod["parameters"] = params
        if not result.get(route_pattern):
            result[route_pattern] = {route.get("method").lower(): amethod}
        else:
            result[route_pattern].update({route.get("method").lower(): amethod})
    return result
