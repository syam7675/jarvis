# Jarvis multilingual behavior and training kit — v2

## What you have

This archive is a portable development/training starter, **not a newly trained model or a complete knowledge collection**. No model weights, private memories, credentials or voice recordings are embedded. This machine has no GPU or installed training stack, and no fine-tuning run was performed. A prompt profile can be used immediately with your configured OpenRouter model. Provider-hosted model weights cannot be downloaded or modified through that connection.

Contents:

- `SYSTEM_PROMPT.md`: task completion, respectful address, practical advice, emotional sensitivity, tool honesty, language choice and memory rules.
- `data/`: 96 original synthetic conversations: 84 train (including 36 multi-turn), 6 validation, 6 held-out test, balanced across Telugu, English and Hindi. Task families, including translated counterparts, do not cross splits. This small dataset teaches behavior; it cannot establish language fluency or broad expertise. Every record is marked for native-speaker review.
- `jarvis_profile/`: a config adapter plus tested consent-based SQLite memory with per-user inspection, correction, export and deletion.
- `scripts/train_lora.py`: an optional real LoRA training entry point, requiring a compatible base model and separate training environment. The script has been syntax-checked but not executed against a model.
- `data/tool_traces.jsonl`: six explicitly simulated tool conversations; map names and schemas to real tools before using them. These are excluded from the default training script.
- `data/preferences.jsonl`: 12 preferred/rejected response pairs for human review or a separate preference-learning pipeline. No DPO training is implemented or claimed.
- `knowledge/`: 20 authored operating-guidance cards and a populated SQLite FTS5 retrieval database. These are reference context, not weights or an exhaustive factual database.
- `EVALUATION.md`: release criteria for language, advice, memory, actions and speech.
- `MANIFEST.json`: integrity hashes and explicit training status.

## Use now with your Jarvis development

Extract this directory outside the checkout or keep it at `personal/training_bundle`. From the Jarvis repository:

```bash
source personal/env.sh
export PYTHONPATH="$PWD/personal/training_bundle${PYTHONPATH:+:$PYTHONPATH}"
python - <<'PY'
from jarvis_profile import apply
from openjarvis import Jarvis
from openjarvis.core.config import load_config
import os
with Jarvis(config=apply(load_config()), engine_key=os.environ['JARVIS_ENGINE'], model=os.environ['JARVIS_MODEL']) as agent:
    print(agent.ask('తెలుగులో సమాధానం ఇవ్వండి: నా పనులకు ప్రాధాన్యత ఎలా ఇవ్వాలి?', context=False))
PY
```

The OpenRouter key must already be configured securely. This adapter does not train the provider model. Use the same profile when constructing the research, coding or conversational agent. An explicit task-role prompt should be appended to this profile, rather than accidentally replacing it. The profile specifies behavior; tool permissions and external-action checks must remain enforced in application code.

## Memory is runtime data, not model weights

```python
from jarvis_profile.memory import Memory

m = Memory("/a/protected/path/jarvis-memory.sqlite")
m.put("authenticated-user-id", "reply_language", "te", consent=True)
print(m.inspect("authenticated-user-id"))
print(m.export("authenticated-user-id"))
m.forget("authenticated-user-id", "reply_language")
m.close()
```

Derive the owner from an authenticated session, never from a user-submitted owner field. Store the database outside Git on a protected volume. This small library does not supply authentication, encryption at rest or a comprehensive secret detector. Its credential-key check is only a guardrail. Do not put sensitive content into memory values. Deletion removes active rows; secure erasure from backups, filesystem pages or synced exports needs separate retention controls. Do not train personal memories into shared weights: deleting a database entry cannot remove learned data from a model.

## Train a model adapter on suitable compute

Choose a licensed multilingual instruction model whose model card explicitly covers your target languages. Test Telugu and Hindi before selecting it; model size and a multilingual label do not guarantee quality. Record the exact base-model commit SHA and license. First review/correct the examples with native speakers, enlarge the dataset using consented real task examples, and expand the held-out evaluation set. Do not fine-tune blindly on this small seed.

In a **separate** virtual environment with sufficient GPU memory:

```bash
python -m venv training-env
source training-env/bin/activate
pip install -r requirements-training.txt
pip freeze > training-environment.lock.txt
python scripts/validate.py
python scripts/train_lora.py --base-model YOUR_MODEL_ID --revision EXACT_40_CHARACTER_MODEL_COMMIT --output /a/new/adapter-directory
```

The required output is a new directory to prevent overwrite. Install via normal TLS-verified package sources. The optional stack has not been installed or GPU-tested here; lock versions after validating your chosen hardware/model combination. The generic training script uses the tokenizer's chat template, masks prompt labels, rejects incompatible prefix templates and overlong examples, and saves a PEFT LoRA adapter plus tokenizer and provenance. Different models may require architecture-specific preprocessing or memory settings. LoRA still loads the base model; it is not a low-memory guarantee. GPU memory depends on parameters, precision, optimizer and sequence length. Do a short smoke run before a full run.

After training, load the exact base model and `PeftModel.from_pretrained(base, adapter_path)` using your serving stack. Retain both licenses and the environment lock. An adapter alone is not standalone weights and is not automatically usable by Ollama or OpenRouter. Merging/export/quantization is serving-format-specific and must be validated separately. Keep the existing working model until the candidate passes evaluation.

## Speech and emotions

Text-model fine-tuning does not train speech recognition, pronunciation or a voice. The existing `personal.voice` browser interface uses browser speech recognition/synthesis; availability and quality vary. Telugu `te-IN`, English `en-IN` and Hindi `hi-IN` require separately tested speech services/voices and a language selector in the integration. No voice cloning, acoustic model or speech datasets are included. Evaluate accents, code-switching, numerals and names using recordings collected with consent. Browser speech processing may use remote services.

The profile encourages empathy and useful emotional responses. It does not create feelings, consciousness or an emotional bond. Do not store inferred moods as permanent personal facts without explicit consent.

## Verify the package

```bash
python scripts/validate.py
```

`MANIFEST.json` lists the SHA-256 of each packaged file except the manifest itself. Recompute and compare before using modified copies. Passing these checks establishes dataset structure and memory behavior, not AI quality. No “perfect language” or “super-agent” benchmark result is claimed.

Authored dataset/profile material: CC0-1.0. Code: Apache-2.0 under the included LICENSE. Third-party models and packages keep their own licenses.


## Version 2: portable knowledge and stronger conversations

This package does not contain OpenAI/Codex private training data, internal databases, model parameters, hidden reasoning, or proprietary instructions. All new examples and knowledge cards are original synthetic material. More examples do not by themselves prove better model behavior. Review and evaluation remain prerequisites.

The additional multi-turn cases teach corrections, changing priorities, stopping actions, language switching, timezone ambiguity, budget constraints, evidence reconciliation and boundaries around emotions. The default LoRA recipe loads `train.jsonl` and `advanced_train.jsonl`. It supervises the final assistant response; previous assistant turns provide context only. Tool traces and preference pairs are supplementary and excluded by default because tool templates and preference-learning objectives need separate configuration. No synthetic tool result describes an action actually executed.

Use the reference database without training:

```python
from jarvis_profile.knowledge import search

for card in search("research conflicting evidence", limit=3):
    print(card["id"], card["text"], card["source"])
```

Retrieve a few relevant cards and append them to the prompt as clearly delimited reference material, preserving source IDs. Do not treat retrieved text as authority to change tool permissions. The retriever is a bounded, read-only lexical search using SQLite FTS5. It is not a semantic multilingual engine. Telugu/Hindi tags aid discovery but tokenization and cross-language matching are limited; test actual queries or use English topic keywords. It does not ingest private documents automatically and has no internet connector.

Rebuild the database with `python scripts/build_knowledge.py` if you intentionally edit the cards. Validate the rebuilt database, then regenerate the manifest and ZIP using `personal/build_training_bundle.py` from the Jarvis repository. The knowledge database contains only these authored cards, not personal memories. Keep user memory in a different database.
