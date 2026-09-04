# atom-tools

Collection of tools for use with slices generated
by [AppThreat/atom](https://github.com/appthreat/atom).

## Install atom

atom-tools does not generate slices itself. It works with the slices that atom produces. The atom
documentation lives in
the [AppThreat/atom](https://github.com/AppThreat/atom?tab=readme-ov-file) GitHub repository.

Atom installs from a
[native image](https://github.com/AppThreat/atom#atom-native-image-advanced-users-only) or with
npm `npm install -g @appthreat/atom`.

## Install atom-tools

`pip install atom-tools`

## Docker image

A prebuilt image with atom-tools, atom, blint, and the companion analyzers is published
at `ghcr.io/appthreat/atom-tools`.

```
docker run --rm -it -v /tmp:/tmp -v $(pwd):/app:rw -w /app ghcr.io/appthreat/atom-tools
```

The image bundles the `rusi` and `golem` analyzer binaries from
the [cdxgen-plugins-bin](https://github.com/cdxgen/cdxgen-plugins-bin/releases) releases. `rusi`
discovers the api endpoints of Rust projects and `golem` does the same for Go projects. Their
reports can be passed straight to the convert command with `-t rust` or `-t go`.

During the image build, the binary for the target platform (amd64 or arm64) is downloaded from the
GitHub release and checked against the published sha256 checksum before it is installed. A
corrupted or replaced download fails the build instead of shipping quietly. Override the
`CDXGEN_PLUGINS_BIN_VERSION` build argument to bundle a different release.

Generate a Rust report inside the container:

```
docker run --rm -v $(pwd):/app -w /app --entrypoint rusi ghcr.io/appthreat/atom-tools analyze --dir . --out rusi.json
```

Generate a Go report:

```
docker run --rm -v $(pwd):/app -w /app --entrypoint golem ghcr.io/appthreat/atom-tools analyze --dir . --out golem.json
```

Convert either report into an OpenAPI document:

```
docker run --rm -v $(pwd):/app -w /app ghcr.io/appthreat/atom-tools convert -i rusi.json -t rust -f openapi3.0.1 -o openapi.json
```

## CLI usage

The command line interface is built with cleo, the library that also powers Poetry, so it follows
the same conventions.

Run `atom-tools list` to see every available command. Run `atom-tools help` followed by a command
name, for example `atom-tools help convert`, to see the options of that command.

```
Usage:
  command [options] [arguments]

Options:
  -h, --help            Display help for the given command. When no command is given display help for the list command.
  -q, --quiet           Do not output any message.
  -V, --version         Display this application version.
      --ansi            Force ANSI output.
      --no-ansi         Disable ANSI output.
  -n, --no-interaction  Do not ask any interactive question.
  -v|vv|vvv, --verbose  Increase the verbosity of messages: 1 for normal output, 2 for more verbose output and 3 for debug.

Available commands:
  apk-analysis     Analyse Android apps (apk/apkm/aab) using blint and atom.
  check-reachable  Find out if there are hits for a given package:version or file:linenumber in an atom slice.
  convert          Convert an atom slice to a different format.
  filter           Filter an atom slice based on specified criteria.
  help             Displays help for a command.
  list             Lists commands.
  query-endpoints  List elements to display in the console.
  validate-lines   Check the accuracy of the line numbers in an atom slice.
```

## Features

### APK analysis

The apk-analysis command analyses an Android application from end to end by driving blint and atom
as subprocesses and presenting a consolidated report. It accepts a single apk, apkm, or aab file, or
a directory containing them. blint generates the CycloneDX SBOM and atom generates the usage and
reachable slices. atom-tools then merges the two views.

blint runs in deep mode by default so the dex classes are parsed. This is what enables service and
tracker detection and the Dalvik behavioural review. atom-tools reads the behavioural findings back
from the BOM and presents them as static behaviours, and it promotes the services that atom proves
reachable into the SBOM with their observed data flow direction and flow counts. A single blint
invocation with disassembly enabled produces both the BOM and the Dalvik callgraph sidecar, so there
is no need for a second run.

Use `--no-deep` to skip dex parsing, `--skip-atom` to generate only the SBOM, `--blint-venv` to
point at a blint installed in its own virtual environment, and `--format json` to write a
consolidated analysis document instead of rendering tables.

For the custom properties that the analysis reads from and writes to the BOM, see the
[blint Custom Properties documentation](https://github.com/owasp-dep-scan/blint/blob/main/docs/CUSTOM_PROPERTIES.md).

**Example**

> `atom-tools apk-analysis -i /path/to/app.apkm -o reports`

### Convert

The convert command turns an atom slice into a different format. It currently builds the endpoints
of an OpenAPI 3.x paths object from a usages slice. The api discovery reports produced by the rusi
(Rust) and golem (Go) analyzers are accepted as input as well, using `-t rust` and `-t go`. Future
releases will fill the path item objects with more detail taken from atom slices.

```
Description:
  Convert an atom slice to a different format

Usage:
  convert [options]

Options:
  -f, --format=FORMAT                    Destination format [default: "openapi3.1.0"]
  -i, --input-slice=INPUT-SLICE          Usages slice file [default: "usages.slices.json"]
  -e, --semantics-slice=SEMANTICS-SLICE  Semantics slice file [default: "semantics.slices.json"]
  -t, --type=TYPE                        Origin type of source on which the atom slice was generated. [default: "java"]
  -o, --output-file=OUTPUT-FILE          Output file [default: "openapi.json"]
  -s, --server=SERVER                    The server url to be included in the server object.
  -h, --help                             Display help for the given command. When no command is given display help for the list command.
  -q, --quiet                            Do not output any message.
  -V, --version                          Display this application version.
      --ansi                             Force ANSI output.
      --no-ansi                          Disable ANSI output.
  -n, --no-interaction                   Do not ask any interactive question.
  -v|vv|vvv, --verbose                   Increase the verbosity of messages: 1 for normal output, 2 for more verbose output and 3 for debug.

Help:
  The convert command converts an atom slice to a different format.
  Currently supports creating an OpenAPI 3.x document based on a usages slice.
```

**Example**

> `atom-tools convert -i usages.slices.json -f openapi3.0.1 -o openapi_usages.json -t java -s https://myserver.com`

### Filter

The filter command can be run on its own to produce a filtered slice, or used before another
command to narrow a slice down first and then run the other command against the results.

> **Filters operate on an inclusive-or basis. If you want to operate on an 'and' basis,
> [chain](#chaining-filter-commands) the filter commands.**

**Mode**

The default mode builds a regular expression from the value given. Fuzzy mode is selected with
the -f option and a number between 0 and 100 that says how close a result must be to count as a
match. To match the input exactly, either add regex anchors at the beginning and end of the value
or use -f 100 for a 100 percent match.

`atom-tools filter -f 100 --criteria filename=path/to/file/server.ts -i usages.json`

`atom-tools filter --criteria filename=^path/to/file/server.ts$ -i usages.json`

Regex word boundaries help when only the file name part must be exact.

`atom-tools filter --criteria filename=\bserver.ts$ -i usages.json`

This keeps files named ftpserver.ts out of the results. Without the \b they would match too.

> Note: You can search for a file name without including the path if needed, and fuzzing ratios
> are then computed based only on the file name.

#### Chaining filter commands

The filter command can act on its own output by specifying an additional filter command as an
argument. This is useful when several criteria must all match.

**Example**

`atom-tools filter -i slices.json --criteria filename=myfile -e "filter --criteria resolvedMethod=mymethod,resolvedMethod=mymethod2 convert"`

This is equivalent to

`if fileName.contains('myfile') and (resolvedMethod.contains('mymethod') or resolvedMethod.contains('mymethod2')):`

#### Available attributes (not case-sensitive)

_For usages slices_

- callName
- fileName
- fullName
- name
- resolvedMethod
- signature

| attribute      | usages slice locations searched                                                                                                                                                            | reachables slice locations searched        |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------- |
| callName       | objectSlices.usages.argToCalls<br>objectSlices.usages.invokedCalls<br>userDefinedTypes.procedures                                                                                          |                                           |
| fileName       | objectSlices<br>userDefinedTypes                                                                                                                                                           |                                           |
| fullName       | objectSlices                                                                                                                                                                               |                                           |
| name           | objectSlices.usages.targetObj<br>objectSlices.usages.definedBy<br>userDefinedTypes.fields                                                                                                  |                                           |
| purl           |                                                                                                                                                                                            | reachables.purls<br>reachables.flows.tags |
| resolvedMethod | objectSlices.usages.targetObj<br>objectSlices.usages.definedBy<br>objectSlices.usages.argToCalls<br>objectSlices.usages.invokedCalls<br>userDefinedTypes.procedures                       |                                           |
| signature      | objectSlices                                                                                                                                                                               |                                           |

#### Searching reachables for package name/version

This option filters reachables to the given package name and version in the format of name:version

`--package mypackage:1.0.0`

#### Criteria syntax

Multiple criteria can be given by using a comma as a separator (no space)

`--criteria [attribute]=[value],[attribute2]=[value],...`

#### Usage

```
Description:
  Filter an atom slice based on specified criteria.

Usage:
  filter [options]

Options:
  -i, --input-slice=INPUT-SLICE  Slice file to filter.
  -c, --criteria=CRITERIA        Filter based on an attribute of the slice. May be a Python regular expression. Please see documentation for syntax.
  -o, --outfile=OUTFILE          File to re-export filtered slice to.
  -f, --fuzz=FUZZ                Minimum percentage to match with the given criteria INSTEAD of using a regex. Must be a number between 0 and 100.
  -e, --execute=EXECUTE          Command to execute after filtering. [default: "export"]
  -h, --help                     Display help for the given command. When no command is given display help for the list command.
  -q, --quiet                    Do not output any message.
  -V, --version                  Display this application version.
      --ansi                     Force ANSI output.
      --no-ansi                  Disable ANSI output.
  -n, --no-interaction           Do not ask any interactive question.
  -v|vv|vvv, --verbose           Increase the verbosity of messages: 1 for normal output, 2 for more verbose output and 3 for debug.

```

#### Examples

**Filter a query**

The following produces endpoints from the server.ts file within the line number range 50 to 70.

`atom-tools filter -i usages.slices.json --criteria fileName=server.ts -e "query-endpoints -l 50-70"`

**Filter with the convert command**

`atom-tools filter -i usages.slices.json --criteria fileName=server.ts -e "convert -f openapi3.0.1 -o openapi_usages.json -t java"`

The above produces an OpenAPI document based only on the slices generated from server.ts.

**Filter based on another attribute**

Create a filtered json that only includes slices where the resolved method equals "validateSignup".
Since no command is specified, the filtered slice is only written to a file.

`atom-tools filter -i usages.slices.json --criteria resolvedMethod=validateSignup`

**Filtering can also exclude. The first example changes to exclude server.ts like this**

`atom-tools filter -i usages.slices.json --criteria fileName!=server.ts -e "convert -f openapi3.0.1 -o openapi_usages.json -t java"`

**Multiple filter criteria may be included. The following example produces a filtered slice based
only on server.ts and router.ts slices.**

`atom-tools filter -i usages.slices.json --criteria fileName=server.ts,callName=router.ts`

### Query endpoints

The query-endpoints command lists the endpoints it finds in a slice and prints them to the console.

> Note: To suppress logging messages and ONLY output the results, use --quiet/-q

**Examples**

Query returning all endpoints, including filenames and line numbers

`atom-tools query-endpoints -i usages.slices -t js`

Query returning all endpoints without filenames and line numbers

`atom-tools query-endpoints --sparse -i usages.slices -t js`

Query filtering by line number or line number range

`atom-tools query-endpoints -i usages.slices -t js -f 50`

`atom-tools query-endpoints -i usages.slices -t js -f 50-70`

Query using the filter command to target by both filename and line number range

`atom-tools filter -i usages.slices -t js -c filename=server.ts -e "query-endpoints -f 50-70"`

### Check reachable

The check-reachable command takes either a package:version or filename:line_number/line_number_range

`atom-tools check-reachable -i reachable_slice.json -p colors:1.0.0`

`atom-tools check-reachable -i reachable_slice.json -p @colors/colors:1.0.0`

`atom-tools check-reachable -i reachable_slice.json -l file:20`

`atom-tools check-reachable -i reachable_slice.json -l file:20-40`

```
Description:
  Find out if there are hits for a given package:version or file:linenumber in an atom slice.

Usage:
  check-reachable [options]

Options:
  -i, --input-slice=INPUT-SLICE  Slice file
  -p, --pkg=PKG                  Package to search for in the format of <package_name>:<version>
  -l, --location=LOCATION        Filename with line number to search for in the format of <filename>:<linenumber>
  -h, --help                     Display help for the given command. When no command is given display help for the list command.
  -q, --quiet                    Do not output any message.
  -V, --version                  Display this application version.
      --ansi                     Force ANSI output.
      --no-ansi                  Disable ANSI output.
  -n, --no-interaction           Do not ask any interactive question.
  -v|vv|vvv, --verbose           Increase the verbosity of messages: 1 for normal output, 2 for more verbose output and 3 for debug.

Help:
  The check-reachables command checks for reachable flows for a package:version or file:linenumber in an atom slice.
```

### Validate lines

The validate-lines command checks the accuracy of the line numbers reported by atom against your
source files.

```
Description:
  Check the accuracy of the line numbers in an atom slice.

Usage:
  validate-lines [options]

Options:
  -i, --input-slice=INPUT-SLICE  Slice file to validate. [default: "slices.json"]
  -t, --type=TYPE                Origin type of source on which the atom slice was generated. [default: "java"]
  -d, --base-path=BASE-PATH      This should be the same path that was used by atom when the slice was generated.
  -l, --interval=INTERVAL        Try matching within a range. Ex. slice has line number 567, with interval of 5, we check lines 562-572. Use 0 for exact matching. [default: 5]
  -r, --report=REPORT            Output summary to file.  [default: "output.txt"]
  -j, --export-json=EXPORT-JSON  JSON report file to store invalid lines. Include valid lines as well using -v flag.
  -h, --help                     Display help for the given command. When no command is given display help for the list command.
  -q, --quiet                    Do not output any message.
  -V, --version                  Display this application version.
      --ansi                     Force ANSI output.
      --no-ansi                  Disable ANSI output.
  -n, --no-interaction           Do not ask any interactive question.
  -v|vv|vvv, --verbose           Increase the verbosity of messages: 1 for normal output, 2 for more verbose output and 3 for debug.

Help:
  Validate source file line numbers in an atom usages or reachables slice.
```

**Example**

> `atom-tools validate-lines -t java -j project_json_report.json -i usages.slices.json -d /home/my_project_dir`
