from atom_tools.lib.utils import add_params_to_cmd, output_endpoints, remove_duplicates_list


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


def test_output_endpoints():
    data = {'openapi': '3.1.0', 'info': {'title': 'OpenAPI Specification for data', 'version': '1.0.0'}, 'paths': {'/uaa/users': {'post': {'responses': {}}, 'x-atom-usages': {'call': {'account-service/src/main/java/com/piggymetrics/account/client/AuthServiceClient.java': [12]}}}, '/statistics/{accountName}': {'parameters': [{'name': 'accountName', 'in': 'path', 'required': True}], 'put': {'responses': {}}, 'x-atom-usages': {'call': {'account-service/src/main/java/com/piggymetrics/account/client/StatisticsServiceClient.java': [13]}}}, '/current': {'put': {'responses': {}}, 'x-atom-usages': {'call': {'account-service/src/main/java/com/piggymetrics/account/controller/AccountController.java': [30, 25], 'auth-service/src/main/java/com/piggymetrics/auth/controller/UserController.java': [22], 'notification-service/src/main/java/com/piggymetrics/notification/controller/RecipientController.java': [26, 21], 'statistics-service/src/main/java/com/piggymetrics/statistics/controller/StatisticsController.java': [20]}, 'target': {'account-service/src/main/java/com/piggymetrics/account/controller/AccountController.java': [30], 'auth-service/src/main/java/com/piggymetrics/auth/controller/UserController.java': [22], 'notification-service/src/main/java/com/piggymetrics/notification/controller/RecipientController.java': [26]}}, 'get': {'responses': {}}}, '/': {'post': {'responses': {}}, 'x-atom-usages': {'call': {'account-service/src/main/java/com/piggymetrics/account/controller/AccountController.java': [35]}}}, '/{name}': {'parameters': [{'name': 'name', 'in': 'path', 'required': True}], 'get': {'responses': {}}, 'x-atom-usages': {'call': {'account-service/src/main/java/com/piggymetrics/account/controller/AccountController.java': [20]}}}, '/accounts/{accountName}': {'parameters': [{'name': 'accountName', 'in': 'path', 'required': True}], 'get': {'responses': {}}, 'x-atom-usages': {'call': {'notification-service/src/main/java/com/piggymetrics/notification/client/AccountServiceClient.java': [12]}}}, '/latest': {'get': {'responses': {}}, 'x-atom-usages': {'call': {'statistics-service/src/main/java/com/piggymetrics/statistics/client/ExchangeRatesClient.java': [13]}}}, '/{accountName}': {'parameters': [{'name': 'accountName', 'in': 'path', 'required': True}], 'put': {'responses': {}}, 'x-atom-usages': {'call': {'statistics-service/src/main/java/com/piggymetrics/statistics/controller/StatisticsController.java': [32, 26]}, 'target': {'statistics-service/src/main/java/com/piggymetrics/statistics/controller/StatisticsController.java': [32]}}, 'get': {'responses': {}}}}}
    assert output_endpoints(data, False, ()) == ('/uaa/users:account-service/src/main/java/com/piggymetrics/account/client/AuthServiceClient.java:12\n'
 '/statistics/{accountName}:account-service/src/main/java/com/piggymetrics/account/client/StatisticsServiceClient.java:13\n'
 '/current:account-service/src/main/java/com/piggymetrics/account/controller/AccountController.java:30:account-service/src/main/java/com/piggymetrics/account/controller/AccountController.java:25:auth-service/src/main/java/com/piggymetrics/auth/controller/UserController.java:22:notification-service/src/main/java/com/piggymetrics/notification/controller/RecipientController.java:26:notification-service/src/main/java/com/piggymetrics/notification/controller/RecipientController.java:21:statistics-service/src/main/java/com/piggymetrics/statistics/controller/StatisticsController.java:20\n'
 '/:account-service/src/main/java/com/piggymetrics/account/controller/AccountController.java:35\n'
 '/{name}:account-service/src/main/java/com/piggymetrics/account/controller/AccountController.java:20\n'
 '/accounts/{accountName}:notification-service/src/main/java/com/piggymetrics/notification/client/AccountServiceClient.java:12\n'
 '/latest:statistics-service/src/main/java/com/piggymetrics/statistics/client/ExchangeRatesClient.java:13\n'
 '/{accountName}:statistics-service/src/main/java/com/piggymetrics/statistics/controller/StatisticsController.java:32:statistics-service/src/main/java/com/piggymetrics/statistics/controller/StatisticsController.java:26\n')
    assert output_endpoints(data, True, ()) == ('/uaa/users\n/statistics/{'
                                                'accountName}\n/current\n/\n/{name}\n/accounts/{'
                                                'accountName}\n/latest\n/{accountName}\n')
    assert output_endpoints(data, False, (1, 14)) == ('/uaa/users:account-service/src/main/java/com/piggymetrics/account/client/AuthServiceClient.java:12\n'
 '/statistics/{accountName}:account-service/src/main/java/com/piggymetrics/account/client/StatisticsServiceClient.java:13\n'
 '/accounts/{accountName}:notification-service/src/main/java/com/piggymetrics/notification/client/AccountServiceClient.java:12\n'
 '/latest:statistics-service/src/main/java/com/piggymetrics/statistics/client/ExchangeRatesClient.java:13\n')
    assert output_endpoints(data, True, (30,30)) == '/current\n'
