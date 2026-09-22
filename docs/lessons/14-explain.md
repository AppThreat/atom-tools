# Lesson 14: Explain

Reports are for machines; reviews are done by people reading sentences. The
explain command renders a report's flows as deterministic, citable narratives,
for a reviewer or for an agent. There is no LLM in it: the narrative is
template-driven, so the same input produces the same sentences every time, which
is what makes it safe to diff in CI and safe to cite in a review.

## The text rendering

On the rusi fixture (Rust microservices talking to kafka):

```console
$ atom-tools explain -i test/data/ecosystem/rust-microservices-kafka-rusi.json
Flow report: rusi 3.2.0 (security mode) — 5 flow(s), 3 package record(s) from 1 input file(s) (rust-microservices-kafka-rusi.json).
severity: 0 error / 5 warning / 0 note; 0 engine-reported, 5 derived
source tags: 5 of 5 flow(s) carry tags on the source node
entry-point join: 1 of 5 flow(s) sit behind an anchored entry point; rusi: 14 of
14 endpoint(s) anchored in the call graph, 2 flow attachment(s).

1. Flow df-slice-a8522d1a3ab83d87 — param-0 → network-request
   Reachability: `pkg:cargo/app-user-service@0.1.0` is reached from `GET /users`
   (app-user-service/src/user/api/rest/routing.rs:11), and 1 more entry point(s);
   rusi does not classify authentication, so the route's exposure is unknown.
   Path: source `u` (.../resources/response/mod.rs:72) tagged `param-0` which
   reaches `get` (.../resources/response/mod.rs:75) in 2 step(s), classified
   `network-request`.
   Evidence: rusi 3.2.0, security mode. Severity `warning` (derived from the
   shared taxonomy, not engine-reported).

2. Flow df-slice-03a64c7753789d6d — param-0 → network-request
   Reachability: `pkg:cargo/common-security@0.1.0` is reached by this flow; its
   source function sits inside no anchored handler's closure (14 of 14 endpoints
   anchored in this report's call graph).
   ...
```

Every clause in those sentences maps to a field in the unified flow model from
lesson 10, and where a field is empty the clause is omitted or hedged, never
filled with a plausible default. The header block counts what the join actually
achieved: how many flows sit behind an anchored entry point, how many endpoints
anchored, how many attachments were made. The honesty clauses are part of the
output, not decoration: rusi does not classify authentication, so the sentence
says the exposure is unknown; the severity line says the taxonomy derived it
because the engine emitted none; an unjoined flow says so.

## Selecting flows

Four selectors narrow the narrative in the text and markdown formats. `--flow`
takes an exact id, `--package` a substring of a purl, `--file` a path suffix, and
`--query` speaks dosai's compact grammar over the whole model:

```console
$ atom-tools explain -i test/data/ecosystem/dotnet-eshoponweb-dosai-dataflows.json \
      --query "flows[source_category=secret && sink_category=auth]"
1 flow(s) match `flows[source_category=secret && sink_category=auth]`.

1. Flow dfs1 — secret → auth
   Path: source `JWT_SECRET_KEY` (ApiTokenHelper.cs:38) tagged `secret` which
   reaches `CreateToken` (ApiTokenHelper.cs:46) in 4 step(s), classified `auth`.
   ...

$ atom-tools explain -i test/data/ecosystem/dotnet-eshoponweb-dosai-dataflows.json \
      --query "flows[source_category=secret] count"
1 flow(s) match `flows[source_category=secret] count`.
```

The grammar takes collections (`flows`, `endpoints`, `packages`), predicates
joined with `&&`, `sort by prop [desc]` and a `count` postfix. A flow also
exposes dotted `source.` and `sink.` paths, an atom-tools addition. The one flow
that matches here is a textbook review finding: an environment-sourced secret
travelling into token creation in the eShopOnWeb API.

## The markdown rendering

`-f markdown` produces the same narratives in a shape that attaches to a pull
request. One flow, selected by id:

```console
$ atom-tools explain -i test/data/ecosystem/dotnet-eshoponweb-dosai-dataflows.json \
      -f markdown --flow dfs1
```

```markdown
### `dfs1` — error (engine)

- **Reachability:** `pkg:nuget/System.IdentityModel.Tokens.Jwt@7.3.1` is reached
  by this flow; dosai links weaknesses — not flows — to entry points, so no
  route is named here.
- **Path:** source `JWT_SECRET_KEY` (ApiTokenHelper.cs:38) tagged `secret` which
  reaches `CreateToken` (ApiTokenHelper.cs:46) in 4 step(s), classified `auth`.
- **Evidence:** dosai 5.0.0.0, dataflows mode. Severity `error` (engine-reported).
  Confidence `medium`.
- **Sanitizer:** No sanitizer reported on this path by dosai's sanitizer
  analysis; this run found none to report.
```

Note what the reachability clause does with dosai's model: dosai links
weaknesses, not flows, to entry points, so the sentence declines to name a route
rather than naming a wrong one. The sanitizer sentence appears only for engines
whose schema carries a sanitizer field.

## The agent rendering

`-f agent` emits a compact, token-budgeted JSON context for a consuming agent:

```console
$ atom-tools explain -i test/data/ecosystem/dotnet-eshoponweb-dosai-dataflows.json \
      -f agent --max-tokens 1200
```

```json
{
  "entryPoints": [],
  "explainVersion": 1,
  "highRiskFlows": [
    {
      "confidence": "medium",
      "id": "dfs1",
      "purls": ["pkg:nuget/System.IdentityModel.Tokens.Jwt@7.3.1"],
      "sanitizerReported": false,
      "severity": "error",
      "severitySource": "engine",
      "sink": { "file": "ApiTokenHelper.cs", "line": 46, "name": "CreateToken" },
      "sinkCategory": "auth",
      "source": { "file": "ApiTokenHelper.cs", "line": 38, "name": "JWT_SECRET_KEY", "tags": ["secret"] },
      "sourceCategory": "secret"
    }
  ]
}
```

The budget is an estimate, characters divided by four, not a real tokeniser, and
the document says so. When the budget binds, the trimming leaves an unmissable
`truncated: N more` marker rather than silently dropping flows.

## The MCP server

With `--mcp` (requires the `mcp` extra, `pip install atom-tools[mcp]`), the
command starts a read-only stdio MCP server over the loaded report, exposing
five tools. `--old` loads a baseline at startup for the drift tool, because the
tools never touch the filesystem:

```console
$ atom-tools explain -i report.json --old baseline.json --mcp
```

The tool list, confirmed by an initialize handshake and a `tools/list` call:

```text
atom.explain_flow    Explain one source-to-sink flow in words (deterministic, template-driven)
atom.attack_surface  Entry points grouped by exposure tier, with what each reaches
atom.drift           Reachability delta against the baseline the server was started with
atom.graph_hotspots  Call-graph chokepoints: nodes on the most source-to-sink paths
atom.query           Filter with dosai's compact grammar
```

This is the integration point for agent workflows: an IDE assistant or a CI bot
that speaks MCP can read the report through these tools without re-implementing
any parsing, and the answers it gets are the same deterministic sentences a human
reviewer gets.

## Determinism, and why it matters

Because there is no model call in the pipeline, running explain twice on the same
report yields byte-identical output. That property has a practical consequence:
you can commit the narrative to the repository, and a later run becomes a diff.
Lesson 16 uses exactly that trick to put narrative drift in front of a reviewer.

## Exercises

Explain the unified three-engine document from lesson 10, one flow per engine,
and watch how the honesty clauses differ per engine. Then try to construct a
query that returns zero flows and read what the output does with the empty
result:

```console
$ atom-tools explain -i unified-mixed.json --query "flows[sink_category=sql && severity=error]"
$ atom-tools explain -i unified-mixed.json --file routes.go --max-flows 3
```
