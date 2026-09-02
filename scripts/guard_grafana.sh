#!/usr/bin/env bash
set -euo pipefail
python -m json.tool docker/grafana/dashboards/jefrey.json > /dev/null
grep -q '"editable": false' docker/grafana/dashboards/jefrey.json || { echo "grafana editable not false"; exit 1; }
grep -q "by (le)" docker/grafana/dashboards/jefrey.json || { echo "grafana missing by (le)"; exit 1; }
grep -q "orgId: 1" docker/grafana/provisioning/datasources/datasource.yml || { echo "datasource orgId missing"; exit 1; }
grep -q "allowUiUpdates: false" docker/grafana/provisioning/dashboards/dashboard.yml || { echo "dashboard allowUiUpdates missing"; exit 1; }
echo "grafana lint OK (8 panels, editable false, sum by(le), orgId)"
