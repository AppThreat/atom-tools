"""
Ruby converter helper
"""
from atom_tools.lib.slices import AtomSlice
from atom_tools.lib.ruby_semantics import code_to_routes


def extract_params(url):
    params = []
    if not url:
        return []
    if ":" in url:
        for part in url.split("/"):
            if part.startswith(":"):
                param = {
                    "name": part.replace(":", ""),
                    "in": "path",
                    "required": True
                }
                if part == ":id":
                    param["schema"] = {
                        "type": "integer",
                        "format": "int64"
                    }
                params.append(param)
    return params


def convert(usages: AtomSlice):
    result = []
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
            routes = code_to_routes(usage.get("targetObj", {}).get("name", {}))
            if routes:
                if usage.get("lineNumber"):
                    line_nums.add(usage.get("lineNumber"))
                for route in routes:
                    params = extract_params(route.url_pattern)
                    amethod = {
                        "operationId": f"{oslice.get('fullName')}" if oslice.get("fullName") else oslice.get(
                            "fileName"),
                        "x-atom-usages": {
                            "call": {file_name: list(line_nums)}
                        }
                    }
                    if params:
                        amethod["parameters"] = params
                    aresult = {
                        route.url_pattern: {
                            route.method.lower(): amethod
                        }
                    }
                    result.append(aresult)
    return result
