# Lesson 12: Drift between two runs

Static reports age. The question that keeps them honest is comparative: what
changed since the last run? The drift command compares two reports from the same
engine and reports the risk delta between them: flows added, removed or merely
moved, newly reachable packages, new entry points. It is a pure function over two
files; it never invokes an engine, so it runs in seconds in CI.

## A real delta: ipsw across about 400 commits

The committed golem fixtures are two runs of the same engine against the same
repository, the Go project ipsw, taken across roughly 400 commits of development.

```console
$ atom-tools drift \
    --old test/data/ecosystem/go-ipsw-golem-baseline.json \
    --new test/data/ecosystem/go-ipsw-golem.json
golem baseline 343 flow(s) / 54 file(s)  ->  current 397 flow(s) / 66 file(s)
severity source: engine

+159 added  -105 removed  ~91 moved  =21 witness-changed
  + error    configuration -> crypto  crypto/x509.ParsePKCS8PrivateKey  (pkg/aea/aea.go:82)  x17
  + error    configuration -> filesystem  os.Open  (internal/diff/ota_inputs.go:126)  x17
  + error    configuration -> filesystem  os.ReadFile  (pkg/aea/aea.go:129)  x15
  + warning  configuration -> external-service  net/http.NewRequest  (pkg/aea/aea.go:155)  x17
  + warning  parameter -> logging  log.Printf  (.../go-macho@v1.1.281/file.go:253)  x20
  - warning  http-input -> http-response  (*github.com/gin-gonic/gin.Context).JSON  (.../gin@v1.12.0/context.go:232)  x5
  - warning  http-input -> panic  github.com/blacktop/go-plist.mustParseUint  (.../go-plist@v1.0.2/must.go:31)
  ...
```

The headline row carries the four verdicts. Read the `~` and `=` ones first,
because they are where naive diffs go wrong.

## Identity: what makes two flows "the same"

Flow identity is built from analysis facts only: source and sink category, sink
symbol, root-relative file, and purls. Line numbers, column numbers and engine
node ids are deliberately excluded, because all of them move on every edit. The
consequence is the difference between the second and third column:

```text
    added        a flow whose identity did not exist in the baseline
    removed      a flow whose identity no longer exists
    moved        same identity, different location
    witness-     same identity and location, but the recorded path
    changed      (the source-to-sink witness) changed shape
```

A function that gained a file and shifted twenty lines down produces a `moved`
flow, not an added plus a removed one. On this fixture pair, 91 flows moved and
21 changed witness; a line-number-keyed diff would have reported all of them as
churn, and a reviewer would have stopped reading. This is the single most
important property of the command, and the reason it survives contact with real
development history.

## The gates

Comparing is for humans; gating is for CI. `--fail-on` takes comma-separated
gate keys, and when any trips, the command exits with code 2:

```console
$ atom-tools drift \
    --old test/data/ecosystem/go-ipsw-golem-baseline.json \
    --new test/data/ecosystem/go-ipsw-golem.json \
    --fail-on new-high,new-package
...
gate tripped — new-high: NewHighSeverityFlows is 67
$ echo $?
2
```

The gate names the key that tripped and the number behind it. Sixty-seven new
high severity flows sounds alarming until you read the next sentence: severity
source on this pair is the engine, and the 400 commits between the runs
genuinely added reachable crypto, filesystem and network sinks. A gate is a
review trigger, not a verdict; the verdict is the reading you do after.

The six gate keys are `new-high`, `new-medium`, `new-anonymous-endpoint`,
`new-package`, `new-sink-category` and `new-entrypoint`. They answer questions a
security reviewer actually asks: did this change put a new high severity flow on
the map, reach a package that was never reached before, expose a route that used
to be behind authentication, or grow a sink category the codebase had never had.

One gate cannot be turned off: a coverage regression trips the gate regardless of
`--fail-on`. If the new run analysed materially fewer files, or the engine
reported the run as truncated, the command refuses to render that as a green
diff. A half-broken build must not look like an improvement. You can spot this
case in the output because the first line of the summary prints the file counts
of both runs side by side.

Exit codes: 0 means a clean diff or no tripped gate, 1 means the command itself
failed (bad input, mixed engines), 2 means a gate tripped. A CI script
distinguishes "the tool broke" from "the tool found risk" on that difference.

## The formats

The console format above is for the person at the terminal. The markdown format
is for attaching to a pull request; it prints to the console, so capture it with
a redirect:

```console
$ atom-tools drift --old baseline.json --new current.json -f markdown > drift.md
```

The markdown opens with the run comparison, then tables the added flows (most
repeated first):

```text
## atom-tools drift

`golem` (severity source: engine)

| | baseline | current |
|---|---|---|
| flows | 343 | 397 |
| files | 54 | 66 |
| packages | 22 | 21 |
| endpoints | 55 | 57 |

**+159 added**, -105 removed, 91 moved (location only), 21 witness changed.

### Added flows

| n | severity | source | sink | where |
|---|---|---|---|---|
| 17 | error | configuration | crypto `crypto/x509.ParsePKCS8PrivateKey` | `pkg/aea/aea.go:82` |
| 17 | warning | configuration | external-service `net/http.NewRequest` | `pkg/aea/aea.go:155` |
| 20 | warning | parameter | logging `log.Printf` | `.../go-macho@v1.1.281/file.go:253` |
```

The json format (`-f json -o drift.json`) carries the whole delta as a document,
which is what a gate-as-code setup wants to consume.

## Comparing the same run to itself

A quick way to sanity check the identity rules is to diff a report against
itself:

```console
$ atom-tools drift --old test/data/ecosystem/go-ipsw-golem.json \
                   --new test/data/ecosystem/go-ipsw-golem.json
golem baseline 397 flow(s) / 66 file(s)  ->  current 397 flow(s) / 66 file(s)
severity source: engine

+0 added  -0 removed  ~0 moved  =0 witness-changed
```

Zero across the board, as it must be: drift is deterministic over its inputs, so
an unchanged report pair always yields an empty delta. This property is what
makes the command safe to wedge between two CI jobs and diff the diff.

## Exercises

The repository ships a second baseline pair, this one from rusi (the Rust
engine, kafka microservices target):

```console
$ atom-tools drift \
    --old test/data/ecosystem/rust-microservices-kafka-rusi-baseline.json \
    --new test/data/ecosystem/rust-microservices-kafka-rusi.json
```

Read its headline row, then set a gate that trips on it, then check the exit
code. When you later re-run the lesson 2 analysis after pulling a newer cdxgen,
you have a genuine atom pair to drift: keep the old reachables file as the
baseline and compare.
