# Durable workflow and recovery

PostgreSQL `stage_runs` is the authoritative queue and execution history. API writes commit the next queued stage with the prospect. The coordinator scans every two seconds and publishes `workflow.v2.execute` notifications on the `workflow.v2` Redis queue. Duplicate delivery is safe: each stage must win a database claim before calling a provider. Legacy task names deliberately do no work and old queues remain quarantined.

A claim owns a 90-second lease with a heartbeat every 15 seconds, bounded by a 13-minute execution deadline. Celery has a 12-minute soft limit, a 13-minute hard limit, late acknowledgment, worker-loss rejection, prefetch one, and a 30-minute Redis visibility timeout. Every result/checkpoint is fenced by ownership. Network requests run outside database transactions. Completed profile/company lookups and Jev subrequests are checkpointed before downstream processing.

## Configuration

The existing `PHASE1_MAX_CONCURRENCY`, `PHASE2_MAX_CONCURRENCY`, `COMPANY_PROVIDER_MAX_CONCURRENCY`, `CONTACT_PROVIDER_MAX_CONCURRENCY`, and `LLM_MAX_CONCURRENCY` settings are concurrency caps across worker processes, not requests-per-minute limits. Sorted PostgreSQL advisory locks serialize reservation checks. Waiting callbacks release submission capacity. Uncertain in-flight work retains capacity until its execution deadline, even if a user acknowledges a retry sooner.

`MAX_RETRY_ATTEMPTS=3` means three automatic retries after the initial call, with delays of 5, 30, and 120 seconds. Higher limits increase delay exponentially up to 300 seconds. Automatic provider retries are restricted to proven pre-transmission failures. Interrupted work with no in-flight external call can also be safely requeued. Local processing failures retain inputs and checkpoints for manual retry. Invalid responses and configuration failures need investigation first. Broker failure retries publication only; it never grants permission for another paid call.

`CONTACT_CALLBACK_TIMEOUT_SECONDS=900` sets the callback deadline. A timeout becomes `CALLBACK_TIMEOUT`. Valid late success can resolve an unsuperseded attempt. An old attempt's callback is retained but cannot change current results after a newer attempt has been queued. Successful profile matches without usable emails or phones finish as `NO_CONTACTS_FOUND`. Provider failure reasons remain failures.

## Operations

Run all services using `docker compose up -d --build`. Python-only installs must run all three application processes:

```sh
uvicorn app.main:app --host 127.0.0.1 --port 8000
celery -A app.workers.celery_app worker --loglevel=info --queues=workflow.v2
python -m app.workers.coordinator
```

`GET /health/workflow` reports coordinator liveness (15-second threshold), the oldest overdue queued stage, publication failures, and expired leases. Review it alongside `docker compose logs api worker coordinator`. Queued work may wait for capacity; unclaimed published work is republished after 30 seconds. A stopped coordinator leaves database work intact.

Inspect `stage_runs` failure codes, publication errors, checkpoints, and lease/deadline fields. Keep provider evidence private. Callback tokens are generated only inside a claimed contact submission; only hashes enter the database and raw tokens are redacted from application access logs. The protected contact endpoint retains its internal API-key requirement and returns only the latest attempt's usable data.

Retry only the failed stage using `POST /prospects/{id}/retry`. Safe failures accept an empty body. Uncertain outcomes return 409 unless the JSON body contains `{"acknowledge_possible_duplicate_charge": true}`. The dashboard asks for this confirmation. A retry records a new attempt and reuses confirmed upstream results. No external system can promise exactly-once billing after a lost response.

The companion extras folder contains the maintained regression runner and maintenance command:

```sh
python '../Leadscoring extras/scripts/run_backend_tests.py' --app-root "$PWD"
python '../Leadscoring extras/scripts/workflow_maintenance.py' --app-root "$PWD"
```

The maintenance command defaults to inspection. `--reconcile` creates missing stage records only for legacy work; it queues proven queued stages and marks ambiguous legacy in-flight work for confirmed manual recovery. Run it in the application's Python environment, with its database configuration available. Never replay old Redis queues as a recovery strategy.

## Upgrade, backup, and rollback

1. Stop API writes, workers, and the coordinator with `docker compose stop api worker coordinator`. Keep PostgreSQL and Redis running.
2. Save a fresh custom-format PostgreSQL backup and Redis snapshot outside the app folder:

   ```sh
   docker compose exec -T postgres pg_dump -U leadscoring -Fc leadscoring > '/private/backup/leadscoring.dump'
   docker compose exec -T redis redis-cli SAVE
   docker compose cp redis:/data/dump.rdb '/private/backup/redis.rdb'
   ```

3. Verify restoration into a separate empty database before modifying the original. Run `createdb` and `pg_restore --exit-on-error` using the local PostgreSQL service. Confirm prospect counts and sample history/results against the original. Do not restore into the live database to test the backup.
4. Run `docker compose run --rm migrate` and then `docker compose run --rm migrate alembic check`. Migration 0010 preserves saved records, associates contact attempts deterministically, closes ambiguous legacy active stages without inventing historical completion timestamps, and queues only known pending stages. Old failures require confirmation because their acceptance history cannot be established.
5. Start API, coordinator, and new workers with `docker compose up -d --build`. Keep old Redis queues untouched and unconsumed. Inspect unresolved attempts, expired leases, publication failures and callback timeouts. Run the fictional demo smoke test on the configured local port. Paid live smoke tests require separate authorization.

For rollback, stop writes and all workflow processes, restore the verified pre-upgrade database into a replacement volume/database, and use the matching previous application image. Retain the upgraded database and Redis snapshot for investigation. Migration 0010 deliberately refuses destructive downgrade: multiple contact attempts cannot safely be flattened into the previous one-row schema. Do not point old workers at the upgraded database or blindly replay old queue snapshots.

Celery settings follow its [configuration documentation](https://docs.celeryq.dev/en/stable/userguide/configuration.html). The receipt endpoint returns HTTP 200 and performs asynchronous processing as specified by [SignalHire's callback contract](https://docs.signalhire.com/person-api/retrieve-person). There is no invented provider polling endpoint for a lost callback.
