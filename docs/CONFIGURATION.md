# Configuration and local development

## Modes

| Setting | Behaviour |
| --- | --- |
| `APP_MODE=demo` | All provider stages use deterministic fictional fixtures. No paid/provider HTTP requests, no callback tunnel. |
| `APP_MODE=live` | Existing real-provider pipeline, using your credentials and real callbacks. |

Compose defaults to `demo` even when no `.env` exists. The example `.env` also selects `demo`. Existing Python-only installations retain their prior `live` default unless `APP_MODE` is set. Restart/recreate API, worker, and coordinator when changing modes; complete or discard old demo batches before interpreting live results.

The `/runtime-config` endpoint returns only the mode and fictional sample inputs. Provider keys and URLs are never included. Demo profiles and outcomes are scripted regardless of custom ICP criteria, and demo contact methods use `example.com` and a reserved fictional phone number.

## Docker settings

Compose explicitly injects recognised application settings at runtime. It does not mount or copy `.env` into the image. It always uses the internal `postgres` and `redis` service names for container connectivity; host `DATABASE_URL` and `REDIS_URL` values are for Python-only development.

| Setting | Default / use |
| --- | --- |
| `APP_PORT` | `8000`; change if another application uses that host port |
| `APP_MODE` | `demo` in Docker |
| `APIFY_API_KEY` | Required for live profile enrichment |
| `APIFY_PROFILE_ACTOR_ID` | Existing configured profile actor |
| `OPENROUTER_API_KEY` | Required for live qualification and priority |
| `JEV_MODEL` | Existing qualification model, `typesafe/jev-1.13` |
| `COMPANY_ENRICH_API_KEY` | Required for live company research |
| `PRIORITIZATION_MODEL` | Existing priority model, `openai/gpt-6-luna` |
| `SIGNALHIRE_API_KEY` | Required for live P1/P2 contact requests |
| `SIGNALHIRE_CALLBACK_BASE_URL` | Public base URL for live callbacks |
| `INTERNAL_API_KEY` | Required to access `GET /internal/prospects/{id}/contact` |
| `CELERY_WORKER_CONCURRENCY` | `2` for local Docker evaluation |
| `CORS_ALLOW_ORIGINS` | Only needed for a dashboard served separately from the API |

To use another local port, set `APP_PORT=8080` in `.env`, or run `APP_PORT=8080 docker compose up --build -d --wait` on a POSIX shell. Open the dashboard and API at that port; the same-origin browser adapter follows it automatically. On Windows, put `APP_PORT=8080` in `.env`.

Postgres and Redis have no host ports in the default stack. The API is published only on `127.0.0.1`. The application image runs as an unprivileged user. The database credentials in Compose are local evaluation defaults, not credentials for a public deployment.

## SignalHire callbacks

Live P1/P2 prospects stay pending until SignalHire POSTs to:

```text
SIGNALHIRE_CALLBACK_BASE_URL/webhooks/signalhire/<per-request-token>
```

The provider must be able to reach that route. For local development, use a public callback host or a tunnel configured to expose only the webhook path to this API. Configure that external service yourself; a tunnel is not started by Compose. Do not expose the unauthenticated dashboard/API as a public production service. P3 skips contact enrichment in both modes.

## Run Python services on the host

Install runtime dependencies as described in the root README. Preserve your existing `.env`; set host URLs and your selected mode:

```dotenv
DATABASE_URL=postgresql+psycopg://leadscoring:leadscoring@localhost:5433/leadscoring
REDIS_URL=redis://localhost:6379/0
APP_MODE=demo
```

Start only the backing services, using the optional port override:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

In another activated terminal:

```bash
# Also run python -m app.workers.coordinator in a separate terminal.
celery -A app.workers.celery_app worker --loglevel=info --pool=solo --queues=workflow.v2
```

Open `http://localhost:8000`. A separate static server is optional: `python3 -m http.server 5173 --directory Leadscorefrontend`, then open `http://localhost:5173/lead-scoring-prioritisation-system.html`. Port 5173 uses the API at `127.0.0.1:8000`; other independently hosted frontends can set `window.LEAD_SCORING_API_BASE_URL` before the application script.

## Troubleshooting

- **Docker daemon permission/connection error:** Check that Docker Desktop or your Docker engine is running and your terminal has permission to use it. A restricted agent session may not have the same access as your normal terminal.
- **Port 8000 already in use:** Set `APP_PORT` and recreate the stack.
- **Migration failed:** Inspect `docker compose logs migrate`; API and worker wait for a successful migration.
- **Prospects stay queued:** Inspect `docker compose logs worker` and `docker compose ps`; the coordinator must be running and the worker must consume `workflow.v2`. Check `/health/workflow` for overdue work.
- **Live P1/P2 remain pending:** Check provider credentials, callback reachability, and SignalHire responses.
- **Stop without deleting data:** `docker compose down`.
- **Start over:** `docker compose down --volumes` deletes this Compose project’s local database and queue volumes permanently.

The startup dependency conditions follow [Docker’s Compose startup-order documentation](https://docs.docker.com/compose/how-tos/startup-order/). Build context exclusions follow [Docker’s build-context documentation](https://docs.docker.com/build/concepts/context/).

Durable execution, concurrency caps, retries, migration and recovery procedures are documented in [WORKFLOW_RECOVERY.md](WORKFLOW_RECOVERY.md).
