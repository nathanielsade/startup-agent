from pathlib import Path
from startup_agent.companies.comeet_harvester import harvest_from_html

def test_harvest_from_real_snippet():
    html = Path("spike/fixtures/comeet_careers_snippet.html").read_text()
    res = harvest_from_html(html)
    assert res is not None
    uid, token = res.split(":", 1)
    assert uid and token

def test_harvest_returns_none_when_absent():
    assert harvest_from_html("<html><body>no comeet here</body></html>") is None
