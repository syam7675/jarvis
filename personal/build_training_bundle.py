"""Package portable, explicitly untrained Jarvis seed data and recipes."""

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent / "training_bundle"
files = sorted(
    p
    for p in root.rglob("*")
    if p.is_file() and "__pycache__" not in p.parts and p.name != "MANIFEST.json"
)
manifest = {
    "package_version": "2.0.0",
    "training_status": "NOT_TRAINED",
    "model_weights_included": False,
    "dataset": {
        "train": 84,
        "validation": 6,
        "test": 6,
        "tool_traces_separate": 6,
        "preference_pairs_separate": 12,
        "knowledge_cards": 20,
        "independent_evaluation_cases": 18,
        "languages": ["te", "en", "hi"],
        "source": "original synthetic seed; native review required",
    },
    "verified": [
        "dataset schema",
        "split separation by intent",
        "memory consent, owner isolation, correction, export, deletion",
        "Python compilation",
        "bounded lexical knowledge retrieval",
        "supplementary data schema",
        "archive checksum verification",
    ],
    "unverified": [
        "actual model fine-tuning",
        "trained model quality",
        "native-speaker review",
        "ASR and TTS performance",
    ],
    "files": {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in files
    },
}
(root / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
out = root.parent / "jarvis-training-kit-v2.zip"
with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
    for path in files + [root / "MANIFEST.json"]:
        archive.write(path, Path("jarvis-training-kit-v2") / path.relative_to(root))
print(out)
print("SHA256", hashlib.sha256(out.read_bytes()).hexdigest())
