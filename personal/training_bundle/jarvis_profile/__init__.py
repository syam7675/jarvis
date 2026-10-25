"""Portable Jarvis behavior profile. No embedded model or credentials."""
from pathlib import Path

def apply(config):
    import copy
    result = copy.deepcopy(config)
    result.agent.default_system_prompt = (Path(__file__).parent.parent / 'SYSTEM_PROMPT.md').read_text()
    return result
