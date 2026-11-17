"""SQLite review queue, transactionally recorded audit trail, SIMULATION ONLY."""
import sqlite3
import json
from datetime import datetime, timezone
ALLOWED_ACTIONS={'collect_evidence','escalate','simulate_isolate_host','simulate_disable_account'}
class ReviewQueue:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.execute('CREATE TABLE IF NOT EXISTS reviews (id TEXT PRIMARY KEY, evidence TEXT NOT NULL, status TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS audit (seq INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, event_id TEXT, actor TEXT, action TEXT, details TEXT)')
        self.db.commit()
    def _audit(self,event_id,actor,action,details):
        self.db.execute('INSERT INTO audit(time,event_id,actor,action,details) VALUES(?,?,?,?,?)',(datetime.now(timezone.utc).isoformat(),event_id,actor,action,json.dumps(details)))
    def submit(self,event):
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO reviews VALUES(?,?,?)',(event['event_id'],json.dumps(event),'pending'))
    def decide(self,event_id,actor,approved,action,reason):
        if not isinstance(approved,bool): raise ValueError('approved must be a boolean')
        if not actor.strip() or not reason.strip(): raise ValueError('Analyst name and reason required')
        if action not in ALLOWED_ACTIONS: raise ValueError('Unsupported action')
        with self.db:
            status='approved' if approved else 'rejected'
            changed=self.db.execute('UPDATE reviews SET status=? WHERE id=? AND status=?',(status,event_id,'pending')).rowcount
            if changed!=1: raise ValueError('Review missing or already decided')
            self._audit(event_id,actor,status,{'requested_action':action,'reason':reason,'executed':False,'simulation':True})
        return {'status':status,'executed':False,'simulation':True}
    def list(self):
        return [dict(event_id=r[0],evidence=json.loads(r[1]),status=r[2]) for r in self.db.execute('SELECT * FROM reviews')]
    def audit(self):
        return [dict(seq=r[0],time=r[1],event_id=r[2],actor=r[3],action=r[4],details=json.loads(r[5])) for r in self.db.execute('SELECT * FROM audit ORDER BY seq')]
