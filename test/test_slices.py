from atom_tools.lib.slices import UsageSlice


def test_usages_class():
    usages = UsageSlice('data/java-piggymetrics-usages.json', 'java')
    assert usages.language == 'java'
    result = usages.generate_endpoints()
    result.sort()
    assert result == ['/', '/accounts/{accountName}', '/current', '/latest',
                      '/statistics/{accountName}', '/uaa/users',
                      '/{accountName}', '/{name}']

    usages = UsageSlice('data/java-sec-code-usages.json', 'java')
    assert usages.language == 'java'
    result = usages.generate_endpoints()
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
