INSTRUCTIONS = (
    "You read ONE job posting and extract a compact structured card a downstream "
    "ranker will use. Return JSON with exactly these keys: "
    '{"tech_stack": [..languages/frameworks/tools..], '
    '"required_years": <int or null - lowest years of experience required>, '
    '"seniority": "junior|mid|senior|staff|principal|director|unknown", '
    '"role_domain": "backend|frontend|full-stack|data|ai|devops|security|other", '
    '"must_haves": [..hard requirements e.g. "fluent Hebrew", a clearance, a degree..], '
    '"domain_industry": "<e.g. fintech, cybersecurity, healthtech, or empty>", '
    '"summary": "<=2 sentences on the role essence"}. '
    "Base everything ONLY on the posting. Use null/empty when unknown."
)
