"""Classes and functions to validate source file line numbers in an atom slice file."""

import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, List, Dict

import jmespath

from atom_tools.lib.slices import AtomSlice
from atom_tools.lib.regex_utils import ValidationRegexCollection


logger = logging.getLogger(__name__)
regex: ValidationRegexCollection = ValidationRegexCollection()
operator_map: Dict[str, List[str]] = {
    '<operator>.addition': ['+'],
    '<operator>.minus': ['-'],
    '<operator>.multiplication': ['*'],
    '<operator>.division': ['/'],
    '<operator>.lessThan': ['<'],
    '<operator>.notEquals': ['!='],
    '<operator>.indexAccess': [':'],
    '<operator>.logicalNot': ['!', ' not '],
    '<operator>.logicalOr': ['||', ' or '],
    '<operator>.throw': ['throw'],
    '<operator>.plus': ['+'],
    '<operator>.formatString': ['`$', 'f"', "f'"],
    '<operator>.conditional': ['?', 'if ', 'elif ', ' else '],
    '<operator>.new': ['new ', '<init>'],
    '<operator>.assignmentDivision': ['/='],
    '<operator>.in': [' in '],
    '<operator>.listLiteral': ['= []', '= ['],
    '<operator>.starredUnpack': ['*'],
    '<operator>.greaterThan': ['>'],
    '<operator>.logicalAnd': ['&&', ' and '],
    '<operator>.postIncrement': ['++'],
    '<operator>.fieldAccess': [':'],
    '<operator>.assignmentMinus': ['-='],
    '<operator>.assignmentMultiplication': ['*='],
    '<operator>.modulo': ['%'],
    '<operator>.iterator': ['for'],
    '<operator>.assignmentPlus': ['+='],
    '<operator>.instanceOf': ['instanceof'],
    '<operator>.subtraction': ['-'],
    '<operator>.equals': ['='],
}
ecma_map: Dict[str, List[str]] = {
    '__ecma.Array.factory': ['[]'],
    '__ecma.Set:<operator>.new': ['new Set('],
    '__ecma.String[]:sort': ['.sort'],
    '__ecma.Array.factory:splice': ['.splice'],
    '__ecma.Array.factory:push': ['.push'],
    '__ecma.Number:toString': ['.toString'],
    '__ecma.Math:floor': ['.floor'],
    '__ecma.String:toLowerCase': ['.toLowerCase'],
}
init_map: List[str] = ['new ', 'super ', 'private ', 'public ', 'constructor ']
py_builtins: Dict[str, str] = {
    '__builtin.str.split': '.split(',
    '__builtin.str.join': '.join(',
    '__builtin.getattr': 'getattr(',
    '__builtin.open': 'with open(',
    '__builtin.print': 'print(',
    '__builtin.str.format': '.format(',
    '__builtin.list': '= [',
    '__builtin.str.replace': '.replace(',
    '__builtin.set<meta>': 'set(',
    '__builtin.len': 'len(',
    '__builtin.list.append': '.append(',
    '__builtin.str.startswith': '.startswith(',
    '__builtin.list<meta>': 'list(',
    '__builtin.set.add': '.add(',
    '__builtin.str.lstrip': '.lstrip(',
    '__builtin.list.extend': '.extend(',
}


def check_init(line: str) -> bool:
    """
    Check if a given line contains any of the specified initialization patterns.

    Args:
        line (str): The line to check for a match.

    Returns:
        bool: True if the line contains any of the specified initialization patterns.
    """
    return any(i in line for i in init_map)


def check_mapping_type(function_name: str, code: str, line: str, mapping: Dict) -> bool:
    """
    Check if a given line contains any of the specified mapping types.

    Args:
        function_name (str): The name of the function to match against.
        code (str): The code snippet to analyze.
        line (str): The line to check for a match.
        mapping (dict): A mapping of function names or codes to types.

    Returns:
        bool: True if the line contains any of the specified mapping types, False otherwise.
    """
    op = mapping.get(function_name) or mapping.get(code)
    return any(i in line for i in op) if op else False


def check_py_builtins(code: str, line: str) -> bool:
    """Checks if Python builtin function is present"""
    return builtin in line if (builtin := py_builtins.get(code)) else False


def check_py_module_members(code: str, line: str) -> bool:
    """
    Check if a given line matches the definition of a Python module member.

    Args:
        code (str): The code snippet to analyze.
        line (str): The line to check for a match.

    Returns:
        bool: True if the line matches a Python module member, False otherwise.
    """
    match = regex.py_mod_members.search(code)
    if not match:
        return False
    if func := match.group('func'):
        obj_type = f'def {func}('
    elif a_class := match.group('class'):
        obj_type = f'class {a_class}'
    else:
        return False

    return bool(line.startswith(obj_type))


def cleanup_usages(usages: Dict[str, List[Dict[str, str]]]) -> Dict[str, List[Dict[str, str]]]:
    """
    Removes entries with no code, function_name, or line_number as there is nothing to validate.

    Args:
        usages (dict): The usage slices consolidated by file.

    Returns:
        dict: The cleaned up usages.
    """
    for fn, entries in usages.items():
        if keep := [
            entries[e]
            for e in range(len(entries) - 1)
            if entries[e]['code'] or entries[e]['function_name'] or entries[e]['line_number']
        ]:
            usages[fn] = keep

    return usages


def consolidate_reachable_slices(data: List[Dict]) -> Dict[str, List[Dict[str, str]]]:
    """Consolidate reachables by parent file name."""
    consolidated: Dict[str, List[Dict]] = {}
    for i in data:
        fn = i.get('file_name') or 'unknown'
        if fn in consolidated:
            consolidated[fn].append(i)
        else:
            consolidated[fn] = [i]
    return consolidated


def consolidate_usage_slices(data: List[Dict]) -> Dict[str, List[Dict[str, str]]]:
    """
    Consolidate data by file, grouping related entries together.

    Args:
        data (list): A list of dictionaries representing data entries.

    Returns:
        dict: A dictionary containing consolidated data entries grouped by file.
    """
    consolidated: Dict = {}
    for i in data:
        fn = i.get('file_name') or 'unknown'
        root_entry = {
            'function_name': i.get('signature'),
            'code': i.get('code'),
            'line_number': i.get('line_number'),
        }
        if fn in consolidated:
            consolidated[fn].append(root_entry)
        else:
            consolidated[fn] = [root_entry]
        consolidated[fn].extend(i.get('usages', []))
    return cleanup_usages(consolidated)


def java_validation_helper(func: str, line: str) -> bool:
    """
    Check if a given line contains a Java library type or user-defined type.

    Args:
        func (str): The function to match against.
        line (str): The line to check for a match.

    Returns:
        bool: True if the line contains a match, False otherwise.
    """
    if match := regex.java_lib_type.search(func):
        if match.group('type') in line:
            return True
    elif match := regex.java_udt_regex.search(func):
        if match.group('udt') in line:
            return True
    return False


def js_validation_helper(function_name: str, code: str, line: str) -> bool:
    """
    Check if a given line matches specific patterns for JavaScript function names.

    Args:
        function_name (str): The name of the function to match against.
        code (str): The code snippet to analyze.
        line (str): The line to check for a match.

    Returns:
        bool: True if the line matches the specified patterns, False otherwise.
    """
    if function_name == 'require':
        if line == 'import {' or not code.startswith('require'):
            return True
        code = code.replace('"', '').replace("'", "")
        a = regex.js_require_extract.search(code)
        b = regex.js_import.search(line)
        if a and b and a.group('mod') in b.group('lib'):
            return True
    elif function_name.startswith('__ecma'):
        return check_mapping_type(function_name, code, line, ecma_map)
    # elif function_name.startswith('_tmp') and '.' in function_name:
    #     a = function_name.split('.')[1]
    #     if a in line:
    #         return True
    elif line.endswith('{') and '{' in function_name:
        function_name = function_name.split('{')[0]
        if function_name in line:
            return True

    return False


def py_validation_helper(function_name: str, code: str, line: str) -> bool:
    """
    Check if a given line contains specific patterns that match a Python function or class.

    Args:
        function_name (str): The name of the function to match against.
        code (str): The code snippet to analyze.
        line (str): The line to check for a match.

    Returns:
        bool: True if the line contains a match, False otherwise.
    """
    if '<module>' in code:
        return check_py_module_members(code, line)
    found = False
    if code.startswith('__builtin'):
        return check_py_builtins(code, line)
    if code.startswith('class '):
        code = code.replace('<meta>', '')
        found = code in line
    if function_name.startswith('__newInstance') and '__init__(' in line:
        return True
    if function_name.startswith('tmp'):
        for i in ('.get', '.keys', '.values', '.items', 'return ['):
            if i in line:
                return True
    if ('__iter__' in function_name or '__next__' in function_name) and 'for ' in line:
        found = True
    return found


def remove_duplicates_list(obj: List[Dict]) -> List[Dict]:
    """Removes duplicates from a list of dictionaries."""
    if not obj:
        return obj
    unique_objs = []
    seen = set()
    for o in obj:
        key = tuple(o.get(k) for k, v in o.items())
        if key not in seen:
            unique_objs.append(o)
            seen.add(key)
    return unique_objs


@dataclass(init=True)
class LineStats:
    """
    A data class representing statistics for a line validation process.

    Attributes:
        close_match_ct (int): Line numbers with matches within interval range.
        file_error_ct (int): Line numbers that could not be verified due to file errors.
        invalid_ln_ct (int): Line numbers that couldn't possibly match the given file.
        matched_ct (int): Line numbers with exact matches.
        no_ln_ct (int): Missing line numbers.
        unmatched_ct (int): Line numbers with no match.

    Properties:
        accuracy (str): The accuracy of the line numbers analyzed as a percentage.
        matched_perc (tuple): matched/total_valid, close/total_valid
        total_analyzed (int): total_valid + total_invalid + file_error_ct
        total_invalid (int): unmatched + missing + invalid
        total_valid (int): matched_ct + close_match_ct
        unmatched_perc (tuple): percentage of total_invalid for each type of invalid
    """
    close_match_ct: int = 0
    file_error_ct: int = 0
    invalid_ln_ct: int = 0
    matched_ct: int = 0
    no_ln_ct: int = 0
    unmatched_ct: int = 0

    @property
    def accuracy(self) -> str:
        """Returns accuracy in percentage format"""
        return f'{self.total_valid / self.total_analyzed:.2%}'

    @property
    def matched_perc(self) -> Tuple[str, str]:
        """Returns validated percentage breakdown"""
        matched = f'{self.matched_ct / self.total_valid:.2%}'
        close = f'{self.close_match_ct / self.total_valid:.2%}'
        return matched, close

    @property
    def total_analyzed(self) -> int:
        """Returns total analyzed"""
        return self.total_valid + self.total_invalid

    @property
    def total_invalid(self) -> int:
        """Returns total not validated"""
        return self.unmatched_ct + self.invalid_ln_ct + self.no_ln_ct + self.file_error_ct

    @property
    def total_valid(self) -> int:
        """Returns total validated"""
        return self.matched_ct + self.close_match_ct

    @property
    def unmatched_perc(self) -> Tuple[str, str, str]:
        """Returns invalid percentage breakdown"""
        unmatched = f'{self.unmatched_ct / self.total_invalid:.2%}'
        invalid_ln = f'{self.invalid_ln_ct / self.total_invalid:.2%}'
        no_ln = f'{self.no_ln_ct / self.total_invalid:.2%}'
        # file_err = '{:.2%}'.format(self.file_error_ct / self.total_invalid)
        return unmatched, invalid_ln, no_ln

    def update(self, matched_count: int, unmatched_count: int, close_match_count: int,  # pylint: disable=too-many-arguments
               no_ln_count: int, file_error_count: int, invalid_ln_count: int) -> None:
        """
        Sets counts for statistic calculations
        """
        self.matched_ct += matched_count
        self.unmatched_ct += unmatched_count
        self.close_match_ct += close_match_count
        self.no_ln_ct += no_ln_count
        self.file_error_ct += file_error_count
        self.invalid_ln_ct += invalid_ln_count


class LineValidator:
    """
    A class for validating line numbers in code files.

    Args:
        base_path (str or Path): The base path for the code files.
        interval (int): The interval for expanding the search range.
        origin_type (str): The origin type of the code files.
        slice_file (str): The path to the slice file.

    Attributes:
        base_path (Path): The base path for the code files.
        interval (int): The interval for expanding the search range.
        matches (dict): A dictionary containing matched line numbers grouped by type.
        problem_files (list): A dictionary containing problem files.
        slc (AtomSlice): An instance of AtomSlice representing the slice file.
        unverifiable (dict): A dictionary containing unverifiable line numbers grouped by type.
    """
    def __init__(self, slice_file: Path, base_path: Path, interval: int, origin_type: str) -> None:
        self.slc = AtomSlice(slice_file, origin_type)
        self.base_path = base_path if isinstance(base_path, Path) else Path(base_path)
        self.matches: Dict[str, List[Dict]] = {
            'matched': [], 'unmatched': [], 'close': [], 'likely_ok': []}
        self.unverifiable: Dict[str, List[Dict]] = {
            'missing': [], 'file': [], 'range': [], 'no_data': []}
        self.problem_files: List[str] = []
        self.interval = interval

    def create_summary(self, stats: LineStats) -> str:
        """
        Creates a summary of the results of the line number validation.

        Args:
            stats (LineStats): The line number validation statistics.

        Returns:
            str: A summary of the results of the line number validation.
        """
        summary = f'\n*** VALIDATION SUMMARY ***\nAccuracy: {stats.accuracy}\n'
        if stats.file_error_ct > 0:
            summary += (f'{stats.file_error_ct} line numbers could not be checked due to issues '
                        f'with the source file.\n')
        summary += (
            f'\n*** MATCHED ***\n{stats.total_valid} slice line numbers were validated.\n\t'
            f'{stats.matched_perc[0]} were matches at exact line numbers.\n\t'
            f'{stats.matched_perc[1]} were inexact matches within {self.interval} lines of the '
            f'expected line number.\n'
        )
        summary += (f'\n*** UNMATCHED ***\n{stats.total_invalid} line numbers were invalid.\n\t'
                    f'{stats.unmatched_perc[0]} of these were just not found in the expected range'
                    f' of line numbers.\n\t{stats.unmatched_perc[1]} of these had line numbers '
                    f'exceeding the lines in the given file.\n\t{stats.unmatched_perc[2]} of these'
                    f' had missing line numbers.\n')
        return summary

    def export_validation_results(self, json_report_path):
        """
        Export details for the validation results to a JSON file.
        """
        results = {
            'valid': {'exact': self.matches['matched'], 'close': self.matches['close']},
            'invalid': {
                'missing_line_number': self.unverifiable['missing'],
                'not_found': self.matches['unmatched'],
                'invalid_line_number': self.unverifiable['range']
            },
            'inaccessible_files': [str(i) for i in self.problem_files]
        }
        with open(json_report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=4)

    def find_reachables(self) -> Dict[str, List[Dict[str, str]]]:
        """Collect reachables for analysis."""
        reachables_pattern = jmespath.compile('reachables[].flows[].{function_name: fullName, '
                                              'code: code, file_name: parentFileName, '
                                              'line_number: lineNumber}')
        res = reachables_pattern.search(self.slc.content)
        return consolidate_reachable_slices(res)

    def find_usages(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Collects usage slices for analysis
        Returns:
             Dict[str, List[Dict[str, str]]]: A list of usage slices
        """
        usages_pattern = jmespath.compile('objectSlices[].{signature: signature, code: code, '
                                          'file_name: fileName, line_number: lineNumber, '
                                          'usages: usages[].*[][].{function_name: name || '
                                          'callName, line_number: lineNumber, '
                                          'code: resolvedMethod || code}}')
        udts_pattern = jmespath.compile('userDefinedTypes[].{file_name: fileName, usages: *[].{'
                                        'function_name: name || callName, code: typeFullName || '
                                        'resolvedMethod, line_number: lineNumber}}')
        res = usages_pattern.search(self.slc.content)
        res.extend(udts_pattern.search(self.slc.content))
        return consolidate_usage_slices(res)

    def get_results(self) -> str:
        """
        Collect results and return a summary
        """
        stats = LineStats()
        stats.update(
            matched_count=len(self.matches["matched"]),
            unmatched_count=len(self.matches["unmatched"]),
            close_match_count=len(self.matches["close"]),
            no_ln_count=len(self.unverifiable["missing"]),
            file_error_count=len(self.unverifiable["file"]),
            invalid_ln_count=len(self.unverifiable["range"])
        )
        return self.create_summary(stats)

    def validate_line_numbers(self) -> None:
        """Validate line numbers in the slice file"""
        if self.slc.slice_type == 'reachables':
            data = self.find_reachables()
        elif self.slc.slice_type == 'usages':
            data = self.find_usages()
        else:
            print("Cannot analyze unidentified slice type.")
            sys.exit(1)

        output = self._remove_dupes(data)

        for fn, val in output.items():
            file_path = self.base_path / fn

            if regex.tests_regex.search(fn):
                logger.debug(f'Skipping test file: {file_path}',)
                continue

            if not file_path or not os.path.isfile(file_path):
                self.problem_files.append(file_path)
                self.unverifiable['file'].extend(val)
                logger.warning(f'Could not locate {file_path}.')
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    lines = file.readlines()
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'rb') as file:
                        lines = file.readlines()  # type: ignore[assignment]
                    if lines and isinstance(lines[0], bytes):
                        lines = [i.decode for i in lines]
                except Exception:  # pylint: disable=broad-exception-caught
                    self.problem_files.append(file_path)
                    self.unverifiable['file'].extend(val)
                    continue
            file_path = str(file_path)
            for v in val:
                self._validate_line_number(v, lines, file_path)

    def write_report(self, report_file: str, summary: str, verbose: bool) -> None:
        """Write the validation report to a file."""
        logger.debug(f"Writing report to {report_file}.")
        if verbose and (vresults := self._get_verbose_results()):
            summary += vresults
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(summary)

    def _expand_search(
            self, code: str, function_name: str, line_number: int, lines: List[str], file_name: str
    ) -> bool:
        """
        Expand the search range.
        """
        start = line_number - self.interval
        # We don't want to exceed the file bounds
        start = max(start, 0)
        end = min(line_number + self.interval, len(lines))
        for n in range(start, end):
            if self._find_line(code.strip(), function_name.strip(), lines[n]):
                self.matches['close'].append(
                    {
                        'function_name': function_name,
                        'code': code,
                        'line_number': line_number,
                        'actual_number': n - 1,
                        'file_name': file_name,
                        'found_line': lines[n].strip()
                    }
                )
                return True
        return False

    def _find_line(self, code: str, function_name: str, line: str) -> bool:
        """
        First pass verification attempt.
        """
        found = False
        if not code and function_name:
            code = function_name
        if not function_name:
            function_name = code
        if len(function_name) == 1 and (match := regex.single_char_var.findall(line)):
            if function_name in match:
                found = True
        elif function_name in line and len(function_name) >= 2:
            found = True
        elif function_name == '<init>' or function_name.startswith('__init__'):
            found = check_init(line)
        elif function_name.startswith('<operator>.') or code.startswith('<operator>.'):
            found = check_mapping_type(function_name, code, line, operator_map)
        elif function_name.startswith('$obj') and 'new ' in line:
            found = True
        elif code.startswith(line) or code.startswith(line.replace('return ', '')):
            found = True
        return found or self._match_by_lang(code, function_name, line)

    def _get_verbose_results(self):
        """
        Add the verbose results of the line number validation.

        Args:
            f: The file object to write the results to.
        """
        verbose_results = '\n*** INVALID ENTRIES ***\n'
        for i in self.matches['unmatched']:
            for k, v in i.items():
                try:
                    verbose_results += f'{k}: {v}\n'
                except UnicodeEncodeError:
                    new_v = v.encode('utf-8')
                    verbose_results += f'{k}: {new_v}\n'
            verbose_results += '\n'
        verbose_results += '\n\n*** VALID BUT INEXACT ENTRIES ***\n'
        for i in self.matches['close']:
            for k, v in i.items():
                try:
                    verbose_results += f'{k}: {v}\n'
                except UnicodeEncodeError:
                    new_v = v.encode('utf-8')
                    verbose_results += f'{k}: {new_v}\n'
            verbose_results += '\n'
        verbose_results += '\n\n*** VALID ENTRIES ***\n'
        for i in self.matches["matched"]:
            for k, v in i.items():
                try:
                    verbose_results += f'{k}: {v}\n'
                except UnicodeEncodeError:
                    new_v = v.encode('utf-8')
                    verbose_results += f'{k}: {new_v}\n'
            verbose_results += '\n'
        return verbose_results

    def _match_by_lang(self, code: str, function_name: str, line: str) -> bool:
        """
        Second pass verification attempt.
        """
        found = False
        match self.slc.origin_type:
            case 'java':
                found = java_validation_helper(function_name, line)
            case 'js' | 'javascript' | 'ts' | 'typescript':
                found = js_validation_helper(function_name, code, line)
            case 'py' | 'python':
                found = py_validation_helper(function_name, code, line)
        return found

    @staticmethod
    def _remove_dupes(result: Dict) -> Dict:
        """Remove duplicates from the result dictionary."""
        for fn, val in result.items():
            result[fn] = remove_duplicates_list(val)
        return result

    def _validate_line_number(self, result: Dict, lines: List[str], file_name: str) -> None:
        """
        Run validation for a slice line number.
        """
        function_name = result.get('function_name') or ''
        function_name = function_name.lstrip().replace('this.', '')
        code = result.get('code') or ''
        code = code.lstrip()
        line_number = result.get('line_number')

        if (not function_name or function_name == '<empty>') and not code:
            self.unverifiable['no_data'].append(result)
            return

        if not line_number:
            self.unverifiable['missing'].append(result)
            return

        if len(lines) < line_number:
            self.unverifiable['range'].append(result)
            return

        line = lines[line_number - 1].strip()
        if self._find_line(code.strip(), function_name.strip(), line):
            self.matches['matched'].append(result)
            return
        if self.interval > 0 and self._expand_search(
                code, function_name, line_number, lines, file_name):
            return
        self.matches['unmatched'].append(
            {
                'function_name': function_name,
                'code': code,
                'line_number': line_number,
                'file_name': file_name,
                'file_line': line
            }
        )
