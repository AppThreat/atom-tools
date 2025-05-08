"""
Ruby converter helper
"""
from atom_tools.lib.slices import AtomSlice
from atom_tools.lib.ruby_semantics import code_to_routes
from atom_tools.lib.utils import extract_params


def convert(usages: AtomSlice):
    result = {}
    object_slices = usages.content.get("objectSlices", {})
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
                                "description": ""
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
