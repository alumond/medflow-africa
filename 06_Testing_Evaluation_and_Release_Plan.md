# MedFlow Africa Testing, Evaluation and Release Plan

## Document control

| Field | Value |
|---|---|
| Document | Testing, Evaluation and Release Plan |
| Version | 1.0 |
| Status | Approved for MVP implementation |
| Test framework | pytest, Hypothesis and supporting security/accessibility tools |

## 1. Quality objective

The release must demonstrate that:

- calculations are correct at boundaries and under missing data;
- unsafe recommendations cannot pass deterministic constraints;
- predictive results are evaluated without temporal leakage;
- UI workflows communicate evidence, uncertainty and review status correctly;
- external-service failure produces a safe fallback;
- security, privacy and accessibility controls are effective;
- installation and operation are reproducible.

Passing tests is necessary but not sufficient. Evaluation artifacts, limitations and release decisions must also be reviewable.

## 2. Test strategy

Use a risk-based test pyramid:

1. **Domain unit tests:** most numerous; fast and deterministic
2. **Property-based tests:** invariants across generated inputs
3. **Service and repository integration tests:** database and adapters
4. **API contract tests:** request, response, validation and errors
5. **UI workflow tests:** critical user journeys
6. **Model evaluation tests:** leakage, reproducibility, calibration and subgroup behaviour
7. **Security, privacy and accessibility checks**
8. **End-to-end acceptance tests:** small number of complete workflows

Avoid relying on screenshots or end-to-end tests for business-rule correctness.

## 3. Test environments

### Unit

- No network
- No real database
- Fixed clock and random seed where needed

### Integration

- Isolated temporary database
- Real migrations
- External LLM replaced with a deterministic fake
- Model artifact generated or copied from trusted test fixtures

### Demo acceptance

- Clean environment
- Bundled synthetic dataset
- Production-like configuration
- LLM tested both disabled and with a stubbed adapter

No automated test requires a live external AI service.

## 4. Test data and fixtures

Create small named fixtures for:

- valid facility, medicine, inventory and order records
- duplicate business key
- missing required field
- invalid reference
- negative quantity
- inconsistent balance
- missing reporting period
- zero consumption
- consumption surge
- delayed delivery
- partially filled order
- near-expiry stock
- safe donor
- donor below safety stock
- invalid pack-size quantity
- poor-quality recipient
- stale recommendation version
- unsupported LLM claim

Fixture names describe the intended behaviour. Large generated datasets are used for evaluation and performance, not basic unit tests.

## 5. Domain unit tests

### 5.1 Inventory calculations

| ID | Test | Expected result |
|---|---|---|
| UT-INV-001 | Reconciled balance | Zero variance |
| UT-INV-002 | Inconsistent closing balance | Consistency finding generated |
| UT-INV-003 | Positive consumption | Correct average daily consumption |
| UT-INV-004 | Missing report | Missing period excluded from observed-day denominator |
| UT-INV-005 | Zero consumption | Days of cover is unknown, not infinite |
| UT-INV-006 | Near-expiry quantity exceeds stock | Record rejected |
| UT-INV-007 | Overdue pending order | Ongoing delay calculated from cut-off |
| UT-INV-008 | Zero order quantity | Fulfilment is unavailable, not division by zero |

### 5.2 Risk

| ID | Test | Expected result |
|---|---|---|
| UT-RSK-001 | Cover below 14 days | Baseline 14-day risk flagged |
| UT-RSK-002 | Cover between 14 and 30 days | 14-day and 30-day results differ correctly |
| UT-RSK-003 | Critical missing evidence | Risk is not assessed or recommendation is blocked |
| UT-RSK-004 | Probability at band boundary | Versioned threshold applied exactly |
| UT-RSK-005 | Feature-schema mismatch | ML path stops and baseline fallback activates |
| UT-RSK-006 | Unknown category | Controlled handling without silent corruption |

### 5.3 Redistribution

| ID | Test | Expected result |
|---|---|---|
| UT-RED-001 | Donor has genuine excess | Positive feasible quantity |
| UT-RED-002 | Donor would fall below safety stock | Candidate rejected |
| UT-RED-003 | Raw quantity is not pack multiple | Rounded down to valid pack size |
| UT-RED-004 | Rounded quantity becomes zero | No recommendation |
| UT-RED-005 | Insufficient shelf life | Candidate rejected |
| UT-RED-006 | Recipient quality is limited | Recommendation withheld |
| UT-RED-007 | Donor quality is blocked | Candidate rejected |
| UT-RED-008 | Edited quantity exceeds safe maximum | Review rejected with validation error |
| UT-RED-009 | Same donor and recipient | Candidate rejected |
| UT-RED-010 | Negative or zero quantity | Candidate rejected |

### 5.4 Reporting

- Deterministic report contains only selected structured findings.
- AI-assisted copy is visibly labelled.
- Unsupported LLM number is rejected.
- Unsupported facility or medicine is rejected.
- Timeout falls back to deterministic narrative.
- Report contains dataset, model, configuration and reporting-period metadata.

## 6. Property-based tests

Use Hypothesis to enforce invariants:

- Proposed transfer is never negative.
- Proposed transfer is always a whole multiple of pack size.
- Donor stock after transfer never falls below configured safety stock.
- Increasing recipient need cannot produce a negative quantity.
- Missing critical data never produces an eligible recommendation.
- Probability remains between 0 and 1.
- Risk-band mapping covers the full valid probability range without gaps.
- Repeating an import with the same checksum and schema is idempotent.
- Editing a recommendation creates a higher version and preserves the original.

## 7. Integration tests

### 7.1 Database

- Apply migrations to an empty database.
- Insert and retrieve all domain entities.
- Enforce foreign keys and check constraints.
- Roll back a failed import transaction.
- Preserve append-only audit behaviour through application routes.
- Reject stale recommendation review version.

### 7.2 Ingestion

- Upload a valid CSV set and verify accepted counts.
- Upload mixed valid and invalid rows and verify separation.
- Upload the same source twice and verify idempotency.
- Reject unsupported schema version.
- Reject oversized file.
- Ignore client filename for server storage path.

### 7.3 Model adapter

- Load approved artifact and matching feature schema.
- Refuse mismatched checksum or schema.
- Record model version on results.
- Fall back safely when artifact is absent.

### 7.4 Narrative adapter

- Enforce timeout and size limits.
- Parse strict response schema.
- Validate every number and named entity against the fact bundle.
- Record validation result without logging secrets.

## 8. API contract tests

For every endpoint test:

- success status and response schema
- invalid input and field-level error
- unknown identifier
- unsupported state transition
- authorisation behaviour when enabled
- correlation identifier
- no stack trace or secret in error body
- stable versioned path

Critical API cases:

- import status remains queryable after partial validation failure;
- analysis cannot use an unapproved or failed import;
- review requires a note and expected recommendation version;
- report generation succeeds with the LLM disabled;
- audit results are paginated and stably ordered.

## 9. Model evaluation verification

### 9.1 Reproducibility

- Same code, data version, configuration and seed reproduce the same split and materially identical metrics.
- Feature schema and model artifact checksums are recorded.
- Training and evaluation commands run from a clean environment.

### 9.2 Leakage tests

- All feature timestamps are on or before prediction cut-off.
- Future deliveries and corrections are excluded.
- Imputers, encoders and calibration are fit on training data only.
- Test records do not influence aggregate training features.
- Incomplete future label windows are excluded.

### 9.3 Metrics

Produce machine-readable and human-readable artifacts containing:

- precision, recall and F1
- PR-AUC
- Brier score
- calibration plot or bins
- confusion matrix at selected threshold
- alert rate
- deterministic baseline comparison
- subgroup results
- missing-data robustness results

### 9.4 Threshold review

The release artifact must show the consequences of candidate thresholds. The selected threshold includes a documented rationale and configuration version.

### 9.5 Subgroup review

For location type, facility type and medicine category:

- verify sample counts;
- calculate available metrics;
- flag unreliable small groups;
- investigate material disparity;
- document whether the result blocks release or becomes a limitation.

## 10. UI and UX tests

### 10.1 Critical workflows

1. Load demo and reach overview.
2. Filter to a high-risk pair.
3. Inspect actual evidence, prediction and quality status.
4. Review a feasible redistribution.
5. Edit within safe bounds and record a note.
6. Attempt unsafe edit and receive clear validation.
7. View rejected rows and quality impact.
8. Build and export an action report.

### 10.2 State coverage

Test:

- loading
- no results
- no feasible transfer
- failed validation
- not-assessed risk
- model unavailable
- LLM unavailable
- stale review conflict
- report export failure

### 10.3 Visual regression

Use targeted visual snapshots for stable components such as risk badges, tables, before/after comparison and report pages. Do not use visual snapshots as the only assertion.

## 11. Accessibility tests

Automated checks are supplemented by manual review:

- keyboard-only navigation and review
- visible focus
- semantic heading order
- labelled controls
- error association
- status announcements
- colour contrast
- risk meaning without colour
- chart text alternative
- 200% zoom
- responsive layout
- reduced motion
- screen-reader walkthrough of one critical flow

Any issue blocking import, risk review, recommendation review or report export with assistive technology blocks release.

## 12. Security and privacy tests

### 12.1 Static and supply chain

- secret scan
- dependency vulnerability scan
- lint for unsafe patterns where available
- verify `.env` and local databases are ignored

### 12.2 Input attacks

- path traversal filename
- CSV formula injection payload
- malformed encoding
- oversized file
- SQL metacharacters in filters
- HTML/script content in names and reviewer notes
- prompt-injection text in imported content
- invalid or malicious model artifact

### 12.3 Access and integrity

- unauthorised review denied when authentication is enabled
- viewer cannot change recommendation
- stale version cannot overwrite newer review
- audit event created for security-relevant change

### 12.4 Privacy

- patient-like prohibited columns trigger rejection or an explicit blocking warning
- logs exclude raw rows, secrets and reviewer-note content
- reports contain only permitted operational fields

## 13. Performance and resilience

Use the documented target dataset and a larger bounded dataset.

Measure:

- import duration and memory
- analysis duration
- overview API latency after analysis
- risk table filtering latency
- report generation duration
- database growth

Test failure behaviour for:

- database unavailable
- corrupt model artifact
- optimiser exception
- LLM timeout
- report renderer failure

The test passes only when the system returns a controlled state and does not produce an unsafe partial recommendation.

## 14. End-to-end acceptance scenarios

### E2E-001: High-risk rural clinic

Given a rural clinic with rising consumption and an overdue delivery, the system shows high 14-day risk, actual stock, days of cover, predicted probability, contributing factors and acceptable data quality.

### E2E-002: Safe transfer

Given a compatible donor with excess stock, the system proposes a pack-aligned quantity and shows both facilities remaining above their applicable constraints.

### E2E-003: Unsafe donor rejected

Given a donor that would fall below safety stock, no recommendation is produced and the reason is visible.

### E2E-004: Near-expiry opportunity

Given stock with sufficient remaining shelf life and plausible recipient consumption, the system may rank the transfer and show the expiry evidence.

### E2E-005: Poor evidence

Given missing critical reports, the risk is marked not assessed or limited and redistribution is withheld.

### E2E-006: Human review

Given a feasible recommendation, a reviewer edits the quantity within safe bounds, adds a note and creates a new version without changing the original.

### E2E-007: LLM failure

Given the LLM is unavailable or returns an unsupported number, the system rejects the draft and produces a deterministic report.

## 15. Requirement traceability

Maintain `docs/requirements_traceability.csv` with:

- requirement ID
- document source
- implementation module
- automated test ID
- manual test ID if applicable
- status
- evidence link or artifact

Every Must requirement and business rule in the PRD needs at least one verification method.

## 16. Coverage policy

Coverage is a diagnostic, not a substitute for test quality. Initial release gate:

- Domain and application services: at least 90% branch coverage
- Repository, API and infrastructure code: at least 80% branch coverage
- No uncovered hard safety constraint
- No uncovered error fallback that can affect recommendations or reports

Any exclusion must be documented and narrow.

## 17. CI release gates

Release is blocked unless:

1. Formatting and linting pass.
2. Type checks pass for domain and application modules.
3. Unit, property, integration and API tests pass.
4. Coverage policy passes.
5. Migrations apply to an empty database.
6. Synthetic data generation is reproducible.
7. Model evaluation artifacts are reproducible.
8. Leakage checks pass.
9. Deterministic fallback tests pass.
10. Accessibility critical-path checks pass.
11. Secret and dependency scans have no unresolved high-severity finding.
12. No hard redistribution constraint can be bypassed.
13. Documentation and known limitations are current.

## 18. Manual release review

Before tagging a portfolio release:

- Run the clean-install instructions exactly as written.
- Complete every E2E acceptance scenario.
- Inspect the data-quality, model and responsible-AI artifacts.
- Visually inspect every dashboard page at desktop and tablet widths.
- Inspect the exported report for clipping, missing metadata and ambiguous labels.
- Verify that synthetic-data labelling appears in the application and report.
- Verify that no local database, secret, personal path or generated credential is committed.
- Record the commit, model version, data version and configuration version.

## 19. Defect severity

| Severity | Definition | Release effect |
|---|---|---|
| Critical | Safety constraint bypass, secret exposure, corrupted audit history | Immediate block |
| High | Wrong data/model version, incorrect core calculation, inaccessible critical flow | Block |
| Medium | Important workflow or fallback impaired with safe workaround | Review required |
| Low | Cosmetic or minor content issue | May defer with record |

## 20. Definition of done

A feature is done when requirements and edge cases are documented, domain logic is separated from UI, automated tests cover normal and failure paths, types and lint pass, logs and errors are safe, accessibility has been considered, documentation is updated, and evidence is linked in the traceability record.

The MVP is release-ready when all PRD Must requirements meet this definition and every release gate passes.
