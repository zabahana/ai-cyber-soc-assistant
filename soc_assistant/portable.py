"""Non-executable JSON model export for reproducible hosted demonstration inference."""
import json
from pathlib import Path
import numpy as np
from xgboost import XGBClassifier


def average_path(n):
    n=np.asarray(n,dtype=float)
    result=np.zeros(n.shape)
    result[n==2]=1.0
    mask=n>2
    result[mask]=2*(np.log(n[mask]-1)+np.euler_gamma)-2*(n[mask]-1)/n[mask]
    return result


class Calibration:
    def __init__(self,coef,intercept): self.coef=coef; self.intercept=intercept
    def predict_proba(self,x):
        z=np.asarray(x,dtype=float).reshape(-1)*self.coef+self.intercept
        # stable logistic function, without serialized Python code
        p=np.exp(-np.logaddexp(0,-z))
        return np.column_stack((1-p,p))


class Forest:
    def __init__(self,trees,max_samples): self.trees=trees; self.max_samples=max_samples
    def score_samples(self,x):
        # sklearn IsolationForest applies float32 before tree traversal.
        x=np.asarray(x,dtype=np.float32); total=np.zeros(len(x))
        for tree in self.trees:
            nodes=np.zeros(len(x),dtype=int); depths=np.zeros(len(x))
            left=np.asarray(tree['left']); right=np.asarray(tree['right'])
            feature=np.asarray(tree['feature']); threshold=np.asarray(tree['threshold'])
            mapping=np.asarray(tree['mapping'])
            active=left[nodes]!=-1
            while active.any():
                rows=np.flatnonzero(active); current=nodes[rows]
                goes_left=x[rows,mapping[feature[current]]]<=threshold[current]
                nodes[rows]=np.where(goes_left,left[current],right[current])
                depths[rows]+=1
                active=left[nodes]!=-1
            total+=depths+average_path(np.asarray(tree['samples'])[nodes])
        denominator=len(self.trees)*float(average_path([self.max_samples])[0])
        return -(2**(-np.divide(total,denominator,out=np.ones_like(total),where=denominator!=0)))


def export_portable(bundle,directory):
    directory=Path(directory); directory.mkdir(parents=True,exist_ok=True)
    bundle['model'].save_model(directory/'xgboost-model.json')
    trees=[]
    for estimator,mapping in zip(bundle['anomaly'].estimators_,bundle['anomaly'].estimators_features_):
        t=estimator.tree_
        trees.append({'left':t.children_left.tolist(),'right':t.children_right.tolist(),
                      'feature':t.feature.tolist(),'threshold':t.threshold.tolist(),
                      'samples':t.n_node_samples.tolist(),'mapping':mapping.tolist()})
    metadata={'format_version':1,'features':bundle['features'],'threshold':bundle['threshold'],
              'reference':bundle['reference'],'calibration':{'coef':float(bundle['calibrator'].coef_[0,0]),
              'intercept':float(bundle['calibrator'].intercept_[0])},
              'isolation_forest':{'max_samples':int(bundle['anomaly'].max_samples_),'trees':trees}}
    (directory/'model-metadata.json').write_text(json.dumps(metadata,separators=(',',':'),allow_nan=False))


def load_portable(directory):
    directory=Path(directory)
    metadata=json.loads((directory/'model-metadata.json').read_text())
    if metadata['format_version']!=1: raise ValueError('Unsupported portable model format')
    model=XGBClassifier(); model.load_model(directory/'xgboost-model.json')
    return {'model':model,'calibrator':Calibration(**metadata['calibration']),
            'anomaly':Forest(**metadata['isolation_forest']), 'features':metadata['features'],
            'threshold':metadata['threshold'],'reference':metadata['reference']}
