"""Classes and functions for filtering slices"""
import logging
import pathlib
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, Generator, List, Set, Tuple

from thefuzz import fuzz, process  # type: ignore

from atom_tools.lib.regex_utils import FilteringPatternCollection
from atom_tools.lib.slices import FlatSlice


logger = logging.getLogger(__name__)
filtering = FilteringPatternCollection()


@dataclass
class AttributeFilter:
    """Attribute filter class"""
    def __init__(self, key: str, value: str, condition: str, fuzz_pct: int | None) -> None:
        self.attribute = key.lower()
        self.value, self.line_numbers, self.fn_only = create_attribute_filter(key, value, fuzz_pct)
        self.condition = condition


class Filter:
    """Class for filtering a slice"""
    def __init__(self, slice_file: str, outfile: str, fuzz_pct: str | None) -> None:
        self.slc = FlatSlice(slice_file)
        self.outfile = outfile
        self.attribute_filters: List[AttributeFilter] = []
        self.results: List[str] = []
        self.negative_results: List[str] = []
        self.fuzz = int(fuzz_pct) if fuzz_pct else None

    def add_filters(self, filters: Generator) -> None:
        """Create a filter and add it to the relevant list"""
        for target, value, condition in filters:
            target = target.lower()
            if target not in {
                'filename',
                'fullname',
                'resolvedmethod',
                'callname',
                'name',
                'signature',
            }:
                raise ValueError(f'Unknown filter target: {target}')
            a_filter = AttributeFilter(target, value, condition, self.fuzz)
            logger.debug(f'Adding attribute filter -> {a_filter.attribute} {condition} '
                         f'{a_filter.value}')
            self.attribute_filters.append(a_filter)

    def filter_reachables(self):
        """Filter reachables"""
        raise NotImplementedError

    def filter_slice(self) -> Dict:
        """Filters the slice"""
        if self.slc.slice_type == 'usages':
            return self.filter_usages()
        if self.slc.slice_type == 'reachables':
            return self.filter_reachables()
        raise ValueError(f'Unknown slice type: {self.slc.slice_type}')

    def filter_usages(self) -> Dict:
        """Filters the usage slice"""
        if self.attribute_filters:
            for f in self.attribute_filters:
                if self.fuzz:
                    self._search_values_fuzzy(f)
                else:
                    self._search_values(f)
        if self.results:
            return self._process_slice_indexes()
        return {'objectSlices': [], 'userDefinedTypes': []}

    def _exclude_indexes(self, include: Set, exclude: Set) -> Dict:
        if include:
            filtered_slice: Dict[str, List] = {'objectSlices': [], 'userDefinedTypes': []}
            include -= exclude
            for i in include:
                if i:
                    filtered_slice[i.group('type')].append(
                        self.slc.content[i.group('type')][int(i.group('index'))])
            return filtered_slice
        return self._handle_exclude_only(exclude) if exclude else self.slc.content

    def _handle_exclude_only(self, exclude: Set[re.Match]) -> Dict:
        filtered_slice = deepcopy(self.slc.content)
        for i in exclude:
            filtered_slice[i.group('type')][int(i.group('index'))] = None
        for key, value in self.slc.content.items():
            for k, v in value.items():
                if v is None:
                    filtered_slice[key].pop(k)
        return filtered_slice

    def _process_fuzzy_results(
            self, f: AttributeFilter, result: List[Tuple[str, int, str]]) -> None:
        include = []
        exclude = []
        for i in result:
            if f.condition == '==':
                include.extend(self.slc.attrib_dicts.get(f.attribute, {}).get(i[2], []))
            else:
                exclude.extend(self.slc.attrib_dicts.get(f.attribute, {}).get(i[2], []))
        self.results.extend(list(set(include)))
        self.negative_results.extend(list(set(exclude)))

    def _process_slice_indexes(self) -> Dict:
        include_indexes = set()
        exclude_indexes = set()
        for k in self.results:
            if matched := filtering.top_level_flat_loc_index.search(k):
                include_indexes.add(matched)
        for k in self.negative_results:
            if matched := filtering.top_level_flat_loc_index.search(k):
                exclude_indexes.add(matched)
        return self._exclude_indexes(include_indexes, exclude_indexes)

    def _search_values(self, f: AttributeFilter) -> None:
        include = []
        exclude = []
        for k, v in self.slc.attrib_dicts.get(f.attribute, {}).items():
            if f.value.search(k):
                if f.condition == '==':
                    include.extend(v)
                else:
                    exclude.extend(v)
        self.results.extend(list(set(include)))
        self.negative_results.extend(list(set(exclude)))

    def _search_values_fuzzy(self, f: AttributeFilter) -> None:
        search_values = self.slc.attrib_dicts.get(f.attribute, {}).keys()
        if f.fn_only:
            search_values = {
                i: f'{pathlib.Path(i).stem}{pathlib.Path(i).suffix}'
                for i in search_values
            }
        else:
            search_values = {i: i for i in search_values}
        if result := process.extractBests(
            f.value,
            search_values,
            limit=len(search_values),
            score_cutoff=self.fuzz,
            scorer=fuzz.ratio,
        ):
            self._process_fuzzy_results(f, result)


def create_attribute_filter(key: str, value: str, fuzz_pct: int | None) -> Tuple:
    """Create an attribute filter"""
    lns = ()
    fn_only = False
    if key.lower() == 'filename' and '/' not in value and '\\' not in value:
        fn_only = True
    if ':' in value and (match := filtering.attribute_and_line.search(value)):
        value = match.group('attrib')
        lns = get_ln_range(match.group('line_nums'))
    if fuzz_pct:
        new_value = value
    else:
        if '.' in value:
            value += '$'
        new_value = re.compile(value, re.IGNORECASE)  # type: ignore
    return new_value, lns, fn_only


def get_ln_range(value: str) -> Tuple[int, int] | Tuple:
    """
    Extracts line numbers from arguments and returns a tuple of (start, end)
    """
    try:
        if '-' not in value:
            return int(value), int(value)
        values = value.split('-')
        return int(values[0]), int(values[1])
    except ValueError:
        logger.warning(f'Ignoring invalid line number: {value}.')
    return ()


def parse_filters(filter_options: str) -> Generator[Tuple[str, str, str], None, None]:
    """Parse file filters"""
    options = filter_options.split(',')
    for i in options:
        condition = '='
        if '!=' in i:
            condition = '!='
        target, value = i.strip().split(condition)
        if condition == '=':
            condition = '=='
        yield target, value, condition
