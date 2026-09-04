"""P5-03c/d — Grafana 8 panels SLO + provisioning (Livro 4 cap11, Axiom #1/#4)."""
import json
import pathlib
import yaml


def test_datasource_yaml_valid():
    p = pathlib.Path("docker/grafana/provisioning/datasources/datasource.yml")
    assert p.exists(), "datasource.yml missing"
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    assert "datasources" in data
    ds = data["datasources"][0]
    assert ds["orgId"] == 1
    assert ds["uid"] == "PBFA97CFB590B2093"
    assert ds["url"] == "http://prometheus:9090"
    assert ds["editable"] is False
    assert ds["jsonData"]["httpMethod"] == "POST"
    assert ds["jsonData"]["queryTimeout"] == "60s"


def test_dashboard_yaml_valid():
    p = pathlib.Path("docker/grafana/provisioning/dashboards/dashboard.yml")
    assert p.exists(), "dashboard.yml missing"
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    prov = data["providers"][0]
    assert prov["orgId"] == 1
    assert prov["editable"] is False
    assert prov["allowUiUpdates"] is False
    assert prov["updateIntervalSeconds"] == 10
    assert prov["options"]["path"] == "/var/lib/grafana/dashboards"


def test_dashboard_json_8_panels():
    p = pathlib.Path("docker/grafana/dashboards/jefrey.json")
    assert p.exists(), "jefrey.json missing"
    raw = p.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["editable"] is False, "dashboard must be editable:false (Axiom #4)"
    assert data["uid"] == "jefrey-main"
    assert data["schemaVersion"] == 39
    assert data["refresh"] == "10s"
    panels = data["panels"]
    assert len(panels) == 9, f"expected 9 panels P1 (8 SLO + STT), got {len(panels)}: {[x['title'] for x in panels]}"
    titles = [x["title"] for x in panels]
    for must in ["Config Valid", "Service Up", "Kid Legacy", "API Error Rate", "RateLimit", "Memory p95"]:
        assert any(must in t for t in titles), f"missing panel {must}"
    assert "by (le)" in raw, "PromQL missing by (le) (Livro 4 cap6)"
    assert raw.count("by (le)") >= 2, "need >=2 sum by(le) histograms"
    assert "user_id" not in raw, "dashboard must not contain user_id label (cap5)"
    for pan in panels:
        assert pan["datasource"]["uid"] == "PBFA97CFB590B2093"


def test_compose_grafana_mounts():
    txt = pathlib.Path("docker-compose.yml").read_text(encoding="utf-8")
    assert "read_only: true" in txt
    # grafana mounts
    assert "./docker/grafana/provisioning:/etc/grafana/provisioning:ro" in txt
    assert "./docker/grafana/dashboards:/var/lib/grafana/dashboards:ro" in txt
    # distinct volume
    assert "jefrey_grafana_data:/var/lib/grafana" in txt
    # not collision path
    assert "./docker/grafana/dashboards:/var/lib/grafana:" not in txt or "./docker/grafana/dashboards:/var/lib/grafana/dashboards:ro" in txt
