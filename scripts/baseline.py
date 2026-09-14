"""Record interactions in a complete synthetic workflow; do not estimate human work.

The earlier 41→2 comparison was an asymmetric task model. It has been withdrawn.
This script executes both approvals, both contributor replies, and the correction,
then reads counts from the database. It measures no human time or productivity.
"""
import json
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from basketbrief.agent import local_process
from basketbrief.store import Store, Conflict


def measure():
    with tempfile.TemporaryDirectory(prefix='basketbrief-interactions-') as tmp:
        store=Store(Path(tmp)/'run.db');pid=store.create_project('local')['id']
        local_process(store,pid)
        question=next(q for q in store.state(pid,'coordinator')['questions'] if q['status']=='open')
        store.submit(pid,'finance','Transport receipt T-204. Total USD 60.00.','receipt',question['id'])
        local_process(store,pid)
        original=store.state(pid,'coordinator')['report']
        store.approve(pid,'coordinator',original['id'],original['hash']);store.deliver(pid)
        store.submit(pid,'field','Correction: 88 kits delivered, not 92.','correction');local_process(store,pid)
        stale_refused=False
        try:store.approve(pid,'coordinator',original['id'],original['hash'])
        except Conflict:stale_refused=True
        question=next(q for q in store.state(pid,'coordinator')['questions'] if q['status']=='open')
        store.submit(pid,'field','Storage recount confirmed: 12 kits returned.','correction',question['id']);local_process(store,pid)
        current=store.state(pid,'coordinator')['report']
        store.approve(pid,'coordinator',current['id'],current['hash']);store.deliver(pid)
        with store.db() as c:
            def count(table,where=''):
                return c.execute(f'SELECT count(*) FROM {table} WHERE project=? '+where,(pid,)).fetchone()[0]
            result={'mode':'scripted local-parser workflow; no AI or human timing',
                    'initial_sources':3,'total_evidence_sources':count('evidence'),
                    'questions_delivered':count('questions'),'contributor_replies':count('evidence','AND question_id IS NOT NULL'),
                    'coordinator_approvals':count('approvals'),'donor_inbox_deliveries':count('inbox',"AND kind='report'"),
                    'unresolved_questions':count('questions',"AND status='open'"),
                    'stale_approval_refused':stale_refused,'final_summary':current['payload']['summary'],
                    'approved_changes':current['payload']['changes'],
                    'limitation':'Counts recorded system interactions. Excludes human reading/review time. No manual comparator or time-saving claim.'}
        assert result['stale_approval_refused'] and result['unresolved_questions']==0
        assert result['final_summary']['returned']==12 and result['final_summary']['delivered']==88
        return result

if __name__=='__main__':
    print(json.dumps(measure(),indent=2))
