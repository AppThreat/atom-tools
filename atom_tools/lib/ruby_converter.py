"""
Ruby converter helper
"""
import json

from atom_tools.lib.slices import AtomSlice
from atom_tools.lib.ruby_semantics import code_to_routes, endpoints_to_routes
from atom_tools.lib.utils import extract_params


def convert(usages: AtomSlice):
    result = {}
    object_slices = usages.content.get("objectSlices", {})
    i = 0
    for oslice in object_slices:
        # Nested lambdas lack prefixes
        if oslice.get('fullName').count("<lambda>") >= 3:
            continue
        file_name = oslice.get("fileName", "")
        if "step_definitions" in file_name:
            continue
        line_nums = set()
        if oslice.get("lineNumber"):
            line_nums.add(oslice.get("lineNumber"))
        for usage in oslice.get("usages", []):
            target_obj = usage.get("targetObj", {})
            if target_obj.get("typeFullName", "") == "HttpEndpoint":
                if target_obj.get("name"):
                    routes = endpoints_to_routes(target_obj.get("name"), target_obj.get("resolvedMethod"))
            else:
                routes = code_to_routes(target_obj.get("name"))
            if routes:
                if usage.get("lineNumber"):
                    line_nums.add(usage.get("lineNumber"))
                for route in routes:
                    i = i + 1
                    params = extract_params(route.url_pattern)
                    amethod = {
                        "operationId": (f"{oslice.get('fullName')}" if oslice.get("fullName") else oslice.get(
                            "fileName")) + f"-{route.method}-{str(i)}",
                        "x-atom-usages": {
                            "call": {file_name: list(line_nums)}
                        },
                        "responses": {
                            "200": {
                                "description": ""
                            }
                        }
                    }
                    # Support for servers per method
                    if route.servers:
                        amethod["servers"] = [{"url": s} for s in route.servers]
                    if params:
                        amethod["parameters"] = params
                    if not result.get(route.url_pattern):
                        result[route.url_pattern] = {
                            route.method.lower(): amethod
                        }
                    else:
                        existing_method = result[route.url_pattern].get(route.method.lower(), {})
                        existing_servers: list[dict[str, str]] = existing_method.get("servers", [])
                        existing_usages = existing_method.get("x-atom-usages", {})
                        if not isinstance(existing_usages, list):
                            existing_usages = [existing_usages]
                        new_servers: list[dict[str, str]] = amethod.get("servers", [])
                        new_usages = amethod.get("x-atom-usages", {})
                        combined_servers = [dict(t) for t in {tuple(d.items()) for d in existing_servers + new_servers}]
                        if new_usages:
                            existing_usages.append(new_usages)
                        if combined_servers:
                            amethod["servers"] = combined_servers
                        if existing_usages:
                            amethod["x-atom-usages"] = [json.loads(item) for item in set(json.dumps(d, sort_keys=True) for d in existing_usages)]
                        result[route.url_pattern].update({
                            route.method.lower(): amethod
                        })
    return result
