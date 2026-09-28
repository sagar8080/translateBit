"""Explicit one-time model downloads/conversion. Runtime inference stays offline."""
import hashlib
import json
from pathlib import Path
import subprocess

from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
MODELS.mkdir(exist_ok=True)
WHISPER = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
WHISPER_REVISION = "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf"
TRANSLATOR = "facebook/m2m100_418M"
TRANSLATOR_REVISION = "55c2e61bbf05dfb8d7abccdc3fae6fc8512fd636"

snapshot_download(WHISPER, revision=WHISPER_REVISION, local_dir=MODELS / "whisper-turbo",
    allow_patterns=["config.json", "model.bin", "tokenizer.json", "vocabulary.*", "preprocessor_config.json"])
if not (MODELS / "m2m100/model.bin").exists():
    source = snapshot_download(TRANSLATOR, revision=TRANSLATOR_REVISION,
        allow_patterns=["config.json", "pytorch_model.bin", "sentencepiece.bpe.model", "tokenizer_config.json", "vocab.json"])
    subprocess.run([
        "uv", "run", "--no-project", "--with", "ctranslate2==4.8.2", "--with", "transformers==4.57.6",
        "--with", "torch==2.14.0", "--with", "sentencepiece==0.2.2", "python", "-c",
        "from ctranslate2.converters.transformers import main; main()",
        "--model", source, "--output_dir", str(MODELS / "m2m100"), "--quantization", "int8",
        "--copy_files", "sentencepiece.bpe.model", "tokenizer_config.json", "vocab.json",
    ], cwd=ROOT, check=True)
manifest = {
    "whisper": {"repository": WHISPER, "revision": WHISPER_REVISION, "license": "MIT"},
    "translation": {"repository": TRANSLATOR, "revision": TRANSLATOR_REVISION, "license": "MIT", "quantization": "int8"},
}
for name, directory in (("whisper", "whisper-turbo"), ("translation", "m2m100")):
    with (MODELS / directory / "model.bin").open("rb") as model:
        manifest[name]["sha256"] = hashlib.file_digest(model, "sha256").hexdigest()
(MODELS / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
print("Models are ready for offline inference.")
