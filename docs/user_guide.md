# User guide

Start with the existing records to learn the workflow. Import only when you want the analysis to describe your own facilities. The current importer expects a complete four-file bundle, rather than one spreadsheet or an automatic live feed. Upload a new bundle when your reporting data changes.

Required files: `facilities.csv`, `medicines.csv`, `inventory.csv` and `orders.csv`. Exact headers are available in `data/demo` and validation schemas in `data/schemas`. Medicine/facility IDs must match across files. Weekly inventory needs balances, receipts, dispensing and expiry evidence; orders need expected delivery dates and status.


1. Open the overview; the bundled synthetic dataset loads automatically. Read the cut-off, selected horizon, actual evidence and model status.
2. Switch between 7, 14 and 30 days. Investigate a priority finding to see actual stock/cover, predicted probability, model contributions, operational factors and gaps in the weekly series.
3. Open the redistribution planner. Inspect donor/recipient cover, expiry, valid packs and quality gates. Accept, edit or reject with a reviewer note and explicit acknowledgement. Nothing moves stock. Unsafe edits and stale versions are rejected.
4. Use Data Quality to inspect reporting gaps and rejected records. Import requires four CSVs, a cut-off and anonymisation attestation. Download example schemas first. A failed import preserves the previous active dataset.
5. Use the explanation and drafting actions within each supply workflow for cited risk, safe-transfer and escalation support. If Gemini is not configured, the answer is visibly a deterministic evidence fallback. Click the citations to inspect the original evidence.
6. In Method & limitations → Model performance, inspect validation selection, synthetic holdout metrics, calibration, subgroup results, current feature shifts and review feedback. Current predictions have no future outcome labels yet.
7. In Supply Brief, select findings and a narrative mode, add a management note and assign actions/owners/dates. Save the working draft, inspect all13 sections and export self-contained HTML. The full-report print dialog can save a PDF. Escalation email is a separate `.eml` download; it is never sent.

Synthetic programme ledgers are inspectable through the report's Readiness & Resources tab. Actual values precede targets and achievement. Major risks and resource bottlenecks appear in bordered call-outs.

## Current import boundary

Operational imports recalculate stock cover, quality, risk and safe options. Workplan, logframe and financial ledgers remain the bundled fictional programme records; they are not imported by these four files. The model is not automatically retrained on upload. Gemini on the free tier receives approved example summaries only; imported operational data uses deterministic reporting.
