from atom_tools.lib.converter import BomFile, OpenAPI


def test_bomfile_class():
    # test bom file with services
    bom = BomFile('data/bom.json')
    assert bom.services[0] == {
        'endpoints': ['/safecode'],
        'name': 'org-joychou-controller-CRLFInjection-crlf-service'}
    assert len(bom.generate_endpoints()) == 127

    # test bom file no services
    bom = BomFile('data/bom_no_svcs.json')
    assert bom.services is None
    assert len(bom.generate_endpoints()) == 0

    # test no bom file included
    bom = BomFile(None)
    assert bom.services is None

    # test invalid bom file
    bom = BomFile('data/invalid_bom.json')
    assert bom.services is None


def test_openapi_class():
    openapi = OpenAPI(
        'openapi3.1.0',
        'data/bom.json',
        'java',
        'data/usages.json')
    assert openapi.openapi_version == '3.1.0'
