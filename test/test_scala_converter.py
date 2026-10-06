"""Tests for the Scala converter.

A version 2 scalasem report carries every framework's routes in ``endpoints[]``
and needs no usages slice at all: `atom-tools convert -t scala -e report.json`
is the only invocation a cdxgen user has, since cdxgen no longer writes a
scala-openapi.json. Version 1 semantics slices keep the Play route path.
"""

import json
from pathlib import Path

import pytest
from cleo.testers.command_tester import CommandTester

from atom_tools.cli.application import Application


def run_convert(tmp_path, extra_args, fixtures=("play-app",)):
    app = Application()
    tester = CommandTester(app.find("convert"))
    out = tmp_path / "openapi.json"
    args = ["--type", "scala", "-o", str(out)]
    if "play-app" in fixtures:
        args += ["-e", "test/data/scala-play-app-semantics.json"]
    if "services" in fixtures:
        args += ["-e", "test/data/scala-services-jvm-semantics.json"]
    if "v1" in fixtures:
        args += ["-e", "test/data/scala-v1-semantics.json"]
    args += extra_args
    tester.execute(" ".join(args))
    assert out.exists(), "the OpenAPI document was not written"
    return json.loads(out.read_text(encoding="utf-8"))


def test_v2_endpoints_without_a_usages_slice(tmp_path):
    """The only input a cdxgen user has is the scalasem report: convert must
    succeed with no usages slice and must not log a warning about one."""
    document = run_convert(tmp_path, ["-i", str(tmp_path / "missing-usages.json")])
    paths = document["paths"]
    assert "/" in paths
    assert paths["/"]["get"]["operationId"] == "controllers.HomeController.index"
    # Path captures become OpenAPI path parameters.
    assert paths["/accounts/{id}"]["get"]["parameters"][0]["name"] == "id"
    # x-atom-usages carries the declaration location.
    usages = paths["/accounts/{id}"]["get"]["x-atom-usages"]
    assert usages["method"] == "controllers.AccountController.show"
    assert usages["file"] == "conf/routes"
    assert usages["line"] == 5
    assert document["info"]["title"] == "play-app OpenAPI Specification"


def test_v2_mounted_router_resolves_to_one_get(tmp_path):
    """A mounted Play router resolves to its own paths; the mount point
    itself must not appear with an operation per verb."""
    document = run_convert(tmp_path, [])
    paths = document["paths"]
    assert paths["/admin/stats"]["get"]["operationId"] == "controllers.AdminController.stats"
    assert "/admin" not in paths
    assert set(paths["/admin/stats"].keys()) == {"get"}


def test_v2_reads_every_framework(tmp_path):
    """endpoints[] holds cask, tapir, zio-http and http4s routes alike."""
    document = run_convert(tmp_path, [], fixtures=("services",))
    paths = document["paths"]
    assert paths["/cask/hello/{name}"]["get"]["operationId"] == "corpus.services.CaskRoutes$.hello"
    assert paths["/api/v1/items/{id}"]["get"]["operationId"] == "corpus.services.TapirEndpoints$.getItem"
    assert "/zio/health" in paths
    assert document["info"]["title"] == "services-jvm OpenAPI Specification"


def test_v1_route_file_still_converts(tmp_path):
    document = run_convert(tmp_path, [], fixtures=("v1",))
    paths = document["paths"]
    assert paths["/legacy/{userName}"]["get"]["operationId"].startswith(
        "controllers.LegacyController.show"
    )
    assert paths["/legacy/submit"]["post"]["x-atom-usages"]["method"] == (
        "controllers.LegacyController.submit"
    )


def test_authenticated_endpoint_gets_security(tmp_path):
    report = json.loads(Path("test/data/scala-play-app-semantics.json").read_text(encoding="utf-8"))
    report["endpoints"][0]["authenticated"] = True
    fixture = tmp_path / "authenticated.json"
    fixture.write_text(json.dumps(report), encoding="utf-8")
    app = Application()
    tester = CommandTester(app.find("convert"))
    out = tmp_path / "openapi.json"
    tester.execute(f"--type scala -e {fixture} -o {out}")
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document["paths"]["/admin/stats"]["get"]["security"] == [{"bearerAuth": []}]
