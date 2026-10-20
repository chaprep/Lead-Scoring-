from typing import Any
import httpx
from app.core.config import get_settings


class ContactProviderError(RuntimeError):
    pass


class SignalHireProvider:
    provider_name = "signalhire"

    def __init__(self, client_factory: Any = httpx.AsyncClient) -> None:
        s = get_settings()
        self.api_key = s.signalhire_api_key
        self.url = s.signalhire_url
        self.timeout = s.signalhire_request_timeout_seconds
        self.client_factory = client_factory

    async def enrich(self, linkedin_url: str, callback_url: str) -> dict[str, Any]:
        if not self.api_key:
            raise ContactProviderError("SIGNALHIRE_API_KEY is required.")
        try:
            async with self.client_factory(timeout=self.timeout) as client:
                response = await client.post(
                    self.url,
                    json={"items": [linkedin_url], "callbackUrl": callback_url},
                    headers={"apikey": self.api_key, "Content-Type": "application/json"},
                )
                body = response.json() if response.content else {}
                response.raise_for_status()
        except (httpx.HTTPError, ValueError) as exc:
            raise ContactProviderError(f"SignalHire request failed: {type(exc).__name__}") from exc
        if (
            response.status_code != 201
            or not isinstance(body, dict)
            or isinstance(body.get("requestId"), bool)
            or not isinstance(body.get("requestId"), (str, int))
            or not str(body["requestId"]).strip()
        ):
            raise ContactProviderError("SignalHire returned an invalid submission acceptance.")
        return body
