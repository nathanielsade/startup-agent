import json
from pathlib import Path

from startup_agent.domain.models import AtsType, Company


def load_companies_from_seed(path: str) -> list[Company]:
    rows = json.loads(Path(path).read_text())
    companies: list[Company] = []
    for row in rows:
        ats_value = row.get("ats_type", "unknown")
        companies.append(
            Company(
                name=row["name"],
                website=row.get("website"),
                ats_type=AtsType(ats_value),
                ats_token=row.get("ats_token"),
            )
        )
    return companies
