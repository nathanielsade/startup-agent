from abc import ABC, abstractmethod

from startup_agent.domain.models import AtsType, Company, RawJob


class ATSAdapter(ABC):
    ats_type: AtsType

    @abstractmethod
    def fetch_jobs(self, company: Company) -> list[RawJob]: ...
