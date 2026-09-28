"""Small synthetic-audio smoke, not a clinical or human-speech accuracy benchmark.

Run from the repository root with `uv run --project backend python -m scripts.evaluate_local`.
Requires macOS's installed Samantha and Lekha voices. Results retain known failures.
"""
import json
import os
from pathlib import Path
import subprocess

os.environ["HF_HUB_OFFLINE"] = "1"
from faster_whisper.audio import decode_audio
from backend.translatebit.local_speech import LocalEngine

cases = [
    ("en", "Samantha", "I have had a headache for three days. I have not taken any medicine."),
    ("hi", "Lekha", "मुझे तीन दिनों से सिरदर्द है। मैंने कोई दवा नहीं ली है।"),
    ("en", "Samantha", "Sorry, I said two days, not three days."),
    ("hi", "Lekha", "मुझे बुखार नहीं है।"),
]
output = Path("output/evaluation")
output.mkdir(parents=True, exist_ok=True)
engine = LocalEngine()
results = []
for number, (language, voice, text) in enumerate(cases):
    audio = output / f"case-{number}.aiff"
    subprocess.run(["say", "-v", voice, "-o", str(audio), text], check=True)
    result = engine.process_sync(decode_audio(str(audio)), language)
    results.append({"language": language, "expected_source": text, "synthetic_voice": voice, **result})
    print(json.dumps(results[-1], ensure_ascii=False), flush=True)
(output / "local-model-results.json").write_text(json.dumps({"synthetic": True, "independent_bilingual_review": False,
    "offline_model_loading": True, "cases": results}, ensure_ascii=False, indent=2) + "\n")
