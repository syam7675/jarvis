#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
cd "$JARVIS_ROOT"
mkdir -p "$OPENJARVIS_HOME/logs"
if [[ "$JARVIS_ENGINE" == cloud ]]; then
  python - <<'PY'
import os
model = os.environ['JARVIS_MODEL']
key = ('OPENROUTER_API_KEY' if model.startswith('openrouter/') else
       'ANTHROPIC_API_KEY' if model.startswith('claude-') else 'OPENAI_API_KEY')
if not os.environ.get(key):
    raise SystemExit(f'Missing {key}. Add it securely in environment settings or your local process, then restart. Never put credentials in Git.')
PY
  exec jarvis --quiet serve --host 127.0.0.1 --port 8000 --engine cloud --model "$JARVIS_MODEL"
fi
if [[ "$JARVIS_ENGINE" != ollama ]]; then
  echo 'JARVIS_ENGINE must be cloud or ollama.' >&2
  exit 1
fi
if ! curl -fsS "http://$OLLAMA_HOST/api/tags" >/dev/null; then
  if command -v ollama >/dev/null && [[ -w "$(getent passwd "$(id -u)" | cut -d: -f6)" ]]; then
    nohup ollama serve >"$OPENJARVIS_HOME/logs/ollama.log" 2>&1 &
  elif command -v docker >/dev/null; then
    if docker container inspect syam-jarvis-ollama >/dev/null 2>&1; then
      docker start syam-jarvis-ollama >/dev/null
    else
      docker run -d --name syam-jarvis-ollama --restart unless-stopped \
        -p 127.0.0.1:11434:11434 -v syam-jarvis-models:/root/.ollama \
        -e HTTP_PROXY -e HTTPS_PROXY -e NO_PROXY -e OLLAMA_NO_CLOUD=1 \
        ollama/ollama:0.40.11 >/dev/null
    fi
  else
    echo 'Install Ollama or Docker, then rerun personal/start.sh.' >&2
    exit 1
  fi
fi
for attempt in {1..30}; do
  if curl -fsS "http://$OLLAMA_HOST/api/tags" >/dev/null; then break; fi
  sleep 1
done
curl -fsS "http://$OLLAMA_HOST/api/tags" >/dev/null
if ! python -c 'import json,os,urllib.request; data=json.load(urllib.request.urlopen("http://"+os.environ["OLLAMA_HOST"]+"/api/tags")); raise SystemExit(not any(m["name"]==os.environ["JARVIS_MODEL"] for m in data["models"]))'; then
  python - <<'PY'
import json, os, urllib.request
request = urllib.request.Request(
    "http://" + os.environ["OLLAMA_HOST"] + "/api/pull",
    data=json.dumps({"model": os.environ["JARVIS_MODEL"], "stream": False}).encode(),
    headers={"Content-Type": "application/json"},
)
try:
    with urllib.request.urlopen(request, timeout=1800) as response:
        result = json.load(response)
    if result.get("status") != "success":
        raise RuntimeError("Model download did not complete")
except Exception:
    raise SystemExit("Model download failed. Check Ollama logs and allow registry.ollama.ai and its download hosts in environment settings; rerun this script after saving.")
PY
fi
# Replace the foreground process; the task runner owns its lifetime.
exec jarvis --quiet serve --host 127.0.0.1 --port 8000 --engine ollama --model "$JARVIS_MODEL"
