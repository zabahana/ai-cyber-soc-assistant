# Validation and extension plan

## Implemented checks
1. Fit (60%), calibration (20%), threshold selection (10%), untouched test (10%) with seeded stratification.
2. Remove duplicate feature vectors before splitting and exclude label/target/IDs from predictors.
3. Report precision, recall, F1, average precision, confusion matrix, Brier score, reliability plot data, PR curve.
4. Input schema rejects missing, nonfinite and negative predictors.
5. Review state machine rejects unsupported actions and repeat decisions; approved decisions never execute containment.
6. Investigation does not expose evaluation labels as evidence.

## Required before real banking use
- Replace the historical network benchmark with approved contemporary multi-source telemetry, true identifiers and timestamps.
- Temporal/entity/campaign holdouts, unseen attack validation, realistic negative prevalence and confidence intervals.
- Point-in-time feature availability, ingestion quality SLAs, missing-feed behavior and protected data controls.
- Cost-sensitive thresholding based on SOC staffing, lockout harm and critical asset exposure.
- Per-alert reason codes with validation against actual evidence, and independent investigation quality grading.
- Evaluate prompt injection, false citations, hallucinated entity links and recommendation harms on a labeled corpus.
- Real SSO/RBAC, tamper-evident audit storage, escalation rules, reversible response connectors and action-time approval.
- Monitor alert volume, analyst acceptance, false-positive workload, delayed-label recall and drift; documented rollback.

The demonstration intentionally has no malware, scanning, exploitation, credential access or real containment capability.
