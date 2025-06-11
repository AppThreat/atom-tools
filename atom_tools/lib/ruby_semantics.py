"""
Ruby semantic utils
"""
import re
from typing import List

from atom_tools.lib import HttpRoute

HTTP_METHODS = ("get", "post", "delete", "patch", "put", "head", "options")

# Default RESTful actions and their HTTP verbs
REST_ACTIONS = [
    ('index',   'GET',    '/{prefix}'),
    ('new',     'GET',    '/{prefix}/{new_name}'),
    ('create',  'POST',   '/{prefix}'),
    ('show',    'GET',    '/{prefix}/{id_str}'),
    ('edit',    'GET',    '/{prefix}/{id_str}/{edit_name}'),
    ('update',  'PATCH',  '/{prefix}/{id_str}'),
    ('destroy', 'DELETE', '/{prefix}/{id_str}/{destroy_name}')
]

def generate_translated_paths(line: str):
    """
    Attempts to solve the various translations and renames in a single shot with regex.
    """
    # Detect scope prefix (literal or dynamic) if present
    scope_match = re.search(r'scope\s*(?:\(\s*)?"([^\"]+)"(?=\s*(?:,|\)|do))', line)
    scope_prefix = scope_match.group(1) if scope_match else None

    if scope_prefix:
        if scope_prefix.startswith(":controller"):
            scope_prefix = None
        else:
            scope_prefix = re.sub("""['"]""", "", scope_prefix)
            scope_prefix = scope_prefix.removesuffix(",")
    # Extract resource name
    resource_match = re.search(r'resources\s+:([a-zA-Z_]\w*)', line)
    if not resource_match:
        return []
    resource = resource_match.group(1)

    # Base prefix is plural resource name
    resource_prefix = resource
    # Override prefix if path: option is given
    path_match = re.search(r'path:\s*"([^"]+)"', line)
    if path_match:
        resource_prefix = path_match.group(1)
    if scope_prefix and scope_prefix.startswith(":"):
        scope_prefix = "{" + scope_prefix.removeprefix(":") + "}"
    if resource_prefix:
        resource_prefix = re.sub("""['"]""", "", resource_prefix)
        resource_prefix = resource_prefix.removesuffix(",")
    # Combine scope and resource prefixes
    prefix = f"{scope_prefix}/{resource_prefix}" if scope_prefix else resource_prefix
    # Parse path_names mapping for new/edit/destroy
    names = {'new': 'new', 'edit': 'edit', 'destroy': 'destroy'}
    names_match = re.search(r'path_names:\s*\{([^}]+)\}', line)
    if names_match:
        pairs = re.findall(r'(new|edit|destroy):\s*"([^"]+)"', names_match.group(1))
        for key, val in pairs:
            names[key] = val

    paths = []
    # Generate standard RESTful actions with scope applied
    for action, verb, template in REST_ACTIONS:
        paths.append(HttpRoute(url_pattern=template.format(
            prefix=prefix,
            new_name=names['new'],
            edit_name=names['edit'],
            destroy_name=names['destroy'],
            id_str="{id}"
        ), method=verb))

    # Handle member routes (inline on: :member)
    member_routes = re.findall(r'get\s+"([^"]+)"\s*,\s*on:\s*:member', line)
    # Handle block member routes
    block = re.search(r'member\s+do(.*?)end', line, re.DOTALL)
    if block:
        block_text = block.group(1)
        member_routes += re.findall(r'get\s+"([^"]+)"', block_text)

    # Append member route paths
    for name in member_routes:
        id_str = "{id}"
        paths.append(HttpRoute(url_pattern=f'/{prefix}/{id_str}/{name}', method="GET"))

    return paths


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
    current_path = re.sub('^:', '', code_parts[i + 1])
    new_path = f"{url_prefix}{current_path}" if not url_prefix.endswith(current_path) and not url_prefix.endswith(f"{current_path}/") else url_prefix
    url_pattern = _clean_url(new_path)
    if kind == "resources":
        routes.append(HttpRoute(url_pattern=url_pattern, method="GET"))
        needs_expansion = False
        if len(code_parts) > (i + 2):
            for part in code_parts[(i + 2):]:
                if "do" in part or "end" in part or "get" in part or "post" in part or "match" in part:
                    break
                if "resources" in part:
                    needs_expansion = True
                    break
            if needs_expansion:
                routes.append(HttpRoute(url_pattern=f"{url_pattern}/new", method="GET"))
                routes.append(HttpRoute(url_pattern=url_pattern, method="POST"))
                routes.append(HttpRoute(url_pattern=f"{url_pattern}" + "/{id}", method="GET"))
                routes.append(HttpRoute(url_pattern=f"{url_pattern}" + "/{id}/edit", method="GET"))
                routes.append(HttpRoute(url_pattern=f"{url_pattern}" + "/{id}", method="PUT"))
                routes.append(HttpRoute(url_pattern=f"{url_pattern}" + "/{id}", method="DELETE"))
                return routes
    if ("match " in code and "via: :all" in code) or ("only: [" not in code and "shallow:" not in code):
        routes.append(HttpRoute(url_pattern=f"{url_pattern}/new", method="GET"))
        routes.append(HttpRoute(url_pattern=url_pattern, method="POST"))
        routes.append(HttpRoute(url_pattern=f"{url_pattern}" + "/{id}", method="GET"))
        routes.append(HttpRoute(url_pattern=f"{url_pattern}" + "/{id}/edit", method="GET"))
        routes.append(HttpRoute(url_pattern=f"{url_pattern}" + "/{id}", method="PUT"))
        routes.append(HttpRoute(url_pattern=f"{url_pattern}" + "/{id}", method="DELETE"))
    return routes


def _clean_url(url_pattern):
    return re.sub('[,/]$', '', url_pattern) if len(url_pattern) > 1 else url_pattern


def _semantic_mounts(mount_path):
    routes = []
    mount_path.removesuffix("/")
    routes.append(HttpRoute(url_pattern=mount_path, method="GET"))
    # Support for sidekiq
    if mount_path.endswith("sidekiq"):
        routes.append(HttpRoute(url_pattern=f"{mount_path}/busy", method="GET"))
        routes.append(HttpRoute(url_pattern=f"{mount_path}/queues", method="GET"))
        routes.append(HttpRoute(url_pattern=f"{mount_path}/queues/" + "{name}", method="GET"))
        routes.append(HttpRoute(url_pattern=f"{mount_path}/queues/" + "{name}", method="POST"))
        routes.append(HttpRoute(url_pattern=f"{mount_path}/retries", method="GET"))
        routes.append(HttpRoute(url_pattern=f"{mount_path}/retries/" + "{id}", method="GET"))
        routes.append(HttpRoute(url_pattern=f"{mount_path}/retries/" + "{id}", method="POST"))
        routes.append(HttpRoute(url_pattern=f"{mount_path}/retries/all/delete", method="POST"))
        routes.append(HttpRoute(url_pattern=f"{mount_path}/retries/all/retry", method="POST"))
        routes.append(HttpRoute(url_pattern=f"{mount_path}/scheduled", method="GET"))
        routes.append(HttpRoute(url_pattern=f"{mount_path}/scheduled/" + "{id}", method="GET"))
        routes.append(HttpRoute(url_pattern=f"{mount_path}/scheduled/" + "{id}", method="POST"))
        routes.append(HttpRoute(url_pattern=f"{mount_path}/scheduled/all", method="POST"))
    return routes


def find_constraints(line: str) -> dict:
    """
    Parse a Rails route definition line and return a dict mapping each dynamic segment
    name to its regex constraint (as a Ruby literal string).
    """
    # Regex to capture key: /pattern/ pairs
    pattern = re.compile(r'([a-zA-Z_]\w*):\s*(/(?:\\.|[^/])+/)')
    matches = pattern.findall(line)
    return {key: regex for key, regex in matches}


def fix_url_params(path_str):
    if path_str == "*":
        return "/"
    s = []
    if path_str.endswith(","):
        path_str.removesuffix(",")
    for p in path_str.split("/"):
        if p.startswith("(") and p.endswith(")") and ":" in p:
            p = p.removeprefix("(").removesuffix(")")
        if p.startswith(":"):
            s.append("{" + p.removeprefix(":").removesuffix(",") + "}")
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
    if not code or code.startswith("Given ") or code.startswith("When ") or code.startswith("Then "):
        return []
    constraints_dict = find_constraints(code)
    keyword_found = False
    handled_with_translate = False
    for keyword in ("namespace", "scope", "concern", "resource", "resources", "match", "mount"):
        if f"{keyword} " in code:
            keyword_found = True
            break
    if not keyword_found:
        for keyword in HTTP_METHODS:
            if f"{keyword} " in code:
                keyword_found = True
                break
    if not keyword_found:
        return []
    # Attempt to solve this code with one-shot
    if "namespace" not in code and "collection" not in code and code.count("resources") <= 1 and code.count("get") <= 1 and "only" not in code:
        routes += generate_translated_paths(code)
    if routes:
        handled_with_translate = True
    code_parts = code.strip().replace("...", "").split()
    # Dangling resources - leads to many kinds of automatic routes
    has_resources = "resources " in code or "resource " in code
    namespace_url_prefix = ""
    scope_url_prefix = ""
    resources_url_prefix = ""
    has_scope = False
    is_in_resource_block = False
    is_in_resource_do_block = False
    is_in_scope_block = False
    url_prefix_to_use = ""
    last_url_prefix_to_use = ""
    for i, part in enumerate(code_parts):
        last_part = code_parts[i - 1] if i > 0 else ""
        if not url_prefix_to_use and namespace_url_prefix:
            url_prefix_to_use = namespace_url_prefix
        if is_in_resource_block and part in ("do",):
            is_in_resource_do_block = True
        if not part or len(part) < 2 or part in ("do", "if") or part.startswith("#"):
            continue
        # Support for nested resources block
        if is_in_resource_block:
            # Reset namespace_url_prefix with nested resources
            if part in ("resources",) and namespace_url_prefix and namespace_url_prefix != resources_url_prefix:
                resources_url_prefix = namespace_url_prefix + "/".join(resources_url_prefix.split("/")[:-1])
                if not is_in_resource_do_block:
                    url_prefix_to_use = last_url_prefix_to_use
                else:
                    last_url_prefix_to_use = url_prefix_to_use
            elif part in ("end", "get", "post", "put", "delete", "match", "scope"):
                if not is_in_resource_do_block:
                    is_in_resource_block = False
                if part in ("end",):
                    is_in_resource_do_block = False
                    url_prefix_to_use = last_url_prefix_to_use
                    last_url_prefix_to_use = namespace_url_prefix
        if part in ("resources",):
            if is_in_resource_block and not is_in_resource_do_block:
                url_prefix_to_use = last_url_prefix_to_use
            is_in_resource_block = True
        # Support for nested scope block
        if is_in_scope_block:
            # Reset namespace_url_prefix with nested scope
            if part in ("scope",) and url_prefix_to_use and url_prefix_to_use != scope_url_prefix:
                scope_url_prefix = url_prefix_to_use
            elif part in ("end",):
                is_in_scope_block = False
                scope_url_prefix = last_url_prefix_to_use if is_in_resource_do_block else namespace_url_prefix
                url_prefix_to_use = namespace_url_prefix
        elif part in ("scope",) and url_prefix_to_use and url_prefix_to_use != scope_url_prefix:
            is_in_scope_block = True
            # Did we just end a block
            if last_part in ("end",):
                scope_url_prefix = namespace_url_prefix
                last_url_prefix_to_use = ""
                url_prefix_to_use = namespace_url_prefix
            else:
                scope_url_prefix = url_prefix_to_use
        if not handled_with_translate and part in ("scope",) or part.startswith("scope("):
            has_scope = True
            if len(code_parts) >= i + 1:
                tmp_parts = code_parts[i + 1]
                if tmp_parts.startswith(":controller"):
                    continue
                if ":" in tmp_parts:
                    tmp_parts = re.sub("""[",']""", '', tmp_parts)
                    fixed_parts = []
                    for p in tmp_parts.split("/"):
                        if p.startswith("(") and p.endswith(")") and ":" in p:
                            p = p.removeprefix("(").removesuffix(")")
                        if p.startswith(":"):
                            if "_id" in p:
                                p = "{" + p.removeprefix(":") + "}"
                            else:
                                p = p.removeprefix(":")
                        fixed_parts.append(p)
                    if fixed_parts:
                        tmp_parts = "/".join(fixed_parts)
                fragment = re.sub("""[",']""", '', tmp_parts)
                if fragment == "{":
                    continue
                if fragment and constraints_dict and fragment in constraints_dict.keys():
                    fragment = "{" + fragment + "}"
                # Check if this fragment could be pattern
                if scope_url_prefix:
                    last_url_prefix_to_use = url_prefix_to_use
                    url_prefix_to_use = f"""{scope_url_prefix}/{fragment.removeprefix("/")}"""
                else:
                    last_url_prefix_to_use = url_prefix_to_use
                    url_prefix_to_use = f"""{url_prefix_to_use}/{fragment.removeprefix("/")}"""
                continue
        if part in ("mount",) and len(code_parts) >= i + 4:
            if code_parts[i + 2] in (":at",):
                mount_path = code_parts[i + 4].split(",")[0]
                url_pattern = _clean_url(re.sub("""["']""", '', mount_path))
                routes += _semantic_mounts(f"{namespace_url_prefix}{url_pattern}")
                continue
        if not handled_with_translate and part in ("resource", "resources", "namespace", "member") and len(code_parts) >= i + 1:
            if code_parts[i + 1] in ("do", "if", "()", "([^]*)"):
                continue
            has_do_block_next = len(code_parts) > (i + 2) and code_parts[i + 2] in ("do",)
            tmp_pattern = f"/{re.sub('^:', '', code_parts[i + 1])}"
            tmp_pattern = re.sub("""['"]""", "", tmp_pattern)
            url_pattern = _clean_url(tmp_pattern)
            # Is there an alias for this patten
            if len(code_parts) > i + 3 and code_parts[i + 2] in ("path:", "path", "path("):
                url_pattern = _clean_url(code_parts[i + 3].replace('"', ""))
                routes += _get_dangling_routes(i, part, code, code_parts,
                                               f"{scope_url_prefix}/{url_pattern}/")
                continue
            if len(code_parts) > i + 2 and code_parts[i + 2] in ("resources", "resource", "get", "post", "delete", "match"):
                routes += _get_dangling_routes(i, code_parts[i + 2], code, code_parts, f"{scope_url_prefix}/" if scope_url_prefix else f"{url_prefix_to_use}/")
                url_prefix_to_use = last_url_prefix_to_use
                if code_parts[i + 2] in ("get", "post", "delete", "match"):
                    is_in_resource_block = False
                    is_in_resource_do_block = False
            elif i == len(code_parts) - 2 and part in ("resource", "resources"):
                routes += _get_dangling_routes(i, part, code, code_parts, f"{scope_url_prefix}/" if scope_url_prefix else f"{url_prefix_to_use}/")
            else:
                if not namespace_url_prefix:
                    namespace_url_prefix = f"{namespace_url_prefix}{url_pattern}"
                last_url_prefix_to_use = url_prefix_to_use
                if (is_in_resource_block and (is_in_resource_do_block or has_do_block_next)) or not is_in_resource_block:
                    url_prefix_to_use = namespace_url_prefix + url_pattern if namespace_url_prefix and url_pattern and namespace_url_prefix != url_pattern else namespace_url_prefix
            continue
        if part in ("collection", "member", "concern", "do", "as:", "constraints:") or part.startswith(
                ":") or part.startswith('"'):
            continue
        # Are we dealing with a match clause
        if part in ("match",):
            fmt_path = fix_url_params(code_parts[i + 1].replace('"', "").replace("'", "")).removesuffix(",")
            full_path = fmt_path if not url_prefix_to_use and fmt_path in ("/", "*") else f"""{url_prefix_to_use}/{fmt_path.removeprefix("/")}"""
            match_via_parts = code_parts[i+2:10]
            routes.append(HttpRoute(url_pattern=_clean_url(full_path), method="GET"))
            for part in match_via_parts:
                if "all" in part:
                    routes.append(HttpRoute(url_pattern=_clean_url(full_path), method="POST"))
                    routes.append(HttpRoute(url_pattern=_clean_url(full_path), method="PUT"))
                    routes.append(HttpRoute(url_pattern=_clean_url(full_path), method="DELETE"))
                    break
                elif "post" in part:
                    routes.append(HttpRoute(url_pattern=_clean_url(full_path), method="POST"))
                elif "put" in part:
                    routes.append(HttpRoute(url_pattern=_clean_url(full_path), method="PUT"))
                elif "delete" in part:
                    routes.append(HttpRoute(url_pattern=_clean_url(full_path), method="DELETE"))
        # Are we dealing with an http method
        if part in HTTP_METHODS:
            for m in HTTP_METHODS:
                if part == m and len(code_parts) > i + 1 and (code_parts[i + 1].startswith(":") or code_parts[i + 1].startswith('"') or code_parts[i + 1].startswith("'")):
                    fmt_path = fix_url_params(code_parts[i + 1].replace('"', "").replace("'", "")).removesuffix(",")
                    if fmt_path and part in ("patch", "put", "delete"):
                        fmt_path = "{id}/" + fmt_path
                    full_path = fmt_path if not url_prefix_to_use and fmt_path in ("/", "*") else f"""{url_prefix_to_use}/{fmt_path.removeprefix("/")}"""
                    # * is not allowed by swagger
                    if m == "options" and full_path == "*":
                        full_path = "/"
                    routes.append(HttpRoute(url_pattern=_clean_url(full_path), method=m.upper() if m != "patch" else "PUT"))
                    break
    if not handled_with_translate and has_resources:
        if not routes:
            for i, part in enumerate(code_parts):
                for m in ("resource", "resources"):
                    if part == m and code_parts[i + 1].startswith(':') and (
                            i == len(code_parts) - 2 or (len(code_parts) > i + 2 and code_parts[i + 1] != "do")):
                        routes += _get_dangling_routes(i, m, code, code_parts, f"{url_prefix_to_use}/{scope_url_prefix}/" if has_scope else "/")

    return routes
