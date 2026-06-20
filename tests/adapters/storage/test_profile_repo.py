from startup_agent.adapters.storage.sqlite_repository import SQLiteJobRepository
from startup_agent.domain.applicant_profile import ApplicantProfile


def test_profile_round_trip(tmp_path):
    repo = SQLiteJobRepository(str(tmp_path / "jobs.db"))
    repo.init_schema()
    assert repo.get_profile() is None
    repo.save_profile(ApplicantProfile(first_name="Netanel", email="a@b.com"))
    got = repo.get_profile()
    assert got.first_name == "Netanel" and got.email == "a@b.com"


def test_save_profile_overwrites(tmp_path):
    repo = SQLiteJobRepository(str(tmp_path / "jobs.db"))
    repo.init_schema()
    repo.save_profile(ApplicantProfile(first_name="A"))
    repo.save_profile(ApplicantProfile(first_name="B"))
    assert repo.get_profile().first_name == "B"
