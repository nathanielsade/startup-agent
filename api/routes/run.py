import json
import queue
import threading

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.services.ingestion import IngestionService

from api.deps import get_embedder, get_factory, get_settings
from api.matching_view import compute_matches

router = APIRouter()

_SENTINEL = object()


@router.get("/run")
def run(factory=Depends(get_factory), embedder=Depends(get_embedder),
        settings=Depends(get_settings)) -> StreamingResponse:
    # Fail fast if no CV — clean 400 instead of a mid-stream error.
    precheck = SQLiteJobRepository(settings.db_path)
    precheck.init_schema()
    if precheck.get_cv() is None:
        raise HTTPException(status_code=400, detail="No CV uploaded. Upload a CV first.")

    events: queue.Queue = queue.Queue()

    def worker():
        try:
            repo = SQLiteJobRepository(settings.db_path)  # own connection in this thread
            repo.init_schema()
            IngestionService(repo=repo, factory=factory).run(
                progress=lambda ev: events.put({"stage": "fetching", **ev})
            )
            matches = compute_matches(repo, embedder, settings.preferences_path,
                                      settings.match_threshold)
            events.put({"stage": "matching", "candidates": len(matches)})
            events.put({"stage": "done", "matched": len(matches),
                        "matches": [m.model_dump() for m in matches]})
        except Exception as error:  # noqa: BLE001 - surface any failure to the UI
            events.put({"stage": "error", "message": str(error)})
        finally:
            events.put(_SENTINEL)

    threading.Thread(target=worker, daemon=True).start()

    def stream():
        while True:
            ev = events.get()
            if ev is _SENTINEL:
                break
            yield f"data: {json.dumps(ev)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")
