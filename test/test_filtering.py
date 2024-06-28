import pytest

from atom_tools.lib.filtering import check_reachable_purl, Filter, filter_flows, parse_filters
from atom_tools.lib.slices import AtomSlice
from atom_tools.lib.utils import check_reachable, sort_dict


@pytest.fixture
def java_usages_1():
    filter_obj = Filter('test/data/java-piggymetrics-usages.json', 'outfile.json', '90')
    filter_obj.add_filters(parse_filters('callName=testFilterQuery'))
    return filter_obj


@pytest.fixture
def java_usages_2():
    filter_obj = Filter('test/data/java-sec-code-usages.json', 'outfile.json', '90')
    filter_obj.add_filters(parse_filters('fileName=test/file/name.java'))
    return filter_obj


@pytest.fixture
def js_usages_1():
    filter_obj = Filter('test/data/js-juiceshop-usages.json', 'outfile.json', '90')
    filter_obj.add_filters(parse_filters('signature=@Pipe'))
    return filter_obj


def test_attribute_filter_class(java_usages_1, js_usages_1, java_usages_2):
    assert sort_dict(java_usages_1.filter_slice()) == {'objectSlices': [{'code': '',
                   'columnNumber': 20,
                   'fileName': 'account-service/src/main/java/com/piggymetrics/account/AccountApplication.java',
                   'fullName': 'com.piggymetrics.account.AccountApplication.<init>:void()',
                   'lineNumber': 400,
                   'signature': 'void()',
                   'usages': [{'argToCalls': [],
                               'definedBy': {'columnNumber': None,
                                             'label': 'UNKNOWN',
                                             'lineNumber': None,
                                             'name': '<empty>',
                                             'typeFullName': 'ANY'},
                               'invokedCalls': [{'callName': 'testFilterQuery',
                                                 'columnNumber': 14,
                                                 'isExternal': False,
                                                 'lineNumber': 106,
                                                 'paramTypes': [],
                                                 'resolvedMethod': 'com.piggymetrics.statistics.domain.Item.getCurrency:com.piggymetrics.statistics.domain.Currency()',
                                                 'returnType': 'ANY'},
                                                {'callName': 'getTitle',
                                                 'columnNumber': 25,
                                                 'isExternal': False,
                                                 'lineNumber': 109,
                                                 'paramTypes': [],
                                                 'resolvedMethod': 'com.piggymetrics.statistics.domain.Item.getTitle:java.lang.String()',
                                                 'returnType': 'ANY'}],
                               'targetObj': {'columnNumber': None,
                                             'label': 'UNKNOWN',
                                             'lineNumber': None,
                                             'name': '<empty>',
                                             'typeFullName': 'ANY'}}]}],
 'userDefinedTypes': []}
    assert sort_dict(js_usages_1.filter_slice()) == {
        'objectSlices': [{'code': "@Pipe({name:'challengeHint',pure:false})",
                   'columnNumber': 0,
                   'fileName': 'frontend/src/app/score-board/pipes/challenge-hint.pipe.ts',
                   'fullName': 'Pipe',
                   'lineNumber': 10,
                   'signature': '@Pipe',
                   'usages': []},
                  {'code': "@Pipe({name:'difficultySelectionSummary',pure:true})",
                   'columnNumber': 0,
                   'fileName': 'frontend/src/app/score-board/components/filter-settings/pipes/difficulty-selection-summary.pipe.ts',
                   'fullName': 'Pipe',
                   'lineNumber': 10,
                   'signature': '@Pipe',
                   'usages': []}],
 'userDefinedTypes': []}

    result = java_usages_2.filter_slice()
    result = sort_dict(result)
    assert result == {'objectSlices': [{'code': '',
                   'columnNumber': 3,
                   'fileName': 'test/file/name.java',
                   'fullName': 'org.joychou.Application.<init>:void()',
                   'lineNumber': 40,
                   'signature': 'void()',
                   'usages': [{'argToCalls': [],
                               'definedBy': {'columnNumber': None,
                                             'label': 'UNKNOWN',
                                             'lineNumber': 40,
                                             'name': '<empty>',
                                             'typeFullName': 'ANY'},
                               'invokedCalls': [],
                               'targetObj': {'columnNumber': None,
                                             'label': 'UNKNOWN',
                                             'lineNumber': 40,
                                             'name': '<empty>',
                                             'typeFullName': 'ANY'}}]}],
 'userDefinedTypes': []}


def test_check_reachable():
    atom_slice = AtomSlice('test/data/js-juiceshop-reachables.json')

    # Test package:version
    assert check_reachable(atom_slice.content, 'colors:1.6.0', '') == True
    assert check_reachable(atom_slice.content, 'colors:1.9.0', '') == False
    assert check_reachable(atom_slice.content, '@colors/colors:1.6.0', '') == True
    assert check_reachable(atom_slice.content, '@colors/colors:1.9.0', '') == False

    # Test filename:linenumber
    assert check_reachable(atom_slice.content, '', 'routes/updateUserProfile.ts:29') == True
    assert check_reachable(atom_slice.content, '', 'updateUserProfile.ts:29') == True
    assert check_reachable(atom_slice.content, '', 'routes/updateUserProfile.ts:25-30') == True
    assert check_reachable(atom_slice.content, '', 'updateUserProfile.ts:25-30') == True
    assert check_reachable(atom_slice.content, '', 'routes/updateUserProfile.ts:400') == False
    assert check_reachable(atom_slice.content, '', 'updateUserProfile.ts:400') == False
    assert check_reachable(atom_slice.content, '', 'routes/updateUserProfile.ts:400-600') == False
    assert check_reachable(atom_slice.content, '', 'updateUserProfile.ts:400-600') == False
