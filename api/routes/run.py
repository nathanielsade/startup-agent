import json
import queue
import threading

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.services.ingestion import IngestionService

from api.deps import get_embedder, get_factory, get_ranker, get_settings
from api.matching_view import match_pairs, _load_prefs
from startup_agent.services.recent_rescore import rescore_recent

router = APIRouter()

_SENTINEL = object()


@router.get("/run")
def run(factory=Depends(get_factory), embedder=Depends(get_embedder),
        ranker=Depends(get_ranker), settings=Depends(get_settings)) -> StreamingResponse:
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
                progress=lambda ev: events.put({"stage": "fetching", **ev}))
            pairs = match_pairs(repo, embedder, settings.preferences_path, settings.match_threshold)
            events.put({"stage": "matching", "candidates": len(pairs)})
            companies = repo.get_companies()
            names = {c.id_hash: c.name for c in companies}
            links = {c.id_hash: c.linkedin_url for c in companies}
            if ranker is not None:
                events.put({"stage": "rating", "count": len(pairs)})
                cv = repo.get_cv()
                prefs = _load_prefs(repo, settings.preferences_path)
                matches = rescore_recent(pairs, ranker, cv["text"], prefs,
                                         settings.llm_recent_hours, names, company_links=links)
            else:
                from api.schemas import to_job_match
                matches = sorted([to_job_match(j, s, names, company_links=links) for j, s in pairs],
                                 key=lambda m: m.score, reverse=True)
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
