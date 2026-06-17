"""Tests for the apk analysis pipeline helpers."""

import os

from atom_tools.lib.apk_pipeline import (
    build_cyclonedx_services,
    categorize_tags,
    collect_attribution,
    collect_behaviours,
    collect_tags,
    dex_callgraph_path,
    enrich_bom_with_services,
    find_apps,
    is_dangerous_permission,
    summarize_bom,
)


def test_find_apps_directory(tmp_path):
    (tmp_path / "a.apk").write_text("")
    (tmp_path / "b.apkm").write_text("")
    (tmp_path / "c.txt").write_text("")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "d.aab").write_text("")
    found = find_apps(str(tmp_path))
    assert sorted(os.path.basename(f) for f in found) == ["a.apk", "b.apkm", "d.aab"]


def test_find_apps_single_file(tmp_path):
    app = tmp_path / "single.apkm"
    app.write_text("")
    assert find_apps(str(app)) == [str(app)]
    other = tmp_path / "single.txt"
    other.write_text("")
    assert find_apps(str(other)) == []


def test_is_dangerous_permission():
    assert is_dangerous_permission("android.permission.CAMERA")
    assert is_dangerous_permission("android.permission.ACCESS_FINE_LOCATION")
    assert not is_dangerous_permission("android.permission.INTERNET")


def test_summarize_bom():
    bom = {
        "metadata": {
            "component": {
                "components": [
                    {
                        "name": "com.example.app",
                        "version": "1.0",
                        "properties": [
                            {
                                "name": "internal.appPermissions",
                                "value": "android.permission.CAMERA\nandroid.permission.INTERNET",
                            },
                            {
                                "name": "internal.appFeatures",
                                "value": "android.hardware.camera",
                            },
                            {"name": "internal:minSdkVersion", "value": "29"},
                        ],
                    }
                ]
            }
        },
        "components": [
            {
                "name": "okhttp",
                "version": "4.0",
                "purl": "pkg:maven/okhttp@4.0",
                "type": "library",
            }
        ],
    }
    summary = summarize_bom(bom)
    assert summary["name"] == "com.example.app"
    assert summary["version"] == "1.0"
    assert summary["permissions"] == [
        "android.permission.CAMERA",
        "android.permission.INTERNET",
    ]
    assert summary["features"] == ["android.hardware.camera"]
    assert summary["properties"]["internal:minSdkVersion"] == "29"
    assert len(summary["components"]) == 1


def test_collect_behaviours_aggregates_and_sorts():
    bom = {
        "components": [
            {
                "name": "classes",
                "properties": [
                    {"name": "internal:behaviours", "value": "ANDROID_REFLECTION"},
                    {
                        "name": "internal:behaviour:ANDROID_REFLECTION",
                        "value": "medium|10|La/A; -> forName",
                    },
                    {
                        "name": "internal:behaviour:ANDROID_NATIVE_EXEC",
                        "value": "high|2|Lb/B; -> loadLibrary",
                    },
                ],
            },
            {
                "name": "classes2",
                "properties": [
                    {
                        "name": "internal:behaviour:ANDROID_REFLECTION",
                        "value": "medium|5|Lc/C; -> invoke",
                    },
                ],
            },
        ]
    }
    behaviours = collect_behaviours(bom)
    # high severity sorts first; reflection counts sum across the two dex files.
    assert behaviours[0]["id"] == "ANDROID_NATIVE_EXEC"
    refl = next(b for b in behaviours if b["id"] == "ANDROID_REFLECTION")
    assert refl["count"] == 15
    assert refl["evidence"] == "La/A; -> forName"


def test_collect_behaviours_empty():
    assert collect_behaviours(None) == []
    assert collect_behaviours({"components": []}) == []


def test_dex_callgraph_path(tmp_path):
    bom = tmp_path / "app.bom.json"
    bom.write_text("{}")
    app = "/some/path/base.apkm"
    cg = tmp_path / "app.bom-base.apkm.dex-callgraph.json"
    assert dex_callgraph_path(str(bom), app) is None
    cg.write_text("{}")
    assert dex_callgraph_path(str(bom), app) == str(cg)


def test_summarize_bom_empty():
    summary = summarize_bom(None)
    assert summary["name"] == ""
    assert summary["components"] == []


def test_collect_tags_handles_shapes():
    found = {}
    collect_tags(
        {
            "flows": [
                {"tags": "pii|tracker"},
                {"tags": ["service-egress", "pii"]},
                {"nested": {"tags": [{"name": "on-device-ai"}]}},
            ]
        },
        found,
    )
    assert found["pii"] == 2
    assert found["tracker"] == 1
    assert found["service-egress"] == 1
    assert found["on-device-ai"] == 1


def test_categorize_tags():
    reachables = [
        {"flows": [{"tags": "pii-email|tracker-analytics"}]},
        {"flows": [{"tags": ["service-egress", "on-device-ai", "secret-credential"]}]},
    ]
    categorized = categorize_tags(reachables)
    assert "PII / Sensitive data" in categorized
    assert "pii-email" in categorized["PII / Sensitive data"]
    assert "Trackers / Adware" in categorized
    assert "Data egress (sinks)" in categorized
    assert "On-device AI" in categorized
    assert "Secrets / Credentials" in categorized


def test_categorize_tags_empty():
    assert categorize_tags(None) == {}
    assert categorize_tags([]) == {}


def test_collect_attribution_services_and_trackers():
    reachables = [
        {
            "flows": [
                {
                    "tags": [
                        "service-egress",
                        "service-ai-llm",
                        "service:OpenAI",
                        "pii-email",
                    ]
                },
                {"tags": ["service-egress", "service-ai-llm", "service:OpenAI"]},
                {
                    "tags": [
                        "service-ingress",
                        "service-http",
                        "service:HttpURLConnection",
                    ]
                },
                {"tags": "tracker|tracker-crash-reporting|tracker:Sentry"},
            ]
        },
    ]
    services, trackers = collect_attribution(reachables)
    assert services["OpenAI"]["flows"] == 2
    assert services["OpenAI"]["categories"] == {"ai-llm"}
    assert services["OpenAI"]["egress"] is True
    assert services["OpenAI"]["ingress"] is False
    assert services["HttpURLConnection"]["ingress"] is True
    assert services["HttpURLConnection"]["egress"] is False
    assert trackers["Sentry"]["flows"] == 1
    assert trackers["Sentry"]["categories"] == {"crash-reporting"}


def test_build_cyclonedx_services_flow_direction():
    services = {
        "OpenAI": {
            "categories": {"ai-llm"},
            "flows": 5,
            "egress": True,
            "ingress": False,
            "local": False,
        },
        "HttpURLConnection": {
            "categories": {"http"},
            "flows": 9,
            "egress": False,
            "ingress": True,
            "local": False,
        },
        "LocalLLM": {
            "categories": {"ai-local"},
            "flows": 2,
            "egress": False,
            "ingress": False,
            "local": True,
        },
    }
    built = {s["name"]: s for s in build_cyclonedx_services(services)}
    assert built["OpenAI"]["data"][0]["flow"] == "inbound"
    assert built["OpenAI"]["data"][0]["classification"] == "ai-llm"
    assert built["OpenAI"]["bom-ref"] == "service:OpenAI"
    assert built["OpenAI"]["x-trust-boundary"] is True
    assert built["HttpURLConnection"]["data"][0]["flow"] == "outbound"
    assert built["LocalLLM"]["data"][0]["flow"] == "inbound"
    assert built["LocalLLM"]["x-trust-boundary"] is False


def test_enrich_bom_with_services_idempotent():
    bom = {"bomFormat": "CycloneDX", "components": []}
    services = [{"bom-ref": "service:OpenAI", "name": "OpenAI", "data": []}]
    enrich_bom_with_services(bom, services)
    assert len(bom["services"]) == 1
    # Running again must not duplicate the service.
    enrich_bom_with_services(bom, services)
    assert len(bom["services"]) == 1
    assert bom["services"][0]["name"] == "OpenAI"


def test_enrich_bom_merges_without_replacing_components():
    # A blint-produced BOM with components and a statically-detected service.
    bom = {
        "bomFormat": "CycloneDX",
        "components": [{"name": "libfoo.so", "type": "library"}],
        "services": [
            {
                "bom-ref": "service:Sentry",
                "name": "Sentry",
                "data": [{"flow": "unknown", "classification": "crash-reporting"}],
            },
            {
                "bom-ref": "service:Stripe",
                "name": "Stripe",
                "data": [{"flow": "unknown", "classification": "payment"}],
            },
        ],
    }
    # atom refines Stripe with a reachability-observed direction and adds OpenAI.
    atom_services = [
        {
            "bom-ref": "service:Stripe",
            "name": "Stripe",
            "data": [{"flow": "inbound", "classification": "payment"}],
        },
        {
            "bom-ref": "service:OpenAI",
            "name": "OpenAI",
            "data": [{"flow": "inbound", "classification": "ai-llm"}],
        },
    ]
    enrich_bom_with_services(bom, atom_services)
    # Components are untouched.
    assert bom["components"] == [{"name": "libfoo.so", "type": "library"}]
    by_ref = {s["bom-ref"]: s for s in bom["services"]}
    # blint-only service is preserved.
    assert by_ref["service:Sentry"]["data"][0]["flow"] == "unknown"
    # Shared service is refined by atom (no duplicate).
    assert by_ref["service:Stripe"]["data"][0]["flow"] == "inbound"
    # atom-only service is added.
    assert by_ref["service:OpenAI"]["data"][0]["flow"] == "inbound"
    assert len(bom["services"]) == 3


def test_resolve_blint_from_venv(tmp_path):
    from atom_tools.lib.apk_pipeline import resolve_blint

    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    blint = venv / "bin" / "blint"
    blint.write_text("#!/bin/sh\n")
    blint.chmod(0o755)
    # Resolves from a venv directory.
    assert resolve_blint(str(venv)) == str(blint)
    # Resolves when pointed at the bin directory.
    assert resolve_blint(str(venv / "bin")) == str(blint)
    # Resolves when pointed at the executable directly.
    assert resolve_blint(str(blint)) == str(blint)


def test_resolve_blint_missing_venv_falls_back(tmp_path, monkeypatch):
    from atom_tools.lib import apk_pipeline

    monkeypatch.delenv("BLINT_HOME", raising=False)
    monkeypatch.setattr(apk_pipeline, "resolve_tool", lambda names: "/usr/bin/blint")
    # A venv with no blint falls back to PATH resolution.
    assert apk_pipeline.resolve_blint(str(tmp_path)) == "/usr/bin/blint"
