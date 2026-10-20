# Security and data handling

This is a local evaluation prototype without user login or multi-user access controls. Docker binds the dashboard/API to localhost. Keep that restriction for local evaluation.

Do not commit API keys, raw production provider responses, callback tokens, real prospect records, or database exports. `.env` and generated media are excluded from the source package and Docker context. Contact access requires `INTERNAL_API_KEY`; other API endpoints are intended for a trusted local environment.

For sensitive reports, contact Charan Prasad at charan@charanprasad.pro without including credentials or personal records in public issues.
