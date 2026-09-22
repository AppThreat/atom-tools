# Lesson 5: Filter

Slices are big. The cdxgen usages slice holds 4,897 object slices; you almost
always want three of them. The filter command narrows a slice down by
attributes, writes the result as a slice of the same shape, and can hand its
output straight to another command.

## The criteria syntax

A criterion is `attribute=value`, several criteria separate with commas, and
the value is a Python regular expression by default:

```console
$ atom-tools filter -i cdxgen-reports/cdxgen.usages.json \
      --criteria filename=purl.js -o filtered-usages.json
Filtered slice written to filtered-usages.json.
```

The match is a search, not equality: `purl.js` as a pattern matches any file
name containing it, so `lib/inventory/purl.js` and a hypothetical
`tools/purl.js.bak` both survive. The result keeps the shape and can be checked:

```console
$ python3 -c "
import json
d = json.load(open('filtered-usages.json'))
print(len(d['objectSlices']), 'object slices')
print(d['objectSlices'][0]['fullName'])
"
25 object slices
lib/inventory/purl.js::program:npmPurl
```

From 4,897 slices to the 25 that live in cdxgen's purl inventory module.

The searchable attributes differ per slice type. On usages slices, filter
searches `callName`, `fileName`, `fullName`, `name`, `resolvedMethod` and
`signature`, each over the specific sub-tables listed in the README's attribute
table (`objectSlices.usages.invokedCalls` for callName, and so on). On
reachables slices the useful criteria are `purl` (matching both
`reachables.purls` and flow tags) plus the shared file and method attributes.

## Anchors, word boundaries, and the fuzzy alternative

Because values are regexes, the usual anchoring idioms apply when you need
precision. `^lib/` keeps only the lib tree. `\bpurl\.js$` matches a file
exactly named purl.js and refuses `fdpurl.jsx`. When matching by name alone,
the fuzzy mode often reads better: `-f 100` with a plain value demands a 100
percent match instead of interpreting it as a pattern, and lower percentages
tolerate typos:

```console
$ atom-tools filter -i cdxgen-reports/cdxgen.usages.json -f 100 \
      --criteria filename=purl.js -o exact-usages.json
```

Fuzzy ratios are computed on the file name part only when the criterion is a
file name, so the path prefix does not penalise the match.

## Exclusion

Prefix the attribute with `!` to exclude instead of include. Exclusions refine
an inclusion in the same criteria list; the practical shape is "these files,
minus those":

```console
$ atom-tools filter -i cdxgen-reports/cdxgen.usages.json \
      --criteria "filename=^lib/,filename!=repotests" -o usages-lib.json
Filtered slice written to usages-lib.json.

$ python3 -c "
import json
d = json.load(open('usages-lib.json'))
s = d['objectSlices']
print(len(s), 'slices,', sum(1 for o in s if 'repotests' in o['fullName']), 'repotests')
"
4526 slices, 0 repotests
```

Everything under `lib/` except the repotest fixtures inside it. A criteria list
that contains only exclusions produces an empty document rather than
"everything except", which is worth knowing before you script around it.

## Inclusive or, and chaining for and

Multiple criteria in one list combine as inclusive or: a slice survives if any
criterion matches it. When several conditions must all hold, chain filter
invocations with `-e`, which runs the named command against the filtered
result. The README's example remains the canonical shape:

```console
$ atom-tools filter -i slices.json \
      --criteria filename=myfile \
      -e "filter --criteria resolvedMethod=mymethod,resolvedMethod=mymethod2 convert"
```

which reads as `fileName.contains('myfile') and (resolvedMethod contains
'mymethod' or 'mymethod2')`. The chain terminates in whatever command you
name; with the default `export` the filtered slice is simply written out.

The natural cdxgen chaining, narrowing to the inventory modules and producing
an OpenAPI document from just them:

```console
$ atom-tools filter -i cdxgen-reports/cdxgen.usages.json \
      --criteria "filename=^lib/inventory/" \
      -e "convert -f openapi3.0.1 -o openapi_inventory.json -t js"
```

## Filtering reachables by package

On reachables slices, `-p/--package-version` filters to flows touching the
given `name:version`, several separated by commas:

```console
$ atom-tools filter -i test/data/chunked/js-juiceshop-reachables.json \
      -p "@colors/colors:1.6.0,body-parser:1.20.1" -o colors-flows.json
```

This is the bulk form of lesson 4's check-reachable: instead of a yes-or-no,
you get the slice subset to feed to visualize or SARIF conversion.

## Exercises

Filter the cdxgen usages slice to the managers (`^lib/managers/`) and count
their object slices; then exclude `binary.js` from that set and count again.
Finally, reproduce the README's exact-match warning: filter with
`filename=server.ts` versus `filename=\bserver.ts$` on a slice you know
contains an `ftpserver.ts`, and observe the difference.
