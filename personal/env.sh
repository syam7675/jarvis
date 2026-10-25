#!/usr/bin/env bash
# Source this from the repository root before using the CLI.
JARVIS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export JARVIS_ROOT
export VIRTUAL_ENV="$JARVIS_ROOT/.venv"
export OPENJARVIS_HOME="${OPENJARVIS_HOME:-$(dirname "$JARVIS_ROOT")/jarvis-state}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-$(dirname "$JARVIS_ROOT")/.cache/uv}"
export JARVIS_TOOLS="${JARVIS_TOOLS:-$(dirname "$JARVIS_ROOT")/jarvis-tools}"
export JARVIS_ENGINE="${JARVIS_ENGINE:-cloud}"
export JARVIS_MODEL="${JARVIS_MODEL:-openrouter/openai/gpt-5-mini}"
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
export OLLAMA_MODELS="${OLLAMA_MODELS:-$OPENJARVIS_HOME/models}"
export OLLAMA_NO_CLOUD=1
export CARGO_HOME="${CARGO_HOME:-$JARVIS_TOOLS/cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-$JARVIS_TOOLS/rustup}"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$JARVIS_TOOLS/rust-target}"
export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-4}"
export PATH="$JARVIS_ROOT/.venv/bin:$JARVIS_TOOLS/npm/node_modules/.bin:$CARGO_HOME/bin:$PATH"
