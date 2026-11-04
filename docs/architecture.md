# Architecture and analytical boundaries

Browser → FastAPI → validation/application services → SQLite → safe JSON model inference → constrained plan → grounded draft → human review → audit/monitoring.

`app/data` handles fixed-seed generation, schema validation, provenance and transactional storage. `app/services/analysis.py` derives metrics, quality gates and risk. `app/models/predict.py` validates a SHA-256 checksum and feature schema before loading a numeric JSON artifact. It never deserialises pickle. `app/services/redistribution.py` preserves donor reservations across each horizon's complete plan. Different forecast horizons are alternative analytical plans, not cumulative operational approvals.

The custom HTML/JS interface is served by FastAPI. An optional Streamlit host embeds that same interface. This deliberately departs from native Streamlit styling to satisfy the user's design request while preserving the specified local host option.

On Vercel, each random, secure-cookie workspace has a private Blob snapshot. `/tmp` is a request scratch directory, never the persistent source of truth. Reads use `cache=0`; writes use `x-if-match` on the prior ETag, or `allowOverwrite=false` for initial creation. This is suitable for a small, isolated portfolio workspace; whole-database snapshot traffic is not a scalable replacement for an operational database.

The currently published Python Blob SDK does not expose conditional PUT. The bounded HTTP adapter follows the official Vercel SDK's API version 13 protocol: [PUT/header mapping](https://github.com/vercel/storage/blob/main/packages/blob/src/put-helpers.ts), [origin read bypass](https://github.com/vercel/storage/blob/main/packages/blob/src/get.ts), [authentication/store normalisation](https://github.com/vercel/storage/blob/main/packages/blob/src/helpers.ts). Credentials remain in environment memory; hosts and paths are application-controlled.

Gemini only assembles approved summary fact IDs with validated connective phrases. Every factual sentence is rendered locally, not trusted from model output. The copilot routes operational questions to approved risk, transfer, explanation or escalation evidence, with policy/finding citations. No arbitrary SQL, browsing, clinical advice, stock movement or external messaging is exposed.
