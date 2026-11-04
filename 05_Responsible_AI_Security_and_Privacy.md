# MedFlow Africa Responsible AI, Security and Privacy Specification

## Document control

| Field | Value |
|---|---|
| Document | Responsible AI, Security and Privacy Specification |
| Version | 1.0 |
| Status | Approved for MVP implementation |
| Risk posture | Human-reviewed operational decision support |
| Prohibited data | Patient-level personally identifiable information |

## 1. Safety statement

MedFlow Africa estimates medicine stock-out risk and proposes constrained redistribution options. Its outputs may influence operational discussions, so evidence quality, uncertainty, safety constraints and human accountability must be visible.

The product does not make clinical decisions, execute transfers, place orders or replace authorised health-system processes.

## 2. Responsible-AI principles

### 2.1 Human accountability

Every recommendation remains pending until reviewed. The application records a review decision; it does not execute an operational action.

### 2.2 Appropriate automation

Deterministic calculations and constraints govern quantities and eligibility. Machine learning ranks risk. An LLM may explain approved facts only.

### 2.3 Transparency

Show evidence type, data period, data-quality status, model version, confidence and key contributing factors.

### 2.4 Equity

Evaluate model behaviour across location type, facility type and medicine category. Poorer data availability must not be silently interpreted as lower need.

### 2.5 Privacy and minimisation

Process only the operational data required for the stated decision. Do not accept patient identifiers or clinical records.

### 2.6 Contestability

Users can inspect, edit or reject a recommendation and record why. The original and reviewed versions remain traceable.

### 2.7 Reliability

External AI failure must degrade to deterministic functionality rather than produce an unverified substitute.

## 3. System decision boundaries

| Function | Method | Authority |
|---|---|---|
| Inventory metrics | Deterministic calculations | Authoritative when source data is valid |
| Data-quality status | Versioned validation rules | Authoritative for the application run |
| Stock-out probability | Evaluated ML model | Advisory prediction |
| Risk band | Versioned threshold over baseline/model result | Advisory prioritisation |
| Donor eligibility | Deterministic constraints | Mandatory safety gate |
| Transfer quantity | Deterministic rules or optimisation | Advisory maximum or suggestion |
| Bottleneck cause | Transparent rules | Inferred unless source-confirmed |
| Narrative | Deterministic template or bounded LLM | Draft explanation |
| Final operational action | Human and authorised process | Outside the application |

No probabilistic or generative component may bypass a deterministic safety gate.

## 4. Prohibited uses

- Diagnosing a patient or recommending treatment
- Determining medicine choice for an individual
- Processing patient names, contact details or clinical records
- Automatically issuing procurement orders
- Automatically authorising or executing stock transfers
- Using synthetic evaluation results as evidence of real-world effectiveness
- Using the tool as the sole basis for disciplinary or funding decisions
- Presenting inferred bottlenecks as confirmed misconduct or negligence
- Loading untrusted model artifacts or plugins

## 5. AI risk register

| ID | Risk | Impact | Primary control | Residual action |
|---|---|---|---|---|
| AI-001 | False negative stock-out risk | Medicine unavailable without warning | Recall-aware threshold, baseline comparison, actual days of cover | Review missed cases when outcomes become available |
| AI-002 | Excessive false alerts | Alert fatigue and loss of trust | Calibration, ranked queue, alert-volume monitoring | Reassess threshold with users |
| AI-003 | Rural facilities underperform due to sparse data | Unequal service quality | Subgroup evaluation and visible quality status | Collect better operational evidence; do not suppress silently |
| AI-004 | Poor data appears as low risk | False reassurance | Quality gating and `Not assessed` state | Escalate reporting gap separately |
| AI-005 | Unsafe donor recommendation | Donor stock-out | Deterministic safety and expiry constraints | Manual validation remains mandatory |
| AI-006 | LLM fabricates a quantity or facility | Misleading report | Structured facts, claim validation and deterministic fallback | Discard invalid draft and log event |
| AI-007 | Explanation overstates causality | Wrong intervention | `Inferred` labels and controlled templates | Require user confirmation in report |
| AI-008 | Model drift | Degraded accuracy | Distribution, alert-rate and calibration monitoring | Investigate before retraining |
| AI-009 | User assumes review executes transfer | Process or accountability failure | Explicit UX copy and confirmation | Training and user-guide reinforcement |
| AI-010 | Synthetic data mistaken for real | Misrepresentation | Persistent synthetic-data labels | Prohibit unsupported claims in documentation |

## 6. Human oversight workflow

1. System calculates or predicts a risk.
2. User inspects actual evidence and quality status.
3. System may generate a constrained recommendation.
4. User inspects donor and recipient impact.
5. User accepts, edits or rejects with a mandatory note.
6. System records the decision and version.
7. Any real transfer follows an external authorised process.

The application must not use dark patterns, default acceptance or language implying that the model is an authority.

## 7. Fairness and equity evaluation

Evaluate at minimum by:

- Rural, peri-urban and urban location
- Hospital, health centre and clinic
- Medicine category
- Data-quality status

For each group report:

- sample and positive counts
- recall and precision
- false-negative and false-positive rates
- calibration or Brier score
- alert rate
- missing-feature rate

Small groups receive uncertainty notes. Do not hide a group solely because its result is poor. Do not declare fairness from equal aggregate accuracy.

When low-quality data drives disparity, state that limitation and treat improved reporting as a separate action. Do not impute away a structural information gap and call the result equitable.

## 8. Explainability requirements

Every alert must include:

- actual usable stock
- recent consumption basis
- days of cover or explicit reason it is unavailable
- model probability if used
- risk threshold and forecast window
- top structured contributing factors
- data-quality status
- model, dataset and configuration versions

Every redistribution must include:

- donor and recipient values before and after
- safety-stock threshold
- pack-size adjustment
- expiry or shelf-life check
- quality check
- distance or cost proxy
- reason a candidate was selected or rejected

## 9. LLM control specification

### 9.1 Permitted task

Transform an approved structured report payload into plain-language narrative.

### 9.2 Prohibited task

- Calculate risk or quantities
- Introduce new facilities, medicines, numbers or causes
- Override quality or safety rules
- Generate clinical advice
- Send messages or execute actions

### 9.3 Input control

- Send only the minimum structured findings.
- Exclude secrets, internal paths, raw rejected rows and user identifiers.
- Use stable fact identifiers.
- Include required caveats and output schema.
- Limit input and output size.

### 9.4 Output control

- Parse into a strict schema.
- Extract every numeric, facility and medicine claim.
- Verify claims against the supplied fact bundle.
- Reject unsupported claims.
- Mark retained copy as `AI-assisted draft`.
- Store provider/model name, prompt version, fact-bundle hash and validation outcome.
- Fall back to deterministic narrative on timeout, error or failed validation.

### 9.5 Prompt-injection posture

Imported operational text is data, not instruction. Do not concatenate free-form imported content into a system prompt. Quote or encode untrusted text as fields and instruct the model not to follow it.

## 10. Privacy requirements

### 10.1 Data minimisation

Allowed:

- Facility reference data
- Medicine reference data
- Inventory, consumption, orders, delivery and expiry data
- Operational review decisions

Disallowed:

- Patient names or identifiers
- Patient diagnoses or treatment records
- Personal contact details unrelated to system access
- Free-text clinical notes

### 10.2 Retention

The MVP documents a configurable retention policy for imports, rejection records, reports and audit events. Demo data may be reset safely. Real retention requirements must be agreed before external use.

### 10.3 Export

Reports include only operational data required for the decision. Filenames must not contain secrets or unsafe user input. Exports must state data period, synthetic status and limitations.

### 10.4 Logging

Logs contain identifiers and counts, not complete uploaded rows or reviewer notes. Errors must be sanitised.

## 11. Security objectives

- Preserve integrity of analytical inputs, configuration, model artifacts and reviews.
- Prevent unauthorised access to imports, audit records and reports.
- Prevent malicious files, injection and unsafe deserialisation.
- Keep credentials and external-service tokens confidential.
- Maintain availability through bounded workloads and graceful fallback.

## 12. Threat model

### 12.1 Trust boundaries

- Browser to Streamlit
- Streamlit to FastAPI
- File upload to ingestion parser
- Application to database
- Application to model artifact
- Application to external LLM
- Application to report renderer

### 12.2 STRIDE summary

| Threat | Example | Controls |
|---|---|---|
| Spoofing | Unauthorised user submits a review | Authentication and role checks before non-local use |
| Tampering | Dataset or model artifact changed | Checksums, version registry, trusted artifact source |
| Repudiation | Reviewer denies changing quantity | Append-only audit event, actor, time and version |
| Information disclosure | Raw rows or secrets appear in logs | Data minimisation, sanitised logs, secret scanning |
| Denial of service | Oversized upload or expensive request | File and row limits, timeouts, bounded queries |
| Elevation of privilege | User accesses audit/admin route | Server-side authorisation and least privilege |

### 12.3 Domain-specific threats

- Spreadsheet formula injection in exported CSV
- Path traversal using uploaded filename
- SQL or HTML injection in filters, names or reports
- Untrusted pickle or model artifact execution
- Prompt injection from imported text
- Cross-site scripting in report preview
- Excessive LLM cost or data exfiltration
- Race condition during recommendation review

## 13. Security controls

### 13.1 Input and upload

- Allowlist file types and schema versions.
- Enforce byte and row-count limits.
- Generate server-side storage names.
- Validate content rather than trusting extension.
- Treat formula-leading cells safely in exports.
- Reject archive files and executable content.

### 13.2 Application

- Use Pydantic validation and explicit domain validation.
- Use parameterised ORM queries.
- Escape or sanitise rendered user content.
- Restrict CORS.
- Add CSRF protection when the deployment and framework require it.
- Use secure headers in deployed environments.
- Do not expose debug mode outside development.

### 13.3 Secrets

- Load from environment or an approved secret manager.
- Provide `.env.example` containing names only.
- Never return, log or commit credentials.
- Rotate exposed demo credentials immediately.

### 13.4 Model artifacts

- Load only approved local artifacts with recorded checksums.
- Prefer safe serialisation where feasible.
- Never load an artifact from a user-supplied URL.
- Validate feature schema and library compatibility.

### 13.5 Database

- Use least-privilege credentials outside local SQLite.
- Apply migrations through controlled tooling.
- Back up before destructive migration in any persistent environment.
- Keep audit and review integrity constraints in the database where practical.

## 14. Roles and permissions

For non-local deployment, define:

- **Viewer:** view approved analyses and reports
- **Analyst:** import data and run analyses
- **Reviewer:** review recommendations and assign actions
- **Administrator:** manage users and versioned configuration

No role executes a transfer. Server-side checks are required; hiding a button is not authorisation.

## 15. Audit requirements

Record:

- successful and failed import events
- validation summary
- analysis run creation
- model and configuration versions
- generated and withheld recommendations
- review decision and version
- report generation and export
- LLM call outcome and claim validation result
- security-relevant configuration changes

Do not store API keys, full prompts containing sensitive content or raw uploaded rows in general logs.

## 16. Incident and failure response

### Severity examples

- **Critical:** unsafe recommendation bypasses a hard constraint; secret exposure
- **High:** wrong model or dataset version used; audit integrity failure
- **Medium:** LLM claim rejected; export unavailable; baseline fallback activated
- **Low:** non-blocking visual defect

For critical or high analytical issues:

1. Disable affected recommendation or model path.
2. Preserve relevant versioned evidence and logs.
3. Fall back to baseline or no recommendation.
4. Document scope and affected analysis runs.
5. Correct through reviewed code/configuration change.
6. Add a regression test before re-enabling.

## 17. Responsible release gates

Release is blocked when:

- A hard redistribution constraint can be bypassed.
- Critical inputs can be missing without a visible status.
- Model provenance or feature schema is unknown.
- Subgroup evaluation is absent.
- LLM output can introduce unchecked claims.
- The application fails when the LLM is disabled.
- Secrets or patient-level data exist in the repository or demo.
- A high-severity security finding remains unresolved.
- Review actions can overwrite history silently.

## 18. Documentation requirements

Maintain:

- Model card
- Data dictionary and schema versions
- Responsible-AI statement
- Threat model
- Security setup guide
- Incident-response notes
- Known limitations
- Change log for thresholds and analytical policy

## 19. Acceptance

This specification is satisfied when the authoritative decision path is bounded and explainable, all redistributions require review, subgroup and calibration results are documented, the LLM is optional and claim-checked, prohibited data is rejected, key threats have tested controls, and critical failures degrade safely rather than produce unverified output.
