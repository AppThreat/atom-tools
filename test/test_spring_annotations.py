"""
Tests for Spring parameter annotation support in the OpenAPI converter.

Covers:
- _spring_annotation_to_http_method: all HTTP verb annotations
- _spring_annotation_to_http_method: @RequestMapping with RequestMethod enum
- _spring_annotation_to_http_method: unknown annotation returns empty string
- _java_type_to_openapi_schema: primitive and complex Java types
- _enrich_from_param_annotations: non-Java origin returns {}
- Full converter: POST endpoint with @RequestBody -> requestBody in output
- Full converter: GET endpoint with @PathVariable -> path parameter in output
- Full converter: GET endpoint with @RequestParam -> query parameter in output
- Full converter: POST endpoint with @RequestBody + @RequestHeader -> both present
- No regression: existing Java slices without annotations are unaffected
"""
import pytest

from atom_tools.lib.converter import (
    OpenAPI,
    _spring_annotation_to_http_method,
    _java_type_to_openapi_schema,
)

JAVA_SLICE_FILE = 'test/data/java-spring-annotations-usages.json'


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def java_spring_annotations_converter():
    return OpenAPI('openapi3.1.0', 'java', JAVA_SLICE_FILE)


@pytest.fixture
def js_converter():
    return OpenAPI('openapi3.1.0', 'js', 'test/data/js-nodegoat-usages.json')


@pytest.fixture
def java_piggymetrics_converter():
    return OpenAPI('openapi3.1.0', 'java', 'test/data/java-piggymetrics-usages.json')


# ---------------------------------------------------------------------------
# _spring_annotation_to_http_method
# ---------------------------------------------------------------------------

def test_post_mapping_returns_post():
    assert _spring_annotation_to_http_method('@PostMapping("/orders")') == 'post'


def test_get_mapping_returns_get():
    assert _spring_annotation_to_http_method('@GetMapping("/{id}")') == 'get'


def test_put_mapping_returns_put():
    assert _spring_annotation_to_http_method('@PutMapping("/{id}")') == 'put'


def test_delete_mapping_returns_delete():
    assert _spring_annotation_to_http_method('@DeleteMapping("/{id}")') == 'delete'


def test_patch_mapping_returns_patch():
    assert _spring_annotation_to_http_method('@PatchMapping("/{id}")') == 'patch'


def test_request_mapping_with_method_post():
    ann = '@RequestMapping(method = RequestMethod.POST, value = "/users")'
    assert _spring_annotation_to_http_method(ann) == 'post'


def test_request_mapping_with_method_put():
    ann = '@RequestMapping(method = RequestMethod.PUT, value = "/{id}")'
    assert _spring_annotation_to_http_method(ann) == 'put'


def test_unknown_annotation_returns_empty():
    assert _spring_annotation_to_http_method('@Component') == ''


def test_empty_string_returns_empty():
    assert _spring_annotation_to_http_method('') == ''


# ---------------------------------------------------------------------------
# _java_type_to_openapi_schema
# ---------------------------------------------------------------------------

def test_string_type():
    assert _java_type_to_openapi_schema('java.lang.String') == {'type': 'string'}


def test_integer_type():
    assert _java_type_to_openapi_schema('java.lang.Integer') == {'type': 'integer'}


def test_int_primitive():
    assert _java_type_to_openapi_schema('int') == {'type': 'integer'}


def test_long_type():
    assert _java_type_to_openapi_schema('java.lang.Long') == {'type': 'integer', 'format': 'int64'}


def test_boolean_type():
    assert _java_type_to_openapi_schema('java.lang.Boolean') == {'type': 'boolean'}


def test_custom_class_returns_object():
    assert _java_type_to_openapi_schema('com.example.dto.OrderRequest') == {'type': 'object'}


def test_unknown_type_returns_object():
    assert _java_type_to_openapi_schema('ANY') == {'type': 'object'}


# ---------------------------------------------------------------------------
# _enrich_from_param_annotations — non-Java returns {}
# ---------------------------------------------------------------------------

def test_enrich_non_java_returns_empty(js_converter):
    result = js_converter._enrich_from_param_annotations()
    assert result == {}


# ---------------------------------------------------------------------------
# Full converter integration — endpoints_to_openapi
# ---------------------------------------------------------------------------

def test_post_endpoint_has_request_body(java_spring_annotations_converter):
    """POST /api/orders has @RequestBody -> requestBody must appear in output."""
    paths = java_spring_annotations_converter.endpoints_to_openapi()['paths']
    post_op = paths.get('/api/orders', {}).get('post', {})
    assert 'requestBody' in post_op
    assert post_op['requestBody']['required'] is True
    assert 'application/json' in post_op['requestBody']['content']


def test_post_request_body_schema_has_properties(java_spring_annotations_converter):
    """Custom Java type is resolved from userDefinedTypes -> schema includes field properties."""
    paths = java_spring_annotations_converter.endpoints_to_openapi()['paths']
    schema = paths['/api/orders']['post']['requestBody']['content']['application/json']['schema']
    assert schema['type'] == 'object'
    assert 'properties' in schema
    assert schema['properties']['productId'] == {'type': 'string'}
    assert schema['properties']['quantity'] == {'type': 'integer'}


def test_java_type_to_openapi_schema_with_udt_map():
    """_java_type_to_openapi_schema resolves custom class fields when udt_map is provided."""
    udt_map = {
        'com.example.dto.OrderRequest': [
            {'name': 'productId', 'typeFullName': 'java.lang.String'},
            {'name': 'quantity',  'typeFullName': 'int'},
        ]
    }
    schema = _java_type_to_openapi_schema('com.example.dto.OrderRequest', udt_map)
    assert schema == {
        'type': 'object',
        'properties': {
            'productId': {'type': 'string'},
            'quantity':  {'type': 'integer'},
        }
    }


def test_get_endpoint_has_path_param(java_spring_annotations_converter):
    """GET /api/orders/{id} has @PathVariable Long id -> path param with int64 schema."""
    paths = java_spring_annotations_converter.endpoints_to_openapi()['paths']
    get_op = paths.get('/api/orders/{id}', {}).get('get', {})
    params = get_op.get('parameters', [])
    path_params = [p for p in params if p.get('in') == 'path' and p.get('name') == 'id']
    assert path_params, 'Expected path param "id" in GET /api/orders/{id}'
    assert path_params[0]['schema'] == {'type': 'integer', 'format': 'int64'}


def test_get_search_has_query_param(java_spring_annotations_converter):
    """GET /api/orders/search has @RequestParam String status -> query param."""
    paths = java_spring_annotations_converter.endpoints_to_openapi()['paths']
    get_op = paths.get('/api/orders/search', {}).get('get', {})
    params = get_op.get('parameters', [])
    query_params = [p for p in params if p.get('in') == 'query' and p.get('name') == 'status']
    assert query_params, 'Expected query param "status" in GET /api/orders/search'
    assert query_params[0]['schema'] == {'type': 'string'}


def test_confirm_endpoint_has_request_body(java_spring_annotations_converter):
    """POST /api/orders/confirm has @RequestBody -> requestBody must appear."""
    paths = java_spring_annotations_converter.endpoints_to_openapi()['paths']
    post_op = paths.get('/api/orders/confirm', {}).get('post', {})
    assert 'requestBody' in post_op
    assert post_op['requestBody']['required'] is True


def test_confirm_endpoint_has_header_param(java_spring_annotations_converter):
    """POST /api/orders/confirm has @RequestHeader -> header param must appear."""
    paths = java_spring_annotations_converter.endpoints_to_openapi()['paths']
    post_op = paths.get('/api/orders/confirm', {}).get('post', {})
    params = post_op.get('parameters', [])
    header_params = [p for p in params if p.get('in') == 'header' and p.get('name') == 'idempotencyKey']
    assert header_params, 'Expected header param "idempotencyKey" in POST /api/orders/confirm'


def test_confirm_endpoint_has_both_request_body_and_header(java_spring_annotations_converter):
    """POST /api/orders/confirm has both @RequestBody and @RequestHeader together."""
    paths = java_spring_annotations_converter.endpoints_to_openapi()['paths']
    post_op = paths.get('/api/orders/confirm', {}).get('post', {})
    assert 'requestBody' in post_op
    params = post_op.get('parameters', [])
    assert any(p.get('in') == 'header' for p in params)


# ---------------------------------------------------------------------------
# No regression — existing Java slices without annotations are unaffected
# ---------------------------------------------------------------------------

def test_no_request_body_injected_into_existing_java_slice(java_piggymetrics_converter):
    """Slices generated before the annotations field existed must be unchanged."""
    paths = java_piggymetrics_converter.endpoints_to_openapi()['paths']
    for path, path_item in paths.items():
        for method in ('get', 'post', 'put', 'patch', 'delete'):
            if method in path_item:
                assert 'requestBody' not in path_item[method], (
                    f'Unexpected requestBody injected into {method.upper()} {path}'
                )
