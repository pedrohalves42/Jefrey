"""tests/test_p5_alerts_drill.py — P5-04 firing drill gates (Livro4 cap10, Axiom #6)"""
import pathlib
import yaml
import py_compile

def test_alerts_test_yaml_valid():
    p = pathlib.Path("docker/prometheus/tests/alerts_test.yml")
    assert p.exists(), "alerts_test.yml missing — P5-04a"
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert "rule_files" in data
    assert any("alerts.yml" in r for r in data["rule_files"])
    assert data["evaluation_interval"] == "1m"
    tests = data["tests"]
    assert len(tests) == 7, f"expected 7 alert groups, got {len(tests)}"
    # check alert_rule_test structure (promtool 2.53)
    for t in tests:
        assert "alert_rule_test" in t, f"missing alert_rule_test in {t}"
        assert "input_series" in t and len(t["input_series"]) >= 1
        for art in t["alert_rule_test"]:
            assert "eval_time" in art
            assert "alertname" in art
            assert "exp_alerts" in art
            assert len(art["exp_alerts"]) >= 1
            assert art["exp_alerts"][0]["exp_labels"]["severity"] in ("critical", "warning")
    names = [t["alert_rule_test"][0]["alertname"] for t in tests]
    assert "JefreyConfigInvalid" in names
    assert "JefreyApiHighErrorRate" in names
    assert "JefreyRateLimitDenialsHigh" in names
    assert "JefreyKidLegacyHigh" in names
    assert "JefreyMemoryLatencyHigh" in names
    assert "JefreyServiceDown" in names
    assert "JefreySttLatencyHigh" in names

def test_drill_script_py_compile_and_no_user_id():
    p = pathlib.Path("scripts/drill_alerts.py")
    assert p.exists()
    py_compile.compile(str(p), doraise=True)
    txt = p.read_text(encoding="utf-8")
    assert "FAIL-CLOSED" in txt
    assert "JEFREY_ENV" in txt
    assert "labelnames.*user_id" not in txt
    # no metric label user_id
    for line in txt.splitlines():
        if "labelnames" in line:
            assert "user_id" not in line, f"user_id label forbidden (cap5): {line}"
    for name in ["ConfigInvalid", "RateLimitDenialsHigh", "KidLegacyHigh", "MemoryLatencyHigh", "ApiHighErrorRate", "ServiceDown"]:
        assert name in txt, f"drill {name} missing"

def test_drill_help_lists_6():
    import subprocess, sys
    r = subprocess.run([sys.executable, "scripts/drill_alerts.py", "--help"], capture_output=True, text=True)
    assert r.returncode == 0
    assert "ConfigInvalid" in r.stdout or "alert" in r.stdout.lower()

def test_alerts_yaml_has_6_with_for_and_severity():
    data = yaml.safe_load(pathlib.Path("docker/prometheus/alerts.yml").read_text(encoding="utf-8"))
    rules = data["groups"][0]["rules"]
    assert len(rules) == 7
    for rule in rules:
        assert "alert" in rule and "expr" in rule
        assert "for" in rule, f"{rule['alert']} missing for"
        assert "severity" in rule["labels"]
        assert rule["labels"]["severity"] in ("critical", "warning")
    mem = [r for r in rules if r["alert"] == "JefreyMemoryLatencyHigh"][0]
    assert "by (le)" in mem["expr"], "MemoryLatency must be sum by(le) per Livro4 cap6 p.132"
    for r in rules:
        assert "user_id" not in r["expr"], f"{r['alert']} must not contain user_id (cap5)"
