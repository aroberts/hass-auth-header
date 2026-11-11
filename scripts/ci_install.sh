#!/usr/bin/env bash
# Install a Home Assistant core plus its test harness into the active virtualenv.
#
# Usage: scripts/ci_install.sh <harness-version|latest> <ha-version|latest> [requirement...]
#
# Extra requirements are installed and also applied as overrides. Use them to pin transitive
# packages that newer releases broke for an old core, e.g. "josepy<2".
set -euo pipefail

HARNESS=$1
HA=$2
shift 2

pypi_json() {
  curl -sSf "https://pypi.org/pypi/$1/json"
}

if [ "$HARNESS" = latest ]; then
  HARNESS=$(pypi_json pytest-homeassistant-custom-component | python3 -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])')
fi
if [ "$HA" = latest ]; then
  HA=$(pypi_json homeassistant | python3 -c 'import json,sys; print(json.load(sys.stdin)["info"]["version"])')
fi
HARNESS_HA=$(pypi_json "pytest-homeassistant-custom-component/$HARNESS" | python3 -c '
import json, re, sys
reqs = json.load(sys.stdin)["info"]["requires_dist"] or []
pins = [m[1] for r in reqs if (m := re.match(r"homeassistant\s*\(?==\s*([^\s)]+)", r))]
print(pins[0] if pins else "")
')
echo "Installing homeassistant==$HA with pytest-homeassistant-custom-component==$HARNESS (pins $HARNESS_HA)"

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# Pin everything to what this core release shipped with. Drop include lines such as "-r".
curl -sSf "https://raw.githubusercontent.com/home-assistant/core/$HA/homeassistant/package_constraints.txt" \
  | grep -vE '^\s*-' > "$WORK/constraints.txt"

# Overriding homeassistant lets the harness run against a core newer than the one it pins.
printf '%s\n' "homeassistant==$HA" "$@" > "$WORK/overrides.txt"

if [ "$HARNESS_HA" = "$HA" ]; then
  uv pip install -c "$WORK/constraints.txt" --override "$WORK/overrides.txt" \
    "pytest-homeassistant-custom-component==$HARNESS" "homeassistant==$HA" "$@"
else
  # The harness pins exact versions from an older core, which conflict with this core's
  # constraints. Apply the constraints as overrides so this core's pins win. Skip packages
  # the extra requirements already override.
  python3 - "$WORK/constraints.txt" "$@" >> "$WORK/overrides.txt" <<'EOF'
import re, sys
name = lambda req: re.split(r"[\s<>=!~;\[]", req, maxsplit=1)[0].lower().replace("_", "-")
skip = {name(req) for req in sys.argv[2:]}
for line in open(sys.argv[1]):
    line = line.strip()
    if line and not line.startswith("#") and name(line) not in skip:
        print(line)
EOF
  uv pip install --override "$WORK/overrides.txt" \
    "pytest-homeassistant-custom-component==$HARNESS" "homeassistant==$HA" "$@"
fi
