# Lesson 11: Attack surface

The attack-surface command answers a question every reviewer eventually asks:
what comes in, and what can it touch? It groups a report's entry points into
exposure tiers and reports what each one reaches, in the shape of dosai's own
`AttackSurface[]` view, for every engine.

## The tier ladder

Entry points are grouped by how exposed they are, most exposed first:

```text
    anonymous-http    an unauthenticated HTTP route
    anonymous-rpc     an unauthenticated RPC
    anonymous         unauthenticated, protocol not HTTP or RPC
    mcp               an MCP server tool
    queue             a queue consumer
    cli               a command line entry point (local trust)
    authenticated-http      an HTTP route with authentication
    authenticated-rpc       an RPC with authentication
    internal          declared unreachable for callers (deny rules, non-exported)
    unknown-auth      the engine could not say (rendered as a gap, never as safe)
```

Two engines can fill this ladder from evidence: dosai classifies authentication
outright, and kosi carries declared requirements from route DSLs, servlet
constraints and manifests. Every other engine's entries, and kosi's undeclared
ones, sit in `unknown-auth`. That tier is printed with a standing reminder that
it is a gap in the evidence, not a verdict of safety. The header of the output
says which situation you are in:

```text
tiers run most-exposed first; only dosai classifies authentication — every other
engine's entries sit in unknown-auth, which is a gap, not a finding.
```

(with kosi the first clause becomes "dosai and kosi classify authentication").

## The dosai report in the cdxgen tree

You met this report in lesson 10. Its attack surface is small and makes a clean
first example:

```console
$ atom-tools attack-surface -i ~/work/cdxgen/cdxgen/data-flow.slices.json
Attack surface: 2 entry point(s) from 1 report(s) (dosai)
tiers run most-exposed first; only dosai classifies authentication — every other
engine's entries sit in unknown-auth, which is a gap, not a finding.

  * cli: 2 entry point(s), 46 weakness(es) (27 high severity)
   ├── ANY ci/images/nuget/nuget.exe  ci/images/nuget/nuget.exe:1
   │     reach: engine · sinks: command, file, network, xxe
   └── ANY ci/images/nuget/Lucene.Net.dll  ci/images/nuget/Lucene.Net.dll:1
         reach: engine · sinks: file, log, reflection

tiers with no entry points here: anonymous-http, anonymous-rpc, anonymous, mcp,
queue, authenticated-http, authenticated-rpc, internal, unknown-auth
headline suppressed: no input classifies authentication, so no entry point is
known to be anonymous — a percentage here would invent a denominator.
```

Read it line by line. Two CLI entry points, dosai's own reachability verdict
(`reach: engine`) and the sink categories each reaches. The last line is the
honesty habit in its purest form: the tool refuses to print a "percentage
anonymous" headline because no input classifies authentication here, and a
percentage over an invented denominator would be decoration pretending to be a
measurement.

## Reach lines and their four shapes

On the golem fixture (Go, ipsw), reach is computed by anchoring each endpoint's
handler in the engine call graph and attaching the flows whose source function
falls inside its transitive closure. The output shows every shape a reach line
can take:

```console
$ atom-tools attack-surface -i test/data/ecosystem/go-ipsw-golem.json
Attack surface: 57 entry point(s) from 1 report(s) (golem)
...
  ? unknown-auth [auth unknown — not an exposure verdict]: 57 entry point(s), 0 weakness(es)
   ├── /GET /  .../internal/commands/ent/ui.go:35  [auth unknown]
   │     reach: seed-not-found (handler not locatable in the call graph)
   ├── GET /_ping  .../api/server/routes/daemon/routes.go:40  [auth unknown]
   │     reach: computed — reaches no analysed flow
   ├── GET /dsc/imports  .../api/server/routes/dsc/routes.go:78  [auth unknown]
   │     reach: 6 flow(s) · sinks: filesystem, http-response, logging
   │     packages: pkg:golang/github.com/blacktop/ipsw, pkg:golang/github.com/gin-gonic/gin
   ├── GET /idev/amfi/dev  .../api/server/routes/idev/routes.go:21  [auth unknown]
   │     reach: 68 flow(s) · sinks: crypto, http-response, panic
   ...
```

The four shapes, and what each one claims:

`reach: N flow(s) · sinks: ...` is a computed closure with flows attached. The
endpoint's handler was found in the call graph, and the listed sink categories
are reachable through it.

`reach: computed — reaches no analysed flow` says the closure was computed and
found nothing. The handler exists, the graph was walked, nothing analysed flows
from it. Note the qualifier "analysed": the claim is about this report, not
about the whole program.

`reach: seed-not-found` says the handler could not be anchored in the call graph
at all. The endpoint declaration exists but the join failed. Treat it as a
review flag on the report, not on the code.

`reach: not computed` (not shown by this fixture) appears when the input has no
call graph to walk. "Reaches nothing" and "not computed" are opposite findings,
and the renderings keep them distinct.

## kosi: declared requirements, quoted not derived

The kosi fixture for a Kotlin routes DSL fills the authenticated and internal
tiers from declarations:

```console
$ atom-tools attack-surface -i test/data/ecosystem/kotlin-dsl-media-auth-kosi.json
Attack surface: 17 entry point(s) from 1 report(s) (kosi)
tiers run most-exposed first; dosai and kosi classify authentication — ...

  * authenticated-http: 9 entry point(s), 0 weakness(es) (0 high severity)
   ├── /secure  src/main/kotlin/fixtures/dslmedia/DslRoutes.kt:155  [kosi declares auth-handler(BasicAuthHandler)]
   │     reach: computed — reaches no analysed flow
   ├── GET /admin  src/main/kotlin/fixtures/dslmedia/DslRoutes.kt:178  [kosi declares role(ADMIN)]
   │     reach: computed — reaches no analysed flow
   └── GET /token  src/main/kotlin/fixtures/dslmedia/DslRoutes.kt:155  [kosi declares auth-handler(JWTAuthHandler)]
         reach: computed — reaches no analysed flow

  * internal: 1 entry point(s), 0 weakness(es) (0 high severity)
   └── GET /denied  src/main/kotlin/fixtures/dslmedia/Servlets.kt:19  [kosi declares a deny rule (security-constraint(denied)): no caller may reach this endpoint]
         reach: computed — reaches no analysed flow

  ? unknown-auth [...]: 7 entry point(s), 0 weakness(es) (0 high severity)
   ...
```

Each bracket prints what kosi actually read: `auth-handler(BasicAuthHandler)`,
`role(ADMIN)`, `security-constraint(denied)`. The mapping is conservative. A
non-empty authentication list lifts the endpoint to `authenticated-http`; a deny
rule plus `exported: false` maps to `internal`; an empty declaration is not a
denial, so endpoints without a declared requirement stay in `unknown-auth`, and
"anonymous" is never asserted for anything that did not say so.

One more kosi behaviour deserves its own paragraph. A declared route whose
handler code was never read is flagged by kosi as `substantiated: false` (think
of an Android manifest naming a class that is not in the tree). atom-tools keeps
it in the surface, because it is a real declared entry point, and marks it
`declared only, handler code not read`. Dropping it would hide an entry point;
publishing it unmarked would present an unexamined route as a clean one. The
Android manifest fixture shows every one of these mechanics at once:

```console
$ atom-tools attack-surface -i test/data/ecosystem/kotlin-android-manifest-app-kosi.json
Attack surface: 5 entry point(s) from 1 report(s) (kosi)

  * internal: 2 entry point(s), 0 weakness(es) (0 high severity)
   ├── PackageReceiver  src/main/AndroidManifest.xml:1  [kosi records the component as not exported (not externally launchable)]
   │     reach: computed — reaches no analysed flow
   └── SyncService  src/main/AndroidManifest.xml:1  [kosi records the component as not exported (not externally launchable)]
         reach: computed — reaches no analysed flow

  ? unknown-auth [auth unknown — not an exposure verdict]: 3 entry point(s), 0 weakness(es) (0 high severity)
   ├── MetaProvider  src/main/AndroidManifest.xml:1  [auth unknown]
   │     reach: computed — reaches no analysed flow
   ├── android.intent.action.MAIN  src/main/AndroidManifest.xml:1  [auth unknown]
   │     reach: computed — reaches no analysed flow
   └── android.intent.action.VIEW  src/main/AndroidManifest.xml:1  [auth unknown]  [declared only — handler code not read]
         reach: not analysable — the engine read none of this endpoint's code, so
         zero flows here means unexamined, not clean
```

Three entry point kinds, three renderings. A component the manifest says is not
exported lands in `internal` with the reason quoted. A provider with no
declaration lands in `unknown-auth` like any other undeclared entry. And the
VIEW intent whose handler was never read stays in the surface, marked declared
only, with its reach line saying outright that zero flows there mean unexamined,
not clean.

## Formats and filters

The console rendering is bounded by `--max-entries` (default 200). The JSON
output always carries every entry point, which is the one to consume from
scripts:

```console
$ atom-tools attack-surface -i test/data/ecosystem/kotlin-dsl-media-auth-kosi.json -f json -o kosi-as.json
Attack surface with 17 entry point(s) written to kosi-as.json.
```

`-f html` writes a mermaid diagram plus a single-file page. `--min-exposure`
keeps only tiers at least as exposed as the named one (`--min-exposure cli`
keeps cli and everything above it); tiers whose authentication is unknown never
match the filter, and the note counts them, so filtering can never silently
delete the unknown tier.

## Exercises

Point attack-surface at the unified document from lesson 10 and watch the tiers
of three engines render in one table. Then run it on the atom reachables you
generated for cdxgen in lesson 2 and check which tier a CLI tool's entry points
land in.

```console
$ atom-tools attack-surface -i unified-mixed.json
$ atom-tools attack-surface -i cdxgen-reports/cdxgen.reachables.json
```
