"""Execute one durable stage. No database transaction spans a network request."""

import asyncio
from contextvars import ContextVar
from dataclasses import asdict
from datetime import timedelta
import hashlib
import secrets
import threading
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.enums import ProspectState, StageName as N, StageStatus
from app.db.session import SessionLocal
from app.models.contact import ContactEnrichmentRequest
from app.models.enrichment import Phase1NormalizedData, Phase2NormalizedData, RawProviderResponse
from app.models.prospect import Prospect
from app.models.priority import PriorityResult
from app.models.qualification import QualificationResult
from app.models.stage_run import StageRun
from app.normalizers.phase1 import normalize_phase1
from app.pipeline.ledger import now, claim, owned, finish, fail, enqueue, STATES
from app.providers.demo import DemoCompanyProvider, DemoPriorityProvider, contact_payload
from app.providers.factory import get_profile_provider, get_qualification_provider
from app.providers.company import CompanyEnrichProvider
from app.providers.contact import SignalHireProvider
from app.providers.priority import OpenRouterPriorityProvider, PriorityResponse
from app.services.batch_service import refresh_batch_status

checkpoint_context = ContextVar("checkpoint_context", default=None)


def ensure_execution_owner():
    context = checkpoint_context.get()
    if context is not None:
        db, run_id, owner = context
        if owned(db, run_id, owner) is None:
            raise RuntimeError("Execution ownership lost")
        db.commit()


def checkpoint_request(key, operation):
    """Provider adapters call this around each paid subrequest."""
    context = checkpoint_context.get()
    if context is None:
        return operation()
    db, run_id, owner = context
    run = owned(db, run_id, owner)
    if run is None:
        raise RuntimeError("Execution ownership lost")
    if key in (run.checkpoint or {}):
        value = run.checkpoint[key]
        db.commit()

        async def cached():
            return value

        return cached()
    run.external_call_status = "IN_FLIGHT"
    db.commit()

    async def execute():
        try:
            value = await operation()
        except Exception as error:
            evidence = getattr(error, "envelopes", None)
            run = owned(db, run_id, owner)
            if run is not None and evidence:
                run.checkpoint = {**(run.checkpoint or {}), "failure_evidence": sanitize(evidence)}
                db.commit()
            raise
        run = owned(db, run_id, owner)
        if run is None:
            raise RuntimeError("Execution ownership lost")
        run.checkpoint = {**(run.checkpoint or {}), key: sanitize(value)}
        run.external_call_status = "CONFIRMED"
        db.commit()
        return value

    return execute()


def sanitize(value):
    if isinstance(value, dict):
        return {
            k: sanitize(v)
            for k, v in value.items()
            if k.lower() not in {"authorization", "apikey", "api_key", "callbackurl", "token"}
        }
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    if isinstance(value, str):
        import re

        for secret in (
            get_settings().apify_api_key,
            get_settings().openrouter_api_key,
            get_settings().signalhire_api_key,
            get_settings().company_enrich_api_key,
        ):
            if secret:
                value = value.replace(secret, "[redacted]")
        return re.sub(r'(/webhooks/signalhire/)[^\s?"/]+', r"\1[redacted]", value)
    return value


def snapshot(model):
    return (
        SimpleNamespace(**{c.key: getattr(model, c.key) for c in model.__table__.columns})
        if model
        else None
    )


def upsert(db, model, prospect_id, values):
    stored = db.scalar(select(model).where(model.prospect_id == prospect_id))
    if stored is None:
        db.add(model(prospect_id=prospect_id, **values))
    else:
        for key, value in values.items():
            setattr(stored, key, value)


def heartbeat(factory, stop, run_id, owner):
    while not stop.wait(15):
        try:
            with factory() as db:
                db.execute(
                    update(StageRun)
                    .where(
                        StageRun.id == run_id,
                        StageRun.owner == owner,
                        StageRun.status == StageStatus.PROCESSING,
                        StageRun.lease_expires_at > now(),
                        StageRun.execution_deadline > now(),
                    )
                    .values(heartbeat_at=now(), lease_expires_at=now() + timedelta(seconds=90))
                )
                db.commit()
        except Exception:
            # A DB outage cannot extend ownership; the next provider checkpoint fences it.
            continue


def run_stage(run_id, session=None):
    run_id = UUID(str(run_id))
    own = session is None
    db = session or SessionLocal()
    old_expire = db.expire_on_commit
    db.expire_on_commit = False
    stop = threading.Event()
    thread = None
    owner = None
    token = None
    try:
        owner = claim(db, run_id)
        if owner is None:
            return False
        if own:
            thread = threading.Thread(
                target=heartbeat,
                args=(sessionmaker(bind=db.bind), stop, run_id, owner),
                daemon=True,
            )
            thread.start()
        token = checkpoint_context.set((db, run_id, owner))
        run = db.get(StageRun, run_id)
        p = db.get(Prospect, run.prospect_id)
        stage = run.stage
        pid = p.id
        # Materialize all provider inputs before ending the read transaction.
        person = snapshot(p.phase1_data)
        icp = snapshot(p.batch.icp_snapshot)
        qualification = snapshot(p.qualification)
        signals = dict(p.phase2_data.signals or {}) if p.phase2_data else {}
        name, url = p.name, p.linkedin_url
        saved = dict(run.checkpoint or {})
        previous = db.scalar(
            select(StageRun)
            .where(StageRun.prospect_id == pid, StageRun.status == StageStatus.COMPLETED)
            .order_by(StageRun.started_at.desc())
        )
        previous_data = dict(previous.checkpoint or {}) if previous else {}
        db.commit()
        provider_name = None
        output = saved.get("output")
        next_stage = None
        terminal_state = None
        contact_id = None
        if stage == N.PHASE1_ENRICHMENT:
            provider = get_profile_provider()
            provider_name = provider.provider_name
            if output is None:

                async def profile():
                    result = await provider.enrich(name, url)
                    return result.model_dump()

                output = asyncio.run(checkpoint_request("output", profile))
            next_stage = N.PHASE1_NORMALISATION
        elif stage == N.PHASE1_NORMALISATION:
            provider_name = "demo_normalisation" if get_settings().app_mode == "demo" else "local"
            source = saved.get("source") or previous_data["output"]
            output = normalize_phase1(source["payload"]).model_dump(mode="json")
            next_stage = N.QUALIFICATION
        elif stage == N.QUALIFICATION:
            provider = get_qualification_provider()
            provider_name = provider.provider_name
            if output is None:

                async def qualify():
                    return asdict(await provider.decide(icp, person))

                output = asyncio.run(checkpoint_request("output", qualify))
            if output["decision"] == "PASS":
                next_stage = N.PHASE2_COMPANY_ENRICHMENT
            else:
                terminal_state = ProspectState(output["decision"])
        elif stage == N.PHASE2_COMPANY_ENRICHMENT:
            provider = (
                DemoCompanyProvider()
                if get_settings().app_mode == "demo"
                else CompanyEnrichProvider()
            )
            provider_name = provider.provider_name
            if output is None:

                async def company():
                    return (
                        await provider.enrich(person.company_domain if person else None)
                    ).model_dump()

                output = asyncio.run(checkpoint_request("output", company))
            next_stage = N.PHASE2_NORMALISATION
        elif stage == N.PHASE2_NORMALISATION:
            provider_name = "demo_normalisation" if get_settings().app_mode == "demo" else "local"
            source = saved.get("source") or previous_data["output"]
            context = dict(source["payload"])
            context.pop("employees", None)
            context.pop("reported_employees", None)
            size = {
                "employee_count_min": person.employee_count_min if person else None,
                "employee_count_max": person.employee_count_max if person else None,
                "source": "apify_linkedin"
                if person and (person.employee_count_min or person.employee_count_max)
                else "company_enrich",
            }
            output = {
                "signals": {"company_enrich_data": context, "authoritative_company_size": size}
            }
            next_stage = N.PRIORITISATION
        elif stage == N.PRIORITISATION:
            provider = (
                DemoPriorityProvider()
                if get_settings().app_mode == "demo"
                else OpenRouterPriorityProvider()
            )
            provider_name = provider.provider_name
            context = {
                "icp": {
                    k: v
                    for k, v in vars(icp).items()
                    if k not in {"id", "batch_id", "created_at", "updated_at"}
                }
                if icp
                else {},
                "phase1_qualification": {
                    "decision": qualification.decision.value,
                    "reason": qualification.reason,
                }
                if qualification
                else {},
                **signals,
            }
            if output is None:

                async def prioritize():
                    result, envelope = await provider.decide(context)
                    return {
                        "result": PriorityResponse.model_validate(result).model_dump(),
                        "envelope": envelope,
                        "model": provider.model,
                    }

                output = asyncio.run(checkpoint_request("output", prioritize))
            if output["result"]["priority"] in {"P1", "P2"}:
                next_stage = N.PHASE2_CONTACT_ENRICHMENT
            else:
                terminal_state = ProspectState.COMPLETED
        elif stage == N.PHASE2_CONTACT_ENRICHMENT:
            provider_name = "demo_contact" if get_settings().app_mode == "demo" else "signalhire"
            callback_token = secrets.token_urlsafe(32)
            run = owned(db, run_id, owner)
            if run is None:
                return False
            request = ContactEnrichmentRequest(
                prospect_id=pid,
                stage_run_id=run_id,
                provider=provider_name,
                callback_token_hash=hashlib.sha256(callback_token.encode()).hexdigest(),
                deadline=now() + timedelta(seconds=get_settings().contact_callback_timeout_seconds),
            )
            db.add(request)
            db.flush()
            contact_id = request.id
            db.commit()
            if get_settings().app_mode == "demo":
                output = contact_payload(name)
            else:
                base = get_settings().signalhire_callback_base_url
                if not base:
                    raise ValueError("SIGNALHIRE_CALLBACK_BASE_URL is required.")

                async def contact():
                    return await SignalHireProvider().enrich(
                        url, f"{base.rstrip('/')}/webhooks/signalhire/{callback_token}"
                    )

                response = asyncio.run(checkpoint_request("submission", contact))
                run = owned(db, run_id, owner)
                if run is None:
                    return False
                request = db.get(ContactEnrichmentRequest, contact_id)
                request.provider_request_id = str(response["requestId"])
                if request.status == "PENDING":
                    request.status = "SUBMITTED"
                run.external_call_status = "WAITING_CALLBACK"
                run.owner = None
                run.lease_expires_at = None
                run.reservation_expires_at = None
                db.commit()
                return True
        output = sanitize(output)
        run = owned(db, run_id, owner)
        if run is None:
            return False
        p = db.get(Prospect, pid)
        run.provider = provider_name
        run.checkpoint = {**(run.checkpoint or {}), "output": output}
        if stage in {N.PHASE1_ENRICHMENT, N.PHASE2_COMPANY_ENRICHMENT}:
            raws = output.get("raw_responses") or [
                {"provider": output["provider"], "payload": output["payload"]}
            ]
            for raw in raws:
                db.add(
                    RawProviderResponse(
                        prospect_id=pid,
                        phase="PHASE1" if stage == N.PHASE1_ENRICHMENT else "PHASE2",
                        **raw,
                    )
                )
        elif stage == N.PHASE1_NORMALISATION:
            upsert(db, Phase1NormalizedData, pid, output)
        elif stage == N.QUALIFICATION:
            upsert(
                db,
                QualificationResult,
                pid,
                {k: v for k, v in output.items() if k != "response_envelopes"},
            )
            for envelope in output["response_envelopes"]:
                db.add(
                    RawProviderResponse(
                        prospect_id=pid, phase="PHASE1", provider=provider_name, payload=envelope
                    )
                )
        elif stage == N.PHASE2_NORMALISATION:
            upsert(db, Phase2NormalizedData, pid, output)
        elif stage == N.PRIORITISATION:
            values = dict(output["result"])
            values["negative_or_weak_signals"] = values.pop("negative_or_unknown_signals")
            values.update(
                model_identifier=output["model"],
                provider_identifier=provider_name,
                usage_metadata=output["envelope"]["response"].get("usage"),
            )
            upsert(db, PriorityResult, pid, values)
            p.final_priority = values["priority"]
            db.add(
                RawProviderResponse(
                    prospect_id=pid,
                    phase="PHASE2",
                    provider=provider_name,
                    payload=output["envelope"],
                )
            )
        elif stage == N.PHASE2_CONTACT_ENRICHMENT:
            from app.services.contacts import apply_contact

            apply_contact(db, db.get(ContactEnrichmentRequest, contact_id), run, output)
        finish(run)
        db.flush()
        if next_stage:
            queued = enqueue(db, p, next_stage)
            if next_stage in {N.PHASE1_NORMALISATION, N.PHASE2_NORMALISATION}:
                queued.checkpoint = {"source": output}
            p.current_state = {
                N.PHASE2_COMPANY_ENRICHMENT: ProspectState.PHASE2_QUEUED,
                N.PHASE2_CONTACT_ENRICHMENT: ProspectState.CONTACT_ENRICHMENT_PENDING,
            }.get(next_stage, STATES[next_stage])
        elif terminal_state:
            p.current_state = terminal_state
        refresh_batch_status(db, p.batch)
        db.commit()
        return True
    except Exception as error:
        if owner:
            return fail(db, run_id, owner, error)
        db.rollback()
        raise
    finally:
        if token is not None:
            checkpoint_context.reset(token)
        stop.set()
        if thread:
            thread.join(timeout=2)
        db.expire_on_commit = old_expire
        if own:
            db.close()
