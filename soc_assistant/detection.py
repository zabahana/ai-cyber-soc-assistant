"""Disjoint fit/calibration/threshold-selection/test partitions."""
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score, average_precision_score, brier_score_loss, confusion_matrix, precision_recall_curve
from sklearn.calibration import calibration_curve
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import IsolationForest
from xgboost import XGBClassifier
from .data import FEATURES

def matrix(frame):
    missing = set(FEATURES)-set(frame.columns)
    if missing: raise ValueError('Missing required features: '+', '.join(sorted(missing)))
    values = frame[FEATURES].astype(float)
    if not np.isfinite(values.to_numpy()).all() or (values<0).any().any():
        raise ValueError('Features must be finite nonnegative numbers')
    return np.log1p(values.to_numpy())

def fit(frame):
    train, rest = train_test_split(frame, test_size=.4, stratify=frame.target, random_state=42)
    cal, rest = train_test_split(rest, test_size=.5, stratify=rest.target, random_state=43)
    validation, test = train_test_split(rest, test_size=.5, stratify=rest.target, random_state=44)
    model = XGBClassifier(n_estimators=100,max_depth=4,learning_rate=.08,subsample=.9,colsample_bytree=.9,random_state=42,n_jobs=2,eval_metric='logloss')
    model.fit(matrix(train),train.target)
    calibrator = LogisticRegression(C=1e6).fit(model.predict(matrix(cal),output_margin=True).reshape(-1,1),cal.target)
    anomaly = IsolationForest(n_estimators=100,contamination=.05,random_state=42,n_jobs=2).fit(matrix(train[train.target==0]))
    bundle = {'model':model,'calibrator':calibrator,'anomaly':anomaly,'features':FEATURES,'threshold':.5}
    pv = score(bundle,validation)['probability'].to_numpy()
    candidates = np.linspace(.05,.95,91)
    # Choose on validation only, with analyst recall preference via F2.
    values=[]
    for threshold in candidates:
        pred=pv>=threshold
        p=precision_score(validation.target,pred,zero_division=0); r=recall_score(validation.target,pred,zero_division=0)
        values.append(5*p*r/(4*p+r) if p+r else 0)
    bundle['threshold']=float(candidates[np.argmax(values)])
    bundle['reference']=reference_profile(train)
    predictions=score(bundle,test)
    y=test.target.to_numpy(); p=predictions.probability.to_numpy(); pred=p>=bundle['threshold']
    fraction, mean = calibration_curve(y,p,n_bins=10,strategy='quantile')
    pr, re, _ = precision_recall_curve(y,p)
    metrics={'precision':float(precision_score(y,pred,zero_division=0)), 'recall':float(recall_score(y,pred,zero_division=0)), 'f1':float(f1_score(y,pred,zero_division=0)), 'average_precision':float(average_precision_score(y,p)), 'brier_score':float(brier_score_loss(y,p)), 'threshold':bundle['threshold'], 'confusion_matrix':confusion_matrix(y,pred,labels=[0,1]).tolist(), 'partitions':{k:len(v) for k,v in [('fit',train),('calibration',cal),('validation',validation),('test',test)]},'test_prevalence':float(y.mean()), 'calibration':{'mean_predicted':mean.tolist(),'fraction_positive':fraction.tolist()},'pr_curve':{'precision':pr.tolist(),'recall':re.tolist()},'feature_importance':dict(zip(FEATURES,map(float,model.feature_importances_)))}
    predictions['actual']=y
    return bundle,metrics,predictions

def score(bundle,frame):
    out=frame.copy()
    x=matrix(frame)
    margin=bundle['model'].predict(x,output_margin=True)
    out['probability']=bundle['calibrator'].predict_proba(margin.reshape(-1,1))[:,1]
    out['anomaly_score']=-bundle['anomaly'].score_samples(x)
    out['alert']=out.probability>=bundle['threshold']
    out['priority']=np.where(out.probability>=.9,'high',np.where(out.alert,'medium','low'))
    return out

def reference_profile(frame):
    profile={}
    for feature in FEATURES:
        edges=np.unique(np.quantile(frame[feature], np.linspace(0,1,11)))
        # retain extrema as inner boundaries so constant-feature shifts remain visible
        inner=np.array([np.nextafter(edges[0],-np.inf), np.nextafter(edges[0],np.inf)]) if len(edges)==1 else edges[1:-1]
        bins=np.r_[-np.inf,inner,np.inf]
        counts=np.histogram(frame[feature],bins=bins)[0].astype(float)
        profile[feature]={'inner_edges':inner.tolist(),'proportions':(counts/counts.sum()).tolist()}
    return profile

def drift(reference,current):
    if len(current)==0: raise ValueError('Current batch must not be empty')
    matrix(current)
    result={}
    for feature, profile in reference.items():
        edges=np.r_[-np.inf,profile['inner_edges'],np.inf]
        expected=np.maximum(profile['proportions'],1e-6)
        observed=np.histogram(current[feature],bins=edges)[0].astype(float)
        observed=np.maximum(observed/observed.sum(),1e-6)
        result[feature]={'psi':float(np.sum((observed-expected)*np.log(observed/expected)))}
    return {'features':result,'note':'PSI is a distribution-shift heuristic, not proof of accuracy degradation; confirm with delayed labels.'}
