# Syam's Jarvis

Personal agents and deployment tooling built on [OpenJarvis](https://github.com/open-jarvis/OpenJarvis). Upstream source and its Apache 2.0 license are retained. Custom behavior lives in `personal/`.

## Install and start

Requirements: Python 3.12, uv, Node.js 22.22+ (24 recommended), and an OpenRouter account/API key. Linux/macOS shell instructions:

```bash
git clone https://github.com/syam7675/jarvis.git
cd jarvis
bash personal/setup.sh
bash personal/start.sh
```

Setup uses the frozen Python lockfile, builds the required Rust extension, installs the frontend's required npm version into a local tools directory, and builds the browser interface. A C compiler and supported Rust toolchain are required; setup installs rustup into the sibling tools directory when needed. Existing user configuration is preserved. State and reports live in the sibling `jarvis-state/`, outside the Git checkout. Add `OPENROUTER_API_KEY` securely through environment settings or your local process before startup. Keys stay on the server; never put them in Git or frontend code. Services bind to loopback.

The selected cloud engine is OpenRouter with `JARVIS_MODEL=openrouter/openai/gpt-5-mini`. Model availability and billing depend on your provider account; this selection has not been live-validated without a key. Change `JARVIS_MODEL` to another OpenRouter model if desired. Existing config is never overwritten by setup. Optional local fallback: set `JARVIS_ENGINE=ollama JARVIS_MODEL=qwen3:4b` before startup and install native Ollama or Docker. The cloud read-only home requires the Docker path. A successful installation is not proof of good research quality: review citations and recommendations.

After startup the API serves the built upstream interface. In another shell:

```bash
source personal/env.sh
jarvis doctor
python -m personal.team list
python -m personal.team run "Plan my next project"
python -m personal.team run "Debug this Python function" --agent coder
python -m personal.team research "Compare local AI inference options and recommend a solution"
python -m personal.skills research
jarvis skill search arxiv --source hermes
```

The task router chooses a role from the request; `--agent` overrides it. Available roles: planner, researcher, critic, reporter, coder, call_assistant. The research pipeline uses three separate model invocations and saves a dated Markdown report with review notes to `jarvis-state/reports/`. Research gets web search and HTTP retrieval; other roles provide advice or drafts. The coding role does not execute code or edit files. These are reusable on-demand role profiles, not continuously running workers. New use cases can be added as a role in `team.py` and an instructional skill in `personal/skills/`.

The local skill finder ranks maintained skills by keywords and supplies matching instructions to agents. Community discovery is provided by upstream `jarvis skill search`; install a selected skill explicitly after inspecting it. Unknown community scripts are not installed automatically.

## Phone calls

The custom adapter supports an outbound spoken-message call, not an interactive telephone conversation. Set these securely in your local process or environment settings, never in Git:

- `JARVIS_TWILIO_ACCOUNT_SID`
- `JARVIS_TWILIO_AUTH_TOKEN`
- `JARVIS_TWILIO_FROM_NUMBER` (a Twilio voice-capable number)

```bash
source personal/env.sh
python -m personal.calls plan --to +15551234567 --message "Your approved message"
# This command contacts the recipient and may incur Twilio charges:
python -m personal.calls place --to +15551234567 --message "Your approved message" --confirm
```

The first command is an offline preview. The second explicitly places a call. No calls are made during installation or testing. Interactive voice calls additionally require a public HTTPS voice webhook/media service and speech turn handling; that service is not implemented here. Upstream also offers local speech features through optional extras, which are not installed by this setup.

## Voice chat

```bash
source personal/env.sh
python -m personal.voice
```

This starts a separate loopback voice-chat interface on port 8765. Use a browser with speech recognition support and grant microphone access when you choose to speak. Speech recognition availability and processing depend on the browser; browser speech services may process audio remotely. Text entry works as a fallback. Responses use the configured server-side model and the browser's speech synthesis. This is browser voice conversation, separate from telephone calls. The cloud onboarding UI does not provide a browser preview; use it on your local machine or a supported secure forwarding setup.

## Automatic updates

The `Update OpenJarvis upstream` GitHub Action checks upstream main daily at **07:00 Asia/Kolkata** and on manual dispatch. It prepares `automation/upstream`, runs the selected tests and frontend build, and opens or refreshes an update PR. It requests auto merge when repository settings permit. Enable **Allow auto-merge** and **Allow GitHub Actions to create and approve pull requests** in repository settings for hands-off PR creation/merging. Required branch checks should include `validate`. If settings disallow these actions, the workflow reports the failure or leaves a PR for review. Conflicts stop the update and require resolution; no direct push to main occurs.

Inherited upstream release, package publishing, issue bot, and tagging workflows are removed from this personal fork; updates preserve only this fork's CI and updater. For automatic local refresh, run:

```bash
source personal/env.sh
python -m personal.watch_updates --voice
```

The supervisor starts its own API and voice services and checks `origin/main` hourly. Clean main checkouts are advanced with a fast-forward merge, dependencies/assets are refreshed, and only the services it started are restarted. Local edits, another branch, or diverged history are preserved and skipped. Setup failures or child exits stop supervision visibly. Keep this process running through your operating system's service manager for continuous operation; it does not install a system daemon. For a one-time refresh with services stopped, use `python -m personal.watch_updates --once`. Manual refresh also works:

```bash
git pull --ff-only origin main
bash personal/setup.sh
# Restart only the Jarvis process you started, then:
bash personal/start.sh
```

Check upstream locally without changing your branch: `bash personal/update.sh --check`. Initial clones must include normal history for merges (the published personal repository includes it).

## Validation and known prerequisites

```bash
source personal/env.sh
python -m pytest -q personal/tests tests/agents/test_orchestrator.py tests/cli/test_skill_cmd.py tests/core/test_config.py
ruff check personal
```

Unit tests use fake inference and mocked Twilio requests; they do not demonstrate a real model answer, a successful web search, microphone recognition, or a placed call. A functional model check is `jarvis --quiet ask -e "$JARVIS_ENGINE" -m "$JARVIS_MODEL" "Reply with READY"`. Then run an actual research question and inspect its sources.

Required cloud/search domains are `openrouter.ai`, `api.you.com`, and DuckDuckGo hosts. Optional local-model downloads need `registry.ollama.ai` and model blob hosts under `*.r2.cloudflarestorage.com`. `api.twilio.com` is needed for calls, and `api.github.com` for GitHub CLI/API operations. Read-only source retrieval may require additional research source domains. The cloud draft records these requirements; saving a draft does not apply or publish it.
