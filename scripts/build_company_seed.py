"""Reproducible utility to build data/companies.json from the classified spike fixture."""

import json
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_SOURCE = _ROOT / "spike" / "fixtures" / "companies_recruiting.json"
_DEST = _ROOT / "data" / "companies.json"
_SUPPORTED = {"greenhouse", "ashby", "lever"}


def main() -> None:
    raw = json.loads(_SOURCE.read_text())

    seen: set[tuple[str, str]] = set()
    companies: list[dict] = []

    for entry in raw:
        ats_type = (entry.get("ats_type") or "").strip()
        ats_token = (entry.get("ats_token") or "").strip()
        if ats_type not in _SUPPORTED or not ats_token:
            continue
        key = (ats_type, ats_token)
        if key in seen:
            continue
        seen.add(key)
        companies.append({
            "name": entry.get("name") or "",
            "website": entry.get("website") or None,
            "ats_type": ats_type,
            "ats_token": ats_token,
        })

    companies.sort(key=lambda c: c["name"].lower())

    _DEST.write_text(json.dumps(companies, indent=2) + "\n")

    counts: dict[str, int] = {}
    for c in companies:
        counts[c["ats_type"]] = counts.get(c["ats_type"], 0) + 1

    print(f"Total written: {len(companies)}")
    for ats, n in sorted(counts.items()):
        print(f"  {ats}: {n}")


if __name__ == "__main__":
    main()
