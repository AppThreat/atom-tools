from atom_tools.lib.utils import add_params_to_cmd, remove_duplicates_list


def test_add_params_to_cmd():
    assert add_params_to_cmd('convert -i usages.json -f openapi3.1.0 -t java', 'test.json') == ('convert', '-i test.json -f openapi3.1.0 -t java')
    assert add_params_to_cmd('convert -f openapi3.1.0', 'usages.json', 'java') == ('convert', '-f openapi3.1.0 -t java -i usages.json')


def test_remove_duplicates_list():
    data = [
        {'function_name': '', 'code': '', 'line_number': 1},
        {'function_name': ':program', 'line_number': 1, 'code': None},
        {'function_name': ':program', 'line_number': 1, 'code': None},
        {'function_name': 'require', 'line_number': 6, 'code': 'app.ts::program:require'}
    ]
    assert remove_duplicates_list(data) == [
        {'code': '', 'function_name': '', 'line_number': 1},
        {'code': None, 'function_name': ':program', 'line_number': 1},
        {'code': 'app.ts::program:require', 'function_name': 'require', 'line_number': 6}
    ]
