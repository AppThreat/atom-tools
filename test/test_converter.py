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
    return OpenAPI('openapi3.0.1', 'python', 'test/data/py-airflow-usages.json')


@pytest.fixture
def py_usages_2():
    return OpenAPI('openapi3.0.1', 'py', 'test/data/py-tornado-usages.json')


def test_populate_endpoints(js_usages_1, js_usages_2):
    # The populate_endpoints method is the final operation in convert_usages.
    # However, it's difficult to test the output when the order of params can
    # differ.
    methods = js_usages_1.process_methods()
    methods = js_usages_1.methods_to_endpoints(methods)
    assert methods == {
        'full_names': {'routes\\dataErasure.ts::program': {
        'resolved_methods': {
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
                'endpoints': ['/']},
            "router.post('/',async(req:Request<Record<string,unknown>,"
            "Record<string,unknown>,DataErasureRequestParams>,res:Response,"
            "next:NextFunction):Promise<void>=>{"
            "\rconstloggedInUser=insecurity.authenticatedUsers.get("
            "req.cookies.token)\rif(!loggedInUser){\rnext(newError("
            "'Blockedillegalactivityby'+req.socket.remoteAddress))\rreturn\r"
            "}\r\rtry{\rawaitPrivacyRequestModel.create({"
            "\rUserId:loggedInUser.data.id,"
            "\rdeletionRequested:true\r})\r\rres.clearCookie('token')\rif("
            "req.body.layout){\rconstfilePath:string=path.resolve("
            "req.body.layout).toLowerCase()\rconstisForbiddenFile:boolean=("
            "filePath.includes('ftp')||filePath.includes("
            "'ctf.key')||filePath.includes('encryptionkeys'))\rif("
            "!isForbiddenFile){\rres.render('dataErasureResult',"
            "{\r...req.body\r},(error,html)=>{\rif(!html||error){\rnext("
            "newError(error.message))\r}else{\r...": {
                'endpoints': ['/']}}}, 'server.ts::program': {
        'resolved_methods': {
            "app.delete('/api/Addresss/:id',security.appendUserId(),"
            "address.delAddressById())": {
                'endpoints': ['/api/Addresss/:id']},
            "app.delete('/api/Cards/:id',security.appendUserId(),"
            "payment.delPaymentMethodById())": {
                'endpoints': ['/api/Cards/:id']},
            "app.delete('/api/Products/:id',security.denyAll())": {
                'endpoints': ['/api/Products/:id']},
            "app.delete('/api/Quantitys/:id',security.denyAll())": {
                'endpoints': ['/api/Quantitys/:id']},
            "app.delete('/api/Recycles/:id',security.denyAll())": {
                'endpoints': ['/api/Recycles/:id']},
            "app.get('/api/Addresss',security.appendUserId(),"
            "address.getAddress())": {
                'endpoints': ['/api/Addresss']},
            "app.get('/api/Addresss/:id',security.appendUserId(),"
            "address.getAddressById())": {
                'endpoints': ['/api/Addresss/:id']},
            "app.get('/api/Cards',security.appendUserId(),"
            "payment.getPaymentMethods())": {
                'endpoints': ['/api/Cards']},
            "app.get('/api/Cards/:id',security.appendUserId(),"
            "payment.getPaymentMethodById())": {
                'endpoints': ['/api/Cards/:id']},
            "app.get('/api/Complaints',security.isAuthorized())": {
                'endpoints': ['/api/Complaints']},
            "app.get('/api/Deliverys',delivery.getDeliveryMethods())": {
                'endpoints': ['/api/Deliverys']},
            "app.get('/api/Deliverys/:id',delivery.getDeliveryMethod())": {
                'endpoints': ['/api/Deliverys/:id']},
            "app.get('/api/PrivacyRequests',security.denyAll())": {
                'endpoints': ['/api/PrivacyRequests']},
            "app.get('/api/Recycles',recycles.blockRecycleItems())": {
                'endpoints': ['/api/Recycles']},
            "app.get('/api/Recycles/:id',recycles.getRecycleItem())": {
                'endpoints': ['/api/Recycles/:id']},
            "app.get('/api/SecurityAnswers',security.denyAll())": {
                'endpoints': ['/api/SecurityAnswers']},
            "app.get('/api/Users',security.isAuthorized())": {
                'endpoints': ['/api/Users']},
            "app.get('/metrics',metrics.serveMetrics())": {
                'endpoints': ['/metrics']},
            "app.get('/profile',security.updateAuthenticatedUsers(),"
            "userProfile())": {
                'endpoints': ['/profile']},
            "app.get('/promotion',videoHandler.promotionVideo())": {
                'endpoints': ['/promotion']},
            "app.get('/redirect',redirect())": {'endpoints': ['/redirect']},
            "app.get('/rest/2fa/status',security.isAuthorized(),"
            "twoFactorAuth.status())": {
                'endpoints': ['/rest/2fa/status']},
            "app.get('/rest/admin/application-configuration',"
            "appConfiguration())": {
                'endpoints': ['/rest/admin/application-configuration']},
            "app.get('/rest/admin/application-version',appVersion())": {
                'endpoints': ['/rest/admin/application-version']},
            "app.get('/rest/basket/:id',basket())": {
                'endpoints': ['/rest/basket/:id']},
            "app.get('/rest/captcha',captcha())": {
                'endpoints': ['/rest/captcha']},
            "app.get('/rest/chatbot/status',chatbot.status())": {
                'endpoints': ['/rest/chatbot/status']},
            "app.get('/rest/continue-code',continueCode.continueCode())": {
                'endpoints': ['/rest/continue-code']},
            "app.get('/rest/continue-code-findIt',"
            "continueCode.continueCodeFindIt())": {
                'endpoints': ['/rest/continue-code-findIt']},
            "app.get('/rest/continue-code-fixIt',"
            "continueCode.continueCodeFixIt())": {
                'endpoints': ['/rest/continue-code-fixIt']},
            "app.get('/rest/country-mapping',countryMapping())": {
                'endpoints': ['/rest/country-mapping']},
            "app.get('/rest/deluxe-membership',deluxe.deluxeMembershipStatus("
            "))": {
                'endpoints': ['/rest/deluxe-membership']},
            "app.get('/rest/image-captcha',imageCaptcha())": {
                'endpoints': ['/rest/image-captcha']},
            "app.get('/rest/languages',languageList())": {
                'endpoints': ['/rest/languages']},
            "app.get('/rest/memories',memory.getMemories())": {
                'endpoints': ['/rest/memories']},
            "app.get('/rest/order-history',orderHistory.orderHistory())": {
                'endpoints': ['/rest/order-history']},
            "app.get('/rest/order-history/orders',security.isAccounting(),"
            "orderHistory.allOrders())": {
                'endpoints': ['/rest/order-history/orders']},
            "app.get('/rest/products/:id/reviews',showProductReviews())": {
                'endpoints': ['/rest/products/:id/reviews']},
            "app.get('/rest/products/search',search())": {
                'endpoints': ['/rest/products/search']},
            "app.get('/rest/repeat-notification',repeatNotification())": {
                'endpoints': ['/rest/repeat-notification']},
            "app.get('/rest/saveLoginIp',saveLoginIp())": {
                'endpoints': ['/rest/saveLoginIp']},
            "app.get('/rest/track-order/:id',trackOrder())": {
                'endpoints': ['/rest/track-order/:id']},
            "app.get('/rest/user/authentication-details',authenticatedUsers("
            "))": {
                'endpoints': ['/rest/user/authentication-details']},
            "app.get('/rest/user/change-password',changePassword())": {
                'endpoints': ['/rest/user/change-password']},
            "app.get('/rest/user/security-question',securityQuestion())": {
                'endpoints': ['/rest/user/security-question']},
            "app.get('/rest/user/whoami',security.updateAuthenticatedUsers(),"
            "currentUser())": {
                'endpoints': ['/rest/user/whoami']},
            "app.get('/rest/wallet/balance',security.appendUserId(),"
            "wallet.getWalletBalance())": {
                'endpoints': ['/rest/wallet/balance']},
            "app.get('/rest/web3/nftMintListen',nftMint.nftMintListener())": {
                'endpoints': ['/rest/web3/nftMintListen']},
            "app.get('/rest/web3/nftUnlocked',checkKeys.nftUnlocked())": {
                'endpoints': ['/rest/web3/nftUnlocked']},
            "app.get('/snippets',"
            "vulnCodeSnippet.serveChallengesWithCodeSnippet())": {
                'endpoints': ['/snippets']},
            "app.get('/snippets/:challenge',vulnCodeSnippet.serveCodeSnippet("
            "))": {
                'endpoints': ['/snippets/:challenge']},
            "app.get('/snippets/fixes/:key',vulnCodeFixes.serveCodeFixes())": {
                'endpoints': ['/snippets/fixes/:key']},
            "app.get('/the/devs/are/so/funny/they/hid/an/easter/egg/within"
            "/the/easter/egg',easterEgg())": {
                'endpoints': [
                    '/the/devs/are/so/funny/they/hid/an/easter/egg/within/the'
                    '/easter/egg']},
            "app.get('/this/page/is/hidden/behind/an/incredibly/high/paywall"
            "/that/could/only/be/unlocked/by/sending/1btc/to/us',"
            "premiumReward())": {
                'endpoints': [
                    '/this/page/is/hidden/behind/an/incredibly/high/paywall'
                    '/that/could/only/be/unlocked/by/sending/1btc/to/us']},
            "app.get('/video',videoHandler.getVideo())": {
                'endpoints': ['/video']},
            "app.get('/we/may/also/instruct/you/to/refuse/all/reasonably"
            "/necessary/responsibility',privacyPolicyProof())": {
                'endpoints': [
                    '/we/may/also/instruct/you/to/refuse/all/reasonably'
                    '/necessary/responsibility']},
            "app.get(['/.well-known/security.txt','/security.txt'],"
            "verify.accessControlChallenges())": {
                'endpoints': ['/.well-known/security.txt', '/security.txt']},
            "app.patch('/rest/products/reviews',security.isAuthorized(),"
            "updateProductReviews())": {
                'endpoints': ['/rest/products/reviews']},
            "app.post('/api/Addresss',security.appendUserId())": {
                'endpoints': ['/api/Addresss']},
            "app.post('/api/BasketItems',security.appendUserId(),"
            "basketItems.quantityCheckBeforeBasketItemAddition(),"
            "basketItems.addBasketItem())": {
                'endpoints': ['/api/BasketItems']},
            "app.post('/api/Cards',security.appendUserId())": {
                'endpoints': ['/api/Cards']},
            "app.post('/api/Challenges',security.denyAll())": {
                'endpoints': ['/api/Challenges']},
            "app.post('/api/Complaints',security.isAuthorized())": {
                'endpoints': ['/api/Complaints']},
            "app.post('/api/Feedbacks',captcha.verifyCaptcha())": {
                'endpoints': ['/api/Feedbacks']},
            "app.post('/api/Feedbacks',verify.captchaBypassChallenge())": {
                'endpoints': ['/api/Feedbacks']},
            "app.post('/api/Feedbacks',verify.forgedFeedbackChallenge())": {
                'endpoints': ['/api/Feedbacks']},
            "app.post('/api/PrivacyRequests',security.isAuthorized())": {
                'endpoints': ['/api/PrivacyRequests']},
            "app.post('/api/Products',security.isAuthorized())": {
                'endpoints': ['/api/Products']},
            "app.post('/api/Quantitys',security.denyAll())": {
                'endpoints': ['/api/Quantitys']},
            "app.post('/api/Recycles',security.isAuthorized())": {
                'endpoints': ['/api/Recycles']},
            "app.post('/api/SecurityQuestions',security.denyAll())": {
                'endpoints': ['/api/SecurityQuestions']},
            "app.post('/api/Users',(req:Request,res:Response,"
            "next:NextFunction)=>{\rif("
            "req.body.email!==undefined&&req.body.password!==undefined&&req"
            ".body.passwordRepeat!==undefined){\rif("
            "req.body.email.length!==0&&req.body.password.length!==0){"
            "\rreq.body.email=req.body.email.trim("
            ")\rreq.body.password=req.body.password.trim("
            ")\rreq.body.passwordRepeat=req.body.passwordRepeat.trim("
            ")\r}else{\rres.status(400).send(res.__("
            "'Invalidemail/passwordcannotbeempty'))\r}\r}\rnext()\r})": {
                'endpoints': ['/api/Users',
                              '/Invalidemail/passwordcannotbeempty']},
            "app.post('/api/Users',verify.emptyUserRegistration())": {
                'endpoints': ['/api/Users']},
            "app.post('/api/Users',verify.passwordRepeatChallenge())": {
                'endpoints': ['/api/Users']},
            "app.post('/api/Users',verify.registerAdminChallenge())": {
                'endpoints': ['/api/Users']},
            "app.post('/b2b/v2/orders',b2bOrder())": {
                'endpoints': ['/b2b/v2/orders']},
            "app.post('/file-upload',uploadToMemory.single('file'),"
            "ensureFileIsPassed,metrics.observeFileUploadMetricsMiddleware(),"
            "handleZipFileUpload,checkUploadSize,checkFileType,"
            "handleXmlUpload)": {
                'endpoints': ['/file-upload']},
            "app.post('/profile',updateUserProfile())": {
                'endpoints': ['/profile']},
            "app.post('/profile/image/file',uploadToMemory.single('file'),"
            "ensureFileIsPassed,metrics.observeFileUploadMetricsMiddleware(),"
            "profileImageFileUpload())": {
                'endpoints': ['/profile/image/file']},
            "app.post('/profile/image/url',uploadToMemory.single('file'),"
            "profileImageUrlUpload())": {
                'endpoints': ['/profile/image/url']},
            "app.post('/rest/2fa/disable',\rnewRateLimit({windowMs:5*60*1000,"
            "max:100}),\rsecurity.isAuthorized(),\rtwoFactorAuth.disable("
            ")\r)": {
                'endpoints': ['/rest/2fa/disable']},
            "app.post('/rest/2fa/setup',\rnewRateLimit({windowMs:5*60*1000,"
            "max:100}),\rsecurity.isAuthorized(),\rtwoFactorAuth.setup()\r)": {
                'endpoints': ['/rest/2fa/setup']},
            "app.post('/rest/2fa/verify',\rnewRateLimit({windowMs:5*60*1000,"
            "max:100}),\rtwoFactorAuth.verify()\r)": {
                'endpoints': ['/rest/2fa/verify']},
            "app.post('/rest/basket/:id/checkout',order())": {
                'endpoints': ['/rest/basket/:id/checkout']},
            "app.post('/rest/chatbot/respond',chatbot.process())": {
                'endpoints': ['/rest/chatbot/respond']},
            "app.post('/rest/deluxe-membership',security.appendUserId(),"
            "deluxe.upgradeToDeluxe())": {
                'endpoints': ['/rest/deluxe-membership']},
            "app.post('/rest/memories',uploadToDisk.single('image'),"
            "ensureFileIsPassed,security.appendUserId(),"
            "metrics.observeFileUploadMetricsMiddleware(),memory.addMemory("
            "))": {
                'endpoints': ['/rest/memories']},
            "app.post('/rest/products/reviews',security.isAuthorized(),"
            "likeProductReviews())": {
                'endpoints': ['/rest/products/reviews']},
            "app.post('/rest/user/data-export',security.appendUserId(),"
            "dataExport())": {
                'endpoints': ['/rest/user/data-export']},
            "app.post('/rest/user/data-export',security.appendUserId(),"
            "imageCaptcha.verifyCaptcha())": {
                'endpoints': ['/rest/user/data-export']},
            "app.post('/rest/user/login',login())": {
                'endpoints': ['/rest/user/login']},
            "app.post('/rest/user/reset-password',resetPassword())": {
                'endpoints': ['/rest/user/reset-password']},
            "app.post('/rest/web3/submitKey',checkKeys.checkKeys())": {
                'endpoints': ['/rest/web3/submitKey']},
            "app.post('/rest/web3/walletExploitAddress',"
            "web3Wallet.contractExploitListener())": {
                'endpoints': ['/rest/web3/walletExploitAddress']},
            "app.post('/rest/web3/walletNFTVerify',nftMint.walletNFTVerify("
            "))": {
                'endpoints': ['/rest/web3/walletNFTVerify']},
            "app.post('/snippets/fixes',vulnCodeFixes.checkCorrectFix())": {
                'endpoints': ['/snippets/fixes']},
            "app.post('/snippets/verdict',vulnCodeSnippet.checkVulnLines())": {
                'endpoints': ['/snippets/verdict']},
            "app.put('/api/Addresss/:id',security.appendUserId())": {
                'endpoints': ['/api/Addresss/:id']},
            "app.put('/api/BasketItems/:id',security.appendUserId(),"
            "basketItems.quantityCheckBeforeBasketItemUpdate())": {
                'endpoints': ['/api/BasketItems/:id']},
            "app.put('/api/Cards/:id',security.denyAll())": {
                'endpoints': ['/api/Cards/:id']},
            "app.put('/api/Feedbacks/:id',security.denyAll())": {
                'endpoints': ['/api/Feedbacks/:id']},
            "app.put('/api/Recycles/:id',security.denyAll())": {
                'endpoints': ['/api/Recycles/:id']},
            "app.put('/rest/basket/:id/coupon/:coupon',coupon())": {
                'endpoints': ['/rest/basket/:id/coupon/:coupon']},
            "app.put('/rest/continue-code-findIt/apply/:continueCode',"
            "restoreProgress.restoreProgressFindIt())": {
                'endpoints': [
                    '/rest/continue-code-findIt/apply/:continueCode']},
            "app.put('/rest/continue-code-fixIt/apply/:continueCode',"
            "restoreProgress.restoreProgressFixIt())": {
                'endpoints': ['/rest/continue-code-fixIt/apply/:continueCode']},
            "app.put('/rest/continue-code/apply/:continueCode',"
            "restoreProgress.restoreProgress())": {
                'endpoints': ['/rest/continue-code/apply/:continueCode']},
            "app.put('/rest/order-history/:id/delivery-status',"
            "security.isAccounting(),orderHistory.toggleDeliveryStatus())": {
                'endpoints': ['/rest/order-history/:id/delivery-status']},
            "app.put('/rest/products/:id/reviews',createProductReviews())": {
                'endpoints': ['/rest/products/:id/reviews']},
            "app.put('/rest/wallet/balance',security.appendUserId(),"
            "wallet.addWalletBalance())": {
                'endpoints': ['/rest/wallet/balance']},
            "app.route('/api/Users/:id')": {'endpoints': ['/api/Users/:id']},
            "app.use('/api-docs',swaggerUi.serve,swaggerUi.setup("
            "swaggerDocument))": {
                'endpoints': ['/api-docs']},
            "app.use('/api/BasketItems',security.isAuthorized())": {
                'endpoints': ['/api/BasketItems']},
            "app.use('/api/BasketItems/:id',security.isAuthorized())": {
                'endpoints': ['/api/BasketItems/:id']},
            "app.use('/api/Challenges/:id',security.denyAll())": {
                'endpoints': ['/api/Challenges/:id']},
            "app.use('/api/Complaints/:id',security.denyAll())": {
                'endpoints': ['/api/Complaints/:id']},
            "app.use('/api/Feedbacks/:id',security.isAuthorized())": {
                'endpoints': ['/api/Feedbacks/:id']},
            "app.use('/api/PrivacyRequests',security.isAuthorized())": {
                'endpoints': ['/api/PrivacyRequests']},
            "app.use('/api/PrivacyRequests/:id',security.denyAll())": {
                'endpoints': ['/api/PrivacyRequests/:id']},
            "app.use('/api/PrivacyRequests/:id',security.isAuthorized())": {
                'endpoints': ['/api/PrivacyRequests/:id']},
            "app.use('/api/Quantitys/:id',security.isAccounting(),ipfilter(["
            "'123.456.789'],{mode:'allow'}))": {
                'endpoints': ['/api/Quantitys/:id']},
            "app.use('/api/SecurityAnswers/:id',security.denyAll())": {
                'endpoints': ['/api/SecurityAnswers/:id']},
            "app.use('/api/SecurityQuestions/:id',security.denyAll())": {
                'endpoints': ['/api/SecurityQuestions/:id']},
            "app.use('/assets/i18n',verify.accessControlChallenges())": {
                'endpoints': ['/assets/i18n']},
            "app.use('/assets/public/images/padding',"
            "verify.accessControlChallenges())": {
                'endpoints': ['/assets/public/images/padding']},
            "app.use('/assets/public/images/products',"
            "verify.accessControlChallenges())": {
                'endpoints': ['/assets/public/images/products']},
            "app.use('/assets/public/images/uploads',"
            "verify.accessControlChallenges())": {
                'endpoints': ['/assets/public/images/uploads']},
            "app.use('/b2b/v2',security.isAuthorized())": {
                'endpoints': ['/b2b/v2']},
            "app.use('/dataerasure',dataErasure)": {
                'endpoints': ['/dataerasure']},
            "app.use('/encryptionkeys',serveIndexMiddleware,serveIndex("
            "'encryptionkeys',{icons:true,view:'details'}))": {
                'endpoints': ['/encryptionkeys']},
            "app.use('/encryptionkeys/:file',keyServer())": {
                'endpoints': ['/encryptionkeys/:file']},
            "app.use('/ftp',serveIndexMiddleware,serveIndex('ftp',"
            "{icons:true}))": {
                'endpoints': ['/ftp']},
            "app.use('/ftp(?!/quarantine)/:file',fileServer())": {
                'endpoints': ['/ftp(?!/quarantine)/:file']},
            "app.use('/ftp/quarantine/:file',quarantineServer())": {
                'endpoints': ['/ftp/quarantine/:file']},
            "app.use('/rest/basket',security.isAuthorized(),"
            "security.appendUserId())": {
                'endpoints': ['/rest/basket']},
            "app.use('/rest/basket/:id',security.isAuthorized())": {
                'endpoints': ['/rest/basket/:id']},
            "app.use('/rest/basket/:id/order',security.isAuthorized())": {
                'endpoints': ['/rest/basket/:id/order']},
            "app.use('/rest/user/authentication-details',"
            "security.isAuthorized())": {
                'endpoints': ['/rest/user/authentication-details']},
            "app.use('/rest/user/reset-password',newRateLimit({"
            "\rwindowMs:5*60*1000,\rmax:100,\rkeyGenerator({headers,"
            "ip}:{headers:any,ip:any}){returnheaders["
            "'X-Forwarded-For']||ip}//vuln-code-snippetvuln"
            "-lineresetPasswordMortyChallenge\r}))": {
                'endpoints': ['/rest/user/reset-password']},
            "app.use('/solve/challenges/server-side',"
            "verify.serverSideChallenges())": {
                'endpoints': ['/solve/challenges/server-side']},
            "app.use('/support/logs',serveIndexMiddleware,serveIndex('logs',"
            "{icons:true,view:'details'}))": {
                'endpoints': ['/support/logs']},
            "app.use('/support/logs',verify.accessControlChallenges())": {
                'endpoints': ['/support/logs']},
            "app.use('/support/logs/:file',logFileServer())": {
                'endpoints': ['/support/logs/:file']},
            "app.use((req:Request,res:Response,next:NextFunction)=>{"
            "\rreq.url=req.url.replace(/[/]+/g,'/')\rnext()\r})": {
                'endpoints': ['/']},
            "app.use(['/.well-known/security.txt','/security.txt'],"
            "securityTxt({\rcontact:config.get("
            "'application.securityTxt.contact'),\rencryption:config.get("
            "'application.securityTxt.encryption'),"
            "\racknowledgements:config.get("
            "'application.securityTxt.acknowledgements'),"
            "\r'Preferred-Languages':[...newSet(locales.map((locale:{"
            "key:string})=>locale.key.substr(0,2)))].join(','),"
            "\rhiring:config.get('application.securityTxt.hiring'),"
            "\rexpires:securityTxtExpiration.toUTCString()\r}))": {
                'endpoints': ['/.well-known/security.txt', '/security.txt']},
            "app.use(bodyParser.text({type:'*/*'}))": {'endpoints': ['/*/*']},
            "app.use(express.static(path.resolve('frontend/dist/frontend')))": {
                'endpoints': ['/frontend/dist/frontend']},
            "app.use(functionjsonParser(req:Request,res:Response,"
            "next:NextFunction){"
            "\r//@ts-expect-errorFIXMEintentionallysavingoriginalrequestinthisproperty\rreq.rawBody=req.body\rif(req.headers['content-type']?.includes('application/json')){\rif(!req.body){\rreq.body={}\r}\rif(req.body!==Object(req.body)){//Expensiveworkaroundfor500errorsduringFrisbytestrun(see#640)\rreq.body=JSON.parse(req.body)\r}\r}\rnext()\r})": {
                'endpoints': ['/application/json']},
            "app.use(robots({UserAgent:'*',Disallow:'/ftp'}))": {
                'endpoints': ['/ftp']}}}}}
    methods = js_usages_1.process_calls(methods)
    result = js_usages_1.populate_endpoints(methods)
    result_keys = list(result.keys())
    result_keys.sort()
    assert result_keys == ['/', '/*/*', '/.well-known/security.txt',
                           '/Invalidemail/passwordcannotbeempty', '/api-docs',
                           '/api/Addresss', '/api/Addresss/{id}',
                           '/api/BasketItems', '/api/BasketItems/{id}',
                           '/api/Cards', '/api/Cards/{id}', '/api/Challenges',
                           '/api/Challenges/{id}', '/api/Complaints',
                           '/api/Complaints/{id}', '/api/Deliverys',
                           '/api/Deliverys/{id}', '/api/Feedbacks',
                           '/api/Feedbacks/{id}', '/api/PrivacyRequests',
                           '/api/PrivacyRequests/{id}', '/api/Products',
                           '/api/Products/{id}', '/api/Quantitys',
                           '/api/Quantitys/{id}', '/api/Recycles',
                           '/api/Recycles/{id}', '/api/SecurityAnswers',
                           '/api/SecurityAnswers/{id}',
                           '/api/SecurityQuestions',
                           '/api/SecurityQuestions/{id}', '/api/Users',
                           '/api/Users/{id}', '/application/json',
                           '/assets/i18n', '/assets/public/images/padding',
                           '/assets/public/images/products',
                           '/assets/public/images/uploads', '/b2b/v2',
                           '/b2b/v2/orders', '/dataerasure', '/encryptionkeys',
                           '/encryptionkeys/{file}', '/file-upload',
                           '/frontend/dist/frontend', '/ftp',
                           '/ftp(?!/quarantine)/{file}',
                           '/ftp/quarantine/{file}', '/metrics', '/profile',
                           '/profile/image/file', '/profile/image/url',
                           '/promotion', '/redirect', '/rest/2fa/disable',
                           '/rest/2fa/setup', '/rest/2fa/status',
                           '/rest/2fa/verify',
                           '/rest/admin/application-configuration',
                           '/rest/admin/application-version', '/rest/basket',
                           '/rest/basket/{id}', '/rest/basket/{id}/checkout',
                           '/rest/basket/{id}/coupon/{coupon}',
                           '/rest/basket/{id}/order', '/rest/captcha',
                           '/rest/chatbot/respond', '/rest/chatbot/status',
                           '/rest/continue-code', '/rest/continue-code-findIt',
                           '/rest/continue-code-findIt/apply/{continueCode}',
                           '/rest/continue-code-fixIt',
                           '/rest/continue-code-fixIt/apply/{continueCode}',
                           '/rest/continue-code/apply/{continueCode}',
                           '/rest/country-mapping', '/rest/deluxe-membership',
                           '/rest/image-captcha', '/rest/languages',
                           '/rest/memories', '/rest/order-history',
                           '/rest/order-history/orders',
                           '/rest/order-history/{id}/delivery-status',
                           '/rest/products/reviews', '/rest/products/search',
                           '/rest/products/{id}/reviews',
                           '/rest/repeat-notification', '/rest/saveLoginIp',
                           '/rest/track-order/{id}',
                           '/rest/user/authentication-details',
                           '/rest/user/change-password',
                           '/rest/user/data-export', '/rest/user/login',
                           '/rest/user/reset-password',
                           '/rest/user/security-question', '/rest/user/whoami',
                           '/rest/wallet/balance', '/rest/web3/nftMintListen',
                           '/rest/web3/nftUnlocked', '/rest/web3/submitKey',
                           '/rest/web3/walletExploitAddress',
                           '/rest/web3/walletNFTVerify', '/security.txt',
                           '/snippets', '/snippets/fixes',
                           '/snippets/fixes/{key}', '/snippets/verdict',
                           '/snippets/{challenge}',
                           '/solve/challenges/server-side', '/support/logs',
                           '/support/logs/{file}',
                           '/the/devs/are/so/funny/they/hid/an/easter/egg'
                           '/within/the/easter/egg',
                           '/this/page/is/hidden/behind/an/incredibly/high'
                           '/paywall/that/could/only/be/unlocked/by/sending'
                           '/1btc/to/us',
                           '/video',
                           '/we/may/also/instruct/you/to/refuse/all/reasonably/necessary/responsibility']
    assert list(
        result['/rest/continue-code-findIt/apply/{continueCode}'].keys()) == ['parameters', 'put']

    methods = js_usages_2.process_methods()
    methods = js_usages_2.methods_to_endpoints(methods)
    assert methods == {
        'full_names': {'app\\routes\\index.js::program:index': {
        'resolved_methods': {'app.get("/",sessionHandler.displayWelcomePage)': {
            'endpoints': ['/']},
                             'app.get("/allocations/:userId",isLoggedIn,'
                             'allocationsHandler.displayAllocations)': {
                                 'endpoints': ['/allocations/:userId']},
                             'app.get("/benefits",isLoggedIn,'
                             'benefitsHandler.displayBenefits)': {
                                 'endpoints': ['/benefits']},
                             'app.get("/contributions",isLoggedIn,'
                             'contributionsHandler.displayContributions)': {
                                 'endpoints': ['/contributions']},
                             'app.get("/dashboard",isLoggedIn,'
                             'sessionHandler.displayWelcomePage)': {
                                 'endpoints': ['/dashboard']},
                             'app.get("/learn",isLoggedIn,(req,res)=>{'
                             '//Insecurewaytohandleredirectsbytakingredirecturlfromquerystringreturnres.redirect(req.query.url);})': {
                                 'endpoints': ['/learn']},
                             'app.get("/login",'
                             'sessionHandler.displayLoginPage)': {
                                 'endpoints': ['/login']},
                             'app.get("/logout",'
                             'sessionHandler.displayLogoutPage)': {
                                 'endpoints': ['/logout']},
                             'app.get("/memos",isLoggedIn,'
                             'memosHandler.displayMemos)': {
                                 'endpoints': ['/memos']},
                             'app.get("/profile",isLoggedIn,'
                             'profileHandler.displayProfile)': {
                                 'endpoints': ['/profile']},
                             'app.get("/research",isLoggedIn,'
                             'researchHandler.displayResearch)': {
                                 'endpoints': ['/research']},
                             'app.get("/signup",'
                             'sessionHandler.displaySignupPage)': {
                                 'endpoints': ['/signup']},
                             'app.post("/benefits",isLoggedIn,'
                             'benefitsHandler.updateBenefits)': {
                                 'endpoints': ['/benefits']},
                             'app.post("/contributions",isLoggedIn,'
                             'contributionsHandler.handleContributionsUpdate'
                             ')': {
                                 'endpoints': ['/contributions']},
                             'app.post("/login",'
                             'sessionHandler.handleLoginRequest)': {
                                 'endpoints': ['/login']},
                             'app.post("/memos",isLoggedIn,'
                             'memosHandler.addMemos)': {
                                 'endpoints': ['/memos']},
                             'app.post("/profile",isLoggedIn,'
                             'profileHandler.handleProfileUpdate)': {
                                 'endpoints': ['/profile']},
                             'app.post("/signup",'
                             'sessionHandler.handleSignup)': {
                                 'endpoints': ['/signup']},
                             'app.use("/tutorial",tutorialRouter)': {
                                 'endpoints': ['/tutorial']}}},
                                      'app\\routes\\tutorial.js::program': {
                                          'resolved_methods': {
                                              'router.get("/",(req,res)=>{'
                                              '"usestrict";returnres.render('
                                              '"tutorial/a1",'
                                              '{environmentalScripts});})': {
                                                  'endpoints': ['/',
                                                                '/tutorial/a1']}}},
                                      'server.js::program': {
                                          'resolved_methods': {
                                              'app.use(favicon('
                                              '__dirname+"/app/assets/favicon.ico"))': {
                                                  'endpoints': [
                                                      '/app/assets/favicon.ico']}}}}}
    methods = js_usages_2.process_calls(methods)
    result = js_usages_2.populate_endpoints(methods)
    assert len(list(result['/login'].keys())) == 2
    result = list(result.keys())
    result.sort()
    assert result == ['/', '/allocations/{userId}', '/app/assets/favicon.ico',
                      '/benefits', '/contributions', '/dashboard', '/learn',
                      '/login', '/logout', '/memos', '/profile', '/research',
                      '/signup', '/tutorial', '/tutorial/a1']


def test_usages_class(java_usages_1):
    assert java_usages_1.title == 'OpenAPI Specification for data'


def test_convert_usages(java_usages_1, java_usages_2, js_usages_1, js_usages_2, py_usages_2):
    assert java_usages_1.convert_usages() == {'/': {'post': {'responses': {}}},
                                              '/accounts/{accountName}': {
                                                  'get': {'responses': {}},
                                                  'parameters': [{'in': 'path',
                                                                  'name':
                                                                      'accountName',
                                                                  'required':
                                                                      True}]},
                                              '/current': {
                                                  'get': {'responses': {}},
                                                  'put': {'responses': {}}},
                                              '/latest': {
                                                  'get': {'responses': {}}},
                                              '/statistics/{accountName}': {
                                                  'parameters': [{'in': 'path',
                                                                  'name':
                                                                      'accountName',
                                                                  'required':
                                                                      True}],
                                                  'put': {'responses': {}}},
                                              '/uaa/users': {
                                                  'post': {'responses': {}}},
                                              '/{accountName}': {
                                                  'get': {'responses': {}},
                                                  'parameters': [{'in': 'path',
                                                                  'name':
                                                                      'accountName',
                                                                  'required':
                                                                      True}],
                                                  'put': {'responses': {}}},
                                              '/{name}': {
                                                  'get': {'responses': {}},
                                                  'parameters': [{'in': 'path',
                                                                  'name':
                                                                      'name',
                                                                  'required':
                                                                      True}]}}
    assert java_usages_2.convert_usages() == {'/': {'get': {'responses': {}}},
                                              '/Digester/sec': {
                                                  'post': {'responses': {}}},
                                              '/Digester/vuln': {
                                                  'post': {'responses': {}}},
                                              '/DocumentBuilder/Sec': {
                                                  'post': {'responses': {}}},
                                              '/DocumentBuilder/vuln': {
                                                  'post': {'responses': {}}},
                                              '/DocumentBuilder/xinclude/sec': {
                                                  'post': {'responses': {}}},
                                              '/DocumentBuilder/xinclude/vuln': {
                                                  'post': {'responses': {}}},
                                              '/DocumentHelper/vuln': {
                                                  'post': {'responses': {}}},
                                              '/HttpSyncClients/vuln': {
                                                  'get': {'responses': {}}},
                                              '/HttpURLConnection/sec': {
                                                  'get': {'responses': {}}},
                                              '/HttpURLConnection/vuln': {
                                                  'get': {'responses': {}}},
                                              '/IOUtils/sec': {
                                                  'get': {'responses': {}}},
                                              '/ImageIO/sec': {
                                                  'get': {'responses': {}}},
                                              '/Jsoup/sec': {
                                                  'get': {'responses': {}}},
                                              '/ProcessBuilder': {
                                                  'get': {'responses': {}}},
                                              '/SAXBuilder/sec': {
                                                  'post': {'responses': {}}},
                                              '/SAXBuilder/vuln': {
                                                  'post': {'responses': {}}},
                                              '/SAXParser/sec': {
                                                  'post': {'responses': {}}},
                                              '/SAXParser/vuln': {
                                                  'post': {'responses': {}}},
                                              '/SAXReader/sec': {
                                                  'post': {'responses': {}}},
                                              '/SAXReader/vuln': {
                                                  'post': {'responses': {}}},
                                              '/XMLReader/sec': {
                                                  'post': {'responses': {}}},
                                              '/XMLReader/vuln': {
                                                  'post': {'responses': {}}},
                                              '/aa': {}, '/any': {
            'get': {'responses': {}}}, '/appInfo': {},
                                              '/application/javascript': {
                                                  'get': {'responses': {}}},
                                              '/classloader': {},
                                              '/codeinject': {
                                                  'get': {'responses': {}}},
                                              '/codeinject/host': {
                                                  'get': {'responses': {}}},
                                              '/codeinject/sec': {
                                                  'get': {'responses': {}}},
                                              '/commonsHttpClient/sec': {
                                                  'get': {'responses': {}}},
                                              '/createToken': {
                                                  'get': {'responses': {}}},
                                              '/deserialize': {
                                                  'post': {'responses': {}}},
                                              '/dnsrebind/vuln': {
                                                  'get': {'responses': {}}},
                                              '/exclued/vuln': {
                                                  'get': {'responses': {}}},
                                              '/fastjsonp/getToken': {
                                                  'get': {'responses': {}}},
                                              '/forward': {}, '/getName': {
            'get': {'responses': {}}}, '/getToken': {'get': {'responses': {}}},
                                              '/httpclient/sec': {
                                                  'get': {'responses': {}}},
                                              '/hutool/vuln': {
                                                  'get': {'responses': {}}},
                                              '/index': {}, '/jdbc/ps/vuln': {},
                                              '/jdbc/sec': {}, '/jdbc/vuln': {},
                                              '/jscmd': {
                                                  'get': {'responses': {}}},
                                              '/log4j': {
                                                  'get': {'responses': {}}},
                                              '/login': {}, '/logout': {
            'get': {'responses': {}}}, '/mybatis/orderby/sec04': {
            'get': {'responses': {}}}, '/mybatis/orderby/vuln03': {
            'get': {'responses': {}}}, '/mybatis/sec01': {
            'get': {'responses': {}}}, '/mybatis/sec02': {
            'get': {'responses': {}}}, '/mybatis/sec03': {
            'get': {'responses': {}}}, '/mybatis/vuln01': {
            'get': {'responses': {}}}, '/mybatis/vuln02': {
            'get': {'responses': {}}}, '/noproxy': {}, '/object2jsonp': {},
                                              '/okhttp/sec': {
                                                  'get': {'responses': {}}},
                                              '/openStream': {
                                                  'get': {'responses': {}}},
                                              '/path_traversal/sec': {
                                                  'get': {'responses': {}}},
                                              '/path_traversal/vul': {
                                                  'get': {'responses': {}}},
                                              '/pic': {
                                                  'get': {'responses': {}}},
                                              '/post': {
                                                  'post': {'responses': {}}},
                                              '/postgresql': {
                                                  'post': {'responses': {}}},
                                              '/proxy': {}, '/readxlsx': {
            'post': {'responses': {}}}, '/redirect': {'get': {'responses': {}}},
                                              '/reflect': {},
                                              '/rememberMe/security': {},
                                              '/rememberMe/vuln': {},
                                              '/request/sec': {
                                                  'get': {'responses': {}}},
                                              '/restTemplate/vuln1': {
                                                  'get': {'responses': {}}},
                                              '/restTemplate/vuln2': {
                                                  'get': {'responses': {}}},
                                              '/runtime/exec': {
                                                  'get': {'responses': {}}},
                                              '/safe': {}, '/safecode': {},
                                              '/sec': {
                                                  'get': {'responses': {}}},
                                              '/sec/array_indexOf': {
                                                  'get': {'responses': {}}},
                                              '/sec/checkOrigin': {
                                                  'get': {'responses': {}}},
                                              '/sec/checkReferer': {},
                                              '/sec/corsFilter': {},
                                              '/sec/crossOrigin': {
                                                  'get': {'responses': {}}},
                                              '/sec/httpCors': {
                                                  'get': {'responses': {}}},
                                              '/sec/originFilter': {
                                                  'get': {'responses': {}}},
                                              '/sec/webMvcConfigurer': {
                                                  'get': {'responses': {}}},
                                              '/sec/yarm': {
                                                  'get': {'responses': {}}},
                                              '/sendRedirect': {},
                                              '/sendRedirect/sec': {},
                                              '/setHeader': {
                                                  'head': {'responses': {}}},
                                              '/spel/vuln': {
                                                  'get': {'responses': {}}},
                                              '/status': {
                                                  'get': {'responses': {}}},
                                              '/stored/show': {},
                                              '/stored/store': {}, '/upload': {
            'get': {'responses': {}}, 'post': {'responses': {}}},
                                              '/upload/picture': {
                                                  'post': {'responses': {}}},
                                              '/urlConnection/sec': {
                                                  'get': {'responses': {}}},
                                              '/urlConnection/vuln': {
                                                  'get': {'responses': {}},
                                                  'post': {'responses': {}}},
                                              '/velocity': {
                                                  'get': {'responses': {}}},
                                              '/vuln/contains': {
                                                  'get': {'responses': {}}},
                                              '/vuln/crossOrigin': {},
                                              '/vuln/emptyReferer': {},
                                              '/vuln/endsWith': {
                                                  'get': {'responses': {}}},
                                              '/vuln/mappingJackson2JsonView': {},
                                              '/vuln/origin': {
                                                  'get': {'responses': {}}},
                                              '/vuln/referer': {},
                                              '/vuln/regex': {
                                                  'get': {'responses': {}}},
                                              '/vuln/setHeader': {
                                                  'get': {'responses': {}},
                                                  'head': {'responses': {}}},
                                              '/vuln/url_bypass': {
                                                  'get': {'responses': {}}},
                                              '/vuln/yarm': {
                                                  'get': {'responses': {}}},
                                              '/vuln01': {
                                                  'get': {'responses': {}}},
                                              '/vuln02': {
                                                  'get': {'responses': {}}},
                                              '/vuln03': {
                                                  'get': {'responses': {}}},
                                              '/vuln04': {
                                                  'get': {'responses': {}}},
                                              '/vuln05': {
                                                  'get': {'responses': {}}},
                                              '/vuln06': {
                                                  'get': {'responses': {}}},
                                              '/websocket/cmd': {},
                                              '/websocket/proxy': {},
                                              '/xmlReader/sec': {
                                                  'post': {'responses': {}}},
                                              '/xmlReader/vuln': {
                                                  'post': {'responses': {}}},
                                              '/xmlbeam/vuln': {
                                                  'post': {'responses': {}}},
                                              '/xstream': {
                                                  'post': {'responses': {}}}}
    assert len(js_usages_1.convert_usages()) == 114
    assert len(js_usages_2.convert_usages()) == 15
    # Airflow slice is too large to upload.
    # assert py_usages_1.convert_usages() == {
    #     '/': {}, '/dags/{dag_id}': {
    #     'parameters': [{'in': 'path', 'name': 'dag_id', 'required': True,
    #                     'schema': {'type': 'string'}}]},
    #     '/dags/{dag_id}/code': {'parameters': [
    #         {'in': 'path', 'name': 'dag_id', 'required': True,
    #          'schema': {'type': 'string'}}]}, '/dags/{dag_id}/dag_runs': {
    #         'parameters': [{'in': 'path', 'name': 'dag_id', 'required': True,
    #                         'schema': {'type': 'string'}}]},
    #     '/dags/{dag_id}/dag_runs/{'
    #     'execution_date}': {'parameters': [
    #         {'in': 'path', 'name': 'dag_id', 'required': True,
    #          'schema': {'type': 'string'}},
    #         {'in': 'path', 'name': 'execution_date', 'required': True,
    #          'schema': {'type': 'string'}}]}, '/dags/{dag_id}/dag_runs/{'
    #                                           'execution_date}/tasks/{task_id}': {
    #         'parameters': [{'in': 'path', 'name': 'dag_id', 'required': True,
    #                         'schema': {'type': 'string'}},
    #                        {'in': 'path', 'name': 'execution_date',
    #                         'required': True, 'schema': {'type': 'string'}},
    #                        {'in': 'path', 'name': 'task_id', 'required': True,
    #                         'schema': {'type': 'string'}}]},
    #     '/dags/{dag_id}/paused': {'parameters': [
    #         {'in': 'path', 'name': 'dag_id', 'required': True,
    #          'schema': {'type': 'string'}}]},
    #     '/dags/{dag_id}/paused/{paused}': {'parameters': [
    #         {'in': 'path', 'name': 'dag_id', 'required': True,
    #          'schema': {'type': 'string'}},
    #         {'in': 'path', 'name': 'paused', 'required': True,
    #          'schema': {'type': 'string'}}]},
    #     '/dags/{dag_id}/tasks/{task_id}': {'parameters': [
    #         {'in': 'path', 'name': 'dag_id', 'required': True,
    #          'schema': {'type': 'string'}},
    #         {'in': 'path', 'name': 'task_id', 'required': True,
    #          'schema': {'type': 'string'}}]}, '/info': {}, '/latest_runs': {},
    #     '/lineage/{dag_id}/{'
    #     'execution_date}': {'parameters': [
    #         {'in': 'path', 'name': 'dag_id', 'required': True,
    #          'schema': {'type': 'string'}},
    #         {'in': 'path', 'name': 'execution_date', 'required': True,
    #          'schema': {'type': 'string'}}]}, '/log/{filename}': {
    #         'parameters': [{'in': 'path', 'name': 'filename', 'required': True,
    #                         'schema': {'type': 'string'}}]}, '/pools': {},
    #     '/pools/{name}': {'parameters': [
    #         {'in': 'path', 'name': 'name', 'required': True,
    #          'schema': {'type': 'string'}}]}, '/test': {}
    #                                         }
    assert py_usages_2.convert_usages() == {'/': {}, '/auth/google': {},
                                            '/logout': {}}
