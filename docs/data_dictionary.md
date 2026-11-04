# Data dictionary

Canonical machine-readable schemas are generated in `data/schemas/`. Supplied document `03_Data_and_Model_Specification.md` is the source contract.

| Dataset | Grain / key | Main fields |
|---|---|---|
| Facilities | One facility / facility_id | Name, facility/location type, synthetic coordinates, lead time, reporting target, active |
| Medicines | One medicine / medicine_id | Generic name, category, pack size, safety days, minimum shelf life, active |
| Inventory | Facility–medicine–week | Opening + receipts − dispensed + adjustments = closing; stock-out days; expiry; near-expiry quantity; timeliness |
| Orders | One order / order_id | Ordered/delivered quantities, expected/actual dates and status |
| Reviews | Recommendation/version | Actor-entered role/name, decision, edited quantity, mandatory note, acknowledgement and analysis provenance |
| Programme | Fictional workplan / indicator / budget line / issue | Synthetic programme records constructed in `app/data/programme.py`; never presented as uploaded programme accounts |

ADC = observed recent dispensing / observed days. Cover = usable stock / positive ADC. Reporting completeness = received / expected 12-week reports. Timeliness uses expected reports, including missing ones. Validity and uniqueness use all source rows; consistency uses inventory source rows. Critical gates override aggregate dimensions.

Indicator achievement = actual / target × 100. Zero eligible denominator is not assessed. Green ≥100% achievement; amber ≥85% and below100%; red below85%. These programme status bands are separate from model probability bands.

Data cut-off: 1 November 2026. Generator seed42, 60 weekly periods. Scenario truth is separate in `data/demo/manifest.json`. User-requested programme period: August–November2026; currency USD. US$185,000 allocation, US$128,750 actual spend, US$18,900 commitments, US$37,350 uncommitted.
