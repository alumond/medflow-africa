# MedFlow Africa UX and Workflow Specification

## Document control

| Field | Value |
|---|---|
| Document | UX and Workflow Specification |
| Version | 1.0 |
| Status | Approved for MVP implementation |
| Experience type | Operational health-supply-chain dashboard |
| Accessibility target | WCAG 2.2 AA |

## 1. Experience objective

The interface must help a district user move from **signal** to **evidence** to **reviewed action** without mistaking a prediction for a confirmed fact.

The product should feel calm, precise and trustworthy. It should not resemble a promotional AI dashboard. Avoid excessive cards, gradients, decorative charts, animation and unexplained scores.

## 2. Design principles

### 2.1 Evidence before recommendation

Show the actual value, reporting period and data-quality status before the risk comparison or recommendation.

### 2.2 Urgency without alarmism

Red is reserved for genuine high-risk or blocking conditions. Do not use red for neutral navigation, branding or ordinary labels.

### 2.3 Progressive disclosure

The overview answers what needs attention. Detail screens explain why. Technical provenance remains available without overwhelming the primary task.

### 2.4 No colour-only meaning

Every status includes text and an icon or shape. A high-risk item is not communicated through red alone.

### 2.5 Reversible review

Recommendations are never executed. Reviewers can inspect, edit or reject them. The system keeps the original recommendation and records the new version.

### 2.6 Visible uncertainty

Unknown, incomplete, inferred and model-estimated values use distinct labels. Never display missing evidence as zero.

### 2.7 Consistent decisions

The same status, metric and review language appears across tables, detail panels and reports.

## 3. Research assumptions to validate

The MVP begins with these hypotheses:

- Users often start with a district-wide list and then investigate one facility-medicine pair.
- Users need actual quantities and stock cover more than a raw probability.
- Low data quality is itself an operational problem and must be visible beside risk.
- A redistribution recommendation is useful only when donor impact and expiry are visible.
- Managers need an exportable action record with owners and due dates.
- Technical users need provenance; operational users need plain-language evidence.

Record these as assumptions, not proven user facts. Validate later through structured walkthroughs with relevant practitioners.

## 4. Information architecture

### Primary navigation

1. **District Overview**
2. **Risk Explorer**
3. **Redistribution Planner**
4. **Data Quality**
5. **Action Report**

### Persistent context bar

Display:

- District or demonstration dataset name
- Reporting period
- Forecast window: 14 or 30 days
- Data version
- Analysis time
- Model or baseline status

Changing dataset or forecast window requires an explicit user action and refreshes dependent results.

## 5. Global visual system

### 5.1 Colour tokens

| Token | Value | Use |
|---|---|---|
| `canvas` | `#F5F7FA` | Page background |
| `surface` | `#FFFFFF` | Panels and tables |
| `ink` | `#182230` | Primary text |
| `muted` | `#526071` | Secondary text |
| `navy` | `#17324D` | Brand, selected navigation and headings |
| `action` | `#1D5FBF` | Links and primary action |
| `border` | `#D7DEE7` | Dividers and control outlines |
| `success` | `#157A55` | Low risk/on track text and icon |
| `success-bg` | `#E5F5EE` | Low-risk badge background |
| `warning` | `#8A4B00` | Medium risk/attention text and icon |
| `warning-bg` | `#FFF1D6` | Medium-risk badge background |
| `danger` | `#B42318` | High risk/blocking text and icon |
| `danger-bg` | `#FEE9E7` | High-risk badge background |
| `info-bg` | `#EAF2FF` | Informational note |

Verify colour contrast in the implemented context. Do not assume a token is compliant merely because it is listed here.

### 5.2 Typography

- UI and data: Source Sans 3, Inter or a system sans-serif
- Base size: 16 px
- Table text: no smaller than 14 px
- Page title: 28-32 px, semibold
- Section title: 20-22 px, semibold
- Labels: 14-16 px, semibold
- Numbers: tabular numerals where supported
- Line height: approximately 1.4-1.55 for body text

Use one primary type family in the application. Decorative serif typography is reserved for exported-report headings only if it remains legible.

### 5.3 Spacing and layout

Use an 8 px spacing system. Recommended content width is 1200-1440 px with 24-32 px desktop gutters. Keep related evidence within a shared visual region.

Do not place more than four top-level KPI summaries in one row. A KPI is not a substitute for a ranked table.

### 5.4 Surfaces and elevation

- Use borders and whitespace more than shadows.
- Keep corner radius restrained at 6-10 px.
- Avoid nested cards where a section and divider are sufficient.
- Reserve modal dialogs for focused confirmation or review tasks.

## 6. Status language

### Risk

- **High risk:** immediate review required
- **Medium risk:** attention required
- **Low risk:** currently within configured threshold
- **Not assessed:** evidence is insufficient

### Data quality

- **Blocked:** analysis or recommendation cannot proceed
- **Limited:** analysis available; recommendation withheld
- **Acceptable:** usable with documented warnings
- **Strong:** configured quality requirements met

### Evidence type

- **Reported:** directly present in validated source data
- **Calculated:** deterministic metric
- **Predicted:** model estimate
- **Inferred:** rule-based likely cause
- **Reviewed:** human decision or note

## 7. Global interaction patterns

### 7.1 Filters

- Keep primary filters visible above results.
- Show active filters as removable chips.
- Provide `Clear filters` when any filter is active.
- Display the number of matching records.
- Preserve filters when navigating into and back from a detail view.

### 7.2 Tables

- Use sticky headers for long tables.
- Keep row actions in a consistent final column.
- Default sort by operational priority, then stable identifier.
- Allow sorting only where meaning is clear.
- Keep units in headers or values.
- Provide an accessible text summary for complex visual results.
- Avoid horizontal scrolling at the primary desktop target; reveal secondary columns in details.

### 7.3 Details

Open a dedicated detail page or stable side panel. Do not rely on hover for essential evidence.

### 7.4 Confirmation

Accept, edit and reject are review decisions, not transfers. Confirmation copy must state: **This records a review decision and does not move stock.**

### 7.5 Notifications

- Inline errors remain near the affected control.
- Success confirmation states what was recorded and provides a link to the audit event.
- Toasts may supplement but never replace persistent status.

## 8. District Overview

### 8.1 Purpose

Answer: What requires attention now, and can I trust the evidence?

### 8.2 Page structure

1. Page title and one-sentence context
2. Persistent context bar
3. Four summary indicators
4. Priority risk table
5. Medicine and facility patterns
6. Redistribution and data-quality call-outs

### 8.3 Summary indicators

Show actual first, then comparison:

- `12 high-risk pairs` — `+4 versus previous reporting period`
- `84% reports complete` — `target 95%`
- `6 feasible transfers` — `pending review`
- `3 blocked facilities` — `insufficient evidence`

Each indicator links to the relevant filtered page.

### 8.4 Priority risk table

Columns:

- Risk status
- Facility
- Medicine
- Usable stock
- Days of cover
- 14-day or 30-day risk
- Data-quality status
- Primary contributing factor
- View details

Risk probability is secondary to days of cover and status. Show the probability with a clear `Predicted` label.

### 8.5 Charts

Use at most two decision-relevant charts:

- Ranked horizontal bars for medicines with the most high-risk facilities
- Facility risk-and-quality matrix or grouped bar chart

Avoid pie charts, gauges and 3D charts.

## 9. Risk Explorer

### 9.1 Purpose

Answer: Why is this pair at risk, and how reliable is the conclusion?

### 9.2 Results view

Provide filters for facility, medicine, risk, quality and forecast window. Results use the same columns and status language as the overview.

### 9.3 Risk detail hierarchy

1. **Decision header:** facility, medicine, risk band, forecast window
2. **Actual evidence:** usable stock, recent consumption, days of cover, open orders
3. **Comparison:** safety stock and risk threshold
4. **Trend:** stock and consumption over time with data gaps shown
5. **Contributing factors:** structured values and plain-language explanations
6. **Data quality:** completeness, rejected records and warnings
7. **Provenance:** model, dataset, configuration and analysis identifiers

Never place the AI-generated narrative above the actual evidence.

### 9.4 Trend chart

- Use a line for stock balance and a separate axis or panel for consumption.
- Show missing periods as gaps, not interpolated lines.
- Mark deliveries and stock-out periods.
- Provide a text/table alternative.

## 10. Redistribution Planner

### 10.1 Purpose

Answer: Is there a safe, feasible transfer worth reviewing?

### 10.2 Recommendation row

Show:

- Recipient and medicine
- Donor
- Suggested quantity and pack count
- Recipient cover before and after
- Donor cover before and after
- Remaining shelf life
- Distance or cost proxy
- Quality status
- Review status

### 10.3 Comparison component

Use a two-column before/after comparison for donor and recipient. Do not use a gauge. Include a labelled safety threshold on the values or chart.

### 10.4 Review workflow

1. User opens recommendation.
2. System displays all passed constraints and warnings.
3. User selects Accept, Edit or Reject.
4. Edit permits quantity only within safe calculated bounds and valid pack sizes.
5. Reviewer note is mandatory.
6. User confirms that the action records a decision only.
7. System records the new recommendation version and audit event.

Accept is not preselected. Destructive or rejecting actions use neutral confirmation language, not shame or coercion.

## 11. Data Quality

### 11.1 Purpose

Answer: Which results are limited by the source data, and what needs correction?

### 11.2 Page structure

- Overall quality status and accepted/rejected counts
- Dimension scores with actual values and thresholds
- Facility comparison table
- Rule failure table
- Rejected-row detail with safe export
- Explanation of how quality affects risk and recommendations

Do not collapse quality into one percentage without showing critical failures.

## 12. Action Report

### 12.1 Builder

The user can include reviewed findings, assign owners and due dates, and add a short management note. Suggested content is visibly separate from user-authored content.

### 12.2 Report order

1. Executive summary
2. Reporting context and data quality
3. Priority stock-out risks
4. Reviewed redistribution actions
5. Operational bottlenecks
6. Owners, actions and due dates
7. Method, model and limitations

### 12.3 AI-assisted copy

Mark as `AI-assisted draft`. Provide `Use deterministic version` and `Regenerate from approved facts` controls. Do not make the LLM output the only editable version.

## 13. Empty, loading and error states

### Empty

Explain why nothing is shown and the next safe action. Example: `No feasible transfers meet the safety and data-quality rules.` Do not suggest that the absence of a recommendation means there is no risk.

### Loading

State the operation, such as `Validating 12,480 inventory records`. Use a progress indicator only when progress is measurable.

### Validation error

Show accepted and rejected counts, top failure categories and a link to details. Preserve the user's context.

### Model unavailable

Display: `ML score unavailable. Showing the deterministic baseline.` Do not present the fallback as equivalent without explanation.

### LLM unavailable

Generate the deterministic report and show a low-priority note. This is not a blocking error.

## 14. Responsive behaviour

The primary target is desktop and large tablet. On smaller widths:

- Collapse navigation into an accessible menu.
- Stack summary indicators.
- Prioritise facility, medicine, risk and action in tables.
- Move secondary columns into expandable row details.
- Keep review actions large enough for touch.
- Never hide critical warnings behind horizontal scrolling alone.

## 15. Accessibility

- Meet WCAG 2.2 AA for implemented screens.
- Use semantic headings in logical order.
- Provide visible keyboard focus.
- Ensure all controls have programmatic labels.
- Support keyboard-only review workflows.
- Announce validation and status changes to assistive technology.
- Provide chart summaries and tabular alternatives.
- Avoid colour-only risk meaning.
- Keep touch targets approximately 44 by 44 CSS pixels where practical.
- Honour reduced-motion preferences.
- Test at 200% zoom without loss of task completion.

## 16. Content design

Use plain, operational language:

- Prefer `12 days of stock remaining` to `inventory runway: 12`.
- Prefer `Recommendation withheld because 3 reports are missing` to `low-confidence result` alone.
- Prefer `Likely cause: delivery is 9 days overdue` to `supply-chain anomaly detected`.
- Prefer `Review decision recorded` to `transfer approved`.

Avoid anthropomorphism such as `the AI thinks`. Name the source: reported, calculated, predicted, inferred or reviewed.

## 17. Design QA checklist

- Primary task is apparent without scrolling through decorative content.
- Actual values appear before targets or percentages.
- High, medium, low and not-assessed states are distinguishable without colour.
- Missing evidence is not displayed as zero.
- Recommendation details show donor and recipient impact.
- Review copy never implies that the application executes a transfer.
- Chart axes, units, dates and data gaps are clear.
- Loading, empty, validation, fallback and error states exist.
- Focus order and keyboard operation are logical.
- Text and controls pass contrast and zoom checks.
- The PDF or HTML report preserves hierarchy and does not clip tables.

## 18. UX acceptance

The experience is accepted when a first-time user can load the demo, find the highest-priority risk, explain the evidence, review a feasible transfer, understand why an unsafe transfer was withheld, record a decision and export an action report without mistaking prediction for fact or review for execution.
