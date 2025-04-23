import pytest

from atom_tools.lib.converter import filter_calls, OpenAPI
from atom_tools.lib.utils import sort_list
from atom_tools.lib.ruby_converter import convert as ruby_convert

def sort_openapi_result(result):
    for k, v in result.items():
        if k == 'x-atom-usages':
            for a, b in result['x-atom-usages'].items():
                for key, value in b.items():
                    value.sort()
                    result[k][a][key] = value
        elif isinstance(v, list) and len(v) >= 2:
            result[k] = sort_list(v)
        elif isinstance(v, dict):
            result[k] = sort_openapi_result(v)
    return result


@pytest.fixture
def java_usages_1():
    return OpenAPI('openapi3.1.0', 'java',
                   'test/data/java-piggymetrics-usages.json')


@pytest.fixture
def java_usages_2():
    return OpenAPI('openapi3.0.1', 'java', 'test/data/java-sec-code-usages.json')


@pytest.fixture
def js_usages_1():
    return OpenAPI('openapi3.0.1', 'javascript', 'test/data/js-juiceshop-usages.json')


@pytest.fixture
def js_usages_2():
    return OpenAPI('openapi3.0.1', 'js', 'test/data/js-nodegoat-usages.json')


@pytest.fixture
def js_usages_3():
    return OpenAPI('openapi3.0.1', 'js', 'test/data/js-cdxgen-usages.json')


@pytest.fixture
def py_usages_1():
    return OpenAPI('openapi3.0.1', 'python', 'test/data/py-django-goat-usages.json')


@pytest.fixture
def py_usages_2():
    return OpenAPI('openapi3.0.1', 'py', 'test/data/py-breakable-flask-usages.json')

@pytest.fixture
def rb_usages_1():
    return OpenAPI('openapi3.0.1', 'rb', 'test/data/rb-railsgoat-usages.json')

def test_populate_endpoints(js_usages_1, js_usages_2, js_usages_3):
    # The populate_endpoints method is the final operation in convert_usages.
    # However, it's difficult to test the output when the order of params can
    # differ.
    methods = js_usages_1._process_methods()
    methods = js_usages_1.methods_to_endpoints(methods)
    assert methods

    methods = js_usages_2._process_methods()
    methods = js_usages_2.methods_to_endpoints(methods)
    assert methods
    assert methods['file_names']
    methods = js_usages_2._process_calls(methods)
    result = js_usages_2.populate_endpoints(methods)
    assert len(list(result['/login'].keys())) == 3
    result = sorted(result.keys())
    assert result == ['/',
 '/allocations/{userId}',
 '/app/assets/favicon.ico',
 '/benefits',
 '/contributions',
 '/dashboard',
 '/learn',
 '/login',
 '/logout',
 '/memos',
 '/profile',
 '/research',
 '/signup',
 '/tutorial',
 '/tutorial/a1']

def test_populate_endpoints2(js_usages_3):
    methods = js_usages_3._process_methods()
    methods = js_usages_3.methods_to_endpoints(methods)
    assert methods
    methods = js_usages_3._process_calls(methods)
    result = js_usages_3.populate_endpoints(methods)
    assert len(list(result['/sbom'].keys())) == 1
    result = sorted(result.keys())
    assert result == ["/", "/health", "/sbom"]


def test_usages_class(java_usages_1):
    assert java_usages_1.title == 'OpenAPI Specification for data'


def test_convert_usages(java_usages_1, java_usages_2, js_usages_1, js_usages_2, py_usages_1, py_usages_2):
    assert sort_openapi_result(java_usages_1.convert_usages())
    result = js_usages_1.convert_usages()
    result = sort_openapi_result(result)
    assert result
    result = py_usages_1.convert_usages()
    result = sort_openapi_result(result)
    assert result


def test_endpoints_to_openapi(java_usages_1):
    result = sort_openapi_result(java_usages_1.endpoints_to_openapi())
    assert result == {'info': {'title': 'OpenAPI Specification for data', 'version': '1.0.0'},
 'openapi': '3.1.0',
 'paths': {'/': {'post': {'responses': {}},
                 'x-atom-usages': {'call': {'account-service/src/main/java/com/piggymetrics/account/controller/AccountController.java': [35]}}},
           '/accounts/{accountName}': {'get': {'responses': {}},
                                       'parameters': [{'in': 'path',
                                                       'name': 'accountName',
                                                       'required': True}],
                                       'x-atom-usages': {'call': {'notification-service/src/main/java/com/piggymetrics/notification/client/AccountServiceClient.java': [12]}}},
           '/current': {'get': {'responses': {}},
                        'put': {'responses': {}},
                        'x-atom-usages': {'call': {'account-service/src/main/java/com/piggymetrics/account/controller/AccountController.java': [25,
                                                                                                                                                30],
                                                   'auth-service/src/main/java/com/piggymetrics/auth/controller/UserController.java': [22],
                                                   'notification-service/src/main/java/com/piggymetrics/notification/controller/RecipientController.java': [21,
                                                                                                                                                            26],
                                                   'statistics-service/src/main/java/com/piggymetrics/statistics/controller/StatisticsController.java': [20]},
                                          'target': {'account-service/src/main/java/com/piggymetrics/account/controller/AccountController.java': [30],
                                                     'auth-service/src/main/java/com/piggymetrics/auth/controller/UserController.java': [22],
                                                     'notification-service/src/main/java/com/piggymetrics/notification/controller/RecipientController.java': [26]}}},
           '/latest': {'get': {'responses': {}},
                       'x-atom-usages': {'call': {'statistics-service/src/main/java/com/piggymetrics/statistics/client/ExchangeRatesClient.java': [13]}}},
           '/statistics/{accountName}': {'parameters': [{'in': 'path',
                                                         'name': 'accountName',
                                                         'required': True}],
                                         'put': {'responses': {}},
                                         'x-atom-usages': {'call': {'account-service/src/main/java/com/piggymetrics/account/client/StatisticsServiceClient.java': [13]}}},
           '/uaa/users': {'post': {'responses': {}},
                          'x-atom-usages': {'call': {'account-service/src/main/java/com/piggymetrics/account/client/AuthServiceClient.java': [12]}}},
           '/{accountName}': {'get': {'responses': {}},
                              'parameters': [{'in': 'path',
                                              'name': 'accountName',
                                              'required': True}],
                              'put': {'responses': {}},
                              'x-atom-usages': {'call': {'statistics-service/src/main/java/com/piggymetrics/statistics/controller/StatisticsController.java': [26,
                                                                                                                                                               32]},
                                                'target': {'statistics-service/src/main/java/com/piggymetrics/statistics/controller/StatisticsController.java': [32]}}},
           '/{name}': {'get': {'responses': {}},
                       'parameters': [{'in': 'path',
                                       'name': 'name',
                                       'required': True}],
                       'x-atom-usages': {'call': {'account-service/src/main/java/com/piggymetrics/account/controller/AccountController.java': [20]}}}}}


def test_filter_calls():
    queried_calls = [{'callName': 'org.springframework.web.bind.annotation.RequestMapping',
                      'resolvedMethod': '@RequestMapping(value = "/current", method = RequestMethod.GET)',
                      'paramTypes': [], 'returnType': '', 'isExternal': False, 'lineNumber': 20,
                      'columnNumber': 2},
                     {'callName': 'org.springframework.web.bind.annotation.RequestMapping',
                      'resolvedMethod': '@RequestMapping(value = "/{accountName}", method = RequestMethod.GET)',
                      'paramTypes': [], 'returnType': '', 'isExternal': False, 'lineNumber': 26,
                      'columnNumber': 2},
                     {'callName': 'org.springframework.web.bind.annotation.RequestMapping',
                      'resolvedMethod': '@RequestMapping(value = "/{accountName}", method = RequestMethod.PUT)',
                      'paramTypes': [], 'returnType': '', 'isExternal': False, 'lineNumber': 32,
                      'columnNumber': 2}
                     ]
    resolved_methods = {'resolved_methods': {
        '@RequestMapping(value = "/current", method = RequestMethod.GET)': {
            'endpoints': ['/current'], 'calls': [
                {'callName': 'org.springframework.web.bind.annotation.RequestMapping',
                 'resolvedMethod': '@RequestMapping(value = "/current", method = RequestMethod.GET)',
                 'paramTypes': [], 'returnType': '', 'isExternal': False, 'lineNumber': 20,
                 'columnNumber': 2}], 'line_nos': [20]},
        '@RequestMapping(value = "/{accountName}", method = RequestMethod.GET)': {
            'endpoints': ['/{accountName}'], 'calls': [
                {'callName': 'org.springframework.web.bind.annotation.RequestMapping',
                 'resolvedMethod': '@RequestMapping(value = "/{accountName}", method = RequestMethod.GET)',
                 'paramTypes': [], 'returnType': '', 'isExternal': False, 'lineNumber': 26,
                 'columnNumber': 2}], 'line_nos': [26]},
        '@RequestMapping(value = "/{accountName}", method = RequestMethod.PUT)': {
            'endpoints': ['/{accountName}'], 'calls': [
                {'callName': 'org.springframework.web.bind.annotation.RequestMapping',
                 'resolvedMethod': '@RequestMapping(value = "/{accountName}", method = RequestMethod.PUT)',
                 'paramTypes': [], 'returnType': '', 'isExternal': False, 'lineNumber': 32,
                 'columnNumber': 2}], 'line_nos': [32]}}
    }

    assert filter_calls(queried_calls, resolved_methods) == {'resolved_methods': {'@RequestMapping(value = "/current", method = RequestMethod.GET)': {'calls': [{'callName': 'org.springframework.web.bind.annotation.RequestMapping',
                                                                                                     'columnNumber': 2,
                                                                                                     'isExternal': False,
                                                                                                     'lineNumber': 20,
                                                                                                     'paramTypes': [],
                                                                                                     'resolvedMethod': '@RequestMapping(value '
                                                                                                                       '= '
                                                                                                                       '"/current", '
                                                                                                                       'method '
                                                                                                                       '= '
                                                                                                                       'RequestMethod.GET)',
                                                                                                     'returnType': ''}],
                                                                                          'endpoints': ['/current'],
                                                                                          'line_nos': [20]},
                      '@RequestMapping(value = "/{accountName}", method = RequestMethod.GET)': {'calls': [{'callName': 'org.springframework.web.bind.annotation.RequestMapping',
                                                                                                           'columnNumber': 2,
                                                                                                           'isExternal': False,
                                                                                                           'lineNumber': 26,
                                                                                                           'paramTypes': [],
                                                                                                           'resolvedMethod': '@RequestMapping(value '
                                                                                                                             '= '
                                                                                                                             '"/{accountName}", '
                                                                                                                             'method '
                                                                                                                             '= '
                                                                                                                             'RequestMethod.GET)',
                                                                                                           'returnType': ''}],
                                                                                                'endpoints': ['/{accountName}'],
                                                                                                'line_nos': [26]},
                      '@RequestMapping(value = "/{accountName}", method = RequestMethod.PUT)': {'calls': [{'callName': 'org.springframework.web.bind.annotation.RequestMapping',
                                                                                                           'columnNumber': 2,
                                                                                                           'isExternal': False,
                                                                                                           'lineNumber': 32,
                                                                                                           'paramTypes': [],
                                                                                                           'resolvedMethod': '@RequestMapping(value '
                                                                                                                             '= '
                                                                                                                             '"/{accountName}", '
                                                                                                                             'method '
                                                                                                                             '= '
                                                                                                                             'RequestMethod.PUT)',
                                                                                                           'returnType': ''}],
                                                                                                'endpoints': ['/{accountName}'],
                                                                                                'line_nos': [32]}}
                                                             }


def test_java(java_usages_1):
    methods = java_usages_1._process_methods()
    for k, v in methods.items():
        methods[k].sort()
    assert methods == {'account-service/src/main/java/com/piggymetrics/account/AccountApplication.java': ['<operator>.arrayInitializer',
                                                                                    '<operator>.fieldAccess',
                                                                                    'com.piggymetrics.statistics.domain.Item.getCurrency:com.piggymetrics.statistics.domain.Currency()',
                                                                                    'com.piggymetrics.statistics.domain.Item.getTitle:java.lang.String()',
                                                                                    'org.springframework.boot.SpringApplication.run:org.springframework.context.ConfigurableApplicationContext(java.lang.Class,java.lang.String[])'],
 'account-service/src/main/java/com/piggymetrics/account/client/AuthServiceClient.java': ['@RequestMapping(method '
                                                                                          '= '
                                                                                          'RequestMethod.POST, '
                                                                                          'value '
                                                                                          '= '
                                                                                          '"/uaa/users", '
                                                                                          'consumes '
                                                                                          '= '
                                                                                          'MediaType.APPLICATION_JSON_UTF8_VALUE)',
                                                                                          'com.piggymetrics.account.client.AuthServiceClient.createUser:void(com.piggymetrics.account.domain.User)'],
 'account-service/src/main/java/com/piggymetrics/account/client/StatisticsServiceClient.java': ['@RequestMapping(method '
                                                                                                '= '
                                                                                                'RequestMethod.PUT, '
                                                                                                'value '
                                                                                                '= '
                                                                                                '"/statistics/{accountName}", '
                                                                                                'consumes '
                                                                                                '= '
                                                                                                'MediaType.APPLICATION_JSON_UTF8_VALUE)',
                                                                                                'com.piggymetrics.account.client.StatisticsServiceClient.updateStatistics:void(java.lang.String,com.piggymetrics.account.domain.Account)'],
 'account-service/src/main/java/com/piggymetrics/account/client/StatisticsServiceClientFallback.java': ['@Override',
                                                                                                        'LOGGER',
                                                                                                        'com.piggymetrics.account.client.StatisticsServiceClientFallback.updateStatistics:void(java.lang.String,com.piggymetrics.account.domain.Account)',
                                                                                                        'org.slf4j.Logger.error:void(java.lang.String,java.lang.Object)'],
 'account-service/src/main/java/com/piggymetrics/account/config/ResourceServerConfig.java': ['<operator>.alloc',
                                                                                             '@Autowired',
                                                                                             '@Bean',
                                                                                             '@ConfigurationProperties(prefix '
                                                                                             '= '
                                                                                             '"security.oauth2.client")',
                                                                                             '@Override',
                                                                                             'com.piggymetrics.account.config.ResourceServerConfig.clientCredentialsResourceDetails:org.springframework.security.oauth2.client.token.grant.client.ClientCredentialsResourceDetails()',
                                                                                             'org.springframework.boot.autoconfigure.security.oauth2.resource.ResourceServerProperties.getClientId:java.lang.String()',
                                                                                             'org.springframework.boot.autoconfigure.security.oauth2.resource.ResourceServerProperties.getUserInfoUri:java.lang.String()',
                                                                                             'org.springframework.cloud.security.oauth2.client.feign.OAuth2FeignRequestInterceptor.<init>:void(org.springframework.security.oauth2.client.OAuth2ClientContext,org.springframework.security.oauth2.client.resource.OAuth2ProtectedResourceDetails)',
                                                                                             'org.springframework.security.config.annotation.web.builders.HttpSecurity.authorizeRequests:org.springframework.security.config.annotation.web.configurers.ExpressionUrlAuthorizationConfigurer$ExpressionInterceptUrlRegistry()',
                                                                                             'org.springframework.security.config.annotation.web.configurers.ExpressionUrlAuthorizationConfigurer$AuthorizedUrl.authenticated:org.springframework.security.config.annotation.web.configurers.ExpressionUrlAuthorizationConfigurer$ExpressionInterceptUrlRegistry()',
                                                                                             'org.springframework.security.config.annotation.web.configurers.ExpressionUrlAuthorizationConfigurer$AuthorizedUrl.permitAll:org.springframework.security.config.annotation.web.configurers.ExpressionUrlAuthorizationConfigurer$ExpressionInterceptUrlRegistry()',
                                                                                             'org.springframework.security.config.annotation.web.configurers.ExpressionUrlAuthorizationConfigurer$ExpressionInterceptUrlRegistry.antMatchers:java.lang.Object(java.lang.String[])',
                                                                                             'org.springframework.security.config.annotation.web.configurers.ExpressionUrlAuthorizationConfigurer$ExpressionInterceptUrlRegistry.anyRequest:java.lang.Object()',
                                                                                             'org.springframework.security.oauth2.client.DefaultOAuth2ClientContext.<init>:void()',
                                                                                             'org.springframework.security.oauth2.client.OAuth2RestTemplate.<init>:void(org.springframework.security.oauth2.client.resource.OAuth2ProtectedResourceDetails)',
                                                                                             'org.springframework.security.oauth2.client.token.grant.client.ClientCredentialsResourceDetails.<init>:void()',
                                                                                             'sso'],
 'account-service/src/main/java/com/piggymetrics/account/controller/AccountController.java': ['@PreAuthorize("#oauth2.hasScope(\'server\') '
                                                                                              'or '
                                                                                              '#name.equals(\'demo\')")',
                                                                                              '@RequestMapping(path '
                                                                                              '= '
                                                                                              '"/", '
                                                                                              'method '
                                                                                              '= '
                                                                                              'RequestMethod.POST)',
                                                                                              '@RequestMapping(path '
                                                                                              '= '
                                                                                              '"/current", '
                                                                                              'method '
                                                                                              '= '
                                                                                              'RequestMethod.GET)',
                                                                                              '@RequestMapping(path '
                                                                                              '= '
                                                                                              '"/current", '
                                                                                              'method '
                                                                                              '= '
                                                                                              'RequestMethod.PUT)',
                                                                                              '@RequestMapping(path '
                                                                                              '= '
                                                                                              '"/{name}", '
                                                                                              'method '
                                                                                              '= '
                                                                                              'RequestMethod.GET)',
                                                                                              'accountService',
                                                                                              'com.piggymetrics.account.service.AccountService.create:com.piggymetrics.account.domain.Account(com.piggymetrics.account.domain.User)',
                                                                                              'com.piggymetrics.account.service.AccountService.findByName:com.piggymetrics.account.domain.Account(java.lang.String)',
                                                                                              'com.piggymetrics.account.service.AccountService.saveChanges:void(java.lang.String,com.piggymetrics.account.domain.Account)',
                                                                                              'java.security.Principal.getName:java.lang.String()'],
 'account-service/src/main/java/com/piggymetrics/account/controller/ErrorHandler.java': ['@ExceptionHandler(IllegalArgumentException.class)',
                                                                                         '@ResponseStatus(HttpStatus.BAD_REQUEST)',
                                                                                         'com.piggymetrics.account.controller.ErrorHandler.getClass:java.lang.Class()',
                                                                                         'log',
                                                                                         'org.slf4j.Logger.info:void(java.lang.String,java.lang.Throwable)'],
 'account-service/src/main/java/com/piggymetrics/account/domain/Account.java': ['com.piggymetrics.account.domain.Account.<init>:void()',
                                                                                'com.piggymetrics.account.domain.Account.getExpenses:java.util.List()',
                                                                                'com.piggymetrics.account.domain.Account.getIncomes:java.util.List()',
                                                                                'com.piggymetrics.account.domain.Account.getName:java.lang.String()',
                                                                                'com.piggymetrics.account.domain.Account.getNote:java.lang.String()',
                                                                                'com.piggymetrics.account.domain.Account.getSaving:com.piggymetrics.account.domain.Saving()',
                                                                                'com.piggymetrics.account.domain.Account.setExpenses:void(java.util.List)',
                                                                                'com.piggymetrics.account.domain.Account.setIncomes:void(java.util.List)',
                                                                                'com.piggymetrics.account.domain.Account.setLastSeen:void(java.util.Date)',
                                                                                'com.piggymetrics.account.domain.Account.setName:void(java.lang.String)',
                                                                                'com.piggymetrics.account.domain.Account.setNote:void(java.lang.String)',
                                                                                'com.piggymetrics.account.domain.Account.setSaving:void(com.piggymetrics.account.domain.Saving)',
                                                                                'expenses',
                                                                                'incomes',
                                                                                'lastSeen',
                                                                                'name',
                                                                                'note',
                                                                                'saving'],
 'account-service/src/main/java/com/piggymetrics/account/domain/Currency.java': ['EUR',
                                                                                 'RUB',
                                                                                 'USD',
                                                                                 'com.piggymetrics.account.domain.Currency.getDefault:com.piggymetrics.account.domain.Currency()'],
 'account-service/src/main/java/com/piggymetrics/account/domain/Item.java': ['amount',
                                                                             'currency',
                                                                             'icon',
                                                                             'period',
                                                                             'title'],
 'account-service/src/main/java/com/piggymetrics/account/domain/Saving.java': ['amount',
                                                                               'capitalization',
                                                                               'com.piggymetrics.account.domain.Saving.<init>:void()',
                                                                               'com.piggymetrics.account.domain.Saving.setAmount:void(java.math.BigDecimal)',
                                                                               'com.piggymetrics.account.domain.Saving.setCapitalization:void(java.lang.Boolean)',
                                                                               'com.piggymetrics.account.domain.Saving.setCurrency:void(com.piggymetrics.account.domain.Currency)',
                                                                               'com.piggymetrics.account.domain.Saving.setDeposit:void(java.lang.Boolean)',
                                                                               'com.piggymetrics.account.domain.Saving.setInterest:void(java.math.BigDecimal)',
                                                                               'currency',
                                                                               'deposit',
                                                                               'interest'],
 'account-service/src/main/java/com/piggymetrics/account/domain/TimePeriod.java': ['DAY',
                                                                                   'HOUR',
                                                                                   'MONTH',
                                                                                   'QUARTER',
                                                                                   'YEAR'],
 'account-service/src/main/java/com/piggymetrics/account/domain/User.java': ['com.piggymetrics.account.domain.User.getUsername:java.lang.String()',
                                                                             'password',
                                                                             'username'],
 'account-service/src/main/java/com/piggymetrics/account/repository/AccountRepository.java': ['com.piggymetrics.account.repository.AccountRepository.findByName:com.piggymetrics.account.domain.Account(java.lang.String)'],
 'account-service/src/main/java/com/piggymetrics/account/service/AccountService.java': ['com.piggymetrics.account.service.AccountService.create:com.piggymetrics.account.domain.Account(com.piggymetrics.account.domain.User)',
                                                                                        'com.piggymetrics.account.service.AccountService.findByName:com.piggymetrics.account.domain.Account(java.lang.String)',
                                                                                        'com.piggymetrics.account.service.AccountService.saveChanges:void(java.lang.String,com.piggymetrics.account.domain.Account)'],
 'account-service/src/main/java/com/piggymetrics/account/service/AccountServiceImpl.java': ['<operator>.addition',
                                                                                            '@Override',
                                                                                            'authClient',
                                                                                            'com.piggymetrics.account.client.AuthServiceClient.createUser:void(com.piggymetrics.account.domain.User)',
                                                                                            'com.piggymetrics.account.client.StatisticsServiceClient.updateStatistics:void(java.lang.String,com.piggymetrics.account.domain.Account)',
                                                                                            'com.piggymetrics.account.domain.Account.<init>:void()',
                                                                                            'com.piggymetrics.account.domain.Account.getExpenses:java.util.List()',
                                                                                            'com.piggymetrics.account.domain.Account.getIncomes:java.util.List()',
                                                                                            'com.piggymetrics.account.domain.Account.getName:java.lang.String()',
                                                                                            'com.piggymetrics.account.domain.Account.getNote:java.lang.String()',
                                                                                            'com.piggymetrics.account.domain.Account.getSaving:com.piggymetrics.account.domain.Saving()',
                                                                                            'com.piggymetrics.account.domain.Account.setExpenses:void(java.util.List)',
                                                                                            'com.piggymetrics.account.domain.Account.setIncomes:void(java.util.List)',
                                                                                            'com.piggymetrics.account.domain.Account.setName:void(java.lang.String)',
                                                                                            'com.piggymetrics.account.domain.Account.setNote:void(java.lang.String)',
                                                                                            'com.piggymetrics.account.domain.Account.setSaving:void(com.piggymetrics.account.domain.Saving)',
                                                                                            'com.piggymetrics.account.domain.Saving.<init>:void()',
                                                                                            'com.piggymetrics.account.domain.Saving.setCapitalization:void(java.lang.Boolean)',
                                                                                            'com.piggymetrics.account.domain.Saving.setCurrency:void(com.piggymetrics.account.domain.Currency)',
                                                                                            'com.piggymetrics.account.domain.Saving.setDeposit:void(java.lang.Boolean)',
                                                                                            'com.piggymetrics.account.domain.User.getUsername:java.lang.String()',
                                                                                            'com.piggymetrics.account.repository.AccountRepository.findByName:com.piggymetrics.account.domain.Account(java.lang.String)',
                                                                                            'com.piggymetrics.account.repository.AccountRepository.save:java.lang.Object(java.lang.Object)',
                                                                                            'com.piggymetrics.account.service.AccountServiceImpl.create:com.piggymetrics.account.domain.Account(com.piggymetrics.account.domain.User)',
                                                                                            'com.piggymetrics.account.service.AccountServiceImpl.findByName:com.piggymetrics.account.domain.Account(java.lang.String)',
                                                                                            'com.piggymetrics.account.service.AccountServiceImpl.getClass:java.lang.Class()',
                                                                                            'com.piggymetrics.account.service.AccountServiceImpl.saveChanges:void(java.lang.String,com.piggymetrics.account.domain.Account)',
                                                                                            'com.piggymetrics.statistics.domain.Account',
                                                                                            'com.piggymetrics.statistics.domain.Saving',
                                                                                            'java.math.BigDecimal',
                                                                                            'java.math.BigDecimal.<init>:void(int)',
                                                                                            'java.util.Date',
                                                                                            'java.util.Date.<init>:void()',
                                                                                            'log',
                                                                                            'org.slf4j.Logger.debug:void(java.lang.String,java.lang.Object)',
                                                                                            'org.slf4j.Logger.info:void(java.lang.String)',
                                                                                            'org.springframework.util.Assert.hasLength:void(java.lang.String)',
                                                                                            'org.springframework.util.Assert.isNull:void(java.lang.Object,java.lang.String)',
                                                                                            'org.springframework.util.Assert.notNull:void(java.lang.Object,java.lang.String)',
                                                                                            'repository',
                                                                                            'statisticsClient'],
 'account-service/src/main/java/com/piggymetrics/account/service/security/CustomUserInfoTokenServices.java': ['<operator>.cast',
                                                                                                              '<operator>.conditional',
                                                                                                              '<operator>.equals',
                                                                                                              '<operator>.indexAccess',
                                                                                                              '<operator>.lessThan',
                                                                                                              '<operator>.logicalNot',
                                                                                                              '<operator>.logicalOr',
                                                                                                              '<operator>.postIncrement',
                                                                                                              '<operator>.throw',
                                                                                                              '@Override',
                                                                                                              '@SuppressWarnings({ '
                                                                                                              '"unchecked" '
                                                                                                              '})',
                                                                                                              'PRINCIPAL_KEYS',
                                                                                                              'authoritiesExtractor',
                                                                                                              'clientId',
                                                                                                              'com.piggymetrics.account.service.security.CustomUserInfoTokenServices.<init>:void(java.lang.String,java.lang.String)',
                                                                                                              'com.piggymetrics.account.service.security.CustomUserInfoTokenServices.extractAuthentication:org.springframework.security.oauth2.provider.OAuth2Authentication(java.util.Map)',
                                                                                                              'com.piggymetrics.account.service.security.CustomUserInfoTokenServices.getClass:java.lang.Class()',
                                                                                                              'com.piggymetrics.account.service.security.CustomUserInfoTokenServices.getMap:java.util.Map(java.lang.String,java.lang.String)',
                                                                                                              'com.piggymetrics.account.service.security.CustomUserInfoTokenServices.getPrincipal:java.lang.Object(java.util.Map)',
                                                                                                              'com.piggymetrics.account.service.security.CustomUserInfoTokenServices.getRequest:org.springframework.security.oauth2.provider.OAuth2Request(java.util.Map)',
                                                                                                              'java.lang.Exception.getClass:java.lang.Class()',
                                                                                                              'java.lang.Exception.getMessage:java.lang.String()',
                                                                                                              'java.lang.String.equals:boolean(java.lang.Object)',
                                                                                                              'java.lang.UnsupportedOperationException.<init>:void(java.lang.String)',
                                                                                                              'java.util.Collections.emptySet:java.util.Set()',
                                                                                                              'java.util.Collections.singletonMap:java.util.Map(java.lang.Object,java.lang.Object)',
                                                                                                              'java.util.HashSet.<init>:void(java.util.Collection)',
                                                                                                              'java.util.LinkedHashSet.<init>:void(java.util.Collection)',
                                                                                                              'java.util.Map.containsKey:boolean(java.lang.Object)',
                                                                                                              'java.util.Map.get:java.lang.Object(java.lang.Object)',
                                                                                                              'logger',
                                                                                                              'org.apache.commons.logging.Log.debug:void(java.lang.Object)',
                                                                                                              'org.apache.commons.logging.Log.info:void(java.lang.Object)',
                                                                                                              'org.apache.commons.logging.LogFactory.getLog:org.apache.commons.logging.Log(java.lang.Class)',
                                                                                                              'org.springframework.boot.autoconfigure.security.oauth2.resource.AuthoritiesExtractor.extractAuthorities:java.util.List(java.util.Map)',
                                                                                                              'org.springframework.boot.autoconfigure.security.oauth2.resource.FixedAuthoritiesExtractor.<init>:void()',
                                                                                                              'org.springframework.http.ResponseEntity.getBody:java.lang.Object()',
                                                                                                              'org.springframework.security.authentication.UsernamePasswordAuthenticationToken',
                                                                                                              'org.springframework.security.authentication.UsernamePasswordAuthenticationToken.<init>:void(java.lang.Object,java.lang.Object,java.util.Collection)',
                                                                                                              'org.springframework.security.authentication.UsernamePasswordAuthenticationToken.setDetails:void(java.lang.Object)',
                                                                                                              'org.springframework.security.oauth2.client.OAuth2ClientContext.getAccessToken:org.springframework.security.oauth2.common.OAuth2AccessToken()',
                                                                                                              'org.springframework.security.oauth2.client.OAuth2ClientContext.setAccessToken:void(org.springframework.security.oauth2.common.OAuth2AccessToken)',
                                                                                                              'org.springframework.security.oauth2.client.OAuth2RestOperations.getForEntity:org.springframework.http.ResponseEntity(java.lang.String,java.lang.Class,java.lang.Object[])',
                                                                                                              'org.springframework.security.oauth2.client.OAuth2RestOperations.getOAuth2ClientContext:org.springframework.security.oauth2.client.OAuth2ClientContext()',
                                                                                                              'org.springframework.security.oauth2.client.OAuth2RestTemplate',
                                                                                                              'org.springframework.security.oauth2.client.OAuth2RestTemplate.<init>:void(org.springframework.security.oauth2.client.resource.OAuth2ProtectedResourceDetails)',
                                                                                                              'org.springframework.security.oauth2.client.resource.BaseOAuth2ProtectedResourceDetails',
                                                                                                              'org.springframework.security.oauth2.client.resource.BaseOAuth2ProtectedResourceDetails.<init>:void()',
                                                                                                              'org.springframework.security.oauth2.client.resource.BaseOAuth2ProtectedResourceDetails.setClientId:void(java.lang.String)',
                                                                                                              'org.springframework.security.oauth2.common.DefaultOAuth2AccessToken',
                                                                                                              'org.springframework.security.oauth2.common.DefaultOAuth2AccessToken.<init>:void(java.lang.String)',
                                                                                                              'org.springframework.security.oauth2.common.DefaultOAuth2AccessToken.setTokenType:void(java.lang.String)',
                                                                                                              'org.springframework.security.oauth2.common.OAuth2AccessToken.getValue:java.lang.String()',
                                                                                                              'org.springframework.security.oauth2.common.exceptions.InvalidTokenException.<init>:void(java.lang.String)',
                                                                                                              'org.springframework.security.oauth2.provider.OAuth2Authentication.<init>:void(org.springframework.security.oauth2.provider.OAuth2Request,org.springframework.security.core.Authentication)',
                                                                                                              'org.springframework.security.oauth2.provider.OAuth2Request',
                                                                                                              'org.springframework.security.oauth2.provider.OAuth2Request.<init>:void(java.util.Map,java.lang.String,java.util.Collection,boolean,java.util.Set,java.util.Set,java.lang.String,java.util.Set,java.util.Map)',
                                                                                                              'restTemplate',
                                                                                                              'tokenType',
                                                                                                              'userInfoEndpointUrl'],
 'auth-service/src/main/java/com/piggymetrics/auth/config/OAuth2AuthorizationConfig.java': ['@Override',
                                                                                            'NOOP_PASSWORD_ENCODE',
                                                                                            'authenticationManager',
                                                                                            'env',
                                                                                            'org.springframework.core.env.Environment.getProperty:java.lang.String(java.lang.String)',
                                                                                            'org.springframework.security.crypto.password.NoOpPasswordEncoder.getInstance:org.springframework.security.crypto.password.PasswordEncoder()',
                                                                                            'org.springframework.security.oauth2.config.annotation.builders.ClientDetailsServiceBuilder$ClientBuilder.and:org.springframework.security.oauth2.config.annotation.builders.ClientDetailsServiceBuilder()',
                                                                                            'org.springframework.security.oauth2.config.annotation.builders.ClientDetailsServiceBuilder$ClientBuilder.authorizedGrantTypes:org.springframework.security.oauth2.config.annotation.builders.ClientDetailsServiceBuilder$ClientBuilder(java.lang.String[])',
                                                                                            'org.springframework.security.oauth2.config.annotation.builders.ClientDetailsServiceBuilder$ClientBuilder.scopes:org.springframework.security.oauth2.config.annotation.builders.ClientDetailsServiceBuilder$ClientBuilder(java.lang.String[])',
                                                                                            'org.springframework.security.oauth2.config.annotation.builders.ClientDetailsServiceBuilder$ClientBuilder.secret:org.springframework.security.oauth2.config.annotation.builders.ClientDetailsServiceBuilder$ClientBuilder(java.lang.String)',
                                                                                            'org.springframework.security.oauth2.config.annotation.builders.ClientDetailsServiceBuilder.withClient:org.springframework.security.oauth2.config.annotation.builders.ClientDetailsServiceBuilder$ClientBuilder(java.lang.String)',
                                                                                            'org.springframework.security.oauth2.config.annotation.builders.InMemoryClientDetailsServiceBuilder.withClient:org.springframework.security.oauth2.config.annotation.builders.ClientDetailsServiceBuilder$ClientBuilder(java.lang.String)',
                                                                                            'org.springframework.security.oauth2.config.annotation.configurers.ClientDetailsServiceConfigurer.inMemory:org.springframework.security.oauth2.config.annotation.builders.InMemoryClientDetailsServiceBuilder()',
                                                                                            'org.springframework.security.oauth2.config.annotation.web.configurers.AuthorizationServerEndpointsConfigurer.authenticationManager:org.springframework.security.oauth2.config.annotation.web.configurers.AuthorizationServerEndpointsConfigurer(org.springframework.security.authentication.AuthenticationManager)',
                                                                                            'org.springframework.security.oauth2.config.annotation.web.configurers.AuthorizationServerEndpointsConfigurer.tokenStore:org.springframework.security.oauth2.config.annotation.web.configurers.AuthorizationServerEndpointsConfigurer(org.springframework.security.oauth2.provider.token.TokenStore)',
                                                                                            'org.springframework.security.oauth2.config.annotation.web.configurers.AuthorizationServerEndpointsConfigurer.userDetailsService:org.springframework.security.oauth2.config.annotation.web.configurers.AuthorizationServerEndpointsConfigurer(org.springframework.security.core.userdetails.UserDetailsService)',
                                                                                            'org.springframework.security.oauth2.config.annotation.web.configurers.AuthorizationServerSecurityConfigurer.checkTokenAccess:org.springframework.security.oauth2.config.annotation.web.configurers.AuthorizationServerSecurityConfigurer(java.lang.String)',
                                                                                            'org.springframework.security.oauth2.config.annotation.web.configurers.AuthorizationServerSecurityConfigurer.passwordEncoder:org.springframework.security.oauth2.config.annotation.web.configurers.AuthorizationServerSecurityConfigurer(org.springframework.security.crypto.password.PasswordEncoder)',
                                                                                            'org.springframework.security.oauth2.config.annotation.web.configurers.AuthorizationServerSecurityConfigurer.tokenKeyAccess:org.springframework.security.oauth2.config.annotation.web.configurers.AuthorizationServerSecurityConfigurer(java.lang.String)',
                                                                                            'org.springframework.security.oauth2.provider.token.store.InMemoryTokenStore.<init>:void()',
                                                                                            'tokenStore',
                                                                                            'userDetailsService'],
 'auth-service/src/main/java/com/piggymetrics/auth/config/WebSecurityConfig.java': ['<unresolvedNamespace>.disable:<unresolvedSignature>(0)',
                                                                                    '@Bean',
                                                                                    '@Override',
                                                                                    'org.springframework.security.config.annotation.authentication.builders.AuthenticationManagerBuilder.userDetailsService:org.springframework.security.config.annotation.authentication.configurers.userdetails.DaoAuthenticationConfigurer(org.springframework.security.core.userdetails.UserDetailsService)',
                                                                                    'org.springframework.security.config.annotation.authentication.configurers.userdetails.DaoAuthenticationConfigurer.passwordEncoder:org.springframework.security.config.annotation.authentication.configurers.userdetails.AbstractDaoAuthenticationConfigurer(org.springframework.security.crypto.password.PasswordEncoder)',
                                                                                    'org.springframework.security.config.annotation.web.HttpSecurityBuilder.csrf:<unresolvedSignature>(0)',
                                                                                    'org.springframework.security.config.annotation.web.builders.HttpSecurity.authorizeRequests:org.springframework.security.config.annotation.web.configurers.ExpressionUrlAuthorizationConfigurer$ExpressionInterceptUrlRegistry()',
                                                                                    'org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter.authenticationManagerBean:org.springframework.security.authentication.AuthenticationManager()',
                                                                                    'org.springframework.security.config.annotation.web.configurers.ExpressionUrlAuthorizationConfigurer$ExpressionInterceptUrlRegistry.and:org.springframework.security.config.annotation.web.HttpSecurityBuilder()',
                                                                                    'org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder.<init>:void()',
                                                                                    'userDetailsService'],
 'auth-service/src/main/java/com/piggymetrics/auth/controller/UserController.java': ['@PreAuthorize("#oauth2.hasScope(\'server\')")',
                                                                                     '@RequestMapping(method '
                                                                                     '= '
                                                                                     'RequestMethod.POST)',
                                                                                     '@RequestMapping(value '
                                                                                     '= '
                                                                                     '"/current", '
                                                                                     'method '
                                                                                     '= '
                                                                                     'RequestMethod.GET)',
                                                                                     'com.piggymetrics.auth.service.UserService.create:void(com.piggymetrics.auth.domain.User)',
                                                                                     'userService'],
 'auth-service/src/main/java/com/piggymetrics/auth/domain/User.java': ['@Override',
                                                                       'com.piggymetrics.auth.domain.User.getPassword:java.lang.String()',
                                                                       'com.piggymetrics.auth.domain.User.getUsername:java.lang.String()',
                                                                       'com.piggymetrics.auth.domain.User.setPassword:void(java.lang.String)',
                                                                       'password',
                                                                       'username'],
 'auth-service/src/main/java/com/piggymetrics/auth/service/UserService.java': ['com.piggymetrics.auth.service.UserService.create:void(com.piggymetrics.auth.domain.User)'],
 'auth-service/src/main/java/com/piggymetrics/auth/service/UserServiceImpl.java': ['@Override',
                                                                                   'com.piggymetrics.auth.domain.User.getPassword:java.lang.String()',
                                                                                   'com.piggymetrics.auth.domain.User.getUsername:java.lang.String()',
                                                                                   'com.piggymetrics.auth.domain.User.setPassword:void(java.lang.String)',
                                                                                   'com.piggymetrics.auth.repository.UserRepository.findById:java.util.Optional(java.lang.Object)',
                                                                                   'com.piggymetrics.auth.repository.UserRepository.save:java.lang.Object(java.lang.Object)',
                                                                                   'com.piggymetrics.auth.service.UserServiceImpl.create:void(com.piggymetrics.auth.domain.User)',
                                                                                   'com.piggymetrics.auth.service.UserServiceImpl.getClass:java.lang.Class()',
                                                                                   'encoder',
                                                                                   'java.lang.IllegalArgumentException.<init>:void(java.lang.String)',
                                                                                   'java.util.Optional.ifPresent:void(java.util.function.Consumer)',
                                                                                   'log',
                                                                                   'org.slf4j.Logger.info:void(java.lang.String,java.lang.Object)',
                                                                                   'org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder.encode:java.lang.String(java.lang.CharSequence)',
                                                                                   'repository'],
 'auth-service/src/main/java/com/piggymetrics/auth/service/security/MongoUserDetailsService.java': ['@Override',
                                                                                                    'com.piggymetrics.auth.repository.UserRepository.findById:java.util.Optional(java.lang.Object)',
                                                                                                    'java.util.Optional.orElseThrow:java.lang.Object(java.util.function.Supplier)',
                                                                                                    'org.springframework.security.core.userdetails.UsernameNotFoundException.<init>:void(java.lang.String)',
                                                                                                    'repository'],
 'config/src/main/java/com/piggymetrics/config/SecurityConfig.java': ['@Override',
                                                                      'org.springframework.security.config.annotation.web.HttpSecurityBuilder.httpBasic:<unresolvedSignature>(0)',
                                                                      'org.springframework.security.config.annotation.web.builders.HttpSecurity.authorizeRequests:org.springframework.security.config.annotation.web.configurers.ExpressionUrlAuthorizationConfigurer$ExpressionInterceptUrlRegistry()',
                                                                      'org.springframework.security.config.annotation.web.builders.HttpSecurity.csrf:org.springframework.security.config.annotation.web.configurers.CsrfConfigurer()',
                                                                      'org.springframework.security.config.annotation.web.configurers.CsrfConfigurer.disable:org.springframework.security.config.annotation.web.HttpSecurityBuilder()'],
 'notification-service/src/main/java/com/piggymetrics/notification/NotificationServiceApplication.java': ['@Bean',
                                                                                                          'java.util.Arrays.asList:java.util.List(java.lang.Object[])',
                                                                                                          'org.springframework.data.mongodb.core.convert.CustomConversions.<init>:void(java.util.List)'],
 'notification-service/src/main/java/com/piggymetrics/notification/client/AccountServiceClient.java': ['@RequestMapping(method '
                                                                                                       '= '
                                                                                                       'RequestMethod.GET, '
                                                                                                       'value '
                                                                                                       '= '
                                                                                                       '"/accounts/{accountName}", '
                                                                                                       'consumes '
                                                                                                       '= '
                                                                                                       'MediaType.APPLICATION_JSON_UTF8_VALUE)',
                                                                                                       'com.piggymetrics.notification.client.AccountServiceClient.getAccount:java.lang.String(java.lang.String)'],
 'notification-service/src/main/java/com/piggymetrics/notification/config/ResourceServerConfig.java': ['@Bean',
                                                                                                       '@ConfigurationProperties(prefix '
                                                                                                       '= '
                                                                                                       '"security.oauth2.client")',
                                                                                                       'com.piggymetrics.notification.config.ResourceServerConfig.clientCredentialsResourceDetails:org.springframework.security.oauth2.client.token.grant.client.ClientCredentialsResourceDetails()'],
 'notification-service/src/main/java/com/piggymetrics/notification/controller/RecipientController.java': ['@RequestMapping(path '
                                                                                                          '= '
                                                                                                          '"/current", '
                                                                                                          'method '
                                                                                                          '= '
                                                                                                          'RequestMethod.GET)',
                                                                                                          '@RequestMapping(path '
                                                                                                          '= '
                                                                                                          '"/current", '
                                                                                                          'method '
                                                                                                          '= '
                                                                                                          'RequestMethod.PUT)',
                                                                                                          'com.piggymetrics.notification.service.RecipientService.save:com.piggymetrics.notification.domain.Recipient(java.lang.String,com.piggymetrics.notification.domain.Recipient)',
                                                                                                          'java.security.Principal.getName:java.lang.String()',
                                                                                                          'recipientService'],
 'notification-service/src/main/java/com/piggymetrics/notification/domain/Frequency.java': ['MONTHLY',
                                                                                            'QUARTERLY',
                                                                                            'WEEKLY',
                                                                                            'com.piggymetrics.notification.domain.Frequency.getDays:int()',
                                                                                            'com.piggymetrics.notification.domain.Frequency.values:com.piggymetrics.notification.domain.Frequency[]()',
                                                                                            'com.piggymetrics.notification.domain.Frequency.withDays:com.piggymetrics.notification.domain.Frequency(int)',
                                                                                            'days',
                                                                                            'java.util.stream.Stream.filter:java.util.stream.Stream(java.util.function.Predicate)',
                                                                                            'java.util.stream.Stream.findFirst:java.util.Optional()',
                                                                                            'java.util.stream.Stream.of:java.util.stream.Stream(java.lang.Object[])'],
 'notification-service/src/main/java/com/piggymetrics/notification/domain/NotificationSettings.java': ['active',
                                                                                                       'com.piggymetrics.notification.domain.NotificationSettings.getLastNotified:java.util.Date()',
                                                                                                       'com.piggymetrics.notification.domain.NotificationSettings.setLastNotified:void(java.util.Date)',
                                                                                                       'frequency',
                                                                                                       'lastNotified'],
 'notification-service/src/main/java/com/piggymetrics/notification/domain/NotificationType.java': ['BACKUP',
                                                                                                   'REMIND',
                                                                                                   'attachment',
                                                                                                   'com.piggymetrics.notification.domain.NotificationType.getAttachment:java.lang.String()',
                                                                                                   'com.piggymetrics.notification.domain.NotificationType.getSubject:java.lang.String()',
                                                                                                   'com.piggymetrics.notification.domain.NotificationType.getText:java.lang.String()',
                                                                                                   'subject',
                                                                                                   'text'],
 'notification-service/src/main/java/com/piggymetrics/notification/domain/Recipient.java': ['@Override',
                                                                                            'accountName',
                                                                                            'com.piggymetrics.notification.domain.Recipient.getAccountName:java.lang.String()',
                                                                                            'com.piggymetrics.notification.domain.Recipient.getEmail:java.lang.String()',
                                                                                            'com.piggymetrics.notification.domain.Recipient.getScheduledNotifications:java.util.Map()',
                                                                                            'com.piggymetrics.notification.domain.Recipient.setAccountName:void(java.lang.String)',
                                                                                            'email',
                                                                                            'scheduledNotifications'],
 'notification-service/src/main/java/com/piggymetrics/notification/repository/RecipientRepository.java': ['@Query("{ '
                                                                                                          '$and: '
                                                                                                          '[ '
                                                                                                          "{'scheduledNotifications.BACKUP.active': "
                                                                                                          'true '
                                                                                                          '}, '
                                                                                                          '{ '
                                                                                                          '$where: '
                                                                                                          "'this.scheduledNotifications.BACKUP.lastNotified "
                                                                                                          '< '
                                                                                                          '" '
                                                                                                          '+ '
                                                                                                          '"new '
                                                                                                          'Date(new '
                                                                                                          'Date().setDate(new '
                                                                                                          'Date().getDate() '
                                                                                                          '- '
                                                                                                          'this.scheduledNotifications.BACKUP.frequency '
                                                                                                          "))' "
                                                                                                          '}] '
                                                                                                          '}")',
                                                                                                          '@Query("{ '
                                                                                                          '$and: '
                                                                                                          '[ '
                                                                                                          "{'scheduledNotifications.REMIND.active': "
                                                                                                          'true '
                                                                                                          '}, '
                                                                                                          '{ '
                                                                                                          '$where: '
                                                                                                          "'this.scheduledNotifications.REMIND.lastNotified "
                                                                                                          '< '
                                                                                                          '" '
                                                                                                          '+ '
                                                                                                          '"new '
                                                                                                          'Date(new '
                                                                                                          'Date().setDate(new '
                                                                                                          'Date().getDate() '
                                                                                                          '- '
                                                                                                          'this.scheduledNotifications.REMIND.frequency '
                                                                                                          "))' "
                                                                                                          '}] '
                                                                                                          '}")',
                                                                                                          'com.piggymetrics.notification.repository.RecipientRepository.findByAccountName:com.piggymetrics.notification.domain.Recipient(java.lang.String)',
                                                                                                          'com.piggymetrics.notification.repository.RecipientRepository.findReadyForBackup:java.util.List()',
                                                                                                          'com.piggymetrics.notification.repository.RecipientRepository.findReadyForRemind:java.util.List()'],
 'notification-service/src/main/java/com/piggymetrics/notification/repository/converter/FrequencyReaderConverter.java': ['@Override',
                                                                                                                         'com.piggymetrics.notification.domain.Frequency.withDays:com.piggymetrics.notification.domain.Frequency(int)',
                                                                                                                         'com.piggymetrics.notification.repository.converter.FrequencyReaderConverter.<init>:void()'],
 'notification-service/src/main/java/com/piggymetrics/notification/repository/converter/FrequencyWriterConverter.java': ['@Override',
                                                                                                                         'com.piggymetrics.notification.domain.Frequency.getDays:int()',
                                                                                                                         'com.piggymetrics.notification.repository.converter.FrequencyWriterConverter.<init>:void()'],
 'notification-service/src/main/java/com/piggymetrics/notification/service/EmailServiceImpl.java': ['@Override',
                                                                                                    'com.piggymetrics.notification.domain.NotificationType.getAttachment:java.lang.String()',
                                                                                                    'com.piggymetrics.notification.domain.NotificationType.getSubject:java.lang.String()',
                                                                                                    'com.piggymetrics.notification.domain.NotificationType.getText:java.lang.String()',
                                                                                                    'com.piggymetrics.notification.domain.Recipient.getAccountName:java.lang.String()',
                                                                                                    'com.piggymetrics.notification.domain.Recipient.getEmail:java.lang.String()',
                                                                                                    'com.piggymetrics.notification.service.EmailServiceImpl.getClass:java.lang.Class()',
                                                                                                    'env',
                                                                                                    'java.lang.String.getBytes:byte[]()',
                                                                                                    'java.text.MessageFormat.format:java.lang.String(java.lang.String,java.lang.Object[])',
                                                                                                    'log',
                                                                                                    'mailSender',
                                                                                                    'org.slf4j.Logger.info:void(java.lang.String,java.lang.Object,java.lang.Object)',
                                                                                                    'org.springframework.core.env.Environment.getProperty:java.lang.String(java.lang.String)',
                                                                                                    'org.springframework.core.io.ByteArrayResource',
                                                                                                    'org.springframework.core.io.ByteArrayResource.<init>:void(byte[])',
                                                                                                    'org.springframework.mail.javamail.JavaMailSender.createMimeMessage:javax.mail.internet.MimeMessage()',
                                                                                                    'org.springframework.mail.javamail.JavaMailSender.send:void(javax.mail.internet.MimeMessage)',
                                                                                                    'org.springframework.mail.javamail.MimeMessageHelper',
                                                                                                    'org.springframework.mail.javamail.MimeMessageHelper.<init>:void(javax.mail.internet.MimeMessage,boolean)',
                                                                                                    'org.springframework.mail.javamail.MimeMessageHelper.addAttachment:void(java.lang.String,org.springframework.core.io.InputStreamSource)',
                                                                                                    'org.springframework.mail.javamail.MimeMessageHelper.setSubject:void(java.lang.String)',
                                                                                                    'org.springframework.mail.javamail.MimeMessageHelper.setText:void(java.lang.String)',
                                                                                                    'org.springframework.mail.javamail.MimeMessageHelper.setTo:void(java.lang.String)',
                                                                                                    'org.springframework.util.StringUtils.hasLength:boolean(java.lang.String)'],
 'notification-service/src/main/java/com/piggymetrics/notification/service/NotificationServiceImpl.java': ['<operator>.fieldAccess',
                                                                                                           '@Override',
                                                                                                           '@Scheduled(cron '
                                                                                                           '= '
                                                                                                           '"${backup.cron}")',
                                                                                                           '@Scheduled(cron '
                                                                                                           '= '
                                                                                                           '"${remind.cron}")',
                                                                                                           'client',
                                                                                                           'com.piggymetrics.notification.client.AccountServiceClient.getAccount:java.lang.String(java.lang.String)',
                                                                                                           'com.piggymetrics.notification.service.EmailService.send:<unresolvedSignature>(3)',
                                                                                                           'com.piggymetrics.notification.service.NotificationServiceImpl.getClass:java.lang.Class()',
                                                                                                           'com.piggymetrics.notification.service.RecipientService.findReadyToNotify:java.util.List(com.piggymetrics.notification.domain.NotificationType)',
                                                                                                           'com.piggymetrics.notification.service.RecipientService.markNotified:<unresolvedSignature>(2)',
                                                                                                           'emailService',
                                                                                                           'java.lang.Object.getAccountName:<unresolvedSignature>(0)',
                                                                                                           'java.util.List.forEach:void(java.util.function.Consumer)',
                                                                                                           'java.util.List.size:int()',
                                                                                                           'java.util.concurrent.CompletableFuture.runAsync:java.util.concurrent.CompletableFuture(java.lang.Runnable)',
                                                                                                           'log',
                                                                                                           'org.slf4j.Logger.error:<unresolvedSignature>(3)',
                                                                                                           'recipientService'],
 'notification-service/src/main/java/com/piggymetrics/notification/service/RecipientService.java': ['com.piggymetrics.notification.service.RecipientService.findByAccountName:com.piggymetrics.notification.domain.Recipient(java.lang.String)',
                                                                                                    'com.piggymetrics.notification.service.RecipientService.findReadyToNotify:java.util.List(com.piggymetrics.notification.domain.NotificationType)',
                                                                                                    'com.piggymetrics.notification.service.RecipientService.save:com.piggymetrics.notification.domain.Recipient(java.lang.String,com.piggymetrics.notification.domain.Recipient)'],
 'notification-service/src/main/java/com/piggymetrics/notification/service/RecipientServiceImpl.java': ['@Override',
                                                                                                        'com.piggymetrics.notification.domain.NotificationSettings.getLastNotified:java.util.Date()',
                                                                                                        'com.piggymetrics.notification.domain.Recipient.getScheduledNotifications:java.util.Map()',
                                                                                                        'com.piggymetrics.notification.domain.Recipient.setAccountName:void(java.lang.String)',
                                                                                                        'com.piggymetrics.notification.repository.RecipientRepository.findByAccountName:com.piggymetrics.notification.domain.Recipient(java.lang.String)',
                                                                                                        'com.piggymetrics.notification.repository.RecipientRepository.save:java.lang.Object(java.lang.Object)',
                                                                                                        'com.piggymetrics.notification.service.RecipientServiceImpl.findByAccountName:com.piggymetrics.notification.domain.Recipient(java.lang.String)',
                                                                                                        'com.piggymetrics.notification.service.RecipientServiceImpl.findReadyToNotify:java.util.List(com.piggymetrics.notification.domain.NotificationType)',
                                                                                                        'com.piggymetrics.notification.service.RecipientServiceImpl.getClass:java.lang.Class()',
                                                                                                        'com.piggymetrics.notification.service.RecipientServiceImpl.save:com.piggymetrics.notification.domain.Recipient(java.lang.String,com.piggymetrics.notification.domain.Recipient)',
                                                                                                        'java.lang.IllegalArgumentException.<init>:void()',
                                                                                                        'java.util.Collection.forEach:void(java.util.function.Consumer)',
                                                                                                        'java.util.Date',
                                                                                                        'java.util.Map.get:java.lang.Object(java.lang.Object)',
                                                                                                        'java.util.Map.values:java.util.Collection()',
                                                                                                        'log',
                                                                                                        'org.slf4j.Logger.info:void(java.lang.String,java.lang.Object)',
                                                                                                        'org.springframework.util.Assert.hasLength:void(java.lang.String)',
                                                                                                        'repository'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/StatisticsApplication.java': ['@Bean'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/client/ExchangeRatesClient.java': ['@RequestMapping(method '
                                                                                                  '= '
                                                                                                  'RequestMethod.GET, '
                                                                                                  'value '
                                                                                                  '= '
                                                                                                  '"/latest")',
                                                                                                  'com.piggymetrics.statistics.client.ExchangeRatesClient.getRates:com.piggymetrics.statistics.domain.ExchangeRatesContainer(com.piggymetrics.statistics.domain.Currency)'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/client/ExchangeRatesClientFallback.java': ['@Override',
                                                                                                          'com.piggymetrics.statistics.client.ExchangeRatesClientFallback.getRates:com.piggymetrics.statistics.domain.ExchangeRatesContainer(com.piggymetrics.statistics.domain.Currency)',
                                                                                                          'com.piggymetrics.statistics.domain.ExchangeRatesContainer',
                                                                                                          'com.piggymetrics.statistics.domain.ExchangeRatesContainer.<init>:void()',
                                                                                                          'com.piggymetrics.statistics.domain.ExchangeRatesContainer.setBase:void(com.piggymetrics.statistics.domain.Currency)',
                                                                                                          'com.piggymetrics.statistics.domain.ExchangeRatesContainer.setRates:void(java.util.Map)',
                                                                                                          'java.util.Collections.emptyMap:java.util.Map()'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/config/ResourceServerConfig.java': ['@Bean',
                                                                                                   'sso'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/controller/StatisticsController.java': ['@PreAuthorize("#oauth2.hasScope(\'server\') '
                                                                                                       'or '
                                                                                                       '#accountName.equals(\'demo\')")',
                                                                                                       '@PreAuthorize("#oauth2.hasScope(\'server\')")',
                                                                                                       '@RequestMapping(value '
                                                                                                       '= '
                                                                                                       '"/current", '
                                                                                                       'method '
                                                                                                       '= '
                                                                                                       'RequestMethod.GET)',
                                                                                                       '@RequestMapping(value '
                                                                                                       '= '
                                                                                                       '"/{accountName}", '
                                                                                                       'method '
                                                                                                       '= '
                                                                                                       'RequestMethod.GET)',
                                                                                                       '@RequestMapping(value '
                                                                                                       '= '
                                                                                                       '"/{accountName}", '
                                                                                                       'method '
                                                                                                       '= '
                                                                                                       'RequestMethod.PUT)',
                                                                                                       'com.piggymetrics.statistics.service.StatisticsService.findByAccountName:java.util.List(java.lang.String)',
                                                                                                       'com.piggymetrics.statistics.service.StatisticsService.save:com.piggymetrics.statistics.domain.timeseries.DataPoint(java.lang.String,com.piggymetrics.statistics.domain.Account)',
                                                                                                       'java.security.Principal.getName:java.lang.String()',
                                                                                                       'statisticsService'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/domain/Account.java': ['com.piggymetrics.statistics.domain.Account.getExpenses:java.util.List()',
                                                                                      'com.piggymetrics.statistics.domain.Account.getIncomes:java.util.List()',
                                                                                      'com.piggymetrics.statistics.domain.Account.getSaving:com.piggymetrics.statistics.domain.Saving()',
                                                                                      'expenses',
                                                                                      'incomes',
                                                                                      'saving'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/domain/Currency.java': ['EUR',
                                                                                       'RUB',
                                                                                       'USD',
                                                                                       'com.piggymetrics.statistics.domain.Currency.getBase:com.piggymetrics.statistics.domain.Currency()'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/domain/ExchangeRatesContainer.java': ['@Override',
                                                                                                     'base',
                                                                                                     'com.piggymetrics.statistics.domain.ExchangeRatesContainer.<init>:void()',
                                                                                                     'com.piggymetrics.statistics.domain.ExchangeRatesContainer.getDate:java.time.LocalDate()',
                                                                                                     'com.piggymetrics.statistics.domain.ExchangeRatesContainer.getRates:java.util.Map()',
                                                                                                     'com.piggymetrics.statistics.domain.ExchangeRatesContainer.setBase:void(com.piggymetrics.statistics.domain.Currency)',
                                                                                                     'com.piggymetrics.statistics.domain.ExchangeRatesContainer.setRates:void(java.util.Map)',
                                                                                                     'date',
                                                                                                     'java.time.LocalDate.now:java.time.LocalDate()',
                                                                                                     'rates'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/domain/Item.java': ['amount',
                                                                                   'com.piggymetrics.statistics.domain.Item.getAmount:java.math.BigDecimal()',
                                                                                   'com.piggymetrics.statistics.domain.Item.getCurrency:com.piggymetrics.statistics.domain.Currency()',
                                                                                   'com.piggymetrics.statistics.domain.Item.getPeriod:com.piggymetrics.statistics.domain.TimePeriod()',
                                                                                   'com.piggymetrics.statistics.domain.Item.getTitle:java.lang.String()',
                                                                                   'currency',
                                                                                   'period',
                                                                                   'title'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/domain/Saving.java': ['amount',
                                                                                     'capitalization',
                                                                                     'com.piggymetrics.statistics.domain.Saving.getAmount:java.math.BigDecimal()',
                                                                                     'com.piggymetrics.statistics.domain.Saving.getCurrency:com.piggymetrics.statistics.domain.Currency()',
                                                                                     'currency',
                                                                                     'deposit',
                                                                                     'interest'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/domain/TimePeriod.java': ['DAY',
                                                                                         'HOUR',
                                                                                         'MONTH',
                                                                                         'QUARTER',
                                                                                         'YEAR',
                                                                                         'baseRatio',
                                                                                         'com.piggymetrics.statistics.domain.TimePeriod.getBaseRatio:java.math.BigDecimal()',
                                                                                         'java.math.BigDecimal.<init>:void(double)'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/domain/timeseries/DataPoint.java': ['com.piggymetrics.statistics.domain.timeseries.DataPoint.<init>:void()',
                                                                                                   'com.piggymetrics.statistics.domain.timeseries.DataPoint.setExpenses:void(java.util.Set)',
                                                                                                   'com.piggymetrics.statistics.domain.timeseries.DataPoint.setId:void(com.piggymetrics.statistics.domain.timeseries.DataPointId)',
                                                                                                   'com.piggymetrics.statistics.domain.timeseries.DataPoint.setIncomes:void(java.util.Set)',
                                                                                                   'com.piggymetrics.statistics.domain.timeseries.DataPoint.setRates:void(java.util.Map)',
                                                                                                   'com.piggymetrics.statistics.domain.timeseries.DataPoint.setStatistics:void(java.util.Map)',
                                                                                                   'expenses',
                                                                                                   'id',
                                                                                                   'incomes',
                                                                                                   'rates',
                                                                                                   'statistics'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/domain/timeseries/DataPointId.java': ['@Override',
                                                                                                     'account',
                                                                                                     'com.piggymetrics.statistics.domain.timeseries.DataPointId.<init>:void(java.lang.String,java.util.Date)',
                                                                                                     'com.piggymetrics.statistics.domain.timeseries.DataPointId.getAccount:java.lang.String()',
                                                                                                     'com.piggymetrics.statistics.domain.timeseries.DataPointId.getDate:java.util.Date()',
                                                                                                     'date',
                                                                                                     'serialVersionUID'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/domain/timeseries/ItemMetric.java': ['<operator>.notEquals',
                                                                                                    '@Override',
                                                                                                    'amount',
                                                                                                    'com.piggymetrics.statistics.domain.timeseries.ItemMetric.<init>:void(java.lang.String,java.math.BigDecimal)',
                                                                                                    'com.piggymetrics.statistics.domain.timeseries.ItemMetric.getClass:java.lang.Class()',
                                                                                                    'java.lang.Object.getClass:java.lang.Class()',
                                                                                                    'java.lang.String.equalsIgnoreCase:boolean(java.lang.String)',
                                                                                                    'java.lang.String.hashCode:int()',
                                                                                                    'title'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/domain/timeseries/StatisticMetric.java': ['EXPENSES_AMOUNT',
                                                                                                         'INCOMES_AMOUNT',
                                                                                                         'SAVING_AMOUNT'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/repository/DataPointRepository.java': ['com.piggymetrics.statistics.repository.DataPointRepository.findByIdAccount:java.util.List(java.lang.String)'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/repository/converter/DataPointIdReaderConverter.java': ['<operator>.cast',
                                                                                                                       '@Override',
                                                                                                                       'com.mongodb.DBObject.get:java.lang.Object(java.lang.String)',
                                                                                                                       'com.piggymetrics.statistics.domain.timeseries.DataPointId.<init>:void(java.lang.String,java.util.Date)',
                                                                                                                       'com.piggymetrics.statistics.repository.converter.DataPointIdReaderConverter.<init>:void()'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/repository/converter/DataPointIdWriterConverter.java': ['@Override',
                                                                                                                       'FIELDS',
                                                                                                                       'com.mongodb.BasicDBObject',
                                                                                                                       'com.mongodb.BasicDBObject.<init>:void(int)',
                                                                                                                       'com.mongodb.DBObject.put:java.lang.Object(java.lang.String,java.lang.Object)',
                                                                                                                       'com.piggymetrics.statistics.domain.timeseries.DataPointId.getAccount:java.lang.String()',
                                                                                                                       'com.piggymetrics.statistics.domain.timeseries.DataPointId.getDate:java.util.Date()',
                                                                                                                       'com.piggymetrics.statistics.repository.converter.DataPointIdWriterConverter.<init>:void()'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/service/ExchangeRatesService.java': ['com.piggymetrics.statistics.service.ExchangeRatesService.convert:java.math.BigDecimal(com.piggymetrics.statistics.domain.Currency,com.piggymetrics.statistics.domain.Currency,java.math.BigDecimal)',
                                                                                                    'com.piggymetrics.statistics.service.ExchangeRatesService.getCurrentRates:java.util.Map()'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/service/ExchangeRatesServiceImpl.java': ['@Override',
                                                                                                        'client',
                                                                                                        'com.google.common.collect.ImmutableMap.of:com.google.common.collect.ImmutableMap(java.lang.Object,java.lang.Object,java.lang.Object,java.lang.Object,java.lang.Object,java.lang.Object)',
                                                                                                        'com.piggymetrics.statistics.domain.Currency.name:java.lang.String()',
                                                                                                        'com.piggymetrics.statistics.service.ExchangeRatesServiceImpl.convert:java.math.BigDecimal(com.piggymetrics.statistics.domain.Currency,com.piggymetrics.statistics.domain.Currency,java.math.BigDecimal)',
                                                                                                        'com.piggymetrics.statistics.service.ExchangeRatesServiceImpl.getCurrentRates:java.util.Map()',
                                                                                                        'container',
                                                                                                        'java.math.BigDecimal.divide:java.math.BigDecimal(java.math.BigDecimal,int,java.math.RoundingMode)',
                                                                                                        'java.math.BigDecimal.multiply:java.math.BigDecimal(java.math.BigDecimal)',
                                                                                                        'java.time.LocalDate.equals:boolean(java.lang.Object)',
                                                                                                        'java.util.Map.get:java.lang.Object(java.lang.Object)',
                                                                                                        'log',
                                                                                                        'org.springframework.util.Assert.notNull:void(java.lang.Object)'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/service/StatisticsService.java': ['com.piggymetrics.statistics.service.StatisticsService.findByAccountName:java.util.List(java.lang.String)',
                                                                                                 'com.piggymetrics.statistics.service.StatisticsService.save:com.piggymetrics.statistics.domain.timeseries.DataPoint(java.lang.String,com.piggymetrics.statistics.domain.Account)'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/service/StatisticsServiceImpl.java': ['@Override',
                                                                                                     'com.google.common.collect.ImmutableMap.of:com.google.common.collect.ImmutableMap(java.lang.Object,java.lang.Object,java.lang.Object,java.lang.Object,java.lang.Object,java.lang.Object)',
                                                                                                     'com.piggymetrics.statistics.domain.Account.getExpenses:java.util.List()',
                                                                                                     'com.piggymetrics.statistics.domain.Account.getIncomes:java.util.List()',
                                                                                                     'com.piggymetrics.statistics.domain.Account.getSaving:com.piggymetrics.statistics.domain.Saving()',
                                                                                                     'com.piggymetrics.statistics.domain.Item.getAmount:java.math.BigDecimal()',
                                                                                                     'com.piggymetrics.statistics.domain.Item.getCurrency:com.piggymetrics.statistics.domain.Currency()',
                                                                                                     'com.piggymetrics.statistics.domain.Item.getPeriod:com.piggymetrics.statistics.domain.TimePeriod()',
                                                                                                     'com.piggymetrics.statistics.domain.Item.getTitle:java.lang.String()',
                                                                                                     'com.piggymetrics.statistics.domain.Saving.getAmount:java.math.BigDecimal()',
                                                                                                     'com.piggymetrics.statistics.domain.Saving.getCurrency:com.piggymetrics.statistics.domain.Currency()',
                                                                                                     'com.piggymetrics.statistics.domain.timeseries.DataPoint',
                                                                                                     'com.piggymetrics.statistics.domain.timeseries.DataPoint.<init>:void()',
                                                                                                     'com.piggymetrics.statistics.domain.timeseries.DataPoint.setExpenses:void(java.util.Set)',
                                                                                                     'com.piggymetrics.statistics.domain.timeseries.DataPoint.setId:void(com.piggymetrics.statistics.domain.timeseries.DataPointId)',
                                                                                                     'com.piggymetrics.statistics.domain.timeseries.DataPoint.setIncomes:void(java.util.Set)',
                                                                                                     'com.piggymetrics.statistics.domain.timeseries.DataPoint.setRates:void(java.util.Map)',
                                                                                                     'com.piggymetrics.statistics.domain.timeseries.DataPoint.setStatistics:void(java.util.Map)',
                                                                                                     'com.piggymetrics.statistics.domain.timeseries.DataPointId',
                                                                                                     'com.piggymetrics.statistics.domain.timeseries.DataPointId.<init>:void(java.lang.String,java.util.Date)',
                                                                                                     'com.piggymetrics.statistics.domain.timeseries.ItemMetric.<init>:void(java.lang.String,java.math.BigDecimal)',
                                                                                                     'com.piggymetrics.statistics.repository.DataPointRepository.findByIdAccount:java.util.List(java.lang.String)',
                                                                                                     'com.piggymetrics.statistics.repository.DataPointRepository.save:java.lang.Object(java.lang.Object)',
                                                                                                     'com.piggymetrics.statistics.service.ExchangeRatesService.convert:java.math.BigDecimal(com.piggymetrics.statistics.domain.Currency,com.piggymetrics.statistics.domain.Currency,java.math.BigDecimal)',
                                                                                                     'com.piggymetrics.statistics.service.StatisticsServiceImpl.createStatisticMetrics:java.util.Map(java.util.Set,java.util.Set,com.piggymetrics.statistics.domain.Saving)',
                                                                                                     'com.piggymetrics.statistics.service.StatisticsServiceImpl.findByAccountName:java.util.List(java.lang.String)',
                                                                                                     'com.piggymetrics.statistics.service.StatisticsServiceImpl.getClass:java.lang.Class()',
                                                                                                     'com.piggymetrics.statistics.service.StatisticsServiceImpl.save:com.piggymetrics.statistics.domain.timeseries.DataPoint(java.lang.String,com.piggymetrics.statistics.domain.Account)',
                                                                                                     'java.math.BigDecimal.divide:java.math.BigDecimal(java.math.BigDecimal,int,java.math.RoundingMode)',
                                                                                                     'java.time.LocalDate.atStartOfDay:java.time.LocalDateTime()',
                                                                                                     'java.time.LocalDateTime.atZone:java.time.ZonedDateTime(java.time.ZoneId)',
                                                                                                     'java.time.ZoneId.systemDefault:java.time.ZoneId()',
                                                                                                     'java.time.ZonedDateTime.toInstant:java.time.Instant()',
                                                                                                     'java.util.Date.from:java.util.Date(java.time.Instant)',
                                                                                                     'java.util.List.stream:java.util.stream.Stream()',
                                                                                                     'java.util.Set.stream:java.util.stream.Stream()',
                                                                                                     'java.util.stream.Collectors.toSet:java.util.stream.Collector()',
                                                                                                     'java.util.stream.Stream.collect:java.lang.Object(java.util.stream.Collector)',
                                                                                                     'java.util.stream.Stream.map:java.util.stream.Stream(java.util.function.Function)',
                                                                                                     'java.util.stream.Stream.reduce:java.lang.Object(java.lang.Object,java.util.function.BinaryOperator)',
                                                                                                     'log',
                                                                                                     'org.slf4j.Logger.debug:void(java.lang.String,java.lang.Object)',
                                                                                                     'org.springframework.util.Assert.hasLength:void(java.lang.String)',
                                                                                                     'ratesService',
                                                                                                     'repository'],
 'statistics-service/src/main/java/com/piggymetrics/statistics/service/security/CustomUserInfoTokenServices.java': ['<operator>.cast',
                                                                                                                    '<operator>.indexAccess',
                                                                                                                    '@Override',
                                                                                                                    '@SuppressWarnings({ '
                                                                                                                    '"unchecked" '
                                                                                                                    '})',
                                                                                                                    'PRINCIPAL_KEYS',
                                                                                                                    'authoritiesExtractor',
                                                                                                                    'clientId',
                                                                                                                    'com.piggymetrics.statistics.service.security.CustomUserInfoTokenServices.<init>:void(java.lang.String,java.lang.String)',
                                                                                                                    'com.piggymetrics.statistics.service.security.CustomUserInfoTokenServices.extractAuthentication:org.springframework.security.oauth2.provider.OAuth2Authentication(java.util.Map)',
                                                                                                                    'com.piggymetrics.statistics.service.security.CustomUserInfoTokenServices.getClass:java.lang.Class()',
                                                                                                                    'com.piggymetrics.statistics.service.security.CustomUserInfoTokenServices.getMap:java.util.Map(java.lang.String,java.lang.String)',
                                                                                                                    'com.piggymetrics.statistics.service.security.CustomUserInfoTokenServices.getPrincipal:java.lang.Object(java.util.Map)',
                                                                                                                    'com.piggymetrics.statistics.service.security.CustomUserInfoTokenServices.getRequest:org.springframework.security.oauth2.provider.OAuth2Request(java.util.Map)',
                                                                                                                    'java.lang.String.equals:boolean(java.lang.Object)',
                                                                                                                    'java.util.HashSet.<init>:void(java.util.Collection)',
                                                                                                                    'java.util.LinkedHashSet.<init>:void(java.util.Collection)',
                                                                                                                    'java.util.Map.containsKey:boolean(java.lang.Object)',
                                                                                                                    'java.util.Map.get:java.lang.Object(java.lang.Object)',
                                                                                                                    'logger',
                                                                                                                    'org.springframework.boot.autoconfigure.security.oauth2.resource.AuthoritiesExtractor.extractAuthorities:java.util.List(java.util.Map)',
                                                                                                                    'org.springframework.security.authentication.UsernamePasswordAuthenticationToken',
                                                                                                                    'org.springframework.security.authentication.UsernamePasswordAuthenticationToken.<init>:void(java.lang.Object,java.lang.Object,java.util.Collection)',
                                                                                                                    'org.springframework.security.authentication.UsernamePasswordAuthenticationToken.setDetails:void(java.lang.Object)',
                                                                                                                    'org.springframework.security.oauth2.client.OAuth2ClientContext.getAccessToken:org.springframework.security.oauth2.common.OAuth2AccessToken()',
                                                                                                                    'org.springframework.security.oauth2.client.OAuth2ClientContext.setAccessToken:void(org.springframework.security.oauth2.common.OAuth2AccessToken)',
                                                                                                                    'org.springframework.security.oauth2.client.OAuth2RestOperations.getForEntity:org.springframework.http.ResponseEntity(java.lang.String,java.lang.Class,java.lang.Object[])',
                                                                                                                    'org.springframework.security.oauth2.client.OAuth2RestOperations.getOAuth2ClientContext:org.springframework.security.oauth2.client.OAuth2ClientContext()',
                                                                                                                    'org.springframework.security.oauth2.client.OAuth2RestTemplate',
                                                                                                                    'org.springframework.security.oauth2.client.OAuth2RestTemplate.<init>:void(org.springframework.security.oauth2.client.resource.OAuth2ProtectedResourceDetails)',
                                                                                                                    'org.springframework.security.oauth2.client.resource.BaseOAuth2ProtectedResourceDetails',
                                                                                                                    'org.springframework.security.oauth2.client.resource.BaseOAuth2ProtectedResourceDetails.<init>:void()',
                                                                                                                    'org.springframework.security.oauth2.client.resource.BaseOAuth2ProtectedResourceDetails.setClientId:void(java.lang.String)',
                                                                                                                    'org.springframework.security.oauth2.common.DefaultOAuth2AccessToken',
                                                                                                                    'org.springframework.security.oauth2.common.DefaultOAuth2AccessToken.<init>:void(java.lang.String)',
                                                                                                                    'org.springframework.security.oauth2.common.DefaultOAuth2AccessToken.setTokenType:void(java.lang.String)',
                                                                                                                    'org.springframework.security.oauth2.common.OAuth2AccessToken.getValue:java.lang.String()',
                                                                                                                    'org.springframework.security.oauth2.common.exceptions.InvalidTokenException.<init>:void(java.lang.String)',
                                                                                                                    'org.springframework.security.oauth2.provider.OAuth2Authentication.<init>:void(org.springframework.security.oauth2.provider.OAuth2Request,org.springframework.security.core.Authentication)',
                                                                                                                    'org.springframework.security.oauth2.provider.OAuth2Request',
                                                                                                                    'restTemplate',
                                                                                                                    'tokenType',
                                                                                                                    'userInfoEndpointUrl']
                       }
    methods = java_usages_1.methods_to_endpoints(methods)
    assert methods
    java_usages_1.target_line_nums = java_usages_1._identify_target_line_nums(methods)
    file_endpoint_map = java_usages_1.create_file_to_method_dict(methods)
    java_usages_1.file_endpoint_map = sort_openapi_result(file_endpoint_map)
    assert java_usages_1.file_endpoint_map

    methods = java_usages_1._process_calls(methods)
    assert methods
    endpoints = java_usages_1.populate_endpoints(methods)
    assert endpoints


def test_js(js_usages_1):
    methods = js_usages_1._process_methods()
    assert list(methods.keys()) == ['app.ts',
 'data/datacache.ts',
 'data/datacreator.ts',
 'data/mongodb.ts',
 'data/static/codefixes/accessLogDisclosureChallenge_1_correct.ts',
 'data/static/codefixes/accessLogDisclosureChallenge_2.ts',
 'data/static/codefixes/accessLogDisclosureChallenge_3.ts',
 'data/static/codefixes/accessLogDisclosureChallenge_4.ts',
 'data/static/codefixes/adminSectionChallenge_1_correct.ts',
 'data/static/codefixes/adminSectionChallenge_2.ts',
 'data/static/codefixes/adminSectionChallenge_3.ts',
 'data/static/codefixes/adminSectionChallenge_4.ts',
 'data/static/codefixes/changeProductChallenge_1.ts',
 'data/static/codefixes/changeProductChallenge_2.ts',
 'data/static/codefixes/changeProductChallenge_3_correct.ts',
 'data/static/codefixes/changeProductChallenge_4.ts',
 'data/static/codefixes/dbSchemaChallenge_1.ts',
 'data/static/codefixes/dbSchemaChallenge_2_correct.ts',
 'data/static/codefixes/dbSchemaChallenge_3.ts',
 'data/static/codefixes/directoryListingChallenge_1_correct.ts',
 'data/static/codefixes/directoryListingChallenge_2.ts',
 'data/static/codefixes/directoryListingChallenge_3.ts',
 'data/static/codefixes/directoryListingChallenge_4.ts',
 'data/static/codefixes/exposedMetricsChallenge_1.ts',
 'data/static/codefixes/exposedMetricsChallenge_2.ts',
 'data/static/codefixes/exposedMetricsChallenge_3_correct.ts',
 'data/static/codefixes/localXssChallenge_1.ts',
 'data/static/codefixes/localXssChallenge_2_correct.ts',
 'data/static/codefixes/localXssChallenge_3.ts',
 'data/static/codefixes/localXssChallenge_4.ts',
 'data/static/codefixes/noSqlReviewsChallenge_3_correct.ts',
 'data/static/codefixes/redirectChallenge_1.ts',
 'data/static/codefixes/redirectChallenge_3.ts',
 'data/static/codefixes/restfulXssChallenge_1_correct.ts',
 'data/static/codefixes/restfulXssChallenge_2.ts',
 'data/static/codefixes/restfulXssChallenge_3.ts',
 'data/static/codefixes/restfulXssChallenge_4.ts',
 'data/static/codefixes/scoreBoardChallenge_1_correct.ts',
 'data/static/codefixes/scoreBoardChallenge_2.ts',
 'data/static/codefixes/scoreBoardChallenge_3.ts',
 'data/static/codefixes/unionSqlInjectionChallenge_1.ts',
 'data/static/codefixes/unionSqlInjectionChallenge_2_correct.ts',
 'data/static/codefixes/unionSqlInjectionChallenge_3.ts',
 'data/static/codefixes/web3SandboxChallenge_1_correct.ts',
 'data/static/codefixes/web3SandboxChallenge_2.ts',
 'data/static/codefixes/web3SandboxChallenge_3.ts',
 'data/static/codefixes/xssBonusChallenge_1_correct.ts',
 'data/static/codefixes/xssBonusChallenge_2.ts',
 'data/static/codefixes/xssBonusChallenge_3.ts',
 'data/static/codefixes/xssBonusChallenge_4.ts',
 'data/types.ts',
 'frontend/src/app/Models/challenge.model.ts',
 'frontend/src/app/Services/address.service.ts',
 'frontend/src/app/Services/administration.service.ts',
 'frontend/src/app/Services/basket.service.ts',
 'frontend/src/app/Services/captcha.service.ts',
 'frontend/src/app/Services/challenge.service.ts',
 'frontend/src/app/Services/chatbot.service.ts',
 'frontend/src/app/Services/code-fixes.service.ts',
 'frontend/src/app/Services/code-snippet.service.ts',
 'frontend/src/app/Services/complaint.service.ts',
 'frontend/src/app/Services/configuration.service.ts',
 'frontend/src/app/Services/country-mapping.service.ts',
 'frontend/src/app/Services/data-subject.service.ts',
 'frontend/src/app/Services/delivery.service.ts',
 'frontend/src/app/Services/feature-flag.service.ts',
 'frontend/src/app/Services/feedback.service.ts',
 'frontend/src/app/Services/form-submit.service.ts',
 'frontend/src/app/Services/image-captcha.service.ts',
 'frontend/src/app/Services/keys.service.ts',
 'frontend/src/app/Services/languages.service.ts',
 'frontend/src/app/Services/local-backup.service.ts',
 'frontend/src/app/Services/order-history.service.ts',
 'frontend/src/app/Services/payment.service.ts',
 'frontend/src/app/Services/photo-wall.service.ts',
 'frontend/src/app/Services/product-review.service.ts',
 'frontend/src/app/Services/product.service.ts',
 'frontend/src/app/Services/quantity.service.ts',
 'frontend/src/app/Services/recycle.service.ts',
 'frontend/src/app/Services/request.interceptor.ts',
 'frontend/src/app/Services/security-answer.service.ts',
 'frontend/src/app/Services/security-question.service.ts',
 'frontend/src/app/Services/snack-bar-helper.service.ts',
 'frontend/src/app/Services/socket-io.service.ts',
 'frontend/src/app/Services/track-order.service.ts',
 'frontend/src/app/Services/two-factor-auth-service.ts',
 'frontend/src/app/Services/user.service.ts',
 'frontend/src/app/Services/vuln-lines.service.ts',
 'frontend/src/app/Services/wallet.service.ts',
 'frontend/src/app/Services/window-ref.service.ts',
 'frontend/src/app/about/about.component.ts',
 'frontend/src/app/accounting/accounting.component.ts',
 'frontend/src/app/address-create/address-create.component.ts',
 'frontend/src/app/address-select/address-select.component.ts',
 'frontend/src/app/address/address.component.ts',
 'frontend/src/app/administration/administration.component.ts',
 'frontend/src/app/app.component.ts',
 'frontend/src/app/app.guard.ts',
 'frontend/src/app/app.module.ts',
 'frontend/src/app/app.routing.ts',
 'frontend/src/app/basket/basket.component.ts',
 'frontend/src/app/challenge-solved-notification/challenge-solved-notification.component.ts',
 'frontend/src/app/challenge-status-badge/challenge-status-badge.component.ts',
 'frontend/src/app/change-password/change-password.component.ts',
 'frontend/src/app/chatbot/chatbot.component.ts',
 'frontend/src/app/code-area/code-area.component.ts',
 'frontend/src/app/code-fixes/code-fixes.component.ts',
 'frontend/src/app/code-snippet/code-snippet.component.ts',
 'frontend/src/app/complaint/complaint.component.ts',
 'frontend/src/app/contact/contact.component.ts',
 'frontend/src/app/data-export/data-export.component.ts',
 'frontend/src/app/delivery-method/delivery-method.component.ts',
 'frontend/src/app/deluxe-user/deluxe-user.component.ts',
 'frontend/src/app/error-page/error-page.component.ts',
 'frontend/src/app/faucet/faucet.component.ts',
 'frontend/src/app/faucet/faucet.module.ts',
 'frontend/src/app/feedback-details/feedback-details.component.ts',
 'frontend/src/app/forgot-password/forgot-password.component.ts',
 'frontend/src/app/last-login-ip/last-login-ip.component.ts',
 'frontend/src/app/login/login.component.ts',
 'frontend/src/app/navbar/navbar.component.ts',
 'frontend/src/app/nft-unlock/nft-unlock.component.ts',
 'frontend/src/app/oauth/oauth.component.ts',
 'frontend/src/app/order-completion/order-completion.component.ts',
 'frontend/src/app/order-history/order-history.component.ts',
 'frontend/src/app/order-summary/order-summary.component.ts',
 'frontend/src/app/payment-method/payment-method.component.ts',
 'frontend/src/app/payment/payment.component.ts',
 'frontend/src/app/photo-wall/mime-type.validator.ts',
 'frontend/src/app/photo-wall/photo-wall.component.ts',
 'frontend/src/app/privacy-policy/privacy-policy.component.ts',
 'frontend/src/app/privacy-security/privacy-security.component.ts',
 'frontend/src/app/product-details/product-details.component.ts',
 'frontend/src/app/product-review-edit/product-review-edit.component.ts',
 'frontend/src/app/purchase-basket/purchase-basket.component.ts',
 'frontend/src/app/qr-code/qr-code.component.ts',
 'frontend/src/app/recycle/recycle.component.ts',
 'frontend/src/app/register/register.component.ts',
 'frontend/src/app/saved-address/saved-address.component.ts',
 'frontend/src/app/saved-payment-methods/saved-payment-methods.component.ts',
 'frontend/src/app/score-board-legacy/score-board-legacy.component.ts',
 'frontend/src/app/score-board/components/challenge-card/challenge-card.component.ts',
 'frontend/src/app/score-board/components/challenges-unavailable-warning/challenges-unavailable-warning.component.ts',
 'frontend/src/app/score-board/components/coding-challenge-progress-score-card/coding-challenge-progress-score-card.component.ts',
 'frontend/src/app/score-board/components/difficulty-overview-score-card/difficulty-overview-score-card.component.ts',
 'frontend/src/app/score-board/components/difficulty-stars/difficulty-stars.component.ts',
 'frontend/src/app/score-board/components/filter-settings/components/category-filter/category-filter.component.ts',
 'frontend/src/app/score-board/components/filter-settings/components/score-board-additional-settings-dialog/score-board-additional-settings-dialog.component.ts',
 'frontend/src/app/score-board/components/filter-settings/filter-settings.component.ts',
 'frontend/src/app/score-board/components/filter-settings/pipes/difficulty-selection-summary.pipe.ts',
 'frontend/src/app/score-board/components/hacking-challenge-progress-score-card/hacking-challenge-progress-score-card.component.ts',
 'frontend/src/app/score-board/components/legacy-notice/legacy-notice.component.ts',
 'frontend/src/app/score-board/components/score-card/score-card.component.ts',
 'frontend/src/app/score-board/components/tutorial-mode-warning/tutorial-mode-warning.component.ts',
 'frontend/src/app/score-board/components/warning-card/warning-card.component.ts',
 'frontend/src/app/score-board/filter-settings/query-params-converters.ts',
 'frontend/src/app/score-board/helpers/challenge-filtering.ts',
 'frontend/src/app/score-board/helpers/challenge-sorting.ts',
 'frontend/src/app/score-board/pipes/challenge-hint.pipe.ts',
 'frontend/src/app/score-board/score-board.component.ts',
 'frontend/src/app/score-board/score-board.module.ts',
 'frontend/src/app/score-board/types/EnrichedChallenge.ts',
 'frontend/src/app/search-result/search-result.component.ts',
 'frontend/src/app/server-started-notification/server-started-notification.component.ts',
 'frontend/src/app/sidenav/sidenav.component.ts',
 'frontend/src/app/token-sale/token-sale.component.ts',
 'frontend/src/app/track-result/track-result.component.ts',
 'frontend/src/app/two-factor-auth-enter/two-factor-auth-enter.component.ts',
 'frontend/src/app/two-factor-auth/two-factor-auth.component.ts',
 'frontend/src/app/user-details/user-details.component.ts',
 'frontend/src/app/wallet-web3/wallet-web3.component.ts',
 'frontend/src/app/wallet-web3/wallet-web3.module.ts',
 'frontend/src/app/wallet/wallet.component.ts',
 'frontend/src/app/web3-sandbox/web3-sandbox.component.ts',
 'frontend/src/app/web3-sandbox/web3-sandbox.module.ts',
 'frontend/src/app/welcome-banner/welcome-banner.component.ts',
 'frontend/src/app/welcome/welcome.component.ts',
 'frontend/src/assets/private/EffectComposer.js',
 'frontend/src/assets/private/MaskPass.js',
 'frontend/src/assets/private/OrbitControls.js',
 'frontend/src/confetti/index.ts',
 'frontend/src/hacking-instructor/challenges/bonusPayload.ts',
 'frontend/src/hacking-instructor/challenges/codingChallenges.ts',
 'frontend/src/hacking-instructor/challenges/domXss.ts',
 'frontend/src/hacking-instructor/challenges/forgedFeedback.ts',
 'frontend/src/hacking-instructor/challenges/loginBender.ts',
 'frontend/src/hacking-instructor/challenges/loginJim.ts',
 'frontend/src/hacking-instructor/challenges/passwordStrength.ts',
 'frontend/src/hacking-instructor/challenges/privacyPolicy.ts',
 'frontend/src/hacking-instructor/challenges/scoreBoard.ts',
 'frontend/src/hacking-instructor/challenges/viewBasket.ts',
 'frontend/src/hacking-instructor/helpers/helpers.ts',
 'frontend/src/hacking-instructor/index.ts',
 'frontend/src/hacking-instructor/tutorialUnavailable.ts',
 'frontend/src/main.ts',
 'frontend/src/polyfills.ts',
 'lib/accuracy.ts',
 'lib/antiCheat.ts',
 'lib/botUtils.ts',
 'lib/challengeUtils.ts',
 'lib/codingChallenges.ts',
 'lib/insecurity.ts',
 'lib/is-docker.ts',
 'lib/is-heroku.ts',
 'lib/is-windows.ts',
 'lib/logger.ts',
 'lib/noUpdate.ts',
 'lib/startup/cleanupFtpFolder.ts',
 'lib/startup/customizeApplication.ts',
 'lib/startup/customizeEasterEgg.ts',
 'lib/startup/registerWebsocketEvents.ts',
 'lib/startup/restoreOverwrittenFilesWithOriginals.ts',
 'lib/startup/validateChatBot.ts',
 'lib/startup/validateDependencies.ts',
 'lib/startup/validatePreconditions.ts',
 'lib/utils.ts',
 'lib/webhook.ts',
 'models/address.ts',
 'models/basket.ts',
 'models/basketitem.ts',
 'models/captcha.ts',
 'models/card.ts',
 'models/challenge.ts',
 'models/complaint.ts',
 'models/delivery.ts',
 'models/feedback.ts',
 'models/imageCaptcha.ts',
 'models/index.ts',
 'models/memory.ts',
 'models/privacyRequests.ts',
 'models/product.ts',
 'models/quantity.ts',
 'models/recycle.ts',
 'models/relations.ts',
 'models/securityAnswer.ts',
 'models/securityQuestion.ts',
 'models/user.ts',
 'models/wallet.ts',
 'routes/2fa.ts',
 'routes/address.ts',
 'routes/angular.ts',
 'routes/appConfiguration.ts',
 'routes/appVersion.ts',
 'routes/authenticatedUsers.ts',
 'routes/b2bOrder.ts',
 'routes/basket.ts',
 'routes/basketItems.ts',
 'routes/captcha.ts',
 'routes/changePassword.ts',
 'routes/chatbot.ts',
 'routes/checkKeys.ts',
 'routes/continueCode.ts',
 'routes/countryMapping.ts',
 'routes/coupon.ts',
 'routes/createProductReviews.ts',
 'routes/currentUser.ts',
 'routes/dataErasure.ts',
 'routes/dataExport.ts',
 'routes/delivery.ts',
 'routes/deluxe.ts',
 'routes/easterEgg.ts',
 'routes/fileServer.ts',
 'routes/fileUpload.ts',
 'routes/imageCaptcha.ts',
 'routes/keyServer.ts',
 'routes/languages.ts',
 'routes/likeProductReviews.ts',
 'routes/logfileServer.ts',
 'routes/login.ts',
 'routes/memory.ts',
 'routes/metrics.ts',
 'routes/nftMint.ts',
 'routes/order.ts',
 'routes/orderHistory.ts',
 'routes/payment.ts',
 'routes/premiumReward.ts',
 'routes/privacyPolicyProof.ts',
 'routes/profileImageFileUpload.ts',
 'routes/profileImageUrlUpload.ts',
 'routes/quarantineServer.ts',
 'routes/recycles.ts',
 'routes/redirect.ts',
 'routes/repeatNotification.ts',
 'routes/resetPassword.ts',
 'routes/restoreProgress.ts',
 'routes/saveLoginIp.ts',
 'routes/search.ts',
 'routes/securityQuestion.ts',
 'routes/showProductReviews.ts',
 'routes/trackOrder.ts',
 'routes/updateProductReviews.ts',
 'routes/updateUserProfile.ts',
 'routes/userProfile.ts',
 'routes/verify.ts',
 'routes/videoHandler.ts',
 'routes/vulnCodeFixes.ts',
 'routes/vulnCodeSnippet.ts',
 'routes/wallet.ts',
 'routes/web3Wallet.ts',
 'rsn/rsn-update.ts',
 'rsn/rsn-verbose.ts',
 'rsn/rsn.ts',
 'rsn/rsnUtil.ts',
 'server.ts',
 'data/static/codefixes/forgedReviewChallenge_1.ts',
 'data/static/codefixes/forgedReviewChallenge_2_correct.ts',
 'data/static/codefixes/forgedReviewChallenge_3.ts',
 'data/static/codefixes/noSqlReviewsChallenge_1.ts',
 'data/static/codefixes/noSqlReviewsChallenge_2.ts',
 'data/static/codefixes/redirectChallenge_2.ts',
 'data/static/codefixes/redirectChallenge_4_correct.ts',
 'data/static/codefixes/redirectCryptoCurrencyChallenge_1.ts',
 'data/static/codefixes/redirectCryptoCurrencyChallenge_2.ts',
 'data/static/codefixes/redirectCryptoCurrencyChallenge_3_correct.ts',
 'data/static/codefixes/redirectCryptoCurrencyChallenge_4.ts',
 'frontend/src/assets/private/RenderPass.js',
 'frontend/src/assets/private/ShaderPass.js',
 'data/static/codefixes/resetPasswordMortyChallenge_1.ts',
 'data/static/codefixes/resetPasswordMortyChallenge_2.ts',
 'data/static/codefixes/resetPasswordMortyChallenge_3.ts',
 'frontend/src/app/Models/backup.model.ts',
 'frontend/src/app/Models/deliveryMethod.model.ts',
 'frontend/src/app/Models/product.model.ts',
 'frontend/src/app/Models/review.model.ts',
 'frontend/src/app/Models/securityQuestion.model.ts',
 'frontend/src/app/score-board/filter-settings/FilterSetting.ts']
    methods = js_usages_1.methods_to_endpoints(methods)
    assert methods

    js_usages_1.target_line_nums = js_usages_1._identify_target_line_nums(methods)
    js_usages_1.file_endpoint_map = js_usages_1.create_file_to_method_dict(methods)
    file_endpoint_map = sort_openapi_result(js_usages_1.file_endpoint_map)
    assert file_endpoint_map
    assert js_usages_1.target_line_nums == {'frontend/src/app/score-board/score-board.component.ts': {'__whatwg.console:warn': [168],
                                                           'frontend/src/app/score-board/score-board.component.ts::program:ScoreBoardComponent:rewriteLegacyChallengeDirectLink': [83]},
 'routes/dataErasure.ts': {'()': [80]},
 'server.ts': {'()': [694], 'server.ts::program:readyCallback': [702]}}

    methods = js_usages_1._process_calls(methods)
    assert methods

    endpoints = js_usages_1.populate_endpoints(methods)
    endpoints = sort_openapi_result(endpoints)
    assert endpoints


def test_rb(rb_usages_1):
    result = ruby_convert(rb_usages_1.usages)
    assert result
