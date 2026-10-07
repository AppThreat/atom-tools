"""Tests for the Scala converter.

A version 2 scalasem report carries every framework's routes in ``endpoints[]``
and needs no usages slice at all: `atom-tools convert -t scala -e report.json`
is the only invocation a cdxgen user has, since cdxgen no longer writes a
scala-openapi.json. Version 1 semantics slices keep the Play route path.
"""

import json
import logging
from pathlib import Path

from cleo.testers.command_tester import CommandTester
from openapi_spec_validator import validate

from atom_tools.cli.application import Application
from atom_tools.lib.converter import OpenAPI

PLAY_APP = "test/data/scala-play-app-semantics.json"
SERVICES_JVM = "test/data/scala-services-jvm-semantics.json"
V1_SLICE = "test/data/scala-v1-semantics.json"


def run_convert(tmp_path, semantics, extra_args=()):
    app = Application()
    tester = CommandTester(app.find("convert"))
    out = tmp_path / "openapi.json"
    args = ["--type", "scala", "-o", str(out), "-e", str(semantics), *extra_args]
    tester.execute(" ".join(args))
    assert out.exists(), "the OpenAPI document was not written"
    return json.loads(out.read_text(encoding="utf-8"))


def write_report(tmp_path, endpoints):
    report = json.loads(Path(PLAY_APP).read_text(encoding="utf-8"))
    report["endpoints"] = endpoints
    fixture = tmp_path / "report.json"
    fixture.write_text(json.dumps(report), encoding="utf-8")
    return fixture


def test_v2_endpoints_without_a_usages_slice(tmp_path, caplog):
    """The only input a cdxgen user has is the scalasem report: convert must
    succeed with no usages slice and must not log a warning about one."""
    with caplog.at_level(logging.WARNING):
        document = OpenAPI(
            "openapi3.0.1", "scala", str(tmp_path / "missing-usages.json"), PLAY_APP
        ).endpoints_to_openapi()
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    validate(document)
    paths = document["paths"]
    assert paths["/"]["get"]["operationId"] == "controllers.HomeController.index"
    # Path captures become OpenAPI path parameters.
    assert paths["/accounts/{id}"]["get"]["parameters"][0]["name"] == "id"
    # x-atom-usages carries the declaration location in the shape every
    # other converter uses.
    assert paths["/accounts/{id}"]["get"]["x-atom-usages"] == {"call": {"conf/routes": [5]}}
    assert paths["/accounts/{id}"]["get"]["x-scalasem-framework"] == "play"
    assert document["info"]["title"] == "play-app OpenAPI Specification"


def test_cli_converts_without_a_usages_slice(tmp_path):
    document = run_convert(tmp_path, PLAY_APP, ["-i", str(tmp_path / "missing-usages.json")])
    validate(document)
    assert document["paths"]["/admin/stats"]["get"]["operationId"] == (
        "controllers.AdminController.stats"
    )


def test_v2_mounted_router_resolves_to_one_get(tmp_path):
    """A mounted Play router resolves to its own paths; the mount point
    itself must not appear with an operation per verb."""
    paths = run_convert(tmp_path, PLAY_APP)["paths"]
    assert "/admin" not in paths
    assert set(paths["/admin/stats"].keys()) == {"get"}


def test_v2_reads_every_framework_into_a_valid_document(tmp_path):
    """endpoints[] holds cask, tapir, zio-http, http4s, akka and pekko routes
    alike; anonymous captures get names and every operationId is unique."""
    document = run_convert(tmp_path, SERVICES_JVM)
    validate(document)
    paths = document["paths"]
    assert paths["/cask/hello/{name}"]["get"]["operationId"] == "corpus.services.CaskRoutes$.hello"
    assert paths["/api/v1/items/{id}"]["get"]["operationId"] == (
        "corpus.services.TapirEndpoints$.getItem"
    )
    assert "/zio/health" in paths
    assert not [p for p in paths if "{}" in p]
    operation_ids = [op["operationId"] for item in paths.values() for op in item.values()]
    assert len(operation_ids) == len(set(operation_ids))
    assert document["info"]["title"] == "services-jvm OpenAPI Specification"


def test_v2_any_method_duplicates_and_unknown_verbs(tmp_path):
    fixture = write_report(
        tmp_path,
        [
            {"framework": "akka-http", "method": "ANY", "path": "/files/{}/{}",
             "handler": "a.Routes$.files", "file": "a/Routes.scala", "line": 3},
            {"framework": "cask", "method": "GET", "path": "/dup",
             "handler": "a.C$.one", "file": "a/C.scala", "line": 4},
            {"framework": "tapir", "method": "GET", "path": "/dup",
             "handler": "a.T$.two", "file": "a/T.scala", "line": 9},
            {"framework": "play", "method": "PROPFIND", "path": "/dav",
             "handler": "a.Dav.find", "file": "conf/routes", "line": 2},
        ],
    )
    document = run_convert(tmp_path, fixture)
    validate(document)
    files = document["paths"]["/files/{path}/{path1}"]
    assert set(files) == {"get", "put", "post", "delete", "options", "head", "patch", "trace"}
    assert all(op["x-scalasem-any-method"] for op in files.values())
    assert [p["name"] for p in files["get"]["parameters"]] == ["path", "path1"]
    dup = document["paths"]["/dup"]["get"]
    assert dup["x-scalasem-handlers"] == ["a.C$.one", "a.T$.two"]
    assert dup["x-atom-usages"]["call"] == {"a/C.scala": [4], "a/T.scala": [9]}
    assert "/dav" not in document["paths"]
    assert document["x-scalasem-unsupported-methods"] == [
        {"framework": "play", "method": "PROPFIND", "path": "/dav",
         "handler": "a.Dav.find", "file": "conf/routes", "line": 2}
    ]


def test_v1_route_file_still_converts(tmp_path):
    paths = run_convert(tmp_path, V1_SLICE)["paths"]
    assert paths["/legacy/{userName}"]["get"]["operationId"].startswith(
        "controllers.LegacyController.show"
    )
    assert paths["/legacy/submit"]["post"]["x-atom-usages"]["method"] == (
        "controllers.LegacyController.submit"
    )


def test_authenticated_endpoint_is_marked_without_an_invented_scheme(tmp_path):
    report = json.loads(Path(PLAY_APP).read_text(encoding="utf-8"))
    report["endpoints"][0]["authenticated"] = True
    fixture = tmp_path / "authenticated.json"
    fixture.write_text(json.dumps(report), encoding="utf-8")
    document = run_convert(tmp_path, fixture)
    validate(document)
    operation = document["paths"]["/admin/stats"]["get"]
    assert operation["x-scalasem-authenticated"] is True
    assert "security" not in operation


def test_missing_report_is_reported(tmp_path, caplog):
    out = tmp_path / "openapi.json"
    tester = CommandTester(Application().find("convert"))
    with caplog.at_level(logging.WARNING):
        tester.execute(f"--type scala -e {tmp_path / 'typo.json'} -o {out}")
    assert "scalasem report" in caplog.text


def test_other_languages_still_read_their_usages_slice(tmp_path):
    converter = OpenAPI("openapi3.0.1", "java", "test/data/java-piggymetrics-usages.json")
    assert converter.usages is not None
    assert converter.endpoints_to_openapi()["paths"]
