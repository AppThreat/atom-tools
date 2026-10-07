"""
Scala converter helper
"""

import re
from copy import deepcopy
from typing import Dict, List

from atom_tools.lib.kosi_converter import normalize_path, unique_operation_ids
from atom_tools.lib.slices import AtomSlice
from atom_tools.lib.utils import extract_params

# Every method an OpenAPI path item can carry. A route that serves any method
# (an akka-http or pekko `path` block with no verb directive) is expanded to
# all of them, each operation marked so the expansion is never mistaken for
# eight declarations.
_ALL_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


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
    if is_v2_report(content):
        return convert_endpoints(content)
    return convert_routes(content)


def is_v2_report(content: Dict) -> bool:
    return (content or {}).get("_meta", {}).get("schemaVersion") == "scalasem/2"


def extensions(semantics: AtomSlice | None) -> Dict[str, List[Dict]]:
    """Document-level ``x-scalasem-*`` lists: endpoints whose method an
    OpenAPI path item cannot carry, kept rather than dropped."""
    if not semantics or not is_v2_report(semantics.content):
        return {}
    unsupported = [
        _endpoint_ref(endpoint)
        for endpoint in semantics.content.get("endpoints", [])
        if _methods(endpoint) is None
    ]
    return {"x-scalasem-unsupported-methods": unsupported} if unsupported else {}


def _methods(endpoint: Dict) -> List[str] | None:
    method = str(endpoint.get("method") or "").lower()
    if method == "any":
        return list(_ALL_METHODS)
    return [method] if method in _ALL_METHODS else None


def _endpoint_ref(endpoint: Dict) -> Dict:
    return {
        key: endpoint[key]
        for key in ("framework", "method", "path", "handler", "file", "line")
        if endpoint.get(key) not in (None, "")
    }


def _path_param_names(path: str) -> List[str]:
    return list(dict.fromkeys(re.findall(r"\{([^{}]+)\}", path)))


def _build_operation(endpoint: Dict, path: str) -> Dict:
    operation: Dict = {"responses": {"200": {"description": ""}}}
    if handler := endpoint.get("handler"):
        operation["operationId"] = handler
    file_path = endpoint.get("file")
    line_number = endpoint.get("line")
    if file_path and isinstance(line_number, int):
        operation["x-atom-usages"] = {"call": {file_path: [line_number]}}
    if framework := endpoint.get("framework"):
        operation["x-scalasem-framework"] = framework
    # scalasem states that a route requires authentication, not which scheme
    # it uses, so the document records the requirement without inventing a
    # security scheme.
    if endpoint.get("authenticated") is True:
        operation["x-scalasem-authenticated"] = True
    parameters = [
        {"name": name, "in": "path", "required": True, "schema": {"type": "string"}}
        for name in _path_param_names(path)
    ]
    if parameters:
        operation["parameters"] = parameters
    return operation


def _merge_operations(existing: Dict, new: Dict) -> Dict:
    """One path and method declared twice (a route file mounted at two
    prefixes that resolve alike, or two frameworks serving one route) keeps
    every handler and every declaration line."""
    merged = deepcopy(existing)
    if new.get("operationId") and new.get("operationId") != existing.get("operationId"):
        handlers = merged.setdefault(
            "x-scalasem-handlers", [h for h in [existing.get("operationId")] if h]
        )
        if new["operationId"] not in handlers:
            handlers.append(new["operationId"])
    if not (existing.get("x-scalasem-any-method") and new.get("x-scalasem-any-method")):
        merged.pop("x-scalasem-any-method", None)
    if new.get("x-scalasem-authenticated"):
        merged["x-scalasem-authenticated"] = True
    new_calls = new.get("x-atom-usages", {}).get("call", {})
    if new_calls:
        existing_calls = merged.setdefault("x-atom-usages", {}).setdefault("call", {})
        for file_path, line_numbers in new_calls.items():
            bucket = existing_calls.setdefault(file_path, [])
            for line_number in line_numbers:
                if line_number not in bucket:
                    bucket.append(line_number)
    return merged


def convert_endpoints(content: dict):
    """Version 2 scalasem reports carry every framework's routes in
    ``endpoints[]``, with the resolved path pattern, the handler and the file
    and line it was declared at."""
    result: Dict[str, Dict] = {}
    for endpoint in content.get("endpoints", []):
        methods = _methods(endpoint)
        if not methods or not endpoint.get("path"):
            continue
        # `{}` captures, `*` wildcards and `:name` segments become named
        # OpenAPI placeholders, numbered so none repeats.
        path = normalize_path(endpoint["path"])
        any_method = str(endpoint.get("method")).lower() == "any"
        path_item = result.setdefault(path, {})
        for method in methods:
            operation = _build_operation(endpoint, path)
            if any_method:
                operation["x-scalasem-any-method"] = True
            existing = path_item.get(method)
            path_item[method] = _merge_operations(existing, operation) if existing else operation
    return unique_operation_ids(result, "x-scalasem-handler")


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
