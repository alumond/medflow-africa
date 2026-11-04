# MedFlow Africa Data and Model Specification

## Document control

| Field | Value |
|---|---|
| Document | Data and Model Specification |
| Version | 1.0 |
| Status | Approved for MVP implementation |
| Permitted data | Synthetic or properly anonymised operational data |
| Analytical unit | Facility-medicine-reporting period |

## 1. Purpose

This document defines the data contract, validation rules, derived metrics, labels, features, model-evaluation method, redistribution constraints and model-governance artifacts.

The design prevents three common failures:

- Training or evaluating on information from the future
- Treating missing or poor-quality data as normal operational evidence
- Allowing a predictive model or LLM to bypass safety rules

## 2. Dataset versioning and provenance

Every import must produce:

- `import_id`
- source type and original display name
- SHA-256 checksum
- schema name and semantic version
- ingestion timestamp in UTC
- reporting-period minimum and maximum
- total, accepted and rejected row counts
- validation-rule version
- synthetic-data generator version and seed, when applicable

An analysis run references exactly one approved import version, one analytical configuration version and zero or one approved model version.

## 3. Canonical data contracts

### 3.1 Facilities

| Field | Type | Required | Rules |
|---|---|---:|---|
| `facility_id` | string | Yes | Stable, unique, 1-50 safe characters |
| `facility_name` | string | Yes | 1-120 characters; display only |
| `facility_type` | enum | Yes | `hospital`, `health_centre`, `clinic` |
| `location_type` | enum | Yes | `urban`, `peri_urban`, `rural` |
| `latitude` | decimal | No | Synthetic/demo; -90 to 90 |
| `longitude` | decimal | No | Synthetic/demo; -180 to 180 |
| `lead_time_days` | integer | Yes | 0-365 |
| `reporting_target` | decimal | Yes | 0-1 |
| `active` | boolean | Yes | Defaults true |

### 3.2 Medicines

| Field | Type | Required | Rules |
|---|---|---:|---|
| `medicine_id` | string | Yes | Stable and unique |
| `medicine_name` | string | Yes | Generic name; 1-120 characters |
| `category` | string | Yes | Controlled reference value |
| `pack_size` | integer | Yes | Greater than zero |
| `safety_stock_days` | integer | Yes | 0-365 |
| `minimum_shelf_life_days` | integer | Yes | 0-730 |
| `active` | boolean | Yes | Defaults true |

### 3.3 Inventory records

| Field | Type | Required | Rules |
|---|---|---:|---|
| `record_id` | string | Yes | Unique within the import |
| `reporting_date` | date | Yes | Not in the future relative to dataset cut-off |
| `facility_id` | string | Yes | Must exist and be active |
| `medicine_id` | string | Yes | Must exist and be active |
| `opening_balance` | integer | Yes | Non-negative |
| `quantity_received` | integer | Yes | Non-negative |
| `quantity_dispensed` | integer | Yes | Non-negative |
| `adjustments` | integer | Yes | May be negative with documented bounds |
| `closing_balance` | integer | Yes | Non-negative |
| `stockout_days` | integer | Yes | 0 through days in reporting period |
| `expiry_date` | date | No | Must be on or after reporting date for usable stock |
| `quantity_near_expiry` | integer | Yes | 0 through closing balance |
| `report_submitted_on_time` | boolean | Yes | Explicit boolean |

Balance reconciliation:

```text
expected_closing = opening_balance + quantity_received - quantity_dispensed + adjustments
balance_variance = closing_balance - expected_closing
```

A non-zero variance is not silently corrected. It produces a validation or consistency finding according to configured tolerance.

### 3.4 Orders

| Field | Type | Required | Rules |
|---|---|---:|---|
| `order_id` | string | Yes | Unique |
| `facility_id` | string | Yes | Valid facility reference |
| `medicine_id` | string | Yes | Valid medicine reference |
| `order_date` | date | Yes | On or before expected delivery |
| `quantity_ordered` | integer | Yes | Greater than zero |
| `expected_delivery_date` | date | Yes | On or after order date |
| `actual_delivery_date` | date | No | Required for fulfilled or partial order |
| `quantity_delivered` | integer | Yes | Non-negative |
| `order_status` | enum | Yes | `pending`, `partial`, `fulfilled`, `cancelled` |

## 4. Validation layers

### 4.1 Structural validation

- Supported encoding and delimiter
- Expected schema version
- Required columns present
- No unknown critical columns
- Parseable dates, integers, decimals and booleans
- File and row-count limits

### 4.2 Referential validation

- Facility and medicine references exist
- Reference records are active for the reporting period
- Duplicate business keys are rejected or resolved by an explicit rule

### 4.3 Semantic validation

- Non-negative quantities where required
- Inventory balance reconciliation
- Stock-out days within period length
- Near-expiry quantity no greater than usable stock
- Delivery status consistent with delivered quantity and dates
- Expiry date plausible for usable inventory

### 4.4 Longitudinal validation

- Reporting dates follow the configured cadence
- Previous closing balance plausibly connects to next opening balance
- Extreme consumption change is flagged, not automatically removed
- Missing reporting periods are recorded explicitly

### 4.5 Rejection record

Each rejected record contains:

- import identifier
- source row number
- entity type
- safe business-key fields
- rule identifier
- field
- machine-readable reason
- human-readable explanation
- severity

Do not store secrets or unnecessary raw content in rejection messages.

## 5. Data-quality dimensions

Calculate each dimension from explicit rules:

- **Completeness:** required expected values present
- **Timeliness:** expected reports submitted by due date
- **Validity:** values conform to type and domain rules
- **Consistency:** balances and related fields reconcile
- **Uniqueness:** business keys are not duplicated

The overall quality status is not a simple average if a critical rule fails. Use a policy such as:

- `blocked`: critical reference, balance or period evidence missing
- `limited`: analysis allowed but recommendations withheld
- `acceptable`: analysis and recommendations permitted with warnings
- `strong`: all configured thresholds met

Version the policy and store it on every analysis run.

## 6. Derived metrics

### 6.1 Average daily consumption

```text
ADC = sum(quantity_dispensed over lookback) / observed_non_missing_days
```

Do not treat missing reports as zero consumption. Record the observed-day denominator.

### 6.2 Usable stock

```text
usable_stock = closing_balance - expired_quantity - quarantined_quantity
```

For the MVP, unavailable fields are explicitly zero only in synthetic data and documented as a limitation.

### 6.3 Days of cover

```text
if ADC > 0:
    days_of_cover = usable_stock / ADC
else:
    days_of_cover = null
    zero_consumption_status = true
```

Never represent zero consumption as infinite cover.

### 6.4 Order fulfilment

```text
order_fulfilment_rate = quantity_delivered / quantity_ordered
```

Calculate only when quantity ordered is greater than zero.

### 6.5 Delivery delay

```text
delivery_delay_days = max(0, actual_delivery_date - expected_delivery_date)
```

For overdue pending orders, calculate delay relative to the dataset cut-off and label it as ongoing.

### 6.6 Consumption trend

Use a robust slope or short/long moving-average comparison over observed periods. Persist the method and lookback window.

### 6.7 Reporting completeness

```text
reporting_completeness = received_expected_reports / expected_reports
```

## 7. Outcome labels

For each observation at cut-off time `t`:

```text
label_14d = 1 if a stock-out occurs in (t, t + 14 days] else 0
label_30d = 1 if a stock-out occurs in (t, t + 30 days] else 0
```

Only information available at or before `t` may be used as a feature. Records whose future label window is incomplete are excluded from supervised evaluation, not labelled negative.

Document the operational definition of stock-out used by the synthetic generator and evaluation.

## 8. Feature contract

Initial features:

- days of cover
- current usable stock
- 4-week and 12-week average daily consumption
- consumption slope and volatility
- recent quantity received
- open-order quantity
- delivery delay
- order fulfilment rate
- facility lead time
- reporting completeness
- previous stock-out days
- quantity and proportion near expiry
- balance-variance flag
- missing-period count
- facility type
- location type
- medicine category
- forecast window

Each feature definition includes name, type, unit, source fields, lookback period, missing-value policy, allowed range and owner.

Create a feature-schema hash and validate it before model inference.

## 9. Leakage prevention

- Use time-based splits with training dates strictly before validation and test dates.
- Fit imputers, encoders and calibration only on training data.
- Do not use future deliveries, future orders, future corrections or future reporting status.
- Ensure records from the same cut-off are not split across train and test in a way that leaks shared aggregates.
- Generate rolling features using closed-left historical windows.
- Include leakage tests for every feature that uses dates or future outcome fields.

## 10. Baseline and models

### 10.1 Deterministic baseline

```text
baseline_high_risk = days_of_cover is known and days_of_cover < forecast_window
```

Extend the baseline with visible rules for overdue supply and data-quality limitations, but keep the rule set understandable.

### 10.2 Statistical benchmark

Use logistic regression in a scikit-learn pipeline with:

- versioned feature list
- training-only imputation
- categorical encoding
- scaling where needed
- class weighting evaluated rather than assumed
- calibrated probabilities when supported by sufficient validation data

### 10.3 Candidate tree model

Histogram gradient boosting may be evaluated. Promote it only if it improves a predeclared combination of recall, precision and calibration without unacceptable subgroup degradation or explainability loss.

Do not select a model from test-set performance. Use validation results for selection and report the test set once.

## 11. Risk thresholds and bands

Threshold selection must be explicit. Record:

- candidate thresholds
- false negatives and false positives
- alert volume
- precision, recall and calibration
- selected threshold and rationale
- configuration version

Example bands are configuration, not hard-coded truth:

- Low: probability below medium threshold
- Medium: probability at or above medium and below high threshold
- High: probability at or above high threshold

Data-quality gating can override display behaviour but must not rewrite the probability.

## 12. Explanations

Contributing factors are generated from structured feature values and rules, not open-ended model prose.

Each factor contains:

- factor identifier
- observed value
- comparison value or historical baseline
- direction of influence
- source period
- explanation template

For model-specific explanations, prefer coefficient contribution for logistic regression. If a tree model is promoted, use a reproducible local explanation method and label it as an approximation.

## 13. Redistribution specification

### 13.1 Recipient eligibility

- High or configured medium risk
- Acceptable minimum data quality
- Known positive consumption
- Valid medicine and facility status

### 13.2 Donor eligibility

- Same medicine
- Usable stock above safety requirement
- Acceptable minimum data quality
- Sufficient remaining shelf life
- No unresolved critical balance discrepancy

### 13.3 Maximum transferable quantity

```text
donor_required_stock = donor_ADC * donor_safety_stock_days
donor_excess = max(0, donor_usable_stock - donor_required_stock)
recipient_need = max(0, recipient_target_stock - recipient_usable_stock)
raw_transfer = min(donor_excess, recipient_need)
transfer_quantity = floor(raw_transfer / pack_size) * pack_size
```

The result must be positive and pass expiry and quality constraints.

### 13.4 Ranking objective

Rank feasible candidates using a documented score or linear objective that considers:

- recipient urgency
- risk reduction
- donor post-transfer safety margin
- near-expiry stock that can be consumed safely
- distance or transfer-cost proxy

Keep scoring components visible. Do not present rank as proof that a transfer is operationally possible.

## 14. Synthetic-data generator

Use a fixed seed and versioned configuration. Generate:

- 10 facilities across rural, peri-urban and urban settings
- 10 medicines with varied consumption and pack sizes
- at least 12 months of weekly records
- seasonality, random demand and plausible deliveries
- linked orders
- known injected scenarios with expected outcomes

Required injected scenarios:

1. Consumption surge plus late delivery
2. Safe donor with excess stock
3. Donor that would violate safety stock and must be rejected
4. Near-expiry stock suitable for transfer
5. Low-quality recipient whose recommendation must be withheld
6. Balance discrepancy
7. Zero-consumption case

Store the scenario truth separately from model features so it can support tests without leakage.

## 15. Evaluation protocol

### 15.1 Metrics

- Precision
- Recall
- F1
- PR-AUC
- Brier score
- Calibration curve and calibration error
- Confusion matrix at selected threshold
- Alert count and alert rate

Accuracy and ROC-AUC may be reported but are not sufficient for an imbalanced operational problem.

### 15.2 Comparisons

- ML model versus deterministic baseline
- Uncalibrated versus calibrated probabilities
- Overall versus facility type
- Overall versus location type
- Overall versus medicine category
- Complete versus limited-quality records

### 15.3 Robustness

Test:

- delayed reports
- missing periods
- consumption spikes
- delivery outliers
- zero consumption
- previously unseen categorical values
- feature-range violations

### 15.4 Acceptance approach

The initial MVP does not assume a universal numeric performance threshold from synthetic data. Promotion requires:

- reproducible improvement over baseline on a predeclared metric set
- acceptable calibration
- documented subgroup results
- no critical leakage or schema failure
- stable inference and graceful fallback

## 16. Model registry and artifacts

For every model version store:

- model identifier and semantic version
- training data import or generator version
- data cut-off
- feature-schema hash
- code commit identifier when available
- hyperparameters
- training seed
- evaluation artifact path
- calibration method
- risk-threshold configuration
- intended use
- limitations
- approval status

Use a safe, trusted artifact format. Do not load arbitrary untrusted pickle files.

## 17. Monitoring and drift

Even in a demo, produce monitoring-ready calculations:

- missingness by feature
- out-of-range values
- category changes
- feature distribution shift
- score distribution shift
- alert-rate change
- calibration and outcome metrics when labels become available

Drift is an investigation trigger, not an automatic retraining command.

## 18. Model card requirements

The repository must contain a model card covering:

- purpose and intended users
- decision supported
- training and evaluation data
- feature set
- evaluation design and metrics
- subgroup results
- threshold choice
- ethical and operational risks
- limitations
- prohibited uses
- fallback behaviour
- version history

## 19. Data and model acceptance

This specification is satisfied when imports are versioned and reproducible, invalid records are traceable, metric formulas have unit tests, labels and features are leakage-safe, baseline and ML results use a time-based holdout, calibration and subgroup results are reported, redistribution constraints are deterministic, and model inference fails safely to the baseline.
