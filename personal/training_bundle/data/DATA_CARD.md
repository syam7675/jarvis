# Dataset card — v2

Original synthetic seed material; no harvested chats, private records or internal Codex datasets. Dataset license: CC0-1.0. No model training performed.

- Train: 84 conversations, 28 per language, including 36 multi-turn conversations.
- Validation: 6 conversations, 2 per language.
- Test: 6 conversations, 2 per language.
- Supplementary: 6 simulated tool traces (2 per language), excluded from default SFT.
- Supplementary: 12 response preference pairs, mostly English with Hindi/Telugu cases, excluded from default SFT; not a balanced multilingual preference dataset.
- Knowledge: 20 original English operating-guidance cards with discovery tags; not a general encyclopedia.

Every supervision record is marked for native-speaker review. The original 20 task families retain their intent-disjoint split; all 12 new multi-turn families are train-only. No held-out set was moved to training. This controls exact labeled-family leakage, not all possible semantic overlap. The small held-out set cannot establish production quality. Independent evaluation and a larger reviewed corpus are required.

No verified native-language fluency, speech quality or trained-model improvement is claimed. Numeric responses and examples should be reviewed in context. The synthetic tool names/results require adaptation to the actual runtime schema; do not replay the traces as real actions. Preference examples illustrate desired behavior, not actual scored model comparisons.
