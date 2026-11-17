"""Public network benchmark ingestion. Never represents this as production traffic."""
from pathlib import Path
import hashlib
import json
import urllib.request
import numpy as np
import pandas as pd

URL = 'https://ndownloader.figshare.com/files/5976042'
CHECKSUM = '8045aca0d84e70e622d1148d7df782496f6333bf6eb979a1b0837c42a9fd9561'
COLUMNS = ('duration protocol_type service flag src_bytes dst_bytes land wrong_fragment urgent hot num_failed_logins logged_in num_compromised root_shell su_attempted num_root num_file_creations num_shells num_access_files num_outbound_cmds is_host_login is_guest_login count srv_count serror_rate srv_serror_rate rerror_rate srv_rerror_rate same_srv_rate diff_srv_rate srv_diff_host_rate dst_host_count dst_host_srv_count dst_host_same_srv_rate dst_host_diff_srv_rate dst_host_same_src_port_rate dst_host_srv_diff_host_rate dst_host_serror_rate dst_host_srv_serror_rate dst_host_rerror_rate dst_host_srv_rerror_rate label').split()
FEATURES = ['duration','src_bytes','dst_bytes','num_failed_logins','count','srv_count','serror_rate','rerror_rate','same_srv_rate','diff_srv_rate','dst_host_count','dst_host_srv_count','dst_host_same_srv_rate']

def download(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with urllib.request.urlopen(URL, timeout=90) as response:
            path.write_bytes(response.read())
    if hashlib.sha256(path.read_bytes()).hexdigest() != CHECKSUM:
        raise ValueError('Public dataset checksum mismatch; remove file and retry')
    return path

def load_public(path, limit=20000):
    raw = pd.read_csv(path, names=COLUMNS, compression='gzip')
    # Identical feature vectors cannot occur in both train and test, even if labels differ.
    conflicts = raw.groupby(FEATURES, dropna=False)['label'].transform('nunique') > 1
    raw = raw.loc[~conflicts].drop_duplicates(FEATURES).copy()
    raw['label'] = raw.label.str.rstrip('.')
    raw['target'] = (raw.label != 'normal').astype(int)
    if len(raw) > limit:
        raw = raw.sample(limit, random_state=42)
    raw = raw.reset_index(drop=True)
    raw['event_id'] = ['kdd-'+str(i) for i in range(len(raw))]
    provenance = {'source':URL,'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                  'dataset':'KDD Cup 1999 10% (historical simulated network benchmark)',
                  'rows':len(raw),'deduplication':'13 selected predictors, conflicting-label vectors removed',
                  'limitations':['No timestamps or real account/device identifiers','Random disjoint-vector holdout, not temporal or enterprise validation','Attack-enriched benchmark prevalence is not production prevalence']}
    return raw, provenance

def synthetic(n=1000):
    """Explicitly synthetic pipeline smoke-test data, not a performance benchmark."""
    rng = np.random.default_rng(42)
    frame = pd.DataFrame({f:rng.exponential(2,n) for f in FEATURES})
    frame['target'] = ((frame['count']+rng.normal(0,1,n))>4).astype(int)
    frame['label'] = np.where(frame.target,'synthetic_attack','normal')
    frame['event_id'] = ['synthetic-'+str(i) for i in range(n)]
    return frame, {'dataset':'SYNTHETIC SMOKE TEST ONLY','rows':n,'source':'seeded generator, not public telemetry'}
