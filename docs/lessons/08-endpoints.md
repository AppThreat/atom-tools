# Lesson 8: Endpoints and OpenAPI

Many analyses start from the same question: what HTTP (or RPC, or MCP) surface
does this code serve? The usages slice records framework route registrations as
usage records, and atom-tools reconstructs an endpoint list and an OpenAPI
document from them.

## query-endpoints: what routes exist

The query-endpoints command lists the endpoints it finds in a usages slice,
with file and line where they are registered. On the cdxgen usages slice:

```console
$ atom-tools query-endpoints -i cdxgen-reports/cdxgen.usages.json -t js
/mcp:test/data/mcp-repotest/src/http-auth-server.js:75
/mcp-unsafe:test/data/mcp-repotest/src/unsafe-wrapper.js:18
```

Two endpoints, and they are a genuine finding of the analysis: cdxgen's
repository carries MCP (Model Context Protocol) servers in its repotest
fixtures, and atom recognised the registrations. `-t js` tells the command
which language's route idioms to look for; the supported types cover java,
javascript and typescript, python, ruby, go, rust, kotlin, scala and jar.

Two conveniences shape the output. `--sparse` prints names only, for a quick
census, and `-f` filters by line number or range, which pairs with the filter
command to interrogate one file's registrations:

```console
$ atom-tools filter -i cdxgen-reports/cdxgen.usages.json \
      --criteria filename=http-auth-server.js \
      -e "query-endpoints -t js -f 50-100"
```

Use `-q` when you want only the endpoint lines on stdout, with the logging
silenced.

## convert: from usages slice to OpenAPI

The convert command builds the paths object of an OpenAPI 3.x document from a
usages slice. On the cdxgen usages slice:

```console
$ atom-tools convert -i cdxgen-reports/cdxgen.usages.json -t js \
      -f openapi3.1.0 -o openapi_usages.json -s https://cdxgen.example
OpenAPI document written to openapi_usages.json.
```

The document that lands has three paths, one per registered route, and its
details are worth reading closely:

```json
{
  "openapi": "3.1.0",
  "info": { "title": "cdxgen-reports OpenAPI Specification", "version": "1.0.0" },
  "servers": [ { "url": "https://cdxgen.example" } ],
  "paths": {
    "/": {},
    "/mcp": {
      "post": {
        "parameters": [
          {
            "in": "header",
            "name": "@modelcontextprotocol/express:requireBearerAuth:<returnValue>"
          }
        ],
        "responses": {}
      },
      "x-atom-usages": {
        "call": {
          "test/data/mcp-repotest/src/http-auth-server.js": [75]
        }
      }
    },
    "/mcp-unsafe": { "...": "..." }
  }
}
```

Three things to notice. The `/mcp` route is a POST, because MCP over HTTP
posts JSON-RPC messages, and the converter knew that from the registration
idiom. The header parameter is the bearer-token middleware the fixture wires in
front of the route; the name is the resolved middleware symbol, which is more
honest than a prettified "Authorization": it says exactly which expression the
analysis saw. And `x-atom-usages` records the source file and line the path was
reconstructed from, so every path in the document is traceable back to the
registration site, which is what makes the artefact auditable rather than
plausible.

`-s` sets the server object, `-f` selects the OpenAPI version (`openapi3.1.0`
default, `openapi3.0.1` for older tooling), and `-t` must match the slice's
origin language, because route idioms differ per framework family.

## Scope, honestly

The converter reconstructs paths, operations and parameters from what the slice
records. It does not invent response schemas a la OpenAPI examples, and paths
whose registration it could not substantiate are skipped rather than asserted.
Expect a skeleton that is fully sourced, not a hand-written spec's worth of
prose. Future releases fill the path item objects with more detail taken from
atom slices.

For the Kotlin engine the same command converts kosi analyze reports
(`-t kotlin`), with kosi's own honesty rules carried over: an endpoint with no
resolved HTTP method is skipped rather than filed under an invented verb, and
an endpoint kosi flags unsubstantiated carries `x-kosi-substantiated: false`,
so zero declared weaknesses on it reads as unexamined, not clean. The rusi and
golem discovery reports convert the same way with `-t rust` and `-t go`.

## Exercises

Convert the cdxgen usages slice to `openapi3.0.1` and diff it against the 3.1
document; the differences are all in the envelope, which tells you how much of
your tooling actually depends on 3.1 semantics. Then filter the usages slice
down to `http-auth-server.js` before converting, and confirm the
`x-atom-usages` provenance block tracks the narrower input.
