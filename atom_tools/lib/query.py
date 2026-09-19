"""dosai's compact query grammar, ported onto the unified model.

The grammar is Dosai's (``Dosai/DosaiQueryEngine.cs``), kept operator-for-
operator so the same filter syntax works across engines:

    collection[property op value && …] [sort by property [desc]] [count]

- Operators, tried in this order (order matters: ``a>=b`` must parse as
  ``>=``, never as ``>`` followed by ``=b``): ``~=  !=  >=  <=  =  >  <``.
- ``~=`` is a case-insensitive "contains"; ``=``/``!=`` compare
  case-insensitively; ``> >= < <=`` compare numerically and never match
  non-numeric values.
- A term that carries no operator defaults to ``= true``.
- Conjuncts separated by ``&&`` AND together; terms separated by ``||``
  inside a conjunct OR. Property paths are dotted and case-insensitive; a
  property whose value is a list matches when any element matches.
- Postfixes: ``sort by property [desc]`` (stable; items missing the property
  sort last in both directions) and ``count``.
- Values may be wrapped in single or double quotes.

Deliberate differences from dosai (also stated in the ``explain`` help text):
the collections are the unified model's — ``flows``, ``endpoints``,
``packages`` — rather than dosai's report paths, and a flow's dict form adds
``source`` and ``sink`` objects (its first and last node) plus ``steps``
(its node count) as resolvable paths, so ``flows[source.tags~=secret]`` and
``flows[steps>=4]`` work. Everything else matches the C# engine's semantics
exactly.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Match order is the grammar; do not reorder.
OPERATORS = ("~=", "!=", ">=", "<=", "=", ">", "<")


@dataclass
class Term:
    """One ``property op value`` comparison inside a query."""

    property: str
    op: str
    value: str


@dataclass
class Query:
    """A parsed query: collection, filter groups, sort and aggregate."""

    collection: str
    groups: List[List[Term]] = field(default_factory=list)
    sort_property: Optional[str] = None
    sort_descending: bool = False
    count_mode: bool = False

    @property
    def text(self) -> str:
        return " && ".join(
            " || ".join(f"{t.property}{t.op}{t.value}" for t in group) for group in self.groups
        )


def _trim_quotes(value: str) -> str:
    return value.strip().strip("\"'")


def _parse_filter(term: str) -> Term:
    """dosai's ParseFilter: first operator (in match order) at index > 0 wins."""
    for op in OPERATORS:
        index = term.find(op)
        if index > 0:
            return Term(
                property=term[:index].strip(),
                op=op,
                value=_trim_quotes(term[index + len(op) :].strip()),
            )
    return Term(property=term.strip(), op="=", value="true")


def parse_query(query: str, collections: Sequence[str]) -> Query:
    """
    Parse ``collection[terms] sort by p [desc] [count]`` against known collections.

    Mirrors dosai's ParseQuery: with brackets the head is everything before the
    first ``[`` and the filter text runs to the *last* ``]``; without brackets
    the head is the first whitespace-delimited token.
    """
    query = query.strip()
    if not query:
        raise ValueError("Empty query.")
    bracket = query.find("[")
    if bracket >= 0:
        head = query[:bracket].strip()
        tail = query[bracket:]
    else:
        first_space = query.find(" ")
        head = query if first_space < 0 else query[:first_space].strip()
        tail = "" if first_space < 0 else query[first_space:]

    if "." in head:
        raise ValueError(
            f"Unknown collection: {head!r}. Known: {', '.join(collections)}."
            " (Unlike dosai, collections here are the unified model's top-level"
            " lists, so dotted collection paths are not accepted.)"
        )
    if head.lower() not in {c.lower() for c in collections}:
        raise ValueError(f"Unknown collection: {head!r}. Known: {', '.join(collections)}")
    collection = next(c for c in collections if c.lower() == head.lower())

    end = tail.rfind("]")
    filter_text = tail[1:end] if end >= 0 else ""
    remainder = tail[end + 1 :].strip() if end >= 0 else tail.strip()

    groups: List[List[Term]] = []
    for conjunct in (p for p in filter_text.split("&&") if p.strip()):
        terms = [_parse_filter(p) for p in (q for q in conjunct.split("||") if q.strip())]
        if terms:
            groups.append(terms)
    for group in groups:
        for term in group:
            if not term.property:
                raise ValueError(f"Query term with no property: {term!r}")

    sort_property: Optional[str] = None
    sort_descending = False
    count_mode = False
    words = [w for w in remainder.split(" ") if w]
    index = 0
    while index < len(words):
        word = words[index]
        if word.lower() == "count":
            count_mode = True
        elif (
            word.lower() == "sort"
            and index + 2 < len(words)
            and words[index + 1].lower() == "by"
        ):
            sort_property = words[index + 2]
            index += 2
            if index + 1 < len(words) and words[index + 1].lower() == "desc":
                sort_descending = True
                index += 1
        index += 1
    return Query(
        collection=collection,
        groups=groups,
        sort_property=sort_property,
        sort_descending=sort_descending,
        count_mode=count_mode,
    )


def _resolve(item: Any, path: str) -> Tuple[bool, Any]:
    """Walk a dotted, case-insensitive property path (dosai's TryResolvePath)."""
    value = item
    for part in (p for p in path.split(".") if p.strip()):
        if not isinstance(value, dict):
            return False, None
        found = next((k for k in value if isinstance(k, str) and k.lower() == part.lower()), None)
        if found is None:
            return False, None
        value = value[found]
    return True, value


def _scalar_text(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def _compare_scalar(value: Any, op: str, expected: str) -> bool:
    actual = _scalar_text(value)
    try:
        actual_number = float(actual)
        expected_number = float(expected)
    except ValueError:
        if op == "=":
            return actual.lower() == expected.lower()
        if op == "!=":
            return actual.lower() != expected.lower()
        if op == "~=":
            return expected.lower() in actual.lower()
        return False
    return {
        "=": actual_number == expected_number,
        "!=": actual_number != expected_number,
        ">": actual_number > expected_number,
        "<": actual_number < expected_number,
        ">=": actual_number >= expected_number,
        "<=": actual_number <= expected_number,
        "~=": expected.lower() in actual.lower(),
    }[op]


def _compare(value: Any, op: str, expected: str) -> bool:
    if isinstance(value, (list, tuple)):
        return any(_compare_scalar(element, op, expected) for element in value)
    return _compare_scalar(value, op, expected)


def _matches(item: Dict, groups: List[List[Term]]) -> bool:
    # Conjuncts AND, terms inside a conjunct OR — dosai's Matches.
    return all(
        any(
            (found := _resolve(item, term.property))[0] and _compare(found[1], term.op, term.value)
            for term in group
        )
        for group in groups
    )


def _sort_key(item: Dict, property: str) -> Tuple[bool, float, str]:
    """dosai's SortKey: numbers and bools numeric, strings ordinal (lowered).

    The first element is False for items missing the property so they can be
    sorted last in both directions; numeric values carry an empty text key so
    they order before strings at the same number (dosai's null-text rule).
    """
    found, value = _resolve(item, property)
    if not found or value is None:
        return False, 0.0, ""
    if isinstance(value, bool):
        return True, 1.0 if value else 0.0, ""
    if isinstance(value, (int, float)):
        return True, float(value), ""
    return True, 0.0, str(value).lower()


def run_query(items_by_collection: Dict[str, List[Dict]], query: str) -> Dict:
    """Run one query over the collections; returns matches and how they were ordered.

    Returns ``{"query", "collection", "count", "items"}`` where ``items`` is
    ordered by the query's own constraints first (model order), then any
    ``sort by`` postfix, and empty in count mode.
    """
    parsed = parse_query(query, sorted(items_by_collection))
    items = [item for item in items_by_collection[parsed.collection] if _matches(item, parsed.groups)]
    if parsed.sort_property:
        keyed = [(_sort_key(item, parsed.sort_property), item) for item in items]
        with_value = [(k, item) for k, item in keyed if k[0]]
        without_value = [item for k, item in keyed if not k[0]]
        with_value.sort(key=lambda pair: pair[0][1:], reverse=parsed.sort_descending)
        items = [item for _, item in with_value] + without_value
    return {
        "query": query,
        "collection": parsed.collection,
        "count": len(items),
        "countMode": parsed.count_mode,
        "items": [] if parsed.count_mode else items,
    }
