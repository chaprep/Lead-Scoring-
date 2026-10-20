from app.core.config import get_settings
from app.providers.profile.base import ProfileEnrichmentProvider
from app.providers.profile.apify import ApifyProfileProvider
from app.providers.qualification.base import QualificationDecisionProvider
from app.providers.qualification.jev import OpenRouterJevQualificationProvider


def get_profile_provider() -> ProfileEnrichmentProvider:
    if get_settings().app_mode == "demo":
        from app.providers.demo import DemoProfileProvider
        return DemoProfileProvider()
    if get_settings().profile_provider == "apify":
        return ApifyProfileProvider()
    raise ValueError(f"Unsupported PROFILE_PROVIDER: {get_settings().profile_provider}")


def get_qualification_provider() -> QualificationDecisionProvider:
    if get_settings().app_mode == "demo":
        from app.providers.demo import DemoQualificationProvider
        return DemoQualificationProvider()
    if get_settings().qualification_provider == "jev":
        return OpenRouterJevQualificationProvider()
    raise ValueError(f"Unsupported QUALIFICATION_PROVIDER: {get_settings().qualification_provider}")
