import argparse
import json
from pathlib import Path
import joblib
from .data import download,load_public,synthetic
from .detection import fit,drift
from .portable import export_portable
from .investigation import investigate

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['train','demo'])
    parser.add_argument('--synthetic',action='store_true',help='Explicit synthetic smoke test instead of public dataset')
    parser.add_argument('--rows',type=int,default=20000)
    parser.add_argument('--output',default='artifacts')
    args=parser.parse_args()
    out=Path(args.output); out.mkdir(parents=True,exist_ok=True)
    frame,provenance=synthetic(args.rows) if args.synthetic else load_public(download('data/kddcup.data_10_percent.gz'),args.rows)
    bundle,metrics,predictions=fit(frame)
    joblib.dump(bundle,out/'model.joblib')
    export_portable(bundle,out)
    (out/'metrics.json').write_text(json.dumps(metrics,indent=2))
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2))
    predictions.sample(min(150,len(predictions)),random_state=42).sort_values('probability',ascending=False).to_json(out/'events.json',orient='records',indent=2)
    (out/'drift.json').write_text(json.dumps(drift(bundle['reference'],frame),indent=2))
    event=json.loads(predictions.sort_values('probability',ascending=False).head(1).to_json(orient='records'))[0]
    (out/'investigation.json').write_text(json.dumps(investigate(event),indent=2))
    print(json.dumps({k:v for k,v in metrics.items() if k not in ['pr_curve','calibration','feature_importance']},indent=2))
if __name__=='__main__': main()
