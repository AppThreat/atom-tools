# Lesson 9: SARIF for IDEs and code scanning

SARIF 2.1.0 is the lingua franca of code analysis results: GitHub code
scanning, VS Code's SARIF viewer, SonarQube importers and plenty of internal
tooling all speak it. The convert command renders a reachables slice as a SARIF
document where every flow group becomes one result, and the whole
source-to-sink path is preserved inside it.

## Converting the cdxgen reachables

```console
$ atom-tools convert -i cdxgen-reports/cdxgen.reachables.json \
      -f sarif -o cdxgen.sarif
SARIF document written to cdxgen.sarif.
```

The document's shape, summarised from the real artefact:

```text
version: 2.1.0
tool:      atom-tools
rules:     atom:framework-input, atom:reachable-flow, atom:framework-output
results:   789   (737 warning, 52 note)
```

Each result carries four load-bearing parts. The primary location is the
terminal (sink) node, so the result pins where the risk lands in the viewer.
The `codeFlows` thread flow preserves the entire path, step by step, each step
with its own physical location, message and source snippet. The rule id comes
from the atom tags: a flow tagged `sql` becomes `atom:sql`, `ssrf` becomes
`atom:ssrf`, and the level follows the risk (error for high risk sinks,
warning for other tagged flows, note otherwise). And the purls of the group,
when present, are recorded in the result properties.

One result from the real document, the probe server flow you met in lesson 3:

```json
{
  "ruleId": "atom:framework-input",
  "level": "warning",
  "message": { "text": "Data flows from '<operator>.new' to 'end' over 13 steps" },
  "locations": [ { "physicalLocation": {
      "artifactLocation": { "uri": "contrib/server-mem-probe.mjs" },
      "region": { "startLine": 42 }
  } } ],
  "codeFlows": [ { "threadFlows": [ { "locations": [
      { "location": { "message": { "text": "new URL(req.url, \"http://probe\") [tags: framework-input]" } } },
      { "location": { "message": { "text": "_tmp_2 [tags: flow-summary]" } } },
      { "location": { "message": { "text": "url.searchParams.get(\"tag\")" } } },
      "...10 more steps...",
      { "location": { "message": { "text": "res.end(JSON.stringify(obj)) [tags: framework-output]" } } }
  ] } } ] ],
  "partialFingerprints": { "atomToolsFlow/v1": "2456b5ac56e118ce" }
}
```

The `partialFingerprints` field is what GitHub code scanning uses to track a
finding across runs: the fingerprint is derived from the flow's stable facts,
so a flow that moves lines but keeps its identity keeps its fingerprint, the
same identity discipline lesson 12 applies to drift.

## Uploading to GitHub code scanning

The composition with filter is where this becomes a workflow. Narrow the slice
to the flows you consider worth review, convert, upload:

```yaml
- name: Convert reachables to SARIF
  run: |
    atom-tools convert -i reachables.slices.json -f sarif -o reachables.sarif
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: reachables.sarif
```

The output loads into the same viewers that display dep-scan and blint
reports, so atom's flow findings sit next to dependency and binary findings in
one review queue.

## Chunked and filtered inputs

Like every command that consumes reachables, convert understands atom's chunked
output and globs: `-i 'reachables*.json'` loads all chunks at once. And because
filter writes a reachables document of the same shape, the pair composes in a
pipeline:

```console
$ atom-tools filter -i cdxgen-reports/cdxgen.reachables.json \
      -p "some-package:1.2.3" \
      -e "convert -f sarif -o package-flows.sarif"
```

A SARIF document containing only the flows through one dependency, ready for a
focused review or a dedicated code scanning upload.

## Anchors before upload

SARIF pins findings to lines in the viewer, so run lesson 6's validate-lines
before uploading whenever the slice and the code it describes came from
different moments. On the cdxgen usages slice, validation measured 97 percent
exact line anchors and 77 percent overall accuracy counting missing line
numbers; uploading the reachables slice against the same commit it was
generated from avoids the question entirely.

## Exercises

Convert the juiceshop chunks to SARIF and count how many `atom:*` rules appear,
then compare with the tag census from lesson 3's exercise; the rule set is the
tag set, rendered. Then pick one result in the VS Code SARIF viewer and walk
its code flow from source to sink with the viewer's step controls.
