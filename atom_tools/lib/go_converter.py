"""
Go converter helper.

Consumes a golem report (produced by the ``golem`` analyzer shipped in
``cdxgen/cdxgen-plugins-bin`` v3.0.5+) and produces an OpenAPI paths
dict in the same shape that the JVM-style processing in
``atom_tools.lib.converter`` does for other languages.

Golem's ``apiEndpoints`` array already carries the framework, HTTP
method, path (with any group / router-nest prefixes already merged in),
handler function name, path/query parameters, request-body type, and
response type. This module just translates those records into the
OpenAPI shape atom-tools' callers expect.

Path placeholders are normalised across the supported frameworks:

- Gin / Echo / iris ``:id`` → OpenAPI ``{id}``.
- Gin catch-all ``*filepath`` → OpenAPI ``{filepath}`` (mirrors the
  rust converter's handling of axum/rocket's ``<id..>`` catch-all).
- chi / gorilla/mux ``{id}`` and ``{id:regex}`` → OpenAPI ``{id}``.
- net/http ``{id}`` (Go 1.22+ pattern syntax) → OpenAPI ``{id}``.

Go types from parameter and body / response positions are mapped to
OpenAPI schemas. Common scalars, ``[]T`` slice wrappers, and framework
ad-hoc map aliases collapse to the corresponding OpenAPI primitives.
Custom types are emitted as a ``$ref`` pointing at
``#/components/schemas/<TypeName>`` so downstream tooling can still
match by type name even when the field-level schema is not (yet)
available from the analyzer.
"""

import re
from typing import Dict, Optional

from atom_tools.lib.slices import AtomSlice


# Map of recognised Go scalar / builtin types to OpenAPI schema dicts.
# Anything not in here is treated as either a known wrapper (``[]T``,
# framework map alias) or a custom type that becomes a $ref.
_GO_SCALAR_SCHEMA: Dict[str, Dict] = {
    "string": {"type": "string"},
    "bool": {"type": "boolean"},
    "int": {"type": "integer", "format": "int64"},
    "int8": {"type": "integer", "format": "int32"},
    "int16": {"type": "integer", "format": "int32"},
    "int32": {"type": "integer", "format": "int32"},
    "int64": {"type": "integer", "format": "int64"},
    "uint": {"type": "integer", "format": "int64"},
    "uint8": {"type": "integer", "format": "int32"},
    "uint16": {"type": "integer", "format": "int32"},
    "uint32": {"type": "integer", "format": "int64"},
    "uint64": {"type": "integer", "format": "int64"},
    "uintptr": {"type": "integer", "format": "int64"},
    "byte": {"type": "integer", "format": "int32"},
    "rune": {"type": "integer", "format": "int32"},
    "float32": {"type": "number", "format": "float"},
    "float64": {"type": "number", "format": "double"},
    "any": {"type": "object"},
    "interface{}": {"type": "object"},
    "object": {"type": "object"},
    "error": {"type": "string"},
    "time.Time": {"type": "string", "format": "date-time"},
    "time.Duration": {"type": "integer", "format": "int64"},
    "uuid.UUID": {"type": "string", "format": "uuid"},
}

# Path-placeholder patterns. Golem emits the framework-native placeholder
# verbatim, so we look for each shape and normalise to ``{name}``.
#   Gin / Echo / iris: ``:id`` (colon prefix)
#   Gin catch-all:     ``*filepath`` (asterisk prefix, matches the rest
#                      of the path segment) — mirrors the rust converter's
#                      handling of axum/rocket's ``<id..>`` catch-all.
#   chi / gorilla/mux: ``{id}`` or ``{id:regex}`` (already {}-wrapped)
#   net/http 1.22+:    ``{id}`` (already correct — left alone)
_PLACEHOLDER_COLON = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
_PLACEHOLDER_STAR = re.compile(r"\*([A-Za-z_][A-Za-z0-9_]*)")
_PLACEHOLDER_REGEX_BRACE = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*):[^}]+\}")


def normalize_path(path: str) -> str:
    """Convert framework-native path placeholders to OpenAPI ``{name}``.

    Idempotent on paths that already use ``{name}``.
    """
    if not path:
        return ""
    path = _PLACEHOLDER_COLON.sub(r"{\1}", path)
    path = _PLACEHOLDER_STAR.sub(r"{\1}", path)
    path = _PLACEHOLDER_REGEX_BRACE.sub(r"{\1}", path)
    return path


def go_type_to_schema(type_name: str) -> Dict:
    """Map a Go type expression to an OpenAPI schema object.

    Recognises common scalars, ``[]T`` slice wrappers, pointer prefixes
    (``*T``), and framework ad-hoc map aliases (which golem already
    collapses to ``object`` upstream). Custom types become a ``$ref``
    so downstream consumers can match on the type name even when its
    field structure isn't (yet) emitted by the analyzer.
    """
    if not type_name:
        return {"type": "object"}
    # Collapse internal whitespace so source-shaped spellings such as
    # ``interface {}`` or ``map[string] int`` match the scalar/wrapper
    # lookups below the same way their whitespace-free variants do.
    # Without this, ``interface {}`` bypasses the ``any``/``interface{}``
    # scalar entries and falls through to the $ref branch, producing an
    # invalid schema name ``interface {}``.
    name = type_name.strip().replace(" ", "")

    # Pointer types ``*T`` describe the same shape as T for OpenAPI.
    while name.startswith("*"):
        name = name[1:].lstrip()

    # ``[]T`` slice / array wrapper → OpenAPI array of T.
    if name.startswith("[]"):
        inner = name[2:].strip()
        return {"type": "array", "items": go_type_to_schema(inner)}

    # ``map[K]V`` (rarely emitted by golem, since it collapses these
    # upstream, but handle just in case). Fall through to free-form
    # object; carrying the key/value types would require a nested
    # allOf/additionalProperties schema that most OpenAPI consumers
    # don't render usefully.
    if name.startswith("map["):
        return {"type": "object"}

    if name in _GO_SCALAR_SCHEMA:
        return dict(_GO_SCALAR_SCHEMA[name])

    # Fall through: custom type → $ref. Strip any module path so the
    # schema name matches what downstream tooling typically expects.
    schema_name = name.rsplit(".", 1)[-1]
    return {"$ref": f"#/components/schemas/{schema_name}"}


def _parameter_schema(type_name: str) -> Dict:
    """Schema for a path/query parameter, matching go_type_to_schema."""
    return go_type_to_schema(type_name)


def _endpoint_position(endpoint: Dict) -> Optional[Dict]:
    """Golem's endpoints carry ``range.start.{filename,line,column}``
    where rusi's carry a flat ``position``. Normalise access so the rest
    of the module doesn't have to remember the layout difference."""
    range_obj = endpoint.get("range") or {}
    start = range_obj.get("start") or {}
    if not start:
        return None
    return {
        "filename": start.get("filename", ""),
        "line": start.get("line"),
        "column": start.get("column"),
    }


def _build_operation(endpoint: Dict) -> Dict:
    """Build one OpenAPI operation object from a single golem endpoint."""
    handler = endpoint.get("handler", "")
    method = endpoint.get("method", "")
    path = endpoint.get("path", "")
    position = _endpoint_position(endpoint) or {}
    file_path = position.get("filename", "")

    operation: Dict = {
        "operationId": handler or f"{method}-{path}",
        "responses": {"200": {"description": ""}},
    }

    # Line-number tracking mirrors the convention used by the JVM-style
    # processing and the ruby / rust converters so callers that already
    # inspect x-atom-usages keep working.
    line_number = position.get("line")
    if file_path and line_number:
        operation["x-atom-usages"] = {"call": {file_path: [line_number]}}

    # Framework attribution. Carried under an x-* extension so it
    # doesn't pollute the standard OpenAPI shape but is available to
    # consumers that want to filter or visualise by framework.
    if framework := endpoint.get("framework"):
        operation["x-go-framework"] = framework

    # Package path of the user code that registered the route. Useful
    # for downstream tooling that groups endpoints by owning service.
    if package_path := endpoint.get("packagePath"):
        operation["x-go-package"] = package_path

    # Parameters: path and query. Golem already classifies them and
    # gives us the Go type as written, which we map to OpenAPI.
    parameters = []
    for param in endpoint.get("parameters", []) or []:
        name = param.get("name")
        location = param.get("location")
        type_name = param.get("typeName", "")
        if not name or location not in ("path", "query"):
            continue
        parameters.append(
            {
                "name": name,
                "in": location,
                # Path params are always required in OpenAPI; query
                # params default to optional (Go handlers typically
                # tolerate missing query strings).
                "required": location == "path",
                "schema": _parameter_schema(type_name),
            }
        )
    if parameters:
        operation["parameters"] = parameters

    # Request body. Golem records only the type name; the body's
    # media-type defaults to ``application/json`` because every
    # supported framework binder golem detects deserialises JSON.
    body_type = endpoint.get("requestBodyType")
    if body_type:
        operation["requestBody"] = {
            "required": True,
            "content": {
                "application/json": {
                    "schema": go_type_to_schema(body_type),
                }
            },
        }

    # 200 response. Skipped when the analyzer couldn't infer a body
    # type — the response stays at the default ``{description: ""}`` so
    # the operation is still valid OpenAPI.
    response_type = endpoint.get("responseType")
    if response_type:
        response_schema = go_type_to_schema(response_type)
        if response_schema:
            operation["responses"]["200"]["content"] = {
                "application/json": {
                    "schema": response_schema,
                }
            }

    return operation


def convert(usages: AtomSlice) -> Dict[str, Dict]:
    """Convert a golem report into an OpenAPI ``paths`` dict.

    Mirrors the contract of :func:`atom_tools.lib.ruby_converter.convert`,
    :func:`atom_tools.lib.rust_converter.convert`, and
    :func:`atom_tools.lib.scala_converter.convert`: returns a
    ``{path: {method: operation}}`` mapping. The caller (the
    :class:`atom_tools.lib.converter.OpenAPI` class) wraps this into
    the full OpenAPI document.
    """
    result: Dict[str, Dict] = {}
    if not usages or not usages.content:
        return result
    endpoints = usages.content.get("apiEndpoints", [])
    if not endpoints:
        return result

    for endpoint in endpoints:
        # Golem also reports ``http-listener`` and ``rpc-service``
        # entries alongside HTTP routes; only the actual routes belong
        # in an OpenAPI ``paths`` dict.
        if endpoint.get("kind") not in ("http-route", None, ""):
            continue

        raw_path = endpoint.get("path", "")
        path = normalize_path(raw_path)
        if not path:
            continue
        method = endpoint.get("method", "").lower()
        if not method:
            continue

        operation = _build_operation(endpoint)
        if path not in result:
            result[path] = {}
        # If the same method on the same path was already populated
        # (rare — could happen if the same handler is registered under
        # multiple entry points), merge line numbers so all source
        # locations contributing to an endpoint stay visible.
        existing = result[path].get(method)
        if existing:
            result[path][method] = _merge_operations(existing, operation)
        else:
            result[path][method] = operation

    return result


def _merge_operations(existing: Dict, new: Dict) -> Dict:
    """Merge two operations registered against the same path+method.

    Only the ``x-atom-usages.call`` line-number lists concatenate; every
    other field prefers the existing entry, since golem normally
    deduplicates identical endpoints upstream and true collisions carry
    the same shape."""
    merged = dict(existing)
    new_calls = new.get("x-atom-usages", {}).get("call", {})
    if new_calls:
        existing_calls = merged.setdefault("x-atom-usages", {}).setdefault("call", {})
        for file_path, line_numbers in new_calls.items():
            bucket = existing_calls.setdefault(file_path, [])
            for line_number in line_numbers:
                if line_number not in bucket:
                    bucket.append(line_number)
    return merged
