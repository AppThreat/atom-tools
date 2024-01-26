import pytest

from atom_tools.lib.converter import OpenAPI


@pytest.fixture
def java_usages_1():
    return OpenAPI('openapi3.1.0', 'java',
                   'test/data/java-piggymetrics-usages.json')


@pytest.fixture
def java_usages_2():
    return OpenAPI('openapi3.0.1', 'java',
                   'test/data/java-sec-code-usages.json')


@pytest.fixture
def js_usages_1():
    return OpenAPI('openapi3.0.1', 'javascript',
                   'test/data/js-juiceshop-usages.json')


@pytest.fixture
def js_usages_2():
    return OpenAPI('openapi3.0.1', 'js', 'test/data/js-nodegoat-usages.json')


@pytest.fixture
def py_usages_1():
    return OpenAPI('openapi3.0.1', 'python', 'test/data/py-depscan-usages.json')


@pytest.fixture
def py_usages_2():
    return OpenAPI('openapi3.0.1', 'py', 'test/data/py-tornado-usages.json')


def test_populate_endpoints(java_usages_1, java_usages_2, js_usages_1,
                            js_usages_2, py_usages_1, py_usages_2):
    methods = java_usages_1.process_methods()
    methods = java_usages_1.methods_to_endpoints(methods)
    methods = java_usages_1.process_calls(methods)
    assert java_usages_1.populate_endpoints(methods) == {
        '/': {'post': {'parameters': [], 'responses': {}}},
        '/accounts/{accountName}': {'get': {'parameters': [
            {'in': 'path', 'name': 'accountName', 'required': True}],
            'responses': {}}},
        '/current': {'get': {'parameters': [], 'responses': {}},
                     'put': {'parameters': [], 'responses': {}}},
        '/latest': {'get': {'parameters': [], 'responses': {}}},
        '/statistics/{accountName}': {'put': {'parameters': [
            {'in': 'path', 'name': 'accountName', 'required': True}],
            'responses': {}}},
        '/uaa/users': {'post': {'parameters': [], 'responses': {}}},
        '/{accountName}': {'get': {'parameters': [
            {'in': 'path', 'name': 'accountName', 'required': True}],
            'responses': {}}, 'put': {'parameters': [
            {'in': 'path', 'name': 'accountName', 'required': True}],
            'responses': {}}}, '/{name}': {'get': {
            'parameters': [{'in': 'path', 'name': 'name', 'required': True}],
            'responses': {}}}}

    methods = java_usages_2.process_methods()
    methods = java_usages_2.methods_to_endpoints(methods)
    methods = java_usages_2.process_calls(methods)
    assert java_usages_2.populate_endpoints(methods) == {
        '/': {'get': {'parameters': [], 'responses': {}}},
        '/Digester/sec': {'post': {'parameters': [], 'responses': {}}},
        '/Digester/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/DocumentBuilder/Sec': {'post': {'parameters': [], 'responses': {}}},
        '/DocumentBuilder/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/DocumentBuilder/xinclude/sec': {
            'post': {'parameters': [], 'responses': {}}},
        '/DocumentBuilder/xinclude/vuln': {
            'post': {'parameters': [], 'responses': {}}},
        '/DocumentHelper/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/HttpSyncClients/vuln': {'get': {'parameters': [], 'responses': {}}},
        '/HttpURLConnection/sec': {'get': {'parameters': [], 'responses': {}}},
        '/HttpURLConnection/vuln': {'get': {'parameters': [], 'responses': {}}},
        '/IOUtils/sec': {'get': {'parameters': [], 'responses': {}}},
        '/ImageIO/sec': {'get': {'parameters': [], 'responses': {}}},
        '/Jsoup/sec': {'get': {'parameters': [], 'responses': {}}},
        '/ProcessBuilder': {'get': {'parameters': [], 'responses': {}}},
        '/SAXBuilder/sec': {'post': {'parameters': [], 'responses': {}}},
        '/SAXBuilder/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/SAXParser/sec': {'post': {'parameters': [], 'responses': {}}},
        '/SAXParser/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/SAXReader/sec': {'post': {'parameters': [], 'responses': {}}},
        '/SAXReader/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/XMLReader/sec': {'post': {'parameters': [], 'responses': {}}},
        '/XMLReader/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/any': {'get': {'parameters': [], 'responses': {}}},
        '/application/javascript': {'get': {'parameters': [], 'responses': {}}},
        '/codeinject': {'get': {'parameters': [], 'responses': {}}},
        '/codeinject/host': {'get': {'parameters': [], 'responses': {}}},
        '/codeinject/sec': {'get': {'parameters': [], 'responses': {}}},
        '/commonsHttpClient/sec': {'get': {'parameters': [], 'responses': {}}},
        '/createToken': {'get': {'parameters': [], 'responses': {}}},
        '/deserialize': {'post': {'parameters': [], 'responses': {}}},
        '/dnsrebind/vuln': {'get': {'parameters': [], 'responses': {}}},
        '/exclued/vuln': {'get': {'parameters': [], 'responses': {}}},
        '/fastjsonp/getToken': {'get': {'parameters': [], 'responses': {}}},
        '/getName': {'get': {'parameters': [], 'responses': {}}},
        '/getToken': {'get': {'parameters': [], 'responses': {}}},
        '/httpclient/sec': {'get': {'parameters': [], 'responses': {}}},
        '/hutool/vuln': {'get': {'parameters': [], 'responses': {}}},
        '/jscmd': {'get': {'parameters': [], 'responses': {}}},
        '/log4j': {'get': {'parameters': [], 'responses': {}}},
        '/logout': {'get': {'parameters': [], 'responses': {}}},
        '/mybatis/orderby/sec04': {'get': {'parameters': [], 'responses': {}}},
        '/mybatis/orderby/vuln03': {'get': {'parameters': [], 'responses': {}}},
        '/mybatis/sec01': {'get': {'parameters': [], 'responses': {}}},
        '/mybatis/sec02': {'get': {'parameters': [], 'responses': {}}},
        '/mybatis/sec03': {'get': {'parameters': [], 'responses': {}}},
        '/mybatis/vuln01': {'get': {'parameters': [], 'responses': {}}},
        '/mybatis/vuln02': {'get': {'parameters': [], 'responses': {}}},
        '/okhttp/sec': {'get': {'parameters': [], 'responses': {}}},
        '/openStream': {'get': {'parameters': [], 'responses': {}}},
        '/path_traversal/sec': {'get': {'parameters': [], 'responses': {}}},
        '/path_traversal/vul': {'get': {'parameters': [], 'responses': {}}},
        '/pic': {'get': {'parameters': [], 'responses': {}}},
        '/post': {'post': {'parameters': [], 'responses': {}}},
        '/postgresql': {'post': {'parameters': [], 'responses': {}}},
        '/readxlsx': {'post': {'parameters': [], 'responses': {}}},
        '/redirect': {'get': {'parameters': [], 'responses': {}}},
        '/request/sec': {'get': {'parameters': [], 'responses': {}}},
        '/restTemplate/vuln1': {'get': {'parameters': [], 'responses': {}}},
        '/restTemplate/vuln2': {'get': {'parameters': [], 'responses': {}}},
        '/runtime/exec': {'get': {'parameters': [], 'responses': {}}},
        '/sec': {'get': {'parameters': [], 'responses': {}}},
        '/sec/array_indexOf': {'get': {'parameters': [], 'responses': {}}},
        '/sec/checkOrigin': {'get': {'parameters': [], 'responses': {}}},
        '/sec/crossOrigin': {'get': {'parameters': [], 'responses': {}}},
        '/sec/httpCors': {'get': {'parameters': [], 'responses': {}}},
        '/sec/originFilter': {'get': {'parameters': [], 'responses': {}}},
        '/sec/webMvcConfigurer': {'get': {'parameters': [], 'responses': {}}},
        '/sec/yarm': {'get': {'parameters': [], 'responses': {}}},
        '/setHeader': {'head': {'parameters': [], 'responses': {}}},
        '/spel/vuln': {'get': {'parameters': [], 'responses': {}}},
        '/status': {'get': {'parameters': [], 'responses': {}}},
        '/upload': {'get': {'parameters': [], 'responses': {}},
                    'post': {'parameters': [], 'responses': {}}},
        '/upload/picture': {'post': {'parameters': [], 'responses': {}}},
        '/urlConnection/sec': {'get': {'parameters': [], 'responses': {}}},
        '/urlConnection/vuln': {'get': {'parameters': [], 'responses': {}},
                                'post': {'parameters': [], 'responses': {}}},
        '/velocity': {'get': {'parameters': [], 'responses': {}}},
        '/vuln/contains': {'get': {'parameters': [], 'responses': {}}},
        '/vuln/endsWith': {'get': {'parameters': [], 'responses': {}}},
        '/vuln/origin': {'get': {'parameters': [], 'responses': {}}},
        '/vuln/regex': {'get': {'parameters': [], 'responses': {}}},
        '/vuln/setHeader': {'get': {'parameters': [], 'responses': {}},
                            'head': {'parameters': [], 'responses': {}}},
        '/vuln/url_bypass': {'get': {'parameters': [], 'responses': {}}},
        '/vuln/yarm': {'get': {'parameters': [], 'responses': {}}},
        '/vuln01': {'get': {'parameters': [], 'responses': {}}},
        '/vuln02': {'get': {'parameters': [], 'responses': {}}},
        '/vuln03': {'get': {'parameters': [], 'responses': {}}},
        '/vuln04': {'get': {'parameters': [], 'responses': {}}},
        '/vuln05': {'get': {'parameters': [], 'responses': {}}},
        '/vuln06': {'get': {'parameters': [], 'responses': {}}},
        '/xmlReader/sec': {'post': {'parameters': [], 'responses': {}}},
        '/xmlReader/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/xmlbeam/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/xstream': {'post': {'parameters': [], 'responses': {}}}}

    methods = js_usages_1.process_calls({'routes\\dataErasure.ts::program': {
        "router.post('/',async(req:Request<Record<string,unknown>,"
        "Record<string,unknown>,DataErasureRequestParams>,res:Response,"
        "next:NextFunction):Promise<void>=>{"
        "\rconstloggedInUser=insecurity.authenticatedUsers.get("
        "req.cookies.token)\rif(!loggedInUser){\rnext(newError("
        "'Blockedillegalactivityby'+req.socket.remoteAddress))\rreturn\r}\r"
        "\rtry{\rawaitPrivacyRequestModel.create({"
        "\rUserId:loggedInUser.data.id,"
        "\rdeletionRequested:true\r})\r\rres.clearCookie('token')\rif("
        "req.body.layout){\rconstfilePath:string=path.resolve("
        "req.body.layout).toLowerCase()\rconstisForbiddenFile:boolean=("
        "filePath.includes('ftp')||filePath.includes("
        "'ctf.key')||filePath.includes('encryptionkeys'))\rif("
        "!isForbiddenFile){\rres.render('dataErasureResult',"
        "{\r...req.body\r},(error,html)=>{\rif(!html||error){\rnext(newError("
        "error.message))\r}else{\r...": {
            '/': {}},
        "router.get('/',async(req:Request,res:Response,"
        "next:NextFunction):Promise<void>=>{"
        "\rconstloggedInUser=insecurity.authenticatedUsers.get("
        "req.cookies.token)\rif(!loggedInUser){\rnext(newError("
        "'Blockedillegalactivityby'+req.socket.remoteAddress))\rreturn\r"
        "}\rconstemail=loggedInUser.data.email\r\rtry{"
        "\rconstanswer=awaitSecurityAnswerModel.findOne({\rinclude:[{"
        "\rmodel:UserModel,\rwhere:{email}\r}]\r})\rif(answer==null){"
        "\rthrownewError("
        "'Noanswerfound!')\r}\rconstquestion=awaitSecurityQuestionModel"
        ".findByPk(answer.SecurityQuestionId)\rif(question==null){"
        "\rthrownewError('Noquestionfound!')\r}\r\rres.render("
        "'dataErasureForm',{userEmail:email,"
        "securityQuestion:question.question})\r}catch(error){\rnext("
        "error)\r}\r})": {
            '/': {}}}, 'server.ts::program': {
        "app.use('/assets/public/images/padding',"
        "verify.accessControlChallenges())": {
            '/assets/public/images/padding': {}},
        "app.get('/rest/admin/application-version',appVersion())": {
            '/rest/admin/application-version': {}},
        "app.use('/ftp',serveIndexMiddleware,serveIndex('ftp',{icons:true}))": {
            '/ftp': {}},
        "app.post('/api/SecurityQuestions',security.denyAll())": {
            '/api/SecurityQuestions': {}},
        "app.use(robots({UserAgent:'*',Disallow:'/ftp'}))": {'/ftp': {}},
        "app.delete('/api/Cards/:id',security.appendUserId(),"
        "payment.delPaymentMethodById())": {
            '/api/Cards/{id}': {}},
        "app.get('/rest/image-captcha',imageCaptcha())": {
            '/rest/image-captcha': {}},
        "app.get('/promotion',videoHandler.promotionVideo())": {
            '/promotion': {}},
        "app.get('/snippets/:challenge',vulnCodeSnippet.serveCodeSnippet())": {
            '/snippets/{challenge}': {}},
        "app.put('/rest/continue-code-findIt/apply/:continueCode',"
        "restoreProgress.restoreProgressFindIt())": {
            '/rest/continue-code-findIt/apply/{continueCode}': {}}}})
    result = js_usages_1.populate_endpoints(methods)
    assert list(result.keys()) == ['/', '/rest/admin/application-version',
                                   '/api/SecurityQuestions', '/api/Cards/{id}',
                                   '/rest/image-captcha', '/promotion',
                                   '/snippets/{challenge}',
                                   '/rest/continue-code-findIt/apply/{'
                                   'continueCode}']
    assert list(
        result['/rest/continue-code-findIt/apply/{continueCode}'].keys()) == [
               'put']

    methods = js_usages_2.process_methods()
    methods = js_usages_2.methods_to_endpoints(methods)
    assert methods == {'app\\routes\\index.js::program:index': {
        'app.get("/",sessionHandler.displayWelcomePage)': {'/': {}},
        'app.get("/allocations/:userId",isLoggedIn,'
        'allocationsHandler.displayAllocations)': {
            '/allocations/{userId}': {}},
        'app.get("/benefits",isLoggedIn,benefitsHandler.displayBenefits)': {
            '/benefits': {}},
        'app.get("/contributions",isLoggedIn,'
        'contributionsHandler.displayContributions)': {
            '/contributions': {}},
        'app.get("/dashboard",isLoggedIn,sessionHandler.displayWelcomePage)': {
            '/dashboard': {}},
        'app.get("/learn",isLoggedIn,(req,res)=>{'
        '//Insecurewaytohandleredirectsbytakingredirecturlfromquerystringreturnres.redirect(req.query.url);})': {
            '/learn': {}},
        'app.get("/login",sessionHandler.displayLoginPage)': {'/login': {}},
        'app.get("/logout",sessionHandler.displayLogoutPage)': {'/logout': {}},
        'app.get("/memos",isLoggedIn,memosHandler.displayMemos)': {
            '/memos': {}},
        'app.get("/profile",isLoggedIn,profileHandler.displayProfile)': {
            '/profile': {}},
        'app.get("/research",isLoggedIn,researchHandler.displayResearch)': {
            '/research': {}},
        'app.get("/signup",sessionHandler.displaySignupPage)': {'/signup': {}},
        'app.post("/benefits",isLoggedIn,benefitsHandler.updateBenefits)': {
            '/benefits': {}},
        'app.post("/contributions",isLoggedIn,'
        'contributionsHandler.handleContributionsUpdate)': {
            '/contributions': {}},
        'app.post("/login",sessionHandler.handleLoginRequest)': {'/login': {}},
        'app.post("/memos",isLoggedIn,memosHandler.addMemos)': {'/memos': {}},
        'app.post("/profile",isLoggedIn,profileHandler.handleProfileUpdate)': {
            '/profile': {}},
        'app.post("/signup",sessionHandler.handleSignup)': {'/signup': {}},
        'app.use("/tutorial",tutorialRouter)': {'/tutorial': {}}},
                       'app\\routes\\tutorial.js::program': {
                           'router.get("/",(req,res)=>{'
                           '"usestrict";returnres.render("tutorial/a1",'
                           '{environmentalScripts});})': {
                               '/': {}, '/tutorial/a1': {}}},
                       'server.js::program': {
                           'app.use(favicon('
                           '__dirname+"/app/assets/favicon.ico"))': {
                               '/app/assets/favicon.ico': {}}}}
    methods = js_usages_2.process_calls(methods)
    result = js_usages_2.populate_endpoints(methods)
    assert len(list(result['/login'].keys())) == 2
    result = list(result.keys())
    result.sort()
    assert result == ['/', '/allocations/{userId}', '/benefits',
        '/contributions', '/dashboard', '/learn', '/login', '/logout', '/memos',
        '/profile', '/research', '/signup', '/tutorial/a1']


def test_usages_class(java_usages_1):
    assert java_usages_1.title == 'OpenAPI Specification for data'


def test_convert_usages(java_usages_1, java_usages_2, js_usages_2):
    assert java_usages_1.convert_usages() == {
        '/': {'post': {'parameters': [], 'responses': {}}},
        '/accounts/{accountName}': {'get': {'parameters': [
            {'in': 'path', 'name': 'accountName', 'required': True}],
            'responses': {}}},
        '/current': {'get': {'parameters': [], 'responses': {}},
                     'put': {'parameters': [], 'responses': {}}},
        '/latest': {'get': {'parameters': [], 'responses': {}}},
        '/statistics/{accountName}': {'put': {'parameters': [
            {'in': 'path', 'name': 'accountName', 'required': True}],
            'responses': {}}},
        '/uaa/users': {'post': {'parameters': [], 'responses': {}}},
        '/{accountName}': {'get': {'parameters': [
            {'in': 'path', 'name': 'accountName', 'required': True}],
            'responses': {}}, 'put': {'parameters': [
            {'in': 'path', 'name': 'accountName', 'required': True}],
            'responses': {}}}, '/{name}': {'get': {
            'parameters': [{'in': 'path', 'name': 'name', 'required': True}],
            'responses': {}}}}
    assert java_usages_2.convert_usages() == {
        '/': {'get': {'parameters': [], 'responses': {}}},
        '/Digester/sec': {'post': {'parameters': [], 'responses': {}}},
        '/Digester/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/DocumentBuilder/Sec': {'post': {'parameters': [], 'responses': {}}},
        '/DocumentBuilder/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/DocumentBuilder/xinclude/sec': {
            'post': {'parameters': [], 'responses': {}}},
        '/DocumentBuilder/xinclude/vuln': {
            'post': {'parameters': [], 'responses': {}}},
        '/DocumentHelper/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/HttpSyncClients/vuln': {'get': {'parameters': [], 'responses': {}}},
        '/HttpURLConnection/sec': {'get': {'parameters': [], 'responses': {}}},
        '/HttpURLConnection/vuln': {'get': {'parameters': [], 'responses': {}}},
        '/IOUtils/sec': {'get': {'parameters': [], 'responses': {}}},
        '/ImageIO/sec': {'get': {'parameters': [], 'responses': {}}},
        '/Jsoup/sec': {'get': {'parameters': [], 'responses': {}}},
        '/ProcessBuilder': {'get': {'parameters': [], 'responses': {}}},
        '/SAXBuilder/sec': {'post': {'parameters': [], 'responses': {}}},
        '/SAXBuilder/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/SAXParser/sec': {'post': {'parameters': [], 'responses': {}}},
        '/SAXParser/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/SAXReader/sec': {'post': {'parameters': [], 'responses': {}}},
        '/SAXReader/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/XMLReader/sec': {'post': {'parameters': [], 'responses': {}}},
        '/XMLReader/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/any': {'get': {'parameters': [], 'responses': {}}},
        '/application/javascript': {'get': {'parameters': [], 'responses': {}}},
        '/codeinject': {'get': {'parameters': [], 'responses': {}}},
        '/codeinject/host': {'get': {'parameters': [], 'responses': {}}},
        '/codeinject/sec': {'get': {'parameters': [], 'responses': {}}},
        '/commonsHttpClient/sec': {'get': {'parameters': [], 'responses': {}}},
        '/createToken': {'get': {'parameters': [], 'responses': {}}},
        '/deserialize': {'post': {'parameters': [], 'responses': {}}},
        '/dnsrebind/vuln': {'get': {'parameters': [], 'responses': {}}},
        '/exclued/vuln': {'get': {'parameters': [], 'responses': {}}},
        '/fastjsonp/getToken': {'get': {'parameters': [], 'responses': {}}},
        '/getName': {'get': {'parameters': [], 'responses': {}}},
        '/getToken': {'get': {'parameters': [], 'responses': {}}},
        '/httpclient/sec': {'get': {'parameters': [], 'responses': {}}},
        '/hutool/vuln': {'get': {'parameters': [], 'responses': {}}},
        '/jscmd': {'get': {'parameters': [], 'responses': {}}},
        '/log4j': {'get': {'parameters': [], 'responses': {}}},
        '/logout': {'get': {'parameters': [], 'responses': {}}},
        '/mybatis/orderby/sec04': {'get': {'parameters': [], 'responses': {}}},
        '/mybatis/orderby/vuln03': {'get': {'parameters': [], 'responses': {}}},
        '/mybatis/sec01': {'get': {'parameters': [], 'responses': {}}},
        '/mybatis/sec02': {'get': {'parameters': [], 'responses': {}}},
        '/mybatis/sec03': {'get': {'parameters': [], 'responses': {}}},
        '/mybatis/vuln01': {'get': {'parameters': [], 'responses': {}}},
        '/mybatis/vuln02': {'get': {'parameters': [], 'responses': {}}},
        '/okhttp/sec': {'get': {'parameters': [], 'responses': {}}},
        '/openStream': {'get': {'parameters': [], 'responses': {}}},
        '/path_traversal/sec': {'get': {'parameters': [], 'responses': {}}},
        '/path_traversal/vul': {'get': {'parameters': [], 'responses': {}}},
        '/pic': {'get': {'parameters': [], 'responses': {}}},
        '/post': {'post': {'parameters': [], 'responses': {}}},
        '/postgresql': {'post': {'parameters': [], 'responses': {}}},
        '/readxlsx': {'post': {'parameters': [], 'responses': {}}},
        '/redirect': {'get': {'parameters': [], 'responses': {}}},
        '/request/sec': {'get': {'parameters': [], 'responses': {}}},
        '/restTemplate/vuln1': {'get': {'parameters': [], 'responses': {}}},
        '/restTemplate/vuln2': {'get': {'parameters': [], 'responses': {}}},
        '/runtime/exec': {'get': {'parameters': [], 'responses': {}}},
        '/sec': {'get': {'parameters': [], 'responses': {}}},
        '/sec/array_indexOf': {'get': {'parameters': [], 'responses': {}}},
        '/sec/checkOrigin': {'get': {'parameters': [], 'responses': {}}},
        '/sec/crossOrigin': {'get': {'parameters': [], 'responses': {}}},
        '/sec/httpCors': {'get': {'parameters': [], 'responses': {}}},
        '/sec/originFilter': {'get': {'parameters': [], 'responses': {}}},
        '/sec/webMvcConfigurer': {'get': {'parameters': [], 'responses': {}}},
        '/sec/yarm': {'get': {'parameters': [], 'responses': {}}},
        '/setHeader': {'head': {'parameters': [], 'responses': {}}},
        '/spel/vuln': {'get': {'parameters': [], 'responses': {}}},
        '/status': {'get': {'parameters': [], 'responses': {}}},
        '/upload': {'get': {'parameters': [], 'responses': {}},
                    'post': {'parameters': [], 'responses': {}}},
        '/upload/picture': {'post': {'parameters': [], 'responses': {}}},
        '/urlConnection/sec': {'get': {'parameters': [], 'responses': {}}},
        '/urlConnection/vuln': {'get': {'parameters': [], 'responses': {}},
                                'post': {'parameters': [], 'responses': {}}},
        '/velocity': {'get': {'parameters': [], 'responses': {}}},
        '/vuln/contains': {'get': {'parameters': [], 'responses': {}}},
        '/vuln/endsWith': {'get': {'parameters': [], 'responses': {}}},
        '/vuln/origin': {'get': {'parameters': [], 'responses': {}}},
        '/vuln/regex': {'get': {'parameters': [], 'responses': {}}},
        '/vuln/setHeader': {'get': {'parameters': [], 'responses': {}},
                            'head': {'parameters': [], 'responses': {}}},
        '/vuln/url_bypass': {'get': {'parameters': [], 'responses': {}}},
        '/vuln/yarm': {'get': {'parameters': [], 'responses': {}}},
        '/vuln01': {'get': {'parameters': [], 'responses': {}}},
        '/vuln02': {'get': {'parameters': [], 'responses': {}}},
        '/vuln03': {'get': {'parameters': [], 'responses': {}}},
        '/vuln04': {'get': {'parameters': [], 'responses': {}}},
        '/vuln05': {'get': {'parameters': [], 'responses': {}}},
        '/vuln06': {'get': {'parameters': [], 'responses': {}}},
        '/xmlReader/sec': {'post': {'parameters': [], 'responses': {}}},
        '/xmlReader/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/xmlbeam/vuln': {'post': {'parameters': [], 'responses': {}}},
        '/xstream': {'post': {'parameters': [], 'responses': {}}}}

# def test_endpoints_to_openapi(java_usages_1, js_usages_1):
#     assert java_usages_1.endpoints_to_openapi() == {
#         'info': {'title': 'OpenAPI Specification for data', 'version': '1.0.0'},
#         'openapi': '3.1.0',
#         'paths': {'/': {'post': {'parameters': [], 'responses': {}}},
#                   '/accounts/{accountName}': {'get': {'parameters': [
#                       {'in': 'path', 'name': 'accountName', 'required': True}],
#                                                       'responses': {}}},
#                   '/current': {'get': {'parameters': [], 'responses': {}},
#                                'put': {'parameters': [], 'responses': {}}},
#                   '/latest': {'get': {'parameters': [], 'responses': {}}},
#                   '/statistics/{accountName}': {'put': {'parameters': [
#                       {'in': 'path', 'name': 'accountName', 'required': True}],
#                                                         'responses': {}}},
#                   '/uaa/users': {'post': {'parameters': [], 'responses': {}}},
#                   '/{accountName}': {'get': {'parameters': [
#                       {'in': 'path', 'name': 'accountName', 'required': True}],
#                                              'responses': {}}, 'put': {
#                       'parameters': [{'in': 'path', 'name': 'accountName',
#                                       'required': True}], 'responses': {}}},
#                   '/{name}': {'get': {'parameters': [
#                       {'in': 'path', 'name': 'name', 'required': True}],
#                                       'responses': {}}}}}
#     assert js_usages_1.endpoints_to_openapi() == {
#         'info': {'title': 'OpenAPI Specification for data', 'version': '1.0.0'},
#         'openapi': '3.0.1', 'paths': {'/': {'get': {
#             'parameters': [{'in': 'header', 'name': '__ecma.String'},
#                            {'in': 'header', 'name': 'LAMBDA'}],
#             'responses': {}}, 'post': {
#             'parameters': [{'in': 'header', 'name': '__ecma.String'},
#                            {'in': 'header', 'name': 'LAMBDA'}],
#             'responses': {}}}, '/.well-known/security.txt': {
#             'get': {'parameters': [], 'responses': {}}},
#                                       '/Invalidemail/passwordcannotbeempty': {
#                                           'post': {'parameters': [
#                                               {'in': 'header',
#                                                'name': '__ecma.String'},
#                                               {'in': 'header',
#                                                'name': 'LAMBDA'}],
#                                                    'responses': {}}},
#                                       '/api/Addresss': {'get': {'parameters': [
#                                           {'in': 'header',
#                                            'name': '__ecma.String'}],
#                                                                 'responses':
#                                                                     {}},
#                                                         'post': {'parameters': [
#                                                             {'in': 'header',
#                                                              'name':
#                                                                  '__ecma.String'}],
#                                                                  'responses':
#                                                                      {}}},
#                                       '/api/Addresss/{id}': {'delete': {
#                                           'parameters': [
#                                               {'in': 'path', 'name': 'id',
#                                                'required': True}],
#                                           'responses': {}}, 'get': {
#                                           'parameters': [
#                                               {'in': 'path', 'name': 'id',
#                                                'required': True}],
#                                           'responses': {}}, 'put': {
#                                           'parameters': [
#                                               {'in': 'path', 'name': 'id',
#                                                'required': True}],
#                                           'responses': {}}},
#                                       '/api/BasketItems': {'post': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'}],
#                                           'responses': {}}},
#                                       '/api/BasketItems/{id}': {'parameters': [
#                                           {'in': 'path', 'name': 'id',
#                                            'required': True}], 'put': {
#                                           'parameters': [
#                                               {'in': 'path', 'name': 'id',
#                                                'required': True}],
#                                           'responses': {}}}, '/api/Cards': {
#                 'get': {
#                     'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                     'responses': {}}, 'post': {
#                     'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                     'responses': {}}}, '/api/Cards/{id}': {'delete': {
#                 'parameters': [{'in': 'path', 'name': 'id', 'required': True}],
#                 'responses': {}}, 'get': {
#                 'parameters': [{'in': 'path', 'name': 'id', 'required': True}],
#                 'responses': {}}, 'put': {
#                 'parameters': [{'in': 'path', 'name': 'id', 'required': True}],
#                 'responses': {}}}, '/api/Challenges': {'post': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'},
#                                {'in': 'header',
#                                 'name':
#                                     'express-jwt:expressJwt:<returnValue>'}],
#                 'responses': {}}}, '/api/Challenges/{id}': {
#                 'parameters': [{'in': 'path', 'name': 'id', 'required': True}]},
#                                       '/api/Complaints': {'get': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'},
#                                                          {'in': 'header',
#                                                           'name':
#                                                               'express-jwt:expressJwt:<returnValue>'}],
#                                           'responses': {}}, 'post': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'},
#                                                          {'in': 'header',
#                                                           'name':
#                                                               'express-jwt:expressJwt:<returnValue>'}],
#                                           'responses': {}}},
#                                       '/api/Complaints/{id}': {'parameters': [
#                                           {'in': 'path', 'name': 'id',
#                                            'required': True}]},
#                                       '/api/Deliverys': {'get': {'parameters': [
#                                           {'in': 'header',
#                                            'name': '__ecma.String'}],
#                                                                  'responses':
#                                                                      {}}},
#                                       '/api/Deliverys/{id}': {'get': {
#                                           'parameters': [
#                                               {'in': 'path', 'name': 'id',
#                                                'required': True}],
#                                           'responses': {}}}, '/api/Feedbacks': {
#                 'post': {
#                     'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                     'responses': {}}}, '/api/Feedbacks/{id}': {
#                 'parameters': [{'in': 'path', 'name': 'id', 'required': True}],
#                 'put': {'parameters': [
#                     {'in': 'path', 'name': 'id', 'required': True}],
#                         'responses': {}}}, '/api/PrivacyRequests': {'get': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'},
#                                {'in': 'header',
#                                 'name':
#                                     'express-jwt:expressJwt:<returnValue>'}],
#                 'responses': {}}, 'post': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'},
#                                {'in': 'header',
#                                 'name':
#                                     'express-jwt:expressJwt:<returnValue>'}],
#                 'responses': {}}}, '/api/PrivacyRequests/{id}': {
#                 'parameters': [{'in': 'path', 'name': 'id', 'required': True}]},
#                                       '/api/Products': {'post': {'parameters': [
#                                           {'in': 'header',
#                                            'name': '__ecma.String'},
#                                           {'in': 'header',
#                                            'name':
#                                                'express-jwt:expressJwt:<returnValue>'}],
#                                                                  'responses':
#                                                                      {}}},
#                                       '/api/Products/{id}': {'delete': {
#                                           'parameters': [
#                                               {'in': 'path', 'name': 'id',
#                                                'required': True}],
#                                           'responses': {}}}, '/api/Quantitys': {
#                 'post': {
#                     'parameters': [{'in': 'header', 'name': '__ecma.String'},
#                                    {'in': 'header',
#                                     'name':
#                                         'express-jwt:expressJwt:<returnValue>'}],
#                     'responses': {}}}, '/api/Quantitys/{id}': {'delete': {
#                 'parameters': [{'in': 'path', 'name': 'id', 'required': True}],
#                 'responses': {}}, 'parameters': [
#                 {'in': 'path', 'name': 'id', 'required': True}]},
#                                       '/api/Recycles': {'get': {'parameters': [
#                                           {'in': 'header',
#                                            'name': '__ecma.String'}],
#                                                                 'responses':
#                                                                     {}},
#                                                         'post': {'parameters': [
#                                                             {'in': 'header',
#                                                              'name':
#                                                                  '__ecma.String'},
#                                                             {'in': 'header',
#                                                              'name':
#                                                                  'express-jwt:expressJwt:<returnValue>'}],
#                                                                  'responses':
#                                                                      {}}},
#                                       '/api/Recycles/{id}': {'delete': {
#                                           'parameters': [
#                                               {'in': 'path', 'name': 'id',
#                                                'required': True}],
#                                           'responses': {}}, 'get': {
#                                           'parameters': [
#                                               {'in': 'path', 'name': 'id',
#                                                'required': True}],
#                                           'responses': {}}, 'put': {
#                                           'parameters': [
#                                               {'in': 'path', 'name': 'id',
#                                                'required': True}],
#                                           'responses': {}}},
#                                       '/api/SecurityAnswers': {'get': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'},
#                                                          {'in': 'header',
#                                                           'name':
#                                                               'express-jwt:expressJwt:<returnValue>'}],
#                                           'responses': {}}},
#                                       '/api/SecurityAnswers/{id}': {
#                                           'parameters': [
#                                               {'in': 'path', 'name': 'id',
#                                                'required': True}]},
#                                       '/api/SecurityQuestions': {'post': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'},
#                                                          {'in': 'header',
#                                                           'name':
#                                                               'express-jwt:expressJwt:<returnValue>'}],
#                                           'responses': {}}},
#                                       '/api/SecurityQuestions/{id}': {
#                                           'parameters': [
#                                               {'in': 'path', 'name': 'id',
#                                                'required': True}]},
#                                       '/api/Users': {'get': {'parameters': [
#                                           {'in': 'header',
#                                            'name': '__ecma.String'},
#                                           {'in': 'header',
#                                            'name':
#                                                'express-jwt:expressJwt:<returnValue>'}],
#                                                              'responses': {}},
#                                                      'post': {'parameters': [
#                                                          {'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'}],
#                                                               'responses': {}}},
#                                       '/api/Users/{id}': {'parameters': [
#                                           {'in': 'path', 'name': 'id',
#                                            'required': True}]},
#                                       '/application/json': {
#                                           'head': {'parameters': [],
#                                                    'responses': {}}},
#                                       '/b2b/v2/orders': {'post': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'}],
#                                           'responses': {}}},
#                                       '/encryptionkeys/{file}': {'parameters': [
#                                           {'in': 'path', 'name': 'file',
#                                            'required': True}]},
#                                       '/file-upload': {'post': {'parameters': [
#                                           {'in': 'header',
#                                            'name': '__ecma.String'}],
#                                                                 'responses':
#                                                                     {}}},
#                                       '/ftp(?!/quarantine)/{file}': {
#                                           'parameters': [
#                                               {'in': 'path', 'name': 'file',
#                                                'required': True}]},
#                                       '/ftp/quarantine/{file}': {'parameters': [
#                                           {'in': 'path', 'name': 'file',
#                                            'required': True}]}, '/metrics': {
#                 'get': {
#                     'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                     'responses': {}}}, '/profile': {'get': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}, 'post': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/profile/image/file': {'post': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/profile/image/url': {'post': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/promotion': {'get': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/redirect': {'get': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/2fa/disable': {
#                 'post': {'parameters': [], 'responses': {}}},
#                                       '/rest/2fa/setup': {
#                                           'post': {'parameters': [],
#                                                    'responses': {}}},
#                                       '/rest/2fa/status': {'get': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               'routes\\2fa.ts::program:status'},
#                                                          {'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'},
#                                                          {'in': 'header',
#                                                           'name':
#                                                               'express-jwt:expressJwt:<returnValue>'}],
#                                           'responses': {}}},
#                                       '/rest/2fa/verify': {
#                                           'post': {'parameters': [],
#                                                    'responses': {}}},
#                                       '/rest/admin/application-configuration': {
#                                           'get': {'parameters': [
#                                               {'in': 'header',
#                                                'name': '__ecma.String'}],
#                                                   'responses': {}}},
#                                       '/rest/admin/application-version': {
#                                           'get': {'parameters': [
#                                               {'in': 'header',
#                                                'name': '__ecma.String'}],
#                                                   'responses': {}}},
#                                       '/rest/basket/{id}': {'get': {
#                                           'parameters': [
#                                               {'in': 'path', 'name': 'id',
#                                                'required': True}],
#                                           'responses': {}}, 'parameters': [
#                                           {'in': 'path', 'name': 'id',
#                                            'required': True}]},
#                                       '/rest/basket/{id}/checkout': {'post': {
#                                           'parameters': [
#                                               {'in': 'path', 'name': 'id',
#                                                'required': True}],
#                                           'responses': {}}},
#                                       '/rest/basket/{id}/coupon/{coupon}': {
#                                           'put': {'parameters': [
#                                               {'in': 'path', 'name': 'id',
#                                                'required': True},
#                                               {'in': 'path', 'name': 'coupon',
#                                                'required': True}],
#                                                   'responses': {}}},
#                                       '/rest/basket/{id}/order': {
#                                           'parameters': [
#                                               {'in': 'path', 'name': 'id',
#                                                'required': True}]},
#                                       '/rest/captcha': {'get': {'parameters': [
#                                           {'in': 'header',
#                                            'name': '__ecma.String'}],
#                                                                 'responses':
#                                                                     {}}},
#                                       '/rest/chatbot/respond': {'post': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'}],
#                                           'responses': {}}},
#                                       '/rest/chatbot/status': {'get': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'}],
#                                           'responses': {}}},
#                                       '/rest/continue-code': {'get': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'}],
#                                           'responses': {}}},
#                                       '/rest/continue-code-findIt': {'get': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'}],
#                                           'responses': {}}},
#                                       '/rest/continue-code-findIt/apply/{'
#                                       'continueCode}': {
#                                           'put': {'parameters': [{'in': 'path',
#                                                                   'name':
#                                                                       'continueCode',
#                                                                   'required':
#                                                                       True}],
#                                                   'responses': {}}},
#                                       '/rest/continue-code-fixIt': {'get': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'}],
#                                           'responses': {}}},
#                                       '/rest/continue-code-fixIt/apply/{'
#                                       'continueCode}': {
#                                           'put': {'parameters': [{'in': 'path',
#                                                                   'name':
#                                                                       'continueCode',
#                                                                   'required':
#                                                                       True}],
#                                                   'responses': {}}},
#                                       '/rest/continue-code/apply/{'
#                                       'continueCode}': {
#                                           'put': {'parameters': [{'in': 'path',
#                                                                   'name':
#                                                                       'continueCode',
#                                                                   'required':
#                                                                       True}],
#                                                   'responses': {}}},
#                                       '/rest/country-mapping': {'get': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'}],
#                                           'responses': {}}},
#                                       '/rest/deluxe-membership': {'get': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'}],
#                                           'responses': {}}, 'post': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'}],
#                                           'responses': {}}},
#                                       '/rest/image-captcha': {'get': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'}],
#                                           'responses': {}}},
#                                       '/rest/languages': {'get': {
#                                           'parameters': [{'in': 'header',
#                                                           'name':
#                                                               '__ecma.String'}],
#                                           'responses': {}}}, '/rest/memories': {
#                 'get': {
#                     'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                     'responses': {}}, 'post': {
#                     'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                     'responses': {}}}, '/rest/order-history': {'get': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/order-history/orders': {'get': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/order-history/{id}/delivery-status': {
#                 'put': {'parameters': [
#                     {'in': 'path', 'name': 'id', 'required': True}],
#                         'responses': {}}}, '/rest/products/reviews': {'patch': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'},
#                                {'in': 'header',
#                                 'name':
#                                     'express-jwt:expressJwt:<returnValue>'}],
#                 'responses': {}}, 'post': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'},
#                                {'in': 'header',
#                                 'name':
#                                     'express-jwt:expressJwt:<returnValue>'}],
#                 'responses': {}}}, '/rest/products/search': {'get': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/products/{id}/reviews': {'get': {
#                 'parameters': [{'in': 'path', 'name': 'id', 'required': True}],
#                 'responses': {}}, 'put': {
#                 'parameters': [{'in': 'path', 'name': 'id', 'required': True}],
#                 'responses': {}}}, '/rest/repeat-notification': {'get': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/saveLoginIp': {'get': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/track-order/{id}': {'get': {
#                 'parameters': [{'in': 'path', 'name': 'id', 'required': True}],
#                 'responses': {}}}, '/rest/user/authentication-details': {
#                 'get': {
#                     'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                     'responses': {}}}, '/rest/user/change-password': {'get': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/user/data-export': {'post': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/user/login': {'post': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/user/reset-password': {
#                 'head': {'parameters': [], 'responses': {}}, 'post': {
#                     'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                     'responses': {}}}, '/rest/user/security-question': {'get': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/user/whoami': {'get': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/wallet/balance': {'get': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}, 'put': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/web3/nftMintListen': {'get': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/web3/nftUnlocked': {'get': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/web3/submitKey': {'post': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/web3/walletExploitAddress': {'post': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/rest/web3/walletNFTVerify': {'post': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/security.txt': {
#                 'get': {'parameters': [], 'responses': {}}}, '/snippets': {
#                 'get': {
#                     'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                     'responses': {}}}, '/snippets/fixes': {'post': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/snippets/fixes/{key}': {'get': {
#                 'parameters': [{'in': 'path', 'name': 'key', 'required': True}],
#                 'responses': {}}}, '/snippets/verdict': {'post': {
#                 'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                 'responses': {}}}, '/snippets/{challenge}': {'get': {
#                 'parameters': [
#                     {'in': 'path', 'name': 'challenge', 'required': True}],
#                 'responses': {}}}, '/support/logs/{file}': {'parameters': [
#                 {'in': 'path', 'name': 'file', 'required': True}]},
#                                       '/the/devs/are/so/funny/they/hid/an/easter/egg/within/the/easter/egg': {
#                                           'get': {'parameters': [
#                                               {'in': 'header',
#                                                'name': '__ecma.String'}],
#                                                   'responses': {}}},
#                                       '/this/page/is/hidden/behind/an/incredibly/high/paywall/that/could/only/be/unlocked/by/sending/1btc/to/us': {
#                                           'get': {'parameters': [
#                                               {'in': 'header',
#                                                'name': '__ecma.String'}],
#                                                   'responses': {}}}, '/video': {
#                 'get': {
#                     'parameters': [{'in': 'header', 'name': '__ecma.String'}],
#                     'responses': {}}},
#                                       '/we/may/also/instruct/you/to/refuse/all/reasonably/necessary/responsibility': {
#                                           'get': {'parameters': [
#                                               {'in': 'header',
#                                                'name': '__ecma.String'}],
#                                                   'responses': {}}}}}
