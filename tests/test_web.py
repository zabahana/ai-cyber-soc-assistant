from pathlib import Path
import pytest
pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest
APP = Path(__file__).resolve().parents[1] / 'streamlit_app.py'

def app(monkeypatch, tmp_path):
    monkeypatch.setenv('SOC_REVIEW_DB',str(tmp_path/'test-review.db'))
    return AppTest.from_file(str(APP), default_timeout=30).run()

def test_overview_and_investigation(monkeypatch,tmp_path):
    at=app(monkeypatch,tmp_path)
    assert not at.exception
    assert len(at.metric)==4
    at.sidebar.radio[0].set_value('Investigate').run()
    assert not at.exception
    at.button[0].click().run()
    assert at.success
    at.button[0].click().run() # duplicate submit safe
    at.sidebar.radio[0].set_value('Human review').run()
    assert not at.exception
    at.button[0].click().run()
    assert at.error # acknowledgement required
    at.text_input[0].set_value('Test analyst')
    at.text_area[0].set_value('Reviewed benchmark evidence')
    at.checkbox[0].check()
    at.button[0].click().run()
    assert not at.exception
    assert not at.text_input # no pending item remains

@pytest.mark.skipif(not (APP.parent/'artifacts/model-metadata.json').exists(),reason='portable trained model required')
def test_model_and_drift(monkeypatch,tmp_path):
    at=app(monkeypatch,tmp_path)
    at.sidebar.radio[0].set_value('Model lab').run()
    assert not at.exception
    at.button[0].click().run()
    assert not at.exception
    assert len(at.metric)==3
    at.sidebar.radio[0].set_value('Drift monitor').run()
    assert not at.exception
    at.selectbox[0].set_value('num_failed_logins')
    at.number_input[0].set_value(100.0).run()
    assert not at.exception
    assert at.dataframe[0].value.PSI.max()>1

def test_empty_filter(monkeypatch,tmp_path):
    at=app(monkeypatch,tmp_path)
    at.sidebar.radio[0].set_value('Investigate').run()
    at.slider[0].set_value(1.0).run()
    assert not at.exception
    assert at.info

def test_sparse_feature_drift():
    import pandas as pd
    from soc_assistant.data import FEATURES
    from soc_assistant.detection import reference_profile, drift
    baseline=pd.DataFrame({f:[0.0]*99+[1.0] for f in FEATURES})
    shifted=baseline.copy(); shifted['num_failed_logins']=100.0
    assert drift(reference_profile(baseline),shifted)['features']['num_failed_logins']['psi']>1

def test_saved_result_mode(monkeypatch,tmp_path):
    import shutil
    artifacts=tmp_path/'artifacts'; artifacts.mkdir()
    for name in ['events.json','metrics.json','provenance.json']:
        shutil.copy(APP.parent/'artifacts'/name,artifacts/name)
    monkeypatch.setenv('SOC_ARTIFACT_DIR',str(artifacts))
    at=app(monkeypatch,tmp_path)
    assert not at.exception
    assert any('Saved-result mode' in x.value for x in at.info)
    at.sidebar.radio[0].set_value('Model lab').run()
    assert not at.exception
    assert not at.button


def test_approve_simulation(monkeypatch,tmp_path):
    from soc_assistant.review import ReviewQueue
    at=app(monkeypatch,tmp_path)
    at.sidebar.radio[0].set_value('Investigate').run()
    at.button[0].click().run()
    at.sidebar.radio[0].set_value('Human review').run()
    at.text_input[0].set_value('Demo')
    at.text_area[0].set_value('Corroboration requested')
    next(r for r in at.radio if r.label=='Decision').set_value('Approve simulation')
    at.checkbox[0].check()
    at.button[0].click().run()
    assert not at.exception
    queue=ReviewQueue(tmp_path/'test-review.db')
    assert len(queue.audit())==1
    assert queue.audit()[0]['action']=='approved'
    assert queue.audit()[0]['details']['executed'] is False
    queue.db.close()


def test_default_review_sessions_separate(monkeypatch):
    monkeypatch.delenv('SOC_REVIEW_DB',raising=False)
    first=AppTest.from_file(str(APP),default_timeout=30).run()
    first.sidebar.radio[0].set_value('Investigate').run()
    first.button[0].click().run()
    second=AppTest.from_file(str(APP),default_timeout=30).run()
    second.sidebar.radio[0].set_value('Human review').run()
    assert not second.exception
    assert any('Select a record' in message.value for message in second.info)
    first.sidebar.radio[0].set_value('Human review').run()
    assert first.text_input
