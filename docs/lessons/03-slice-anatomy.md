# Lesson 3: Anatomy of a slice

Commands come and go; the file formats are what you actually work with. This
lesson reads the two artefacts from lesson 2 field by field, using real excerpts
from the cdxgen run. Keep this page open when you write queries against slices;
every filter criterion, every SARIF anchor and every diagram label comes from
the fields described here.

## The reachables slice: a bare array of flow groups

`cdxgen.reachables.json` is a JSON array. There is no envelope, no metadata
block: 790 objects, each a flow group. Every command that consumes reachables
accepts this bare array, atom's own `{"reachables": [...]}` envelope, and globs
over chunked files, interchangeably.

A small group from the express app shows the full shape:

```json
[
  {
    "flows": [
      {
        "id": 51,
        "label": "IDENTIFIER",
        "name": "app",
        "fullName": "",
        "code": "app.get(\"/hello\", (req, res) => {\n  const name = req.query.name;\n  res.send(\"hello \" + name);\n})",
        "typeFullName": "",
        "isExternal": false,
        "parentMethodName": ":program",
        "parentFileName": "server.js",
        "parentPackageName": "<global>",
        "parentClassName": "server.js::program",
        "lineNumber": 3,
        "columnNumber": 0,
        "tags": "framework-input, framework-output"
      },
      {
        "id": 12,
        "label": "METHOD_PARAMETER_IN",
        "name": "res",
        "typeFullName": "ANY",
        "code": "res",
        "isExternal": false,
        "parentMethodName": "anonymous",
        "parentFileName": "server.js",
        "lineNumber": 3,
        "columnNumber": 24,
        "tags": "flow-summary"
      },
      {
        "id": 22,
        "label": "IDENTIFIER",
        "name": "res",
        "code": "res.send",
        "isExternal": false,
        "parentMethodName": "anonymous",
        "parentFileName": "server.js",
        "lineNumber": 5,
        "columnNumber": 2,
        "tags": "framework-output"
      }
    ],
    "purls": []
  }
]
```

The fields that carry the analysis:

`label` is the CPG node kind. `IDENTIFIER` is a variable reference,
`METHOD_PARAMETER_IN` a parameter, `CALL` a call site. It tells you what the
node is before you read the code.

`code` is the source text of the node, verbatim. This is what visualize puts in
diagram labels and what SARIF puts in snippet texts.

`parentFileName`, `lineNumber`, `columnNumber` anchor the node in the source
tree. The file is relative to the path atom was given. These anchors are what
lesson 6's validate-lines re-checks.

`parentMethodName` and `parentClassName` locate the node inside its enclosing
function, and `fullName` (when set) is the resolved symbol, which is what the
filter command's `resolvedMethod` criterion searches.

`isExternal` marks whether the node belongs to your code or to a dependency.
External nodes are how a flow crosses a package boundary; a group's `purls`
array lists the packages it touched.

`tags` is a comma-separated string, and it is the most query-worthy field in the
file. Sources carry tags like `framework-input`, `pii-full-name`,
`sensitive-data`; sinks carry `sql`, `ssrf`, `code-execution`,
`framework-output`. Tags drive the SARIF rule ids in lesson 9 and the colour
choices of the diagrams in lesson 7.

Read the group above as a sentence: an express route registration
(`app.get("/hello", ...)`, tagged framework-input because a route handler
receives request data) flows through the `res` parameter into `res.send`
(framework-output). Three nodes, one story. The middle node is tagged
`flow-summary`, which is how atom marks synthesised shortcut nodes that stand
for a longer intra-procedural chain.

A group from the real cdxgen run makes the same walk at scale. One of the 790
groups runs from `new URL(req.url, "http://probe")` in
`contrib/server-mem-probe.mjs:39` through `url.searchParams.get("tag")` to
`res.end(JSON.stringify(obj))`, 13 steps end to end in its SARIF rendering
(lesson 9). Group sizes in the cdxgen run range from 2 to 60-plus nodes; the
big ones are the introspection stage walking every field of a command template,
and one group in `lib/stages/postgen/introspection/score.js` needs 48 steps to
get from a temporary to a Map lookup.

## The usages slice: objects and how they are used

`cdxgen.usages.json` answers a different question: not where data flows, but
what every object is and which methods run on it. The top level carries
`objectSlices` (4,897 in the cdxgen run) and `userDefinedTypes` (26).

Each object slice is one object or function, keyed by `fullName`, carrying its
own anchor fields plus a `usages` list. Here is a usage record from
`bin/audit.js`, trimmed:

```json
{
  "targetObj": {
    "name": "reportFile",
    "typeFullName": "ANY",
    "lineNumber": null,
    "label": "LOCAL"
  },
  "definedBy": {
    "name": "reportFile",
    "typeFullName": "ANY",
    "label": "LOCAL"
  },
  "invokedCalls": [
    {
      "callName": "writeOrPrint",
      "resolvedMethod": "writeOrPrint",
      "paramTypes": ["ANY", "ANY"],
      "returnType": "ANY",
      "isExternal": false,
      "lineNumber": 237,
      "columnNumber": 4
    }
  ],
  "argToCalls": []
}
```

A usage record says: the object `reportFile` (a LOCAL in the enclosing function)
is defined by such-and-such, has these methods invoked on it (`writeOrPrint`,
with parameter and return types when the frontend recovered them), and is passed
as an argument to these calls (`argToCalls`, empty here). When `typeFullName` is
`ANY`, the frontend could not recover a type, which on a babel-only JavaScript
run (lesson 2's `--ts-types false`) is the common case rather than the
exception.

This is the file the endpoint commands read (lesson 8): framework route
registrations appear as usages whose invoked calls are the framework's
registration methods, and the converter reconstructs paths from them.

## userDefinedTypes

The second table lists types the analyser could actually see: 26 in the cdxgen
run against 4,897 object slices. In a TypeScript or Java tree this table fills
up and becomes the backbone of type-aware queries; in plain JavaScript it stays
thin and the object slices do the work. When a filter on `name` or `fullName`
returns puzzlingly few hits on a JavaScript project, check this asymmetry
first.

## Which fields feed which command

```text
    reachables                              usages
    ------------------                      ------------------------------------
    flows[].tags          sarif rules,      objectSlices[].fullName   filter
                          visualize
    flows[].parentFileName,                 usages[].invokedCalls     query-endpoints,
    flows[].lineNumber    check-reachable,                            convert (openapi)
                          validate-lines,
                          visualize, sarif
    flows[].code          visualize labels, usages[].targetObj        convert (openapi)
                          sarif snippets
    purls[]               filter -p,        usages[].argToCalls       filter (callName,
                          check-reachable -p,                         resolvedMethod)
                          visualize SBOM join
```

## Exercises

Count flow groups by tag with a one-liner, then find the single longest flow
group in the cdxgen run and read its nodes end to end:

```console
$ python3 -c "
import json, collections
groups = json.load(open('cdxgen-reports/cdxgen.reachables.json'))
c = collections.Counter()
for g in groups:
    for f in g['flows']:
        for t in (f.get('tags') or '').split(','):
            c[t.strip()] += 1
print(c.most_common())
longest = max(groups, key=lambda g: len(g['flows']))
print(len(longest['flows']), 'nodes;',
      longest['flows'][0]['parentFileName'], '->',
      longest['flows'][-1].get('fullName') or longest['flows'][-1]['name'])
"
```

Then open `cdxgen.usages.json`, pick a slice named after a cdxgen function you
know (say `lib/inventory/purl.js::program:isValidPurl`), and read its usage
records against the source file.
