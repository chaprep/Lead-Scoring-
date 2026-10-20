import asyncio
import time
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from app.core.config import get_settings
from app.providers.profile.base import ProfileProviderError
from app.schemas.phase1 import RawProviderResult


class ApifyProfileProvider:
    provider_name = "apify"
    base_url = "https://api.apify.com/v2"

    async def enrich(self, name: str, linkedin_url: str) -> RawProviderResult:
        settings = get_settings()
        if not settings.apify_api_key:
            raise ProfileProviderError("APIFY_API_KEY is not configured.")
        headers = {"Authorization": f"Bearer {settings.apify_api_key}"}
        timeout = httpx.Timeout(settings.apify_request_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
            from app.pipeline.execution import checkpoint_request

            person, person_meta = await checkpoint_request(
                "apify_person", lambda: self._run(client, linkedin_url, f"person:{uuid4()}")
            )
            company_url = person.get("company_linkedin")
            company, company_meta = (None, None)
            if company_url:
                company, company_meta = await checkpoint_request(
                    "apify_company", lambda: self._run(client, company_url, f"company:{uuid4()}")
                )
        raw = [{"provider": "apify_person", "payload": {"run": person_meta, "item": person}}]
        if company is not None:
            raw.append(
                {"provider": "apify_company", "payload": {"run": company_meta, "item": company}}
            )
        return RawProviderResult(
            provider=self.provider_name,
            payload={"person": person, "company": company},
            raw_responses=raw,
        )

    async def _run(
        self, client: httpx.AsyncClient, url: str, external_id: str
    ) -> tuple[dict, dict]:
        settings = get_settings()
        endpoint = f"{self.base_url}/actors/{settings.apify_profile_actor_id}/runs"
        from app.pipeline.execution import ensure_execution_owner

        accepted = False
        try:
            ensure_execution_owner()
            response = await client.post(
                endpoint, json={"startUrls": [{"url": url, "id": external_id}]}
            )
            accepted = True
            response.raise_for_status()
            run = response.json()["data"]
            run_id = run["id"]
            deadline = time.monotonic() + settings.apify_run_timeout_seconds
            while run["status"] not in {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}:
                if time.monotonic() >= deadline:
                    ensure_execution_owner()
                    await client.post(f"{self.base_url}/actor-runs/{run_id}/abort")
                    raise ProfileProviderError("Apify run timed out.")
                await asyncio.sleep(settings.apify_poll_interval_seconds)
                ensure_execution_owner()
                status_response = await client.get(f"{self.base_url}/actor-runs/{run_id}")
                status_response.raise_for_status()
                run = status_response.json()["data"]
            if run["status"] != "SUCCEEDED":
                raise ProfileProviderError(f"Apify run ended with status {run['status']}.")
            ensure_execution_owner()
            items_response = await client.get(
                f"{self.base_url}/datasets/{run['defaultDatasetId']}/items",
                params={"format": "json", "clean": "true"},
            )
            items_response.raise_for_status()
            items = items_response.json()
        except httpx.HTTPError as error:
            failure = ProfileProviderError(f"Apify HTTP failure: {type(error).__name__}")
            failure.external_outcome_unknown = accepted
            raise failure from error
        item = next(
            (
                item
                for item in items
                if item.get("id") == external_id or self._same_linkedin_url(item.get("url"), url)
            ),
            None,
        )
        if item is None:
            raise ProfileProviderError("Apify returned no matching dataset item.")
        return item, {"run_id": run_id, "dataset_id": run["defaultDatasetId"], "input_url": url}

    @staticmethod
    def _same_linkedin_url(first: str | None, second: str) -> bool:
        if not first:
            return False

        def canonical(value: str) -> tuple[str, str]:
            parsed = urlparse(value)
            return parsed.netloc.lower().removeprefix("www."), parsed.path.rstrip("/").lower()

        return canonical(first) == canonical(second)
