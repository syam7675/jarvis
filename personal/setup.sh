#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$JARVIS_ROOT"
uv sync --frozen --extra dev --extra server --extra tools-search --extra memory-bm25 --extra inference-cloud
mkdir -p "$OPENJARVIS_HOME/logs" "$OPENJARVIS_HOME/models" "$JARVIS_TOOLS"
if ! command -v cargo >/dev/null; then
  rustup_installer=$(mktemp)
  curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs -o "$rustup_installer"
  sh "$rustup_installer" -y --no-modify-path --profile minimal --default-toolchain stable
  rm -f "$rustup_installer"
fi
# Permissions, rate limiting, and several core tools require the native module.
maturin develop --locked --manifest-path rust/crates/openjarvis-python/Cargo.toml
if [[ ! -f "$OPENJARVIS_HOME/config.toml" ]]; then
  cat > "$OPENJARVIS_HOME/config.toml" <<EOF
[engine]
default = "$JARVIS_ENGINE"
[intelligence]
default_model = "$JARVIS_MODEL"
temperature = 0.3
[agent]
default_agent = "orchestrator"
max_turns = 12
default_system_prompt = "You are Syam's Jarvis. Be accurate, cite evidence, and distinguish completed actions from proposals."
[tools]
enabled = "think,calculator,web_search,http_request"
[server]
host = "127.0.0.1"
port = 8000
[telemetry]
enabled = false
[analytics]
enabled = false
[skills]
enabled = true
auto_discover = true
auto_sync = false
sandbox_dangerous = true
[[skills.sources]]
source = "hermes"
auto_update = false
EOF
fi
# Keep npm's pinned engine requirement; do not bypass it.
npm install --prefix "$JARVIS_TOOLS/npm" npm@11.19.0 --cache "$(dirname "$JARVIS_ROOT")/.cache/npm"
cd frontend
"$JARVIS_TOOLS/npm/node_modules/.bin/npm" ci --ignore-scripts --cache "$(dirname "$JARVIS_ROOT")/.cache/npm"
# tsc writes a tracked build-info file. Preserve its original bytes.
build_info_backup=$(mktemp)
cp tsconfig.tsbuildinfo "$build_info_backup"
trap 'cp "$build_info_backup" tsconfig.tsbuildinfo; rm -f "$build_info_backup"' EXIT
"$JARVIS_TOOLS/npm/node_modules/.bin/npm" run build
