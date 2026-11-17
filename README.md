# AI-Powered Cyber Threat Detection & SOC Investigation Assistant

A **defensive portfolio prototype**, not a production SOC product. It trains XGBoost on real, publicly released KDD Cup 1999 network records and supports evidence-grounded analyst investigation. Historical lab traffic is not representative of modern banking environments.

## Quick start
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m soc_assistant.cli train --rows 20000
pytest -q
```
The first training run downloads the UCI 10% compressed file (~2 MB). For completely offline smoke testing use `python -m soc_assistant.cli demo --synthetic --rows 1000 --output artifacts/synthetic`. This mode is **synthetic**, not a public-telemetry benchmark, and uses a separate output directory to avoid replacing the benchmark artifacts.

## Architecture and implementation boundaries
| Stage | Implementation |
|---|---|
| Public network telemetry | UCI KDD99 ingestion, SHA256 provenance, selected-feature duplicate removal |
| Authentication / endpoint events | Separate validated adapters; optional PySpark 5-minute authentication aggregation. No invented join to network records |
| Feature engineering | 13 numeric connection features, finite/nonnegative validation, log1p transformation |
| ML detection | XGBoost classifier plus normal-only Isolation Forest novelty score |
| Prioritization | Disjoint fit/calibration/threshold/test partitions; Platt calibration; F2 threshold chosen on validation only |
| Investigation | Local TF-IDF retrieval of curated playbooks; evidence summaries; optional explicitly enabled OpenAI draft |
| ATT&CK | Transparent candidate technique hypotheses, **not ground-truth technique classification** |
| Human response | SQLite review queue and transactional decision audit. All responses simulated; no host/network/account modification |
| Monitoring | PSI feature shift, precision/recall, AP, Brier, reliability and PR curves |

The network detector does not score authentication/endpoint records. These require separate training data and models. PySpark is an optional, runnable aggregation path, not a claim that the demonstrated training job ran in Spark.

## Outputs and integration
`artifacts/metrics.json`, `events.json` (150 seeded sampled held-out records, sorted by score), `provenance.json`, `investigation.json`, `drift.json`, and local `model.joblib`. The model file is ignored by Git; recreate it with the training command. Only load trusted locally produced joblib files: pickle-based formats can execute arbitrary code.

```python
import joblib, pandas as pd
from soc_assistant.detection import score
from soc_assistant.investigation import investigate
from soc_assistant.review import ReviewQueue
model = joblib.load('artifacts/model.joblib')
events = pd.read_json('artifacts/events.json')
scored = score(model, events)
report = investigate(scored.iloc[0].to_dict())
queue = ReviewQueue('reviews.db')
queue.submit(report)
queue.decide(report['event_id'], 'demo-analyst', True, 'collect_evidence', 'Need independent corroboration')
```
The queue does not authenticate the analyst; names are demo attribution, not verified identity. A production service must add authentication, authorization, immutable external audit storage, retention controls and tenant isolation. The local audit can be modified by the database owner.

### Optional LLM
Install `pip install -e '.[llm]'`, set `OPENAI_API_KEY` securely and optionally `SOC_LLM_MODEL`, then call `investigate(event, question, use_llm=True)`. **This transmits the selected event evidence and question to OpenAI and may incur charges.** Default mode is deterministic retrieval without API calls and is clearly labeled as not an LLM. Never place real customer/security data into the demonstration without an approved data-sharing policy. LLM output is an untrusted advisory draft; no tool execution is available.

### Optional PySpark
Install `pip install -e '.[spark]'` with a compatible Java runtime and call `spark_auth_features` on a DataFrame with timestamp, user, source_ip, boolean success. This optional path was not exercised in the default test run.

## Dataset, provenance and license
Source: [UCI KDD Cup 1999](https://archive.ics.uci.edu/dataset/130/kdd+cup+1999+data), DOI [10.24432/C51C7N](https://doi.org/10.24432/C51C7N); original [competition archive](https://kdd.ics.uci.edu/databases/kddcup99/kddcup99.html). UCI lists CC BY 4.0. Attribution: Stolfo, S., Fan, W., Lee, W., Prodromidis, A., & Chan, P. (1999). KDD Cup 1999 Data. The downloadable file uses the scikit-learn-maintained Figshare mirror and is verified against scikit-learn’s SHA256. Derived excerpts select and score original records. Raw downloaded data are excluded from this repository; inspect current source terms before redistribution. JSON event artifacts are small derived benchmark excerpts, not private enterprise logs.

KDD99 consists of historical simulated network traffic with severe duplication and unrealistic attack prevalence. We remove identical vectors before splitting, remove conflicting-label vectors, and retain a random disjoint holdout. This is **not temporal validation**, not evidence of robustness to unseen campaigns, and not a realistic estimate of banking precision or false-positive workload. Record IDs are generated row identifiers, not real host identities. There are no timestamps, users or actual endpoint events to support cross-source correlation.

## Model risk and safety
- Calibration is assessed on held-out benchmark data; an 0.8 score is not a portable 80% compromise probability.
- Threshold selection uses F2 on validation, not test; choose real thresholds using investigation capacity and asymmetric error costs.
- Isolation Forest output is a novelty score, **not** a probability or attack label.
- ATT&CK mappings are analyst hypotheses based on observable feature heuristics. A high count cannot by itself confirm T1046 or T1498.
- PSI is only an indicator. It uses fixed training quantile bins and empirical reference masses; bin choices affect interpretation. No automatic retraining or response.
- The model's global feature importances are not per-alert explanations or causal effects.
- Raw labels remain in evaluation artifacts for demonstration only and are excluded from model features and investigation evidence.

See `docs/VALIDATION.md` for the validation plan and operational gaps.

## GitHub Actions setup
The CI workflow is retained as `docs/ci-workflow.yml.example`. To activate it, copy it to `.github/workflows/test.yml` using a GitHub credential with workflow permission. The initial push credential did not have that permission; no credentials or permissions were changed.

## Interactive local web interface
```bash
pip install -e '.[dev,web]'
python -m soc_assistant.cli train --rows 20000
streamlit run streamlit_app.py --server.address=127.0.0.1
```
Open **http://localhost:8501** on the computer running the app. The command above explicitly binds to localhost, with usage telemetry disabled. The repository config deliberately leaves the bind address unset so managed hosting can supply the correct listener; always include the localhost flag for a local-only run. It is not publicly hosted or authenticated; do not expose it directly to the Internet. The web app loads non-pickle portable models from `artifacts/xgboost-model.json` and `artifacts/model-metadata.json`. These small files are included for immediate inference without training on deployment. Without a trained model, the app clearly switches to saved-result mode; live scoring and drift experiments are disabled.

Five workspaces:
- **Overview:** held-out precision/recall, PR and calibration curves, confusion matrix, global feature importance and provenance.
- **Investigate:** filter the saved example records, ask retrieval questions, inspect evidence/ATT&CK hypotheses, download a report, and add a record to review.
- **Model lab:** edit 13 numeric features and run actual XGBoost/calibrator/Isolation Forest inference. Outputs are hypothetical inputs, not new observed telemetry.
- **Human review:** approve/reject a simulated playbook with rationale and acknowledgement; session-isolated SQLite audit by default, idempotent record submission, duplicate decisions blocked.
- **Drift monitor:** apply hypothetical feature shifts and recompute PSI against the training reference. No retraining or real response occurs.

The interface does not invoke an external LLM or transmit telemetry. Its investigation mode is explicitly labeled deterministic retrieval. The optional Python LLM API remains opt-in. The UI's review database is isolated per browser session by default and may reset on reconnect or server restart; download the audit before leaving. For a trusted single-user local install, set `SOC_REVIEW_DB` to a persistent SQLite path. That override shares the database across all sessions, so do not enable it on an app with untrusted visitors. `SOC_ARTIFACT_DIR` selects an alternate trusted artifact directory. Never load untrusted joblib files. Headless UI interaction tests use Streamlit AppTest: `pytest -q`; live-model tests skip when no trained model exists.

The Python web app is not deployable as a static Site or JavaScript Worker: it needs a Python process and model files. A public deployment requires appropriate hosting, authentication, access controls and secrets management. No such production controls are claimed here.


## Streamlit Community Cloud deployment
Choose repository `zabahana/ai-cyber-soc-assistant`, branch `main`, main file `streamlit_app.py`, and **Python 3.12** in Advanced settings. The root `requirements.txt` pins tested versions. No API key or secrets are needed. Before sharing the app, verify available access controls and the actual audience in your Streamlit account. This project has no built-in authentication; private hosting access is not assumed or configured by the code.

The committed native XGBoost JSON and explicit calibration/Isolation Forest JSON arrays enable actual inference immediately. No untrusted pickle is downloaded, no dataset download runs during startup, and no training repeats on widget changes. The resource cache loads the portable model once per process/artifact version. JSON data is not executable Python; nevertheless model files must remain maintained repository assets, not user uploads. `soc train` regenerates both local joblib and portable JSON artifacts.

The portable scorer is tested against the trained sklearn/XGBoost pipeline. Benchmark metrics remain historical KDD99 estimates. Startup does not call an LLM or external telemetry API. On Community Cloud, the hosted service necessarily handles the interaction inputs: use public/demo data only. Each visitor gets a separate session review database by default; it is ephemeral, not durable enterprise audit storage. Session separation is not a secure multi-tenant boundary, and there is no user authentication or authorization in the app.

If dependency installation fails, check Cloud logs and Python version; do not bypass package verification or load random model pickles. Review the [official dependency guide](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies). Cloud hosting has not been verified until the hosted app build succeeds.
