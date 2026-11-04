# Verification record

Verified on 4 November 2026. This record covers the implemented prototype, not certification for operational deployment.

## Automated checks

- 98 tests passed on the final implementation; the coverage baseline measured before the final planning-record removal was 93% combined statement/branch coverage. Redistribution constraints have 100% coverage in this run.
- Ruff lint and formatting passed, domain/reporting MyPy checks passed, and browser JavaScript syntax passed.
- Tests cover quarantine and import idempotency, zero/missing demand, quality overrides, model integrity, whole-pack allocation, expiry buffers, shared donor reservations, stale review versions, append-only history, source escaping, report completeness, unsupported AI claims, quota/fallback behavior and isolated hosted snapshots.
- External-adapter tests use fake transports and isolated storage. The live checks below are separate.
- One dependency deprecation warning remains in Starlette's legacy `multipart` import; it did not fail any test.

## Browser checks

- Native Microsoft Edge: district overview, finding investigation, constrained proposal review, acknowledgement and saved review history.
- Contextual “Draft the supply brief” produces an operational summary with inspectable source records within the current workflow.
- Full report preview visibly contains all thirteen sections in the user's specified order. Escalations remain separate drafts; nothing is sent automatically.
- Desktop and 400-pixel responsive layouts inspected. Risk labels now sit above facility names on small screens; no overlap remains in the inspected risk table.
- No prominent “Synthetic demonstration” badge or standalone “AI copilot” navigation. Data origin remains in provenance and method details.
- A browser-extension CSP error concerning everway.com was observed; it is unrelated to MedFlow assets. A complete accessibility audit was not performed.

## Hosted checks

Target: `almondowolabi01-gmailcoms-projects / medflow-africa`.

Promoted website: https://medflow-africa.vercel.app (stable alias, not an expiring share URL).

Verified production build: `dpl_Bw2utsmjmBYnCmSGrDu69NTRJB27`.

- Health returns `ok`, configured Gemini and private Vercel Blob persistence.
- The 14-day summary returns 6 high, 1 medium, 81 low and 12 unassessed pairs, using `gradient_boosting-1.1.0`.
- Hosted report export contains thirteen ordered sections, boxed risks and embedded Garamond.
- Final JavaScript asset contains integrated assistance and no prominent demonstration/copilot branding.
- An earlier staged build with the same persistence implementation saved an accepted review and retrieved it from a later serverless request. Cookie isolation and ETag conflicts are also covered by adapter tests.
- A live request using the production server-side credential returned a validated Gemini draft with one executive, risk and recommendation paragraph. Primary `gemini-3.8-flash` required the free-tier `gemini-3.5-flash-lite` fallback during this check. The latest primary's successful generation was not independently established.
- Every factual sentence in that draft is inserted from the server's approved fact bundle. Unsupported IDs, wording and extra fields fail validation. No raw uploads, management notes, reviewer notes or free-form questions are transmitted.
- The response grammar uses short connective codes and server validation to avoid provider schema-complexity limits. See [Google's structured-output guidance](https://aistudio.google.com/docs/structured-output#simplifying-complex-schemas).

## Remaining limits

The bundled programme, financial and inventory records are invented, internally reconciled examples. Imported inventory does not turn the programme ledger into actual project expenditure or delivery results. Model results are synthetic holdout evidence, not field-validated clinical or supply outcomes. More model alerts also mean more false positives at the selected operating point.

Browser cookies identify isolated workspaces; this is not named-user authentication, shared organisational access or account recovery. Keep operational use behind deployment protection. Automatic workspace retention cleanup, full role enforcement, formal security review and WCAG conformance remain incomplete. Review decisions record intent and never execute stock movements.

## Product clarification and source publication

The invented staff-training and physical-verification achievement records have been removed from the application activity, indicator and issue ledgers, report output and escalation actions. Operational summary cards use inventory quality and review evidence. The optional project-resources area explicitly identifies its remaining workplan and logistics-budget entries as examples. Full report structure retains the user’s thirteen-section order. The final change passes all 98 tests, Ruff, domain type checks and JavaScript syntax checks.

A fresh Playwright run captures all five main pages plus risk detail, integrated explanation, proposal review, import, full report, escalation, project resources, action register, model oversight and mobile overview. Capture requests do not submit review decisions or send email. Screenshots and a manifest are in `docs/screenshots/`. The source repository is https://github.com/alumond/medflow-africa (public); environment files, local databases and credentials are excluded.
