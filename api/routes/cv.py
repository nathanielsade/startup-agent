import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile

from startup_agent.adapters.embedding.serialization import to_bytes
from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.cv.loader import read_pdf_text
from startup_agent.ports.embedder import Embedder

from api.deps import get_embedder, get_settings

router = APIRouter()


@router.post("/cv")
def upload_cv(file: UploadFile,
              embedder: Embedder = Depends(get_embedder),
              settings=Depends(get_settings)) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        text = read_pdf_text(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    vector = embedder.embed([text])[0]
    repo = SQLiteJobRepository(settings.db_path)
    repo.init_schema()
    repo.save_cv(path=file.filename or "cv.pdf", text=text,
                 embedding=to_bytes(vector), model=settings.embedding_model)
    return {"status": "ready", "chars": len(text)}
