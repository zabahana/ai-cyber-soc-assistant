import numpy as np
from soc_assistant.data import synthetic
from soc_assistant.detection import fit, score
from soc_assistant.portable import export_portable, load_portable

def test_portable_predictions_match(tmp_path):
    frame,_=synthetic(600)
    bundle,_,_=fit(frame)
    export_portable(bundle,tmp_path)
    restored=load_portable(tmp_path)
    original=score(bundle,frame); portable=score(restored,frame)
    np.testing.assert_allclose(original.probability,portable.probability,rtol=1e-12)
    np.testing.assert_allclose(original.anomaly_score,portable.anomaly_score,rtol=1e-12)
    assert original.alert.equals(portable.alert)
    assert original.priority.equals(portable.priority)
    assert restored['reference']==bundle['reference']
