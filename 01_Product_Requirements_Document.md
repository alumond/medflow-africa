# MedFlow Africa Product Requirements Document

## Document control

| Field | Value |
|---|---|
| Product | MedFlow Africa |
| Document | Product Requirements Document (PRD) |
| Version | 1.0 |
| Status | Approved for MVP implementation |
| Product type | Health-supply-chain decision support |
| Data classification | Synthetic or anonymised operational data only |

## 1. Product statement

MedFlow Africa helps district health teams identify essential medicines at risk of stock-out, inspect the operational evidence behind each alert, review feasible redistribution options and produce an accountable action report.

The product supports human decisions. It does not diagnose patients, prescribe treatment, place orders, approve procurement or move stock automatically.

## 2. Problem

Medicine availability decisions are often made from inventory records distributed across spreadsheets and reporting systems. Records may be late, incomplete or inconsistent. A manager may know that a facility has low stock without being able to answer four operational questions quickly:

1. How urgent is the risk?
2. What evidence explains it?
3. Can stock be redistributed safely?
4. Who must act, and by when?

The MVP should make these questions answerable from one reviewable workflow without hiding uncertainty or data-quality limitations.

## 3. Product goals

- Detect 14-day and 30-day stock-out risk at facility-medicine level.
- Rank risks using actual stock, consumption, supply and reporting evidence.
- Identify constrained redistribution opportunities without endangering donor facilities.
- Separate confirmed facts, calculated metrics, model predictions and inferred bottlenecks.
- Require human review before any recommendation is accepted.
- Preserve data provenance, model version, thresholds and review decisions.
- Remain usable when no external LLM is configured.
- Provide clear evidence of model performance, limitations and subgroup behaviour.

## 4. Non-goals

- Clinical advice, diagnosis or treatment selection
- Patient-level data processing
- Automated procurement, ordering or transfer execution
- Replacement of national logistics-management systems
- Claims of clinical, regulatory or government approval
- Nationwide production deployment in the MVP
- Autonomous decision-making
- Foundation-model training

## 5. Users and responsibilities

### 5.1 District logistics officer

Needs a ranked district view, evidence for each alert and a practical list of actions. Reviews and records the disposition of redistribution recommendations.

### 5.2 Facility pharmacist or stock officer

Needs to validate balances, consumption, orders and expiry information. Confirms whether a proposed transfer is operationally feasible.

### 5.3 Programme manager

Needs district trends, unresolved bottlenecks, reporting-quality issues and an action report with owners and due dates.

### 5.4 M&E or data officer

Needs import validation, rejected-row reasons, provenance, metric definitions and reproducible analytical outputs.

### 5.5 System administrator

Manages configuration, reference data and access. Does not alter analytical results outside a documented configuration change.

## 6. Primary user journeys

### Journey A: Review district risk

1. User loads bundled demonstration data or uploads supported CSV files.
2. System validates the import and displays quality results.
3. User opens the district overview and selects a forecast window.
4. System displays ranked medicine-facility risks.
5. User opens one alert and reviews actual stock, days of cover, probability, contributing factors and missing-data warnings.

### Journey B: Review redistribution

1. User opens a high-risk alert.
2. System identifies eligible donor facilities under configured constraints.
3. System shows stock cover before and after each proposed transfer.
4. User accepts, edits or rejects the recommendation.
5. User enters a mandatory rationale.
6. System records the decision without executing a transfer.

### Journey C: Investigate data quality

1. System blocks invalid records from analytical inputs.
2. User reviews completeness, timeliness, validity and consistency results.
3. User downloads or views rejected rows and reasons.
4. Risk results affected by weak evidence carry a visible warning or are withheld.

### Journey D: Produce an action report

1. User selects reviewed findings and recommendations.
2. User assigns owners and due dates.
3. System creates a deterministic report.
4. If enabled, the LLM may draft a narrative using only approved structured findings.
5. User reviews and exports the final report.

## 7. Functional requirements

### 7.1 Data ingestion and quality

| ID | Requirement | Priority |
|---|---|---|
| FR-DAT-001 | Load a bundled, reproducible synthetic demonstration dataset. | Must |
| FR-DAT-002 | Accept versioned CSV imports for facilities, medicines, inventory and orders. | Must |
| FR-DAT-003 | Validate columns, types, identifiers, dates, balances, duplicates and reference integrity. | Must |
| FR-DAT-004 | Keep invalid rows out of analysis and preserve them with machine-readable rejection reasons. | Must |
| FR-DAT-005 | Record source name, checksum, schema version, import time, row counts and validation outcome. | Must |
| FR-DAT-006 | Display completeness, timeliness, validity and consistency by dataset and facility. | Must |
| FR-DAT-007 | Prevent analysis when critical reference data or required periods are missing. | Must |

### 7.2 Inventory metrics and risk

| ID | Requirement | Priority |
|---|---|---|
| FR-RSK-001 | Calculate average daily consumption, usable stock, days of cover, delivery delay, order fulfilment and reporting completeness. | Must |
| FR-RSK-002 | Produce deterministic 14-day and 30-day baseline risk. | Must |
| FR-RSK-003 | Produce an evaluated ML risk score when an approved model artifact is available. | Must |
| FR-RSK-004 | Display actual values before thresholds, targets or comparisons. | Must |
| FR-RSK-005 | Classify risk as low, medium or high using versioned thresholds. | Must |
| FR-RSK-006 | Show contributing factors and data-quality warnings for every alert. | Must |
| FR-RSK-007 | Distinguish facts, derived metrics, predictions and inferred causes. | Must |
| FR-RSK-008 | Allow filtering by facility, medicine, risk, forecast window and evidence quality. | Must |
| FR-RSK-009 | Withhold or downgrade recommendations when minimum data-quality rules are not met. | Must |

### 7.3 Redistribution

| ID | Requirement | Priority |
|---|---|---|
| FR-RED-001 | Identify potential donors with stock above the configured safety threshold. | Must |
| FR-RED-002 | Calculate a proposed quantity in valid pack-size increments. | Must |
| FR-RED-003 | Show donor and recipient days of cover before and after the proposed transfer. | Must |
| FR-RED-004 | Reject recommendations that violate donor safety stock, expiry, pack-size or data-quality constraints. | Must |
| FR-RED-005 | Rank feasible transfers using urgency, safety, expiry and distance or cost proxy. | Must |
| FR-RED-006 | Require a reviewer to accept, edit or reject a recommendation with a note. | Must |
| FR-RED-007 | Never execute a stock transfer, order or procurement action. | Must |

### 7.4 Bottleneck diagnostics

| ID | Requirement | Priority |
|---|---|---|
| FR-BOT-001 | Apply transparent rules to classify likely bottlenecks. | Must |
| FR-BOT-002 | Support consumption surge, delayed delivery, partial order, insufficient order, reporting gap, discrepancy, near-expiry surplus and unknown. | Must |
| FR-BOT-003 | Label bottlenecks as inferred unless directly confirmed by source data. | Must |

### 7.5 Reporting and audit

| ID | Requirement | Priority |
|---|---|---|
| FR-REP-001 | Generate a report without an LLM. | Must |
| FR-REP-002 | Include priority risks, evidence, proposed transfers, bottlenecks, owners and due dates. | Must |
| FR-REP-003 | Export a stable HTML report; PDF export may be added when layout is verified. | Must |
| FR-REP-004 | Label an LLM narrative as an AI-assisted draft pending human review. | Must |
| FR-AUD-001 | Record imports, configuration version, model version, recommendations and review events. | Must |
| FR-AUD-002 | Make audit events append-only through application workflows. | Must |
| FR-AUD-003 | Never write secrets, tokens or raw sensitive records to logs. | Must |

## 8. Business rules

| ID | Rule |
|---|---|
| BR-001 | Current usable stock must never be inferred from an invalid balance without a visible data-quality flag. |
| BR-002 | A donor facility must remain at or above its medicine-specific safety-stock days after a proposed transfer. |
| BR-003 | A proposed quantity must be a non-negative whole multiple of pack size. |
| BR-004 | Stock must have enough remaining shelf life for plausible use at the recipient facility. |
| BR-005 | Critical missing fields prohibit redistribution recommendations. |
| BR-006 | Zero consumption must be handled explicitly and never produce division-by-zero or infinite cover. |
| BR-007 | The ML model may rank risk but may not bypass deterministic safety constraints. |
| BR-008 | The LLM may explain approved calculations but may not create risk scores or transfer quantities. |
| BR-009 | Editing a recommendation creates a new reviewed version; it does not overwrite the original. |
| BR-010 | Every recommendation remains non-executable advisory output. |

## 9. Information architecture

The application contains five primary pages:

1. District Overview
2. Risk Explorer
3. Redistribution Planner
4. Data Quality
5. Action Report

Global context includes dataset version, reporting period, forecast window and model version.

## 10. Success measures

### 10.1 Product success

- A new user can load demonstration data and reach the district overview without editing code.
- Every high-risk alert exposes the evidence used to calculate or predict risk.
- Every recommendation passes all documented constraints.
- Every review action is traceable to a user action, timestamp and recommendation version.
- The full application works with the LLM disabled.

### 10.2 Analytical success

- The ML model is compared with the deterministic baseline on a time-based holdout set.
- Precision, recall, PR-AUC and calibration are reported.
- Subgroup results are reported by location type, facility type and medicine category.
- The chosen decision threshold and its false-negative/false-positive trade-off are documented.
- No performance claim is made without a reproducible evaluation artifact.

### 10.3 Quality success

- All release-gate tests pass.
- No high-severity security or privacy finding remains open.
- No critical accessibility failure remains open.
- Installation, test, training and run commands work from a clean environment.

## 11. Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-REL-001 | The deterministic analytical path must work when the LLM or network is unavailable. |
| NFR-PER-001 | District summary for the bundled dataset should load within 2 seconds after data is processed on a typical development laptop. |
| NFR-SEC-001 | Secrets must come from environment variables or an approved secret store. |
| NFR-SEC-002 | All external inputs must be validated at trust boundaries. |
| NFR-OBS-001 | Logs must include correlation identifiers and structured event names. |
| NFR-ACC-001 | User-facing screens must target WCAG 2.2 AA and not rely on colour alone. |
| NFR-MNT-001 | Business logic must be isolated from API and UI frameworks. |
| NFR-REP-001 | Synthetic-data generation and model evaluation must be reproducible from fixed seeds and versioned configuration. |
| NFR-PRV-001 | The MVP must not accept patient-level personally identifiable data. |

## 12. Assumptions and constraints

- MVP data is synthetic or demonstrably anonymised.
- Facility distance may use synthetic coordinates or a documented distance proxy.
- The first supported deployment is a local development environment.
- SQLite is acceptable for the MVP; persistence code must not make migration to PostgreSQL unnecessarily difficult.
- English is the initial interface language.
- Model results are prototype evidence, not claims about real health systems.

## 13. Product risks

| Risk | Impact | Product response |
|---|---|---|
| False reassurance from a low-risk score | Missed stock-out | Show uncertainty, preserve baseline comparison and optimise thresholds with recall in mind. |
| Alert fatigue | Users ignore valid warnings | Rank alerts, calibrate thresholds and expose evidence. |
| Poor data mistaken for operational failure | Wrong intervention | Separate data-quality status and withhold weak recommendations. |
| Unsafe redistribution | Donor facility becomes vulnerable | Enforce deterministic safety, expiry and pack-size constraints. |
| LLM fabricates facts | Misleading report | Use structured inputs, claim validation, deterministic fallback and human review. |
| Synthetic results presented as real | Reputational harm | Label synthetic data and prohibit unsupported deployment claims. |

## 14. Definition of MVP acceptance

The product is accepted when all Must requirements are implemented, all business rules have automated tests, the model evaluation is reproducible, the five pages support the defined user journeys, the deterministic report works without an LLM, and the release gates in the testing document pass.

## 15. Related documents

- `02_Technical_Requirements_and_Design.md`
- `03_Data_and_Model_Specification.md`
- `04_UX_and_Workflow_Specification.md`
- `05_Responsible_AI_Security_and_Privacy.md`
- `06_Testing_Evaluation_and_Release_Plan.md`
