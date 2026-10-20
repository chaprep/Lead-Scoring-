from typing import Protocol

from app.schemas.phase1 import RawProviderResult


class ProfileProviderError(RuntimeError):
    """A provider-specific error that pipeline orchestration can persist."""


class ProfileEnrichmentProvider(Protocol):
    provider_name: str

    async def enrich(self, name: str, linkedin_url: str) -> RawProviderResult: ...
