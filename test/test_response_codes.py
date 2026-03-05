"""
Tests for HTTP response code inference in the OpenAPI converter.

Covers:
- determine_operations backward compatibility (no responses arg)
- determine_operations with pre-inferred responses
- _infer_java_response_codes: ResponseEntity.ok  -> 200
- _infer_java_response_codes: ResponseEntity.created -> 201
- _infer_java_response_codes: ResponseEntity.noContent -> 204
- _infer_java_response_codes: no ResponseEntity -> HTTP method default
- _infer_java_response_codes: non-Java origin -> returns {}
- Full converter: GET endpoint with ResponseEntity.ok  -> 200
- Full converter: POST endpoint with ResponseEntity.created -> 201
- Full converter: DELETE endpoint with ResponseEntity.noContent -> 204
- Full converter: GET endpoint with no ResponseEntity -> default 200
"""
import pytest
from atom_tools.lib.converter import (
    OpenAPI,
    determine_operations,
    RESPONSE_ENTITY_STATUS_MAP,
    HTTP_METHOD_DEFAULT_STATUS,
    STATUS_DESCRIPTIONS,
)
from atom_tools.lib.slices import AtomSlice

JAVA_SLICE_FILE = 'test/data/java-response-codes-usages.json'


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def java_response_codes_converter():
    return OpenAPI('openapi3.1.0', 'java', JAVA_SLICE_FILE)


@pytest.fixture
def js_converter():
    return OpenAPI('openapi3.1.0', 'js', 'test/data/js-nodegoat-usages.json')


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------

def test_response_entity_status_map_has_ok():
    assert RESPONSE_ENTITY_STATUS_MAP['ok'] == '200'


def test_response_entity_status_map_has_not_found():
    assert RESPONSE_ENTITY_STATUS_MAP['notFound'] == '404'


def test_http_method_default_post_is_201():
    assert HTTP_METHOD_DEFAULT_STATUS['post'] == '201'


def test_http_method_default_delete_is_204():
    assert HTTP_METHOD_DEFAULT_STATUS['delete'] == '204'


def test_status_descriptions_200():
    assert STATUS_DESCRIPTIONS['200'] == 'OK'


# ---------------------------------------------------------------------------
# determine_operations — backward compatibility (no responses arg)
# ---------------------------------------------------------------------------

def test_determine_operations_no_responses_arg_returns_empty_responses():
    """Existing callers that don't pass responses must still get {} responses."""
    call = {'callName': 'get', 'resolvedMethod': '@GetMapping("/test")', 'paramTypes': []}
    result = determine_operations(call, [])
    assert result == {'get': {'responses': {}}}


def test_determine_operations_with_responses_uses_provided_dict():
    call = {'callName': 'get', 'resolvedMethod': '@GetMapping("/test")', 'paramTypes': []}
    responses = {'200': {'description': 'OK'}}
    result = determine_operations(call, [], responses)
    assert result == {'get': {'responses': {'200': {'description': 'OK'}}}}


def test_determine_operations_none_responses_treated_as_empty():
    call = {'callName': 'post', 'resolvedMethod': '@PostMapping("/test")', 'paramTypes': []}
    result = determine_operations(call, [], None)
    assert result == {'post': {'responses': {}}}


# ---------------------------------------------------------------------------
# _infer_java_response_codes — unit tests
# ---------------------------------------------------------------------------

def test_infer_non_java_returns_empty(js_converter):
    result = js_converter._infer_java_response_codes(
        'some/file.js', 10, 'get'
    )
    assert result == {}


def test_infer_response_entity_ok(java_response_codes_converter):
    """GET /users/{id} slice has ResponseEntity.ok -> should return 200."""
    result = java_response_codes_converter._infer_java_response_codes(
        'src/main/java/com/example/controller/UserController.java', 20, 'get'
    )
    assert '200' in result
    assert result['200']['description'] == 'OK'


def test_infer_response_entity_created(java_response_codes_converter):
    """POST /users slice has ResponseEntity.created -> should return 201."""
    result = java_response_codes_converter._infer_java_response_codes(
        'src/main/java/com/example/controller/UserController.java', 30, 'post'
    )
    assert '201' in result
    assert result['201']['description'] == 'Created'


def test_infer_response_entity_no_content(java_response_codes_converter):
    """DELETE /users/{id} slice has ResponseEntity.noContent -> should return 204."""
    result = java_response_codes_converter._infer_java_response_codes(
        'src/main/java/com/example/controller/UserController.java', 40, 'delete'
    )
    assert '204' in result
    assert result['204']['description'] == 'No Content'


def test_infer_defaults_to_http_method_when_no_response_entity(java_response_codes_converter):
    """GET /users/{id}/status slice has no ResponseEntity call -> falls back to GET default 200."""
    result = java_response_codes_converter._infer_java_response_codes(
        'src/main/java/com/example/controller/UserController.java', 50, 'get'
    )
    assert '200' in result


def test_infer_defaults_post_when_no_match(java_response_codes_converter):
    """Unknown file/line -> falls back to HTTP method default."""
    result = java_response_codes_converter._infer_java_response_codes(
        'src/main/java/com/example/controller/UserController.java', 9999, 'post'
    )
    assert result == {'201': {'description': 'Created'}}


def test_infer_defaults_delete_when_no_match(java_response_codes_converter):
    result = java_response_codes_converter._infer_java_response_codes(
        'src/main/java/com/example/controller/UserController.java', 9999, 'delete'
    )
    assert result == {'204': {'description': 'No Content'}}


# ---------------------------------------------------------------------------
# Full converter integration — endpoints_to_openapi
# ---------------------------------------------------------------------------

def test_full_converter_get_with_response_entity_ok(java_response_codes_converter):
    """GET /users/{id} should produce 200 in the OpenAPI output."""
    result = java_response_codes_converter.endpoints_to_openapi()
    paths = result.get('paths', {})
    get_responses = paths.get('/users/{id}', {}).get('get', {}).get('responses', {})
    assert '200' in get_responses


def test_full_converter_post_with_response_entity_created(java_response_codes_converter):
    """POST /users should produce 201 in the OpenAPI output."""
    result = java_response_codes_converter.endpoints_to_openapi()
    paths = result.get('paths', {})
    post_responses = paths.get('/users', {}).get('post', {}).get('responses', {})
    assert '201' in post_responses


def test_full_converter_delete_with_no_content(java_response_codes_converter):
    """DELETE /users/{id} should produce 204 in the OpenAPI output."""
    result = java_response_codes_converter.endpoints_to_openapi()
    paths = result.get('paths', {})
    delete_responses = paths.get('/users/{id}', {}).get('delete', {}).get('responses', {})
    assert '204' in delete_responses


def test_full_converter_get_default_fallback(java_response_codes_converter):
    """GET /users/{id}/status has no ResponseEntity -> should fall back to default 200."""
    result = java_response_codes_converter.endpoints_to_openapi()
    paths = result.get('paths', {})
    get_responses = paths.get('/users/{id}/status', {}).get('get', {}).get('responses', {})
    assert '200' in get_responses


def test_full_converter_responses_never_empty_for_java(java_response_codes_converter):
    """No endpoint in a Java slice should have an empty responses dict."""
    result = java_response_codes_converter.endpoints_to_openapi()
    for path, path_item in result.get('paths', {}).items():
        for method in ('get', 'post', 'put', 'patch', 'delete', 'head', 'options'):
            if method in path_item:
                responses = path_item[method].get('responses', None)
                assert responses != {}, (
                    f'Empty responses for {method.upper()} {path}'
                )
