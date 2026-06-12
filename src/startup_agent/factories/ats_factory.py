from startup_agent.adapters.ats.ashby import AshbyAdapter
from startup_agent.adapters.ats.greenhouse import GreenhouseAdapter
from startup_agent.adapters.ats.http_fetcher import JsonFetcher
from startup_agent.domain.models import AtsType, Company
from startup_agent.ports.ats import ATSAdapter

# Registry: add a new ATS by registering its adapter class here. Nothing else changes.
_REGISTRY: dict[AtsType, type] = {
    AtsType.GREENHOUSE: GreenhouseAdapter,
    AtsType.ASHBY: AshbyAdapter,
}


class ATSAdapterFactory:
    def __init__(self, fetch_json: JsonFetcher | None = None) -> None:
        self._fetch_json = fetch_json

    def for_company(self, company: Company) -> ATSAdapter | None:
        adapter_cls = _REGISTRY.get(company.ats_type)
        if adapter_cls is None:
            return None
        return adapter_cls(fetch_json=self._fetch_json)

    def supported_types(self) -> set[AtsType]:
        return set(_REGISTRY)
