import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile

from startup_agent.adapters.embedding.serialization import to_bytes
from startup_agent.cv.loader import read_pdf_text
from startup_agent.ports.embedder import Embedder

from api.deps import get_embedder, get_settings
from api.repos import get_scoped_repo

router = APIRouter()


@router.get("/cv")
def cv_status(repo=Depends(get_scoped_repo)) -> dict:
    """Whether this user already has a stored CV — so the UI can skip re-uploading."""
    cv = repo.get_cv()
    if not cv:
        return {"has_cv": False, "filename": None, "chars": 0}
    return {"has_cv": True, "filename": cv.get("path") or "cv.pdf",
            "chars": len(cv.get("text") or "")}


@router.post("/cv")
def upload_cv(file: UploadFile,
              embedder: Embedder = Depends(get_embedder),
              repo=Depends(get_scoped_repo),
              settings=Depends(get_settings)) -> dict:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file.file.read())
        tmp_path = tmp.name
    try:
        text = read_pdf_text(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    vector = embedder.embed([text])[0]
    repo.save_cv(path=file.filename or "cv.pdf", text=text,
                 embedding=to_bytes(vector), model=settings.active_embedding_model)
    return {"status": "ready", "chars": len(text)}
