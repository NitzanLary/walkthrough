from pathlib import Path

WT_DIR = Path(".walkthrough")
WT_JSON = WT_DIR / "walkthrough.json"
AUDIO_DIR = WT_DIR / "audio"

# Measured against ElevenLabs: a 1,025-word script the 400ms nominal rate put at
# 6:50 came back at 7:27, so plan and validate against the voice that actually
# speaks (~138 wpm), not the faster one the rate card implies.
MS_PER_WORD = 435
# Per-chapter ceiling from the authoring rules; longer explanations split into a
# zoom + scroll pair rather than running as one static shot.
CHAPTER_BUDGET_MS = 25_000
