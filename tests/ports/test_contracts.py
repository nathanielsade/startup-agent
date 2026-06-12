import inspect

from startup_agent.ports.repository import JobRepository
from startup_agent.ports.ats import ATSAdapter
from startup_agent.ports.embedder import Embedder
from startup_agent.ports.ranker import Ranker
from startup_agent.ports.delivery import DeliveryChannel


def test_repository_is_abstract_with_required_methods():
    assert inspect.isabstract(JobRepository)
    for m in ("upsert_company", "get_companies", "upsert_job",
              "job_exists", "record_run", "record_matches"):
        assert hasattr(JobRepository, m)


def test_other_ports_are_abstract():
    for port in (ATSAdapter, Embedder, Ranker, DeliveryChannel):
        assert inspect.isabstract(port)


def test_ats_adapter_has_fetch_jobs():
    assert hasattr(ATSAdapter, "fetch_jobs")
