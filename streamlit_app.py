"""Local-only SOC workbench. No response execution and no API calls by default."""
import hashlib
import json
import os
from pathlib import Path
import joblib
import pandas as pd
import streamlit as st
from soc_assistant.data import FEATURES
from soc_assistant.ui_validation import RATE_FEATURES, validate_model_input
from soc_assistant.detection import score, drift
from soc_assistant.investigation import investigate
from soc_assistant.review import ReviewQueue, ALLOWED_ACTIONS

ROOT = Path(__file__).resolve().parent
ART = Path(os.environ.get('SOC_ARTIFACT_DIR', ROOT / 'artifacts'))
st.set_page_config(page_title='SOC | Investigation Workbench', page_icon='🛡️', layout='wide')
st.markdown('''<style>.block-container{padding-top:2rem;max-width:1500px} [data-testid="stMetric"]{border:1px solid #284355;border-radius:10px;padding:16px} h1{letter-spacing:-1px}</style>''', unsafe_allow_html=True)
st.caption('SECURITY OPERATIONS / RESEARCH WORKBENCH')
st.title('Threat detection. Evidence first.')
st.write('Explore scored network records, challenge the model, and document an analyst decision.')
st.warning('Historical KDD99 benchmark, not production banking telemetry. All responses are simulated. No account, host or network changes are executed.')

def read_json(name):
    return json.loads((ART / name).read_text())

try:
    events = pd.DataFrame(read_json('events.json'))
    metrics = read_json('metrics.json')
except (OSError, ValueError) as error:
    st.error(f'Artifacts unavailable: {error}. Run python -m soc_assistant.cli train --rows 20000 first.')
    st.stop()
model_path = ART / 'model.joblib'
@st.cache_resource
def load_model(path, modified):
    return joblib.load(path)  # Only trusted, locally generated model artifacts.
bundle = load_model(str(model_path), model_path.stat().st_mtime_ns) if model_path.exists() else None
if bundle is None:
    st.info('Saved-result mode. Train locally to enable live model scoring and drift experiments; no model is fabricated.')
with st.sidebar:
    st.header('Investigation workbench')
    page = st.radio('Workspace', ['Overview', 'Investigate', 'Model lab', 'Human review', 'Drift monitor'])
    st.caption('Local Python inference · no external calls')
    st.caption('The UI uses deterministic retrieval, not an LLM. Optional OpenAI generation is available through the Python API, with explicit opt-in.')
    st.divider()
    st.caption('No authentication: run on localhost only. Analyst names are demo attribution.')

if page == 'Overview':
    st.subheader('Held-out detection performance')
    st.caption(f"{metrics['partitions']['test']:,} held-out records. These numbers do not estimate modern SOC performance.")
    cols = st.columns(4)
    for col, label, key in zip(cols, ['Precision','Recall','Average precision','Brier score'], ['precision','recall','average_precision','brier_score']):
        col.metric(label, f'{metrics[key]:.4f}')
    a,b = st.columns(2)
    with a:
        st.markdown('#### Precision–recall')
        curve = pd.DataFrame(metrics['pr_curve']).sort_values('recall')
        st.line_chart(curve, x='recall', y='precision')
    with b:
        st.markdown('#### Calibration reliability')
        cal = pd.DataFrame(metrics['calibration']).sort_values('mean_predicted')
        cal['ideal'] = cal.mean_predicted
        st.line_chart(cal, x='mean_predicted', y=['fraction_positive','ideal'])
    a,b = st.columns(2)
    with a:
        st.markdown('#### Confusion matrix')
        st.dataframe(pd.DataFrame(metrics['confusion_matrix'], index=['Actual normal','Actual attack'], columns=['Predicted normal','Predicted attack']), width='stretch')
    with b:
        st.markdown('#### Global feature importance')
        st.bar_chart(pd.Series(metrics['feature_importance']).sort_values().tail(8))
        st.caption('Global model importance is not a per-alert explanation or causal effect.')
    with st.expander('Data provenance and limitations'):
        st.json(read_json('provenance.json'))
        st.write('Authentication and endpoint adapters are separate; this network benchmark cannot demonstrate cross-source correlation. ATT&CK outputs are hypotheses, not learned technique labels.')

elif page == 'Investigate':
    st.subheader('Alert explorer')
    cutoff = st.slider('Minimum displayed benchmark score', 0.0, 1.0, 0.0, .01)
    filtered = events[events.probability >= cutoff]
    st.caption(f'{len(filtered)} of {len(events)} saved held-out examples. This sample is not the full evaluation set.')
    if filtered.empty:
        st.info('No records at this filter. Lower the cutoff.'); st.stop()
    st.dataframe(filtered[['event_id','probability','anomaly_score','priority']], hide_index=True, width='stretch')
    event_id = st.selectbox('Record', filtered.event_id.tolist())
    event = filtered[filtered.event_id == event_id].iloc[0].to_dict()
    question = st.text_input('Investigation question', 'What should the analyst investigate?')
    report = investigate(event, question)
    st.markdown('#### Evidence-grounded investigation')
    st.caption(report['mode'])
    st.write(report['summary'])
    a,b = st.columns(2)
    with a:
        st.json(report['evidence'])
    with b:
        st.markdown('**Candidate hypotheses**')
        for hypothesis in report['hypotheses']: st.write('• '+hypothesis)
        st.markdown('**Recommended next steps**')
        for step in report['recommended_steps']: st.write('• '+step)
    st.markdown('#### Retrieved playbooks')
    if not report['sources']: st.info('No matching playbook. Rephrase the question; no unsupported answer is invented.')
    for source in report['sources']:
        with st.expander(f"{source['id']} · {source['title']} · {source['technique']}"):
            st.write(source['text']); st.link_button('MITRE ATT&CK reference', source['url'])
    if st.button('Add to human review queue', type='primary'):
        queue = ReviewQueue(os.environ.get('SOC_REVIEW_DB', str(ROOT/'reviews.db')))
        queue.submit(report); queue.db.close()
        st.success('Added to review queue (duplicate records are not added twice). No response executed.')
    st.download_button('Download investigation JSON', json.dumps(report,indent=2), file_name=f'{event_id}-investigation.json', mime='application/json')

elif page == 'Model lab':
    st.subheader('What changes the model score?')
    st.write('Edit a held-out connection and run actual Python inference. Edited records are hypothetical, not new public observations.')
    selected = st.selectbox('Starting record', events.event_id.tolist())
    original = events[events.event_id == selected].iloc[[0]]
    if bundle is None: st.info('Live scoring requires the locally trained model.'); st.stop()
    with st.form('model_form'):
        inputs = {}
        cols = st.columns(3)
        for i, feature in enumerate(FEATURES):
            if feature in RATE_FEATURES:
                inputs[feature] = cols[i%3].number_input(feature, min_value=0.0, max_value=1.0, value=float(original.iloc[0][feature]), step=.01, key=f'{selected}-{feature}', format='%.4f')
            else:
                inputs[feature] = cols[i%3].number_input(feature, min_value=0, value=int(original.iloc[0][feature]), step=1, key=f'{selected}-{feature}', help='Whole-number KDD seconds, bytes or count.')
        submitted = st.form_submit_button('Score edited record', type='primary')
    if submitted:
        try:
            validate_model_input(inputs)
            result = score(bundle, pd.DataFrame([inputs])).iloc[0].to_dict()
            result['event_id'] = 'whatif-'+hashlib.sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest()[:12]
            st.session_state['lab_result'] = result
            st.session_state['lab_base'] = float(score(bundle,original).iloc[0].probability)
        except (ValueError, TypeError) as error:
            st.session_state.pop('lab_result', None)
            st.error(str(error))
    result = st.session_state.get('lab_result')
    if result:
        a,b,c = st.columns(3)
        a.metric('Edited benchmark probability', f"{result['probability']:.4f}", f"{result['probability']-st.session_state['lab_base']:+.4f}")
        b.metric('Novelty score (not probability)', f"{result['anomaly_score']:.4f}")
        c.metric('Model triage', 'Alert' if result['alert'] else 'Below threshold')
        st.caption(f"Last submitted hypothetical record {result['event_id']}; threshold {bundle['threshold']:.2f}. Input edits take effect only after scoring.")
        st.json(result)

elif page == 'Human review':
    st.subheader('Analyst decision queue')
    queue = ReviewQueue(os.environ.get('SOC_REVIEW_DB', str(ROOT/'reviews.db')))
    rows = queue.list()
    if rows:
        st.dataframe(pd.DataFrame([{'event_id':r['event_id'],'status':r['status']} for r in rows]), hide_index=True, width='stretch')
    else: st.info('Select a record in Investigate, then add it to the queue.')
    pending = [r for r in rows if r['status']=='pending']
    if pending:
        selected = st.selectbox('Pending review', [r['event_id'] for r in pending])
        st.json(next(r['evidence'] for r in pending if r['event_id']==selected))
        with st.form('review_form'):
            actor = st.text_input('Analyst name (demo attribution only)')
            action = st.selectbox('Proposed playbook action', sorted(ALLOWED_ACTIONS))
            decision = st.radio('Decision', ['Reject','Approve simulation'])
            reason = st.text_area('Decision rationale')
            confirmed = st.checkbox('I reviewed the evidence and understand no real action will execute.')
            submitted = st.form_submit_button('Record decision')
        if submitted:
            if not confirmed: st.error('Review the evidence and acknowledge the simulation before recording a decision.')
            else:
                try:
                    queue.decide(selected,actor,decision=='Approve simulation',action,reason)
                    queue.db.close(); st.rerun()
                except ValueError as error: st.error(str(error))
    st.markdown('#### Audit trail')
    audit = queue.audit()
    st.dataframe(pd.DataFrame(audit), width='stretch')
    st.download_button('Download audit JSON',json.dumps(audit,indent=2),file_name='soc-audit.json',mime='application/json')
    st.caption('Local SQLite audit is persistent but not tamper-proof or authenticated. Duplicate decisions are blocked.')
    queue.db.close()

elif page == 'Drift monitor':
    st.subheader('Distribution-shift experiment')
    if bundle is None: st.info('Live drift requires the locally trained reference profile.'); st.stop()
    st.write('Compare the saved held-out sample with the training reference. Apply a hypothetical shift to one feature.')
    feature = st.selectbox('Feature to shift', FEATURES)
    shift = st.number_input('Additive shift (hypothetical)', min_value=0.0, value=0.0)
    current = events.copy(); current[feature] = current[feature] + shift
    result = drift(bundle['reference'],current)
    frame = pd.DataFrame([{'feature':k,'PSI':v['psi']} for k,v in result['features'].items()]).sort_values('PSI',ascending=False)
    st.bar_chart(frame,x='feature',y='PSI')
    st.dataframe(frame,hide_index=True,width='stretch')
    st.caption(result['note'])
    st.info('No automatic retraining or containment. This small selected sample is an illustration, not a production drift monitor.')
