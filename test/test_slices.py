from pytest import fixture
from atom_tools.lib.slices import UsageSlice


@fixture
def java_usages_1():
    return UsageSlice('test/data/java-piggymetrics-usages.json', 'java')


@fixture
def java_usages_2():
    return UsageSlice('test/data/java-sec-code-usages.json', 'java')


@fixture
def js_usages_1():
    return UsageSlice('test/data/js-juiceshop-usages.json', 'js')


@fixture
def js_usages_2():
    return UsageSlice('test/data/js-nodegoat-usages.json', 'js')


@fixture
def py_usages_1():
    return UsageSlice('test/data/py-depscan-usages.json', 'py')


@fixture
def py_usages_2():
    return UsageSlice('test/data/py-tornado-usages.json', 'py')


def test_usages_class(
        java_usages_1,
        java_usages_2,
):
    usages = UsageSlice('test/data/java-piggymetrics-usages.json', 'java')
    assert usages.language == 'java'

    usages = UsageSlice('test/data/java-sec-code-usages.json', 'java')
    assert usages.language == 'java'


def test_generate_endpoints(
        java_usages_1,
        java_usages_2,
        js_usages_1,
        js_usages_2,
        py_usages_1,
        py_usages_2
):
    result = java_usages_1.generate_endpoints()
    result.sort()
    assert result == ['/', '/accounts/{accountName}', '/current', '/latest',
                      '/statistics/{accountName}', '/uaa/users',
                      '/{accountName}', '/{name}']

    result = java_usages_2.generate_endpoints()
    result.sort()
    assert result == ['/', '/Digester/sec', '/Digester/vuln',
                      '/DocumentBuilder/Sec', '/DocumentBuilder/vuln',
                      '/DocumentBuilder/xinclude/sec',
                      '/DocumentBuilder/xinclude/vuln', '/DocumentHelper/vuln',
                      '/HttpSyncClients/vuln', '/HttpURLConnection/sec',
                      '/HttpURLConnection/vuln', '/IOUtils/sec', '/ImageIO/sec',
                      '/Jsoup/sec', '/ProcessBuilder', '/SAXBuilder/sec',
                      '/SAXBuilder/vuln', '/SAXParser/sec', '/SAXParser/vuln',
                      '/SAXReader/sec', '/SAXReader/vuln', '/XMLReader/sec',
                      '/XMLReader/vuln', '/aa', '/any', '/appInfo',
                      '/application/javascript', '/classloader', '/codeinject',
                      '/codeinject/host', '/codeinject/sec',
                      '/commonsHttpClient/sec', '/createToken', '/deserialize',
                      '/dnsrebind/vuln', '/exclued/vuln', '/fastjsonp/getToken',
                      '/forward', '/getName', '/getToken', '/httpclient/sec',
                      '/hutool/vuln', '/index', '/jdbc/ps/vuln', '/jdbc/sec',
                      '/jdbc/vuln', '/jscmd', '/log4j', '/login', '/logout',
                      '/mybatis/orderby/sec04', '/mybatis/orderby/vuln03',
                      '/mybatis/sec01', '/mybatis/sec02', '/mybatis/sec03',
                      '/mybatis/vuln01', '/mybatis/vuln02', '/noproxy',
                      '/object2jsonp', '/okhttp/sec', '/openStream',
                      '/path_traversal/sec', '/path_traversal/vul', '/pic',
                      '/post', '/postgresql', '/proxy', '/readxlsx',
                      '/redirect', '/reflect', '/rememberMe/security',
                      '/rememberMe/vuln', '/request/sec', '/restTemplate/vuln1',
                      '/restTemplate/vuln2', '/runtime/exec', '/safe',
                      '/safecode', '/sec', '/sec/array_indexOf',
                      '/sec/checkOrigin', '/sec/checkReferer',
                      '/sec/corsFilter', '/sec/crossOrigin', '/sec/httpCors',
                      '/sec/originFilter', '/sec/webMvcConfigurer', '/sec/yarm',
                      '/sendRedirect', '/sendRedirect/sec', '/setHeader',
                      '/spel/vuln', '/status', '/stored/show', '/stored/store',
                      '/upload', '/upload/picture', '/urlConnection/sec',
                      '/urlConnection/vuln', '/velocity', '/vuln/contains',
                      '/vuln/crossOrigin', '/vuln/emptyReferer',
                      '/vuln/endsWith', '/vuln/mappingJackson2JsonView',
                      '/vuln/origin', '/vuln/referer', '/vuln/regex',
                      '/vuln/setHeader', '/vuln/url_bypass', '/vuln/yarm',
                      '/vuln01', '/vuln02', '/vuln03', '/vuln04', '/vuln05',
                      '/vuln06', '/websocket/cmd', '/websocket/proxy',
                      '/xmlReader/sec', '/xmlReader/vuln', '/xmlbeam/vuln',
                      '/xstream']

    result = js_usages_1.generate_endpoints()
    result.sort()
    assert result == ['/', '/*/*', '/.well-known/security.txt',
                      '/Invalidemail/passwordcannotbeempty', '/api-docs',
                      '/api/Addresss', '/api/Addresss/:id', '/api/BasketItems',
                      '/api/BasketItems/:id', '/api/Cards', '/api/Cards/:id',
                      '/api/Challenges', '/api/Challenges/:id',
                      '/api/Complaints', '/api/Complaints/:id',
                      '/api/Deliverys', '/api/Deliverys/:id', '/api/Feedbacks',
                      '/api/Feedbacks/:id', '/api/PrivacyRequests',
                      '/api/PrivacyRequests/:id', '/api/Products',
                      '/api/Products/:id', '/api/Quantitys',
                      '/api/Quantitys/:id', '/api/Recycles',
                      '/api/Recycles/:id', '/api/SecurityAnswers',
                      '/api/SecurityAnswers/:id', '/api/SecurityQuestions',
                      '/api/SecurityQuestions/:id', '/api/Users',
                      '/api/Users/:id', '/assets/i18n',
                      '/assets/public/images/padding',
                      '/assets/public/images/products',
                      '/assets/public/images/uploads', '/b2b/v2',
                      '/b2b/v2/orders', '/dataerasure', '/encryptionkeys',
                      '/encryptionkeys/:file', '/file-upload',
                      '/frontend/dist/frontend', '/ftp',
                      '/ftp(?!/quarantine)/:file', '/ftp/quarantine/:file',
                      '/metrics', '/profile', '/profile/image/file',
                      '/profile/image/url', '/promotion', '/redirect',
                      '/rest/2fa/disable', '/rest/2fa/setup',
                      '/rest/2fa/status', '/rest/2fa/verify',
                      '/rest/admin/application-configuration',
                      '/rest/admin/application-version', '/rest/basket',
                      '/rest/basket/:id', '/rest/basket/:id/checkout',
                      '/rest/basket/:id/coupon/:coupon',
                      '/rest/basket/:id/order', '/rest/captcha',
                      '/rest/chatbot/respond', '/rest/chatbot/status',
                      '/rest/continue-code', '/rest/continue-code-findIt',
                      '/rest/continue-code-findIt/apply/:continueCode',
                      '/rest/continue-code-fixIt',
                      '/rest/continue-code-fixIt/apply/:continueCode',
                      '/rest/continue-code/apply/:continueCode',
                      '/rest/country-mapping', '/rest/deluxe-membership',
                      '/rest/image-captcha', '/rest/languages',
                      '/rest/memories', '/rest/order-history',
                      '/rest/order-history/:id/delivery-status',
                      '/rest/order-history/orders',
                      '/rest/products/:id/reviews', '/rest/products/reviews',
                      '/rest/products/search', '/rest/repeat-notification',
                      '/rest/saveLoginIp', '/rest/track-order/:id',
                      '/rest/user/authentication-details',
                      '/rest/user/change-password', '/rest/user/data-export',
                      '/rest/user/login', '/rest/user/reset-password',
                      '/rest/user/security-question', '/rest/user/whoami',
                      '/rest/wallet/balance', '/rest/web3/nftMintListen',
                      '/rest/web3/nftUnlocked', '/rest/web3/submitKey',
                      '/rest/web3/walletExploitAddress',
                      '/rest/web3/walletNFTVerify', '/security.txt',
                      '/snippets', '/snippets/:challenge', '/snippets/fixes',
                      '/snippets/fixes/:key', '/snippets/verdict',
                      '/solve/challenges/server-side', '/support/logs',
                      '/support/logs/:file',
                      '/the/devs/are/so/funny/they/hid/an/easter/egg/within'
                      '/the/easter/egg',
                      '/this/page/is/hidden/behind/an/incredibly/high/paywall'
                      '/that/could/only/be/unlocked/by/sending/1btc/to/us',
                      '/video',
                      '/we/may/also/instruct/you/to/refuse/all/reasonably'
                      '/necessary/responsibility']

    result = js_usages_2.generate_endpoints()
    result.sort()
    assert result == ['/', '/allocations/:userId', '/app/assets/favicon.ico',
                      '/benefits', '/contributions', '/dashboard', '/learn',
                      '/login', '/logout', '/memos', '/profile', '/research',
                      '/signup', '/tutorial', '/tutorial/a1']

    result = py_usages_1.generate_endpoints()
    result.sort()
    assert result == ['/scan']

    result = py_usages_2.generate_endpoints()
    result.sort()
    assert result == ['/auth/google', '/logout']


def test_import_slices(js_usages_1):
    # Test nonexistent file
    assert UsageSlice('test/data/js-tornado-usages.json', 'js').usages == {}

    # Test invalid JSON file
    assert UsageSlice('test/data/invalid.json', 'js').usages == {}

    # Valid JSON but reachables not usages
    assert UsageSlice('test/data/js-juiceshop-reachables.json', 'js').usages == {}
