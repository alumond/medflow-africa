# Model card — gradient_boosting-1.1.0

Intended use: advisory probability ranking of medicine–facility stock-out risk over7,14 and30days. Numeric predictions do not authorise stock movement. Dataset: synthetic-1.0.0-seed42; all results below are synthetic.

Feature contract: cover, stock, observed daily consumption, short/long consumption trend, lead time, reporting completeness, previous stock-out days, near-expiry quantity and forecast horizon. Observed windows never include future deliveries or future outcomes. Imputation/scaling fit on training only. Scenario truth is outside features.

Logistic regression and gradient boosting were fitted with seed42. Validation-only selection prioritised PR-AUC with Brier as a tie-breaker. Candidate thresholds used a miss cost of3 versus an extra review cost of1. Selected model: gradient_boosting; operating threshold 0.1. No test observations influenced selection. Training/validation/test ranges and the30-day label purge are in the JSON artifact.

| Synthetic holdout metric | Selected ML | Deterministic baseline |
|---|---:|---:|
| Precision | 0.364 | 0.414 |
| Recall | 1.000 | 1.000 |
| F1 | 0.533 | 0.585 |
| PR-AUC | 0.601 | 0.414 |
| Brier | 0.0111 | 0.0297 |

Holdout observations: 2288. The selected model improves ranking and probability error on this synthetic dataset while producing more false alerts at its recall-oriented threshold. The combined alert rule is measured separately. Do not attribute the standalone metrics to the combined UI behaviour.

Promoted for advisory probability ranking: validation PR-AUC improves and Brier score decreases versus baseline. Baseline alerts remain a hard lower bound on the risk band.

Explanations: numeric JSON tree-path decomposition in log-odds (or logistic coefficient decomposition for the benchmark). Tree-path attribution is order-dependent and is not SHAP or a causal explanation. Probability is not a guarantee; evidence-quality labels are not statistical confidence intervals.

The artifact includes calibration bins, confusion matrices, thresholds, horizon-specific metrics, subgroup sample/positive counts, false-negative/positive rates, alert rates and perturbation results. Sparse subgroups have insufficient support for fairness claims. Missing or zero-consumption pairs are withheld from inference/recommendations rather than silently treated as low need.

Safe serialization: numeric JSON, SHA-256 checksum and feature-schema hash. Any missing, malformed or unapproved artifact falls back to the deterministic baseline. No arbitrary pickle is loaded.

Drift monitoring compares current feature means with training standard deviations; values above2 trigger investigation only. Current-window false/missed alerts are unavailable until future outcomes mature. Review acceptance is not a model label.

Limitations: one fictional district, synthetic stock events and a rare-event holdout. No real-world, clinical or regulatory performance claim. Reproduce with `python -m scripts.train_model`.
