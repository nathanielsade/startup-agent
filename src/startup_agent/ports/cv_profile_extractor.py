from abc import ABC, abstractmethod

from startup_agent.domain.applicant_profile import ApplicantProfile


class CvProfileExtractor(ABC):
    @abstractmethod
    def extract(self, cv_text: str) -> ApplicantProfile: ...
