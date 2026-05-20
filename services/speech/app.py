from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from faster_whisper import WhisperModel


app = FastAPI(title="ASM Digital Speech")
_model: WhisperModel | None = None


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        _model = WhisperModel(
            os.getenv("WHISPER_MODEL_SIZE", "base"),
            device=os.getenv("WHISPER_DEVICE", "cpu"),
            compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
            download_root="/models",
        )
    return _model


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form("pt"),
    prompt: str = Form(""),
) -> dict[str, str]:
    suffix = Path(file.filename or "voice.ogg").suffix or ".ogg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        segments, info = get_model().transcribe(
            tmp_path,
            language=language or "pt",
            task="transcribe",
            beam_size=int(os.getenv("WHISPER_BEAM_SIZE", "8")),
            best_of=int(os.getenv("WHISPER_BEST_OF", "5")),
            temperature=0.0,
            vad_filter=True,
            condition_on_previous_text=False,
            initial_prompt=(
                "Transcricao em portugues do Brasil. ASM Digital. Assistente de Gestao. "
                "Agendar reuniao. Marcar reuniao. Proxima quarta. Proxima sexta. "
                "Amanha. Depois de amanha. Semana que vem. Ferias. Feira. "
                "Leandro Machado. Leandro Montenegro Machado. Alessandra Nunes. "
                "Alessandra Martins Nunes. Anderson Machado. Demandas atrasadas. "
                f"Pendencias. Redmine. {prompt}"
            ),
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text).strip()
        return {
            "text": text,
            "language": info.language or "pt",
            "language_probability": str(info.language_probability),
        }
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
