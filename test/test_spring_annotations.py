"""
Tests for Spring parameter annotation support in the OpenAPI converter.

Covers the new atom slice format where @RequestBody, @PathVariable,
@RequestParam, and @RequestHeader are emitted as separate ANNOTATION
usage entries (label == "ANNOTATION") rather than an annotations array
on PARAM entries.
"""
import pytest

from atom_tools.lib.converter import OpenAPI, _java_type_to_schema, _extract_annotation_string_value


# ── unit helpers ──────────────────────────────────────────────────────────────

def test_java_type_to_schema_primitives():
    assert _java_type_to_schema('java.lang.String') == {'type': 'string'}
    assert _java_type_to_schema('java.lang.Integer') == {'type': 'integer'}
    assert _java_type_to_schema('int') == {'type': 'integer'}
    assert _java_type_to_schema('java.lang.Long') == {'type': 'integer', 'format': 'int64'}
    assert _java_type_to_schema('long') == {'type': 'integer', 'format': 'int64'}
    assert _java_type_to_schema('java.lang.Double') == {'type': 'number', 'format': 'double'}
    assert _java_type_to_schema('java.lang.Boolean') == {'type': 'boolean'}
    assert _java_type_to_schema('boolean') == {'type': 'boolean'}


def test_java_type_to_schema_collections():
    assert _java_type_to_schema('java.util.List') == {'type': 'array'}
    assert _java_type_to_schema('java.util.Map') == {'type': 'object'}
    assert _java_type_to_schema('java.util.UUID') == {'type': 'string', 'format': 'uuid'}


def test_java_type_to_schema_unknown_defaults_to_object():
    assert _java_type_to_schema('com.example.SomeDto') == {'type': 'object'}
    assert _java_type_to_schema('ANY') == {'type': 'object'}
    assert _java_type_to_schema('') == {'type': 'object'}


def test_extract_annotation_string_value_double_quotes():
    assert _extract_annotation_string_value('@RequestHeader("X-Api-Key")') == 'X-Api-Key'


def test_extract_annotation_string_value_named_attribute():
    assert _extract_annotation_string_value('@RequestHeader(value = "X-Auth-Token")') == 'X-Auth-Token'


def test_extract_annotation_string_value_no_value():
    assert _extract_annotation_string_value('@RequestHeader') == ''
    assert _extract_annotation_string_value('@PathVariable') == ''


# ── fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture
def spring_annotations():
    return OpenAPI(
        'openapi3.1.0', 'java',
        'test/data/java-spring-annotations-usages.json'
    )


# ── _build_udt_schema_map ─────────────────────────────────────────────────────

def test_build_udt_schema_map(spring_annotations):
    udt_map = spring_annotations._build_udt_schema_map()
    assert 'com.example.ChargeRequest' in udt_map
    fields = udt_map['com.example.ChargeRequest']
    field_names = [f['name'] for f in fields]
    assert 'amount' in field_names
    assert 'currency' in field_names
    assert 'description' in field_names


# ── _build_schema_from_type ───────────────────────────────────────────────────

def test_build_schema_from_type_known_udt(spring_annotations):
    udt_map = spring_annotations._build_udt_schema_map()
    schema = spring_annotations._build_schema_from_type('com.example.ChargeRequest', udt_map)
    assert schema['type'] == 'object'
    props = schema['properties']
    assert props['amount'] == {'type': 'integer', 'format': 'int64'}
    assert props['currency'] == {'type': 'string'}
    assert props['description'] == {'type': 'string'}


def test_build_schema_from_type_unknown_falls_back(spring_annotations):
    udt_map = spring_annotations._build_udt_schema_map()
    schema = spring_annotations._build_schema_from_type('com.example.Unknown', udt_map)
    assert schema == {'type': 'object'}
    schema2 = spring_annotations._build_schema_from_type('java.lang.String', udt_map)
    assert schema2 == {'type': 'string'}


# ── _enrich_from_param_annotation ────────────────────────────────────────────

def test_enrich_post_requestbody(spring_annotations):
    paths = spring_annotations._enrich_from_param_annotation()
    assert '/charge' in paths
    post_op = paths['/charge']['post']
    assert 'requestBody' in post_op
    rb = post_op['requestBody']
    assert rb['required'] is True
    schema = rb['content']['application/json']['schema']
    assert schema['type'] == 'object'
    assert 'amount' in schema['properties']
    assert 'currency' in schema['properties']
    assert 'description' in schema['properties']


def test_enrich_post_requestheader(spring_annotations):
    paths = spring_annotations._enrich_from_param_annotation()
    post_op = paths['/charge']['post']
    assert 'parameters' in post_op
    params_by_name = {p['name']: p for p in post_op['parameters']}
    # @RequestHeader uses the Java parameter name, not the annotation string value
    assert 'apiKey' in params_by_name
    assert params_by_name['apiKey']['in'] == 'header'
    assert params_by_name['apiKey']['schema'] == {'type': 'string'}


def test_enrich_get_pathvariable_and_queryparam(spring_annotations):
    paths = spring_annotations._enrich_from_param_annotation()
    assert '/orders/{orderId}' in paths
    get_op = paths['/orders/{orderId}']['get']
    assert 'parameters' in get_op
    params_by_name = {p['name']: p for p in get_op['parameters']}
    # @PathVariable orderId
    assert 'orderId' in params_by_name
    assert params_by_name['orderId']['in'] == 'path'
    assert params_by_name['orderId']['required'] is True
    assert params_by_name['orderId']['schema'] == {'type': 'string'}
    # @RequestParam expand
    assert 'expand' in params_by_name
    assert params_by_name['expand']['in'] == 'query'
    assert params_by_name['expand']['schema'] == {'type': 'boolean'}


def test_enrich_delete_pathvariable_and_header(spring_annotations):
    paths = spring_annotations._enrich_from_param_annotation()
    del_op = paths['/orders/{orderId}']['delete']
    assert 'parameters' in del_op
    params_by_name = {p['name']: p for p in del_op['parameters']}
    assert params_by_name['orderId']['in'] == 'path'
    # @RequestHeader uses the Java parameter name (authToken), not the annotation string value
    assert params_by_name['authToken']['in'] == 'header'


# ── full convert_usages integration ──────────────────────────────────────────

def test_convert_usages_includes_requestbody(spring_annotations):
    paths = spring_annotations.convert_usages()
    assert '/charge' in paths
    post_op = paths['/charge'].get('post', {})
    assert 'requestBody' in post_op, "POST /charge must have requestBody"


def test_convert_usages_no_requestbody_on_get(spring_annotations):
    paths = spring_annotations.convert_usages()
    get_op = paths.get('/orders/{orderId}', {}).get('get', {})
    assert 'requestBody' not in get_op


def test_non_java_origin_skipped():
    """_enrich_from_param_annotation returns {} for non-Java slice types."""
    api = OpenAPI('openapi3.1.0', 'python', 'test/data/py-breakable-flask-usages.json')
    assert api._enrich_from_param_annotation() == {}
