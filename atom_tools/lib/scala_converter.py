"""
Scala converter helper
"""
import re
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


def convert(usages: AtomSlice, semantics: AtomSlice):
    result = {}
    if not semantics or not semantics.content:
        return result
    routes = semantics.content.get("config", {}).get("routes")
    if not routes:
        return result
    i = 0
    for route in routes:
        i = i + 1
        route_pattern, params = extract_pattern(route.get('pattern'))
        controller_method = route.get('controllerMethod')
        amethod = {
            "operationId": f"{controller_method if controller_method else route.get('method')}-{str(i)}",
            "responses": {
                "200": {
                    "description": ""
                }
            }
        }
        if controller_method:
            amethod["x-atom-usages"] = {"method": controller_method}
        if params:
            amethod["parameters"] = params
        if not result.get(route_pattern):
            result[route_pattern] = {
                route.get('method').lower(): amethod
            }
        else:
            result[route_pattern].update({
                route.get('method').lower(): amethod
            })
    return result
