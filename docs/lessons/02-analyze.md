# Lesson 2: First analysis of cdxgen

This lesson generates the course material: real data flow slices of the cdxgen
source tree, produced by the atom engine and post-processed by atom-tools. Two
invocations are shown. The `analyze` command is the guided path that drives atom
for you; the raw atom invocation is what you graduate to when a tree needs
tuning. Both were run for real, and every output below is captured from the runs.

## The guided path: atom-tools analyze

`analyze` runs `atom reachables`, reuses the produced atom (the code property
graph) for `atom usages`, merges chunked output, computes statistics, and
optionally extracts an OpenAPI document and writes a SARIF report. To keep the
first run quick, the walkthrough uses a four-line express application; the same
command produced the cdxgen artefacts in the next section. Create it in the
scratch directory as `mini/server.js`:

```javascript
const express = require("express");
const app = express();
app.get("/hello", (req, res) => {
  const name = req.query.name;
  res.send("hello " + name);
});
app.listen(3000);
```

Then run the command:

```console
$ atom-tools analyze -l jssrc -i mini -o mini-reports --sarif
Executing: atom reachables -l jssrc -o mini-reports/mini.atom -s mini-reports/mini.reachables.json mini
Executing: atom usages -l jssrc -o mini-reports/mini.atom -s mini-reports/mini.usages.json mini --reuse-atom
SARIF document written to mini-reports/mini.reachables.sarif.json.
mini-reports/mini.reachables.json
mini-reports/mini.usages.json
mini-reports/mini.reachables.sarif.json
mini-reports/mini.reachables.stats.json
Analysed mini: 7 reachable flow group(s), 0 reachable package(s).
```

The console shows the two engine invocations as they execute, so there is no
mystery about what was run on your behalf, then lists the artefacts. Five files
land in `mini-reports`:

```text
mini.atom                     the code property graph (reuse it for later runs)
mini.reachables.json          source-to-sink flow groups
mini.usages.json              object and method usage slices
mini.reachables.sarif.json    SARIF 2.1.0 rendering of the reachables
mini.reachables.stats.json    machine-readable slice statistics
```

Useful switches: `--extract-endpoints` adds an OpenAPI document from the usages
slice, `--no-usages` skips the second engine pass when only reachables are
needed, and `--atom-cmd` points at an atom binary that is not on PATH.

## The full target: cdxgen

Now the real thing. cdxgen is a large JavaScript and TypeScript workspace, and
the first thing you learn on a large tree is where the time goes. atom's
JavaScript frontend resolves TypeScript declarations by default, which means a
full TypeScript program over the workspace, and on cdxgen that phase does not
finish in a useful time. The run that produced this course's artefacts disabled
it:

```console
$ cd ~/atom-tools-docs
$ atom reachables -l jssrc --ts-types false \
      -o cdxgen-reports/cdxgen.atom \
      -s cdxgen-reports/cdxgen.reachables.json \
      ~/work/cdxgen/cdxgen
Generating data-flow dependencies from atom using the Flux engine. Please wait ...
Slicing the atom for reachables. This might take a few minutes ...

$ atom usages -l jssrc --ts-types false \
      -o cdxgen-reports/cdxgen.atom \
      -s cdxgen-reports/cdxgen.usages.json \
      ~/work/cdxgen/cdxgen --reuse-atom
```

Two minutes later (M1-class laptop, cold cache):

```console
$ ls -la cdxgen-reports/
cdxgen.atom              94552064 bytes
cdxgen.reachables.json   15285935 bytes
cdxgen.usages.json       12012647 bytes
```

What was traded away is type resolution inside the slices: with `--ts-types
false` the frontend parses with babel only and skips the whole-program type
check. On a workspace the size of cdxgen that is the difference between a run
that finishes and a run that does not. The flow finding itself, the tags, the
file and line anchors are all intact; lesson 6's validate-lines pass measured
the anchors against the tree and 97 percent were exact.

For contrast, the same two commands on the express app finish in about
ten seconds with types enabled. `--ts-types` is a scale knob, not a correctness
knob; reach for it when the tree is big.

## What the artefacts are

The `.atom` file is the serialised code property graph. Keep it: the next
`--reuse-atom` run skips CPG construction entirely, which is how the usages pass
above ran twice as fast as the first.

`cdxgen.reachables.json` is a bare JSON array of 790 flow groups. Each group is
one source-to-sink story: an ordered list of flow nodes and the package purls
the path touches. `cdxgen.usages.json` is the `{"objectSlices": [...],
"userDefinedTypes": [...]}` document that records how every object and method is
used. Lesson 3 dissects both formats.

## The astgen child process, and why the first run looks stuck

One operational detail worth knowing before you run atom on a big tree. The
JavaScript frontend spawns a child process called `astgen` that parses every
file before the JVM side starts building the graph. During that phase the atom
process itself shows almost no CPU while `astgen` runs at 100 percent, which
looks exactly like a hang if you are watching the parent. On a cold cache the
ASTs are also written to a `.chen` directory inside the analysed tree, so the
second run starts warm. If a run genuinely needs stopping, kill the `astgen`
child too, or it keeps burning a core as an orphan.

## Post-processing by hand

Because the raw route bypassed `analyze`, run the post-processing steps
yourself, which is what `analyze` would have done:

```console
$ atom-tools stats -i cdxgen-reports/cdxgen.reachables.json
Slice type: reachables
flow_groups: 790
flow_nodes: 30126
sources: 639
sinks: 315
unique_files: 13
top_files:
  lib/stages/postgen/introspection/score.js: 15060
  lib/cli/bomAssembly.js: 9028
  lib/stages/postgen/introspection/shapeCommand.js: 3533
  lib/cli/nativeBom.js: 756
  ...
purls:
  count: 0
  list: []
tags:
  framework-input: 645
  flow-summary: 564
  framework-output: 315
  exported: 166
```

That single screen already tells the story of the analysis. 790 flow groups over
30,126 nodes, concentrated in five files, with the introspection stage
(`score.js`, `shapeCommand.js`) and the CLI assembly carrying nearly everything.
The tag census says what kind of flows they are: framework inputs flowing to
framework outputs, plus exported symbols reached. And the purl count is zero,
which is not a mistake; it is a property of how this run was made, and lesson 7
explains what it means for the SBOM join.

## Exercises

Run `analyze` on the express app without `--sarif`, then with
`--extract-endpoints`, and diff the artefact lists. Then run `stats` on the
usages slice of cdxgen and compare its shape with the reachables summary:

```console
$ atom-tools stats -i cdxgen-reports/cdxgen.usages.json
Slice type: usages
object_slices: 4897
user_defined_types: 26
usages: 19293
procedures: 63
calls:
  external: 12775
  internal: 6490
top_files:
  bin/repl.js: 132
  lib/managers/binary.js: 121
  lib/inventory/display.js: 108
  ...
```

Two numbers to sit with: 4,897 object slices against 26 user-defined types.
cdxgen is JavaScript, so the type system the analyser sees is thin, and almost
everything of interest lives in the object slices.
