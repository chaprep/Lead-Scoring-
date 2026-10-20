from typing import Any
import httpx
from app.core.config import get_settings
from app.schemas.phase1 import RawProviderResult


class CompanyProviderError(RuntimeError):
    pass


class CompanyEnrichProvider:
    provider_name = "company_enrich"

    def __init__(self, client_factory: Any = httpx.AsyncClient) -> None:
        s = get_settings()
        self.api_key = s.company_enrich_api_key
        self.url = s.company_enrich_url
        self.timeout = s.company_enrich_request_timeout_seconds
        self.client_factory = client_factory

    async def enrich(self, domain: str | None) -> RawProviderResult:
        if not domain:
            raise CompanyProviderError(
                "A normalized company domain is required for Company Enrich."
            )
        if not self.api_key:
            raise CompanyProviderError("COMPANY_ENRICH_API_KEY is required.")
        try:
            async with self.client_factory(timeout=self.timeout) as client:
                response = await client.get(
                    self.url,
                    params={"domain": domain, "waitForEnrichment": "true"},
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "accept": "application/json",
                    },
                )
                body = response.json()
                response.raise_for_status()
        except (httpx.HTTPError, ValueError) as exc:
            raise CompanyProviderError(
                f"Company Enrich request failed: {type(exc).__name__}"
            ) from exc
        if not isinstance(body, dict):
            raise CompanyProviderError("Company Enrich returned a malformed response.")
        return RawProviderResult(provider=self.provider_name, payload=body)
