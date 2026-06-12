# companies_seed.json — Dedup Stats

## Source counts (raw)
| Source  | Raw count |
|---------|-----------|
| github  | 116 |
| failory | 102 |
| curated | 52 |

## Dedup summary
| Metric | Value |
|--------|-------|
| Total before dedup | 270 |
| Total after dedup  | 247 |
| Dupes removed      | 23 |
| % deduped          | 8.5% |
| With usable website | 209 (84.6%) |
| Appearing in 2+ sources | 23 |

## 5 example entries
```json
[
  {
    "name": "Accomplish",
    "website": "accomplish.ai",
    "sources": [
      "github"
    ]
  },
  {
    "name": "Agora",
    "website": "agorareal.com",
    "sources": [
      "failory"
    ]
  },
  {
    "name": "AI21 Labs",
    "website": "ai21.com",
    "sources": [
      "failory"
    ]
  },
  {
    "name": "Aidoc",
    "website": "aidoc.com",
    "sources": [
      "failory",
      "curated"
    ]
  },
  {
    "name": "Aim Security",
    "website": "aim.security",
    "sources": [
      "failory"
    ]
  }
]
```

## Notes
- GitHub source: KaplanOpenSource/israeli-opensource-companies README.md
- Failory source: https://www.failory.com/startups/israel (HTML parsed via regex)
- Curated source: spike/fixtures/snc_sample.json (52 manually curated startups)
- Dedup key: registrable domain when available, else normalised name
- First occurrence wins; missing fields filled from later sources
