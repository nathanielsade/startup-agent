from startup_agent.domain.models import AtsType, Company
from startup_agent.factories.ats_factory import ATSAdapterFactory
from startup_agent.adapters.ats.greenhouse import GreenhouseAdapter
from startup_agent.adapters.ats.ashby import AshbyAdapter


def test_factory_returns_adapter_per_ats_type():
    factory = ATSAdapterFactory()
    assert isinstance(factory.for_company(Company(name="A", ats_type=AtsType.GREENHOUSE)), GreenhouseAdapter)
    assert isinstance(factory.for_company(Company(name="B", ats_type=AtsType.ASHBY)), AshbyAdapter)


def test_factory_returns_none_for_unsupported():
    factory = ATSAdapterFactory()
    assert factory.for_company(Company(name="C", ats_type=AtsType.UNKNOWN)) is None


def test_factory_supported_types():
    factory = ATSAdapterFactory()
    assert AtsType.GREENHOUSE in factory.supported_types()
    assert AtsType.ASHBY in factory.supported_types()


def test_factory_lever():
    from startup_agent.adapters.ats.lever import LeverAdapter
    factory = ATSAdapterFactory()
    assert isinstance(factory.for_company(Company(name="x", ats_type=AtsType.LEVER)), LeverAdapter)
    assert AtsType.LEVER in factory.supported_types()


def test_factory_comeet():
    from startup_agent.adapters.ats.comeet import ComeetAdapter
    factory = ATSAdapterFactory()
    assert isinstance(
        factory.for_company(Company(name="x", ats_type=AtsType.COMEET, ats_token="91.001:tok")),
        ComeetAdapter,
    )
    assert AtsType.COMEET in factory.supported_types()
