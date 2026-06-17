"""
Rust converter helper.

Consumes a rusi report (produced by the `rusi` analyzer shipped in
`cdxgen/cdxgen-plugins-bin` v2.4.0+) and produces an OpenAPI paths dict
in the same shape that the JVM-style processing in
``atom_tools.lib.converter`` does for other languages.

Rusi's `api_endpoints` array already carries the framework, HTTP method,
path (with prefixes from nested routers / scopes / mounts composed in),
handler qualified name, path/query parameters, request-body type, and
response type. This module just translates those records into the
OpenAPI shape atom-tools' callers expect.

Path placeholders are normalised across the three supported frameworks:
* axum's ``:id``,
* actix's ``{id}``,
* rocket's ``<id>``,

all become OpenAPI's ``{id}``.

Rust types from parameter and body / response positions are mapped to
OpenAPI schemas. Common scalars, ``Option<T>``, ``Vec<T>``, and the
framework JSON wrappers are recognised; custom types are emitted as a
``$ref`` pointing at ``#/components/schemas/<TypeName>`` so downstream
tooling can still match by type name even when the field-level schema
is not (yet) available.
"""

import re
from typing import Dict, Optional

from atom_tools.lib.slices import AtomSlice


# Map of recognised Rust scalar types to OpenAPI schema dicts. Anything
# not in here is treated as either a known wrapper (Option/Vec/Json) or
# a custom type that becomes a $ref.
_RUST_SCALAR_SCHEMA: Dict[str, Dict] = {
    "i8": {"type": "integer", "format": "int32"},
    "i16": {"type": "integer", "format": "int32"},
    "i32": {"type": "integer", "format": "int32"},
    "i64": {"type": "integer", "format": "int64"},
    "i128": {"type": "integer"},
    "isize": {"type": "integer", "format": "int64"},
    "u8": {"type": "integer", "format": "int32"},
    "u16": {"type": "integer", "format": "int32"},
    "u32": {"type": "integer", "format": "int64"},
    "u64": {"type": "integer", "format": "int64"},
    "u128": {"type": "integer"},
    "usize": {"type": "integer", "format": "int64"},
    "f32": {"type": "number", "format": "float"},
    "f64": {"type": "number", "format": "double"},
    "bool": {"type": "boolean"},
    "char": {"type": "string"},
    "String": {"type": "string"},
    "str": {"type": "string"},
    "&str": {"type": "string"},
}

# Path-placeholder patterns. Rusi emits the framework-native placeholder
# verbatim, so we look for each shape and normalise to ``{name}``.
#   axum:   ``:id``
#   rocket: ``<id>`` (also ``<id..>`` for catch-all segments)
#   actix:  ``{id}`` (already correct — left alone)
_PLACEHOLDER_AXUM = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")
_PLACEHOLDER_ROCKET = re.compile(r"<([A-Za-z_][A-Za-z0-9_]*)(?:\.\.)?>")


def normalize_path(path: str) -> str:
    """Convert framework-native path placeholders to OpenAPI ``{name}``.

    Idempotent on actix-style paths (which already use ``{name}``).
    """
    if not path:
        return ""
    path = _PLACEHOLDER_AXUM.sub(r"{\1}", path)
    path = _PLACEHOLDER_ROCKET.sub(r"{\1}", path)
    return path


def rust_type_to_schema(type_name: str) -> Dict:
    """Map a Rust type expression to an OpenAPI schema object.

    Recognises common scalars and the most-frequent wrappers
    (``Option<T>``, ``Vec<T>``, framework ``Json<T>``). Custom types
    become a ``$ref`` so downstream consumers can match on the type
    name even when its field structure isn't (yet) emitted.
    """
    if not type_name:
        return {"type": "object"}
    name = type_name.strip()

    # Strip leading reference / lifetime tokens that occasionally land
    # in signature text (e.g. ``&'static str``).
    if name.startswith("&"):
        stripped = name.lstrip("&").lstrip()
        if stripped.startswith("'"):
            # Drop a lifetime token like ``'static``.
            parts = stripped.split(None, 1)
            stripped = parts[1] if len(parts) > 1 else ""
        if stripped:
            return rust_type_to_schema(stripped)
        return {"type": "string"}

    # ``Option<T>`` → schema for T with the OpenAPI ``nullable`` flag.
    if match := re.fullmatch(r"Option\s*<\s*(.+)\s*>", name):
        inner = rust_type_to_schema(match.group(1))
        inner["nullable"] = True
        return inner

    # ``Vec<T>`` → OpenAPI array of T.
    if match := re.fullmatch(r"Vec\s*<\s*(.+)\s*>", name):
        return {"type": "array", "items": rust_type_to_schema(match.group(1))}

    # Framework JSON wrappers (axum::Json<T>, actix_web::web::Json<T>,
    # rocket::serde::json::Json<T>, plain Json<T>). Unwrap and recurse.
    if match := re.fullmatch(
        r"(?:axum::|actix_web::|rocket::serde::json::|web::)?Json\s*<\s*(.+)\s*>",
        name,
    ):
        return rust_type_to_schema(match.group(1))

    # serde_json::Value → free-form JSON object.
    if name in ("serde_json::Value", "Value"):
        return {"type": "object"}

    if name in _RUST_SCALAR_SCHEMA:
        return dict(_RUST_SCALAR_SCHEMA[name])

    # ``str`` / ``&str`` variants the lifetime-stripping above didn't
    # catch (e.g. concatenated tokens from rusi's ToTokenStream output).
    if name.endswith("str") or name.endswith("staticstr"):
        return {"type": "string"}

    # Fall through: custom type → $ref. Strip any module path so the
    # schema name matches what downstream tooling typically expects.
    schema_name = name.rsplit("::", 1)[-1]
    return {"$ref": f"#/components/schemas/{schema_name}"}


def _parameter_schema(type_name: str) -> Dict:
    """Schema for a path/query parameter.

    Same mapping as :func:`rust_type_to_schema` but pulls the
    ``nullable`` flag back out so OpenAPI's ``required`` field on the
    parameter level can carry the optionality information instead.
    """
    schema = rust_type_to_schema(type_name)
    if schema.get("nullable"):
        schema = {k: v for k, v in schema.items() if k != "nullable"}
    return schema


def _build_operation(endpoint: Dict) -> Dict:
    """Build one OpenAPI operation object from a single rusi endpoint."""
    handler = endpoint.get("handler", "")
    position = endpoint.get("position", {}) or {}
    file_path = endpoint.get("file_path", "")
    method = endpoint.get("method", "")
    path = endpoint.get("path", "")

    operation: Dict = {
        "operationId": handler or f"{method}-{path}",
        "responses": {"200": {"description": ""}},
    }

    # Line-number tracking mirrors the convention used by the JVM-style
    # processing and the ruby converter so callers that already inspect
    # x-atom-usages keep working.
    line_number = position.get("line")
    if file_path and line_number:
        operation["x-atom-usages"] = {"call": {file_path: [line_number]}}

    # Framework attribution. Carried under an x-* extension so it
    # doesn't pollute the standard OpenAPI shape but is available to
    # consumers that want to filter or visualise by framework.
    if framework := endpoint.get("framework"):
        operation["x-rust-framework"] = framework

    # Dependency purl for the framework crate. Rusi populates this from
    # cargo metadata; passing it through means consumers can correlate
    # endpoints with the framework crate version that exposes them.
    if purl := endpoint.get("purl"):
        operation["x-rust-purl"] = purl

    # Parameters: path and query. rusi already classifies them and
    # gives us the Rust type as written, which we map to OpenAPI.
    parameters = []
    for param in endpoint.get("parameters", []):
        name = param.get("name")
        location = param.get("location")
        type_name = param.get("type_name", "")
        if not name or location not in ("path", "query"):
            continue
        is_optional = type_name.strip().startswith("Option<")
        parameters.append(
            {
                "name": name,
                "in": location,
                # Path params are always required in OpenAPI; query params
                # follow the Rust signature's optionality.
                "required": location == "path" or not is_optional,
                "schema": _parameter_schema(type_name),
            }
        )
    if parameters:
        operation["parameters"] = parameters

    # Request body. Rust extractors only carry the body type name; the
    # body's media-type defaults to ``application/json`` because every
    # supported framework's body extractor (axum::Json, web::Json,
    # rocket Json) deserialises JSON.
    body_type = endpoint.get("request_body_type")
    if body_type:
        operation["requestBody"] = {
            "required": True,
            "content": {
                "application/json": {
                    "schema": rust_type_to_schema(body_type),
                }
            },
        }

    # 200 response. Skipped when we couldn't infer anything useful
    # (e.g. handler returns plain ``StatusCode`` with no body) — the
    # response stays as the default ``{description: ""}`` so the
    # operation is still valid OpenAPI.
    response_type = endpoint.get("response_type")
    if response_type:
        response_schema = rust_type_to_schema(response_type)
        if response_schema and response_schema != {"type": "object"}:
            operation["responses"]["200"]["content"] = {
                "application/json": {
                    "schema": response_schema,
                }
            }

    return operation


def convert(usages: AtomSlice) -> Dict[str, Dict]:
    """Convert a rusi report into an OpenAPI ``paths`` dict.

    Mirrors the contract of :func:`atom_tools.lib.ruby_converter.convert`
    and :func:`atom_tools.lib.scala_converter.convert`: returns a
    ``{path: {method: operation}}`` mapping. The caller (the
    :class:`atom_tools.lib.converter.OpenAPI` class) wraps this into
    the full OpenAPI document.
    """
    result: Dict[str, Dict] = {}
    if not usages or not usages.content:
        return result
    endpoints = usages.content.get("api_endpoints", [])
    if not endpoints:
        return result

    for endpoint in endpoints:
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
        # (extremely rare — could happen if the same handler appears
        # twice through different nested routers), merge line numbers
        # so the call-tracking information isn't dropped.
        existing = result[path].get(method)
        if existing:
            result[path][method] = _merge_operations(existing, operation)
        else:
            result[path][method] = operation

    return result


def _merge_operations(existing: Dict, new: Dict) -> Dict:
    """Merge two operations registered against the same path+method.

    Today this only concatenates the ``x-atom-usages.call`` line-number
    lists so all source locations contributing to an endpoint stay
    visible. Other fields prefer the existing entry; rusi normally
    deduplicates identical endpoints upstream so collisions are rare.
    """
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
