"""
Ruby converter helper
"""
import re
from atom_tools.lib.slices import AtomSlice
from atom_tools.lib.ruby_semantics import code_to_routes


def extract_params(url):
    params = []
    if not url:
        return []
    if "{" in url or ":" in url:
        for part in url.split("/"):
            if part.startswith("{") or part.startswith(":"):
                param = {
                    "name": re.sub(r"[:{}]", "", part),
                    "in": "path",
                    "required": True
                }
                if part == "{id}":
                    param["schema"] = {
                        "type": "integer",
                        "format": "int64"
                    }
                elif part == "{extra_path}":
                    param["schema"] = {
                        "type": "string",
                        "format": "path"
                    }
                elif part.startswith("{"):
                    param["schema"] = {
                        "type": "string"
                    }
                params.append(param)
    return params


def convert(usages: AtomSlice):
    result = {}
    object_slices = usages.content.get("objectSlices", {})
    for oslice in object_slices:
        # Nested lambdas lack prefixes
        if oslice.get('fullName').count("<lambda>") >= 3:
            continue
        file_name = oslice.get("fileName", "")
        line_nums = set()
        if oslice.get("lineNumber"):
            line_nums.add(oslice.get("lineNumber"))
        for usage in oslice.get("usages", []):
            i = 0
            routes = code_to_routes(usage.get("targetObj", {}).get("name", {}))
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
                                "description": f""
                            }
                        }
                    }
                    if params:
                        amethod["parameters"] = params
                    if not result.get(route.url_pattern):
                        result[route.url_pattern] = {
                            route.method.lower(): amethod
                        }
                    else:
                        result[route.url_pattern].update({
                            route.method.lower(): amethod
                        })
    return result
