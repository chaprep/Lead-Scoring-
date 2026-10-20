from __future__ import annotations

from typing import Any

import httpx
import math

from app.core.config import get_settings
from app.core.enums import QualificationDecision
from app.models.enrichment import Phase1NormalizedData
from app.models.icp import ICPSnapshot
from app.providers.qualification.base import (
    QualificationOutcome,
    QualificationProviderError,
)


ASSESSMENT_CHOICES = {
    "department_function": ("MATCH", "ADJACENT", "NO_MATCH", "UNKNOWN"),
    "seniority": ("MATCH", "NO_MATCH", "UNKNOWN"),
    "industry_company_type": ("MATCH", "ADJACENT", "NO_MATCH", "UNKNOWN"),
    "company_size": ("MATCH", "OVERLAP", "NO_MATCH", "UNKNOWN"),
    "geography": ("MATCH", "NO_MATCH", "UNKNOWN"),
    "exclusions": ("EXCLUDED", "NOT_EXCLUDED", "UNCLEAR"),
}
FIT_BANDS = ("0–49", "50–64", "65–79", "80–89", "90–100")
CONFIDENCE_BANDS = ("0–49", "50–64", "65–74", "75–89", "90–100")


from pydantic import BaseModel, ConfigDict, field_validator
from typing import Literal


class JevChoice(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    type: Literal["choice"]
    choice: str


class JevScore(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")
    type: Literal["score"]
    score: int | float
    probabilities: dict[str, int | float]

    @field_validator("score")
    @classmethod
    def finite_score(cls, value):
        if not math.isfinite(value):
            raise ValueError("Score must be finite.")
        return value

    @field_validator("probabilities")
    @classmethod
    def valid_probabilities(cls, value):
        if (
            not value
            or any(k not in {"0", "1", "2", "3", "4"} for k in value)
            or any(not math.isfinite(v) or not 0 <= v <= 1 for v in value.values())
            or abs(sum(value.values()) - 1) > 0.01
        ):
            raise ValueError("Invalid score distribution.")
        return value


def _icp_state(icp: ICPSnapshot) -> dict[str, Any]:
    return {
        "company_size_min": icp.company_size_min,
        "company_size_max": icp.company_size_max,
        "industries": icp.industries or [],
        "company_types": icp.company_types or [],
        "departments": icp.departments or [],
        "seniorities": icp.seniorities or [],
        "geographies": icp.geographies or [],
        "exclusions": icp.exclusions or [],
    }


def _person_company_state(data: Phase1NormalizedData) -> dict[str, Any]:
    fields = (
        "name",
        "linkedin_url",
        "job_title",
        "current_role",
        "department",
        "location",
        "current_company",
        "company_name",
        "company_domain",
        "industry",
        "company_type",
        "employee_count",
        "employee_count_min",
        "employee_count_max",
        "hq_location",
        "company_description",
        "skills",
        "professional_summary",
        "education",
        "open_to_work",
        "person_follower_count",
        "company_tagline",
        "company_specialities",
        "company_founded_year",
        "company_follower_count",
    )
    return {name: getattr(data, name) for name in fields}


def build_assessment_request(
    icp: ICPSnapshot, data: Phase1NormalizedData, model: str
) -> dict[str, Any]:
    state = {"icp": _icp_state(icp), "normalized_person_company": _person_company_state(data)}
    questions: dict[str, Any] = {
        "department_function": {
            "type": "choice",
            "instructions": "Assess whether `normalized_person_company.department`, job title, and role fit the ICP departments in `icp.departments`. Missing evidence is UNKNOWN.",
            "criteria": {
                "MATCH": "Clearly matches an ICP department/function.",
                "ADJACENT": "Related function but not a clear direct match.",
                "NO_MATCH": "Known function does not fit.",
                "UNKNOWN": "Evidence is absent or insufficient.",
            },
        },
        "seniority": {
            "type": "choice",
            "instructions": "Assess `normalized_person_company.current_role` and job title against `icp.seniorities`. Infer seniority from those role details; missing role evidence is UNKNOWN.",
            "criteria": {
                "MATCH": "Current role/title clearly matches ICP seniority.",
                "NO_MATCH": "Current role/title clearly does not fit.",
                "UNKNOWN": "Current role/title evidence is absent or insufficient.",
            },
        },
        "industry_company_type": {
            "type": "choice",
            "instructions": "Assess whether `normalized_person_company.company_name`, `normalized_person_company.industry`, `normalized_person_company.company_description`, and `normalized_person_company.company_specialities` fit `icp.industries` and `icp.company_types`. Use `normalized_person_company.company_type` only as additional evidence when present. Missing or insufficient company evidence is UNKNOWN.",
            "criteria": {
                "MATCH": "Company evidence clearly fits the ICP industry/company type.",
                "ADJACENT": "Company evidence is related but not a clear direct fit.",
                "NO_MATCH": "Known company evidence does not fit the ICP.",
                "UNKNOWN": "Company evidence is absent or insufficient.",
            },
        },
        "company_size": {
            "type": "choice",
            "instructions": "Assess normalized employee-count evidence against `icp.company_size_min` and `icp.company_size_max`. Missing evidence is UNKNOWN.",
            "criteria": {
                "MATCH": "Known size is inside the ICP range.",
                "OVERLAP": "A known size range overlaps the ICP range but is not wholly inside.",
                "NO_MATCH": "Known size is outside the ICP range.",
                "UNKNOWN": "Evidence is absent or insufficient.",
            },
        },
        "geography": {
            "type": "choice",
            "instructions": "Assess normalized person and headquarters locations against `icp.geographies`. Missing evidence is UNKNOWN.",
            "criteria": {
                "MATCH": "Clearly matches ICP geography.",
                "NO_MATCH": "Known geography does not fit.",
                "UNKNOWN": "Evidence is absent or insufficient.",
            },
        },
        "exclusions": {
            "type": "choice",
            "instructions": "Assess all normalized evidence against explicit `icp.exclusions`. Missing or ambiguous evidence is UNCLEAR.",
            "criteria": {
                "EXCLUDED": "An explicit ICP exclusion applies.",
                "NOT_EXCLUDED": "Evidence shows no explicit exclusion applies.",
                "UNCLEAR": "Evidence is absent or insufficient.",
            },
        },
        "overall_icp_fit": {
            "type": "score",
            "instructions": "Score overall ICP fit using the immutable ICP and normalized evidence, preserving uncertainty for missing data.",
            "criteria": [
                "0–49: clearly poor fit",
                "50–64: weak or materially uncertain fit",
                "65–79: plausible fit with meaningful uncertainty",
                "80–89: strong fit",
                "90–100: exceptional, well-supported fit",
            ],
        },
        "decision_confidence": {
            "type": "score",
            "instructions": "Score confidence in an ICP qualification decision from the available normalized evidence; missing data lowers confidence.",
            "criteria": [
                "0–49: very low confidence",
                "50–64: limited confidence",
                "65–74: moderate confidence",
                "75–89: high confidence",
                "90–100: very high confidence",
            ],
        },
    }
    return {"model": model, "state": state, "questions": questions}


def build_final_decision_request(assessment: dict[str, Any], model: str) -> dict[str, Any]:
    state = {
        "assessment": assessment,
        "policy": {
            "core_principle": "Jev is the sole business decision-maker. Missing data is uncertainty and generally requires HUMAN_REVIEW, not rejection.",
            "thresholds": {
                "PASS": "Use when fit is sufficiently supported and confidence is adequate.",
                "HUMAN_REVIEW": "Use for incomplete, adjacent, overlapping, uncertain, or conflicting evidence.",
                "REJECTED": "Use when exclusions is EXCLUDED; explicit exclusion always requires REJECTED.",
            },
        },
    }
    return {
        "model": model,
        "state": state,
        "questions": {
            "final_decision": {
                "type": "choice",
                "instructions": "Choose the final qualification outcome from `assessment` under `policy`. If assessment.exclusions is EXCLUDED, choose REJECTED.",
                "criteria": {
                    "PASS": "Supported ICP fit with adequate confidence and no exclusion.",
                    "HUMAN_REVIEW": "Uncertain, incomplete, adjacent, overlapping, or conflicting evidence; do not reject merely because data is missing.",
                    "REJECTED": "An explicit exclusion applies, or the assessed evidence clearly warrants rejection under policy.",
                },
            }
        },
    }


class OpenRouterJevQualificationProvider:
    provider_name = "openrouter_jev"

    def __init__(self, client_factory: Any = httpx.AsyncClient) -> None:
        settings = get_settings()
        self.api_key, self.model, self.url = (
            settings.openrouter_api_key,
            settings.jev_model,
            settings.jev_decisions_url,
        )
        self.timeout = settings.jev_request_timeout_seconds
        self._client_factory = client_factory

    async def _request(
        self, client: httpx.AsyncClient, payload: dict[str, Any], envelopes: list[dict[str, Any]]
    ) -> dict[str, Any]:
        try:
            response = await client.post(
                self.url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            try:
                body = response.json()
            except ValueError:
                body = {"non_json_response": response.text}
            envelopes.append(
                {"request": payload, "response": body, "status_code": response.status_code}
            )
            if response.status_code == 429 or response.status_code >= 500:
                raise QualificationProviderError(f"Jev HTTP {response.status_code}", envelopes)
            response.raise_for_status()
            if not isinstance(body, dict):
                raise QualificationProviderError(
                    "Jev returned a malformed response envelope.", envelopes
                )
            return body
        except QualificationProviderError:
            raise
        except (httpx.TimeoutException, httpx.HTTPError) as error:
            raise QualificationProviderError(
                f"Jev request failed: {type(error).__name__}", envelopes
            ) from error

    @staticmethod
    def _choice(response: dict[str, Any], key: str, allowed: tuple[str, ...]) -> dict[str, Any]:
        answers = response.get("answers")
        answer = answers.get(key) if isinstance(answers, dict) else None
        if (
            not isinstance(answer, dict)
            or answer.get("type") != "choice"
            or answer.get("choice") not in allowed
        ):
            raise QualificationProviderError(f"Jev returned an invalid {key} answer.")
        try:
            JevChoice.model_validate(answer)
        except ValueError as error:
            raise QualificationProviderError(f"Jev returned an invalid {key} answer.") from error
        return answer

    @staticmethod
    def _score(
        response: dict[str, Any], key: str, bands: tuple[str, ...]
    ) -> tuple[dict[str, Any], str]:
        answers = response.get("answers")
        answer = answers.get(key) if isinstance(answers, dict) else None
        score = answer.get("score") if isinstance(answer, dict) else None
        probabilities = answer.get("probabilities") if isinstance(answer, dict) else None
        if (
            answer is None
            or answer.get("type") != "score"
            or (
                isinstance(score, bool)
                or not isinstance(score, (int, float))
                or not math.isfinite(score)
            )
        ):
            raise QualificationProviderError(f"Jev returned an invalid {key} score.")
        # Jev's score may be a probability-weighted float. Persist the highest-probability
        # rubric band, rather than inventing a more precise numeric score.
        if not isinstance(probabilities, dict):
            raise QualificationProviderError(f"Jev returned {key} without score probabilities.")
        if (
            not probabilities
            or any(str(k) not in {str(i) for i in range(len(bands))} for k in probabilities)
            or any(
                isinstance(v, bool)
                or not isinstance(v, (int, float))
                or not math.isfinite(v)
                or not 0 <= v <= 1
                for v in probabilities.values()
            )
            or abs(sum(probabilities.values()) - 1) > 0.01
        ):
            raise QualificationProviderError(f"Jev returned invalid {key} score probabilities.")
        winning_level = int(max(probabilities, key=probabilities.get))
        try:
            JevScore.model_validate(answer)
        except ValueError as error:
            raise QualificationProviderError(f"Jev returned an invalid {key} score.") from error
        return answer, bands[winning_level]

    async def _validated_request(self, client, payload, envelopes, final=False):
        body = await self._request(client, payload, envelopes)
        try:
            if final:
                self._choice(
                    body, "final_decision", tuple(item.value for item in QualificationDecision)
                )
            else:
                for key, allowed in ASSESSMENT_CHOICES.items():
                    self._choice(body, key, allowed)
                self._score(body, "overall_icp_fit", FIT_BANDS)
                self._score(body, "decision_confidence", CONFIDENCE_BANDS)
        except QualificationProviderError as error:
            error.envelopes = envelopes
            raise
        return body

    async def decide(self, icp: ICPSnapshot, data: Phase1NormalizedData) -> QualificationOutcome:
        if not self.api_key:
            raise QualificationProviderError(
                "OPENROUTER_API_KEY is required for QUALIFICATION_PROVIDER=jev."
            )
        envelopes: list[dict[str, Any]] = []
        async with self._client_factory(timeout=self.timeout) as client:
            from app.pipeline.execution import checkpoint_request

            first = await checkpoint_request(
                "jev_assessment",
                lambda: self._validated_request(
                    client, build_assessment_request(icp, data, self.model), envelopes
                ),
            )
            try:
                assessment_answers = {
                    key: self._choice(first, key, allowed)
                    for key, allowed in ASSESSMENT_CHOICES.items()
                }
                fit_answer, fit_band = self._score(first, "overall_icp_fit", FIT_BANDS)
                confidence_answer, confidence_band = self._score(
                    first, "decision_confidence", CONFIDENCE_BANDS
                )
            except QualificationProviderError as error:
                error.envelopes = envelopes
                raise
            assessment = {key: value["choice"] for key, value in assessment_answers.items()}
            assessment.update({"overall_icp_fit": fit_band, "decision_confidence": confidence_band})
            second = await checkpoint_request(
                "jev_final",
                lambda: self._validated_request(
                    client,
                    build_final_decision_request(assessment, self.model),
                    envelopes,
                    final=True,
                ),
            )
        try:
            final = self._choice(
                second, "final_decision", tuple(item.value for item in QualificationDecision)
            )
        except QualificationProviderError as error:
            error.envelopes = envelopes
            raise
        decision = QualificationDecision(final["choice"])
        ordered = "; ".join(
            (f"{key.replace('_', ' ')}: {assessment[key]}" for key in ASSESSMENT_CHOICES)
        )
        reason = f"{decision.value.replace('_', ' ').title()} — {ordered}; ICP fit: {fit_band}; confidence: {confidence_band}."
        usage = {"assessment": first.get("usage", {}), "final_decision": second.get("usage", {})}
        return QualificationOutcome(
            decision,
            assessment["department_function"],
            assessment["industry_company_type"],
            ["EXCLUDED"] if assessment["exclusions"] == "EXCLUDED" else [],
            reason,
            confidence_band,
            {
                **assessment_answers,
                "overall_icp_fit": fit_answer,
                "decision_confidence": confidence_answer,
            },
            fit_band,
            confidence_band,
            second.get("model") or first.get("model") or self.model,
            self.provider_name,
            usage,
            envelopes,
        )
