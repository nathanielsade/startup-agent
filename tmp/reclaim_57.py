import json
import tempfile
from collections import Counter
from pathlib import Path

from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.models import AtsType, Company
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.services.health_check import CompanyHealthChecker

SUPPORTED = {"greenhouse", "ashby", "lever", "comeet"}

live = {c["name"] for c in json.loads(Path("data/companies.json").read_text())}
pool = json.loads(Path("spike/fixtures/companies_recruiting_v2.json").read_text())
missing = [c for c in pool if c.get("ats_type") in SUPPORTED and c["name"] not in live]
print(f"candidates to reclaim: {len(missing)}")

# health-check them in a throwaway DB
tmpdb = tempfile.mktemp(suffix=".db")
repo = SQLiteJobRepository(tmpdb)
repo.init_schema()
for c in missing:
    repo.upsert_company(Company(
        name=c["name"], website=c.get("website"),
        ats_type=AtsType(c["ats_type"]), ats_token=c.get("ats_token"),
        source=c.get("source", "getro")))

results = CompanyHealthChecker(repo, ATSAdapterFactory()).check()
by_status = {r.name: r for r in results}
counts = Counter(r.status for r in results)
print("health:", dict(counts))

keepers = [c for c in missing if by_status[c["name"]].status in ("ok", "empty")]
failed = [c["name"] for c in missing if by_status[c["name"]].status == "failed"]
print(f"keepers (ok+empty): {len(keepers)} | dropped (failed): {len(failed)}")
print("dropped:", failed)

Path("tmp/reclaim_keepers.json").write_text(json.dumps(keepers, indent=2, ensure_ascii=False))
print("wrote tmp/reclaim_keepers.json")
