import io
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from basketbrief.web import create_app


@pytest.fixture
def team(tmp_path):
    app=create_app(tmp_path/'team.db',engine='local',background=False)
    with TestClient(app) as c:
        yield c,app


def account(c,name):
    r=c.post('/api/team/register',json={'name':name,'email':name+'@example.test','password':'Testing-password-123!'})
    assert r.status_code==201,r.text
    return r.json()


def project(c):
    r=c.post('/api/team/projects',json={'name':'Relief week one','base_currency':'USD'})
    assert r.status_code==201,r.text
    return r.json()['id']


def member(owner,app,pid,name,role):
    invite=owner.post(f'/api/team/projects/{pid}/invitations',json={'role':role}).json()['token']
    c=TestClient(app)
    account(c,name)
    r=c.post('/api/team/join',json={'token':invite})
    assert r.status_code==200,r.text
    return c,invite


def expense(c,pid,amount='60.00',currency='USD'):
    r=c.post(f'/api/team/projects/{pid}/expenses',json={'description':'Truck hire','amount':amount,'currency':currency})
    assert r.status_code==201,r.text
    return r.json()['id']


def test_individual_accounts_invites_and_revocation(team):
    c,app=team;account(c,'owner');pid=project(c)
    other,token=member(c,app,pid,'field','contributor')
    assert other.post('/api/team/join',json={'token':token}).status_code==409
    assert other.post(f'/api/team/projects/{pid}/invitations',json={'role':'coordinator'}).status_code==403
    uid=other.get('/api/team/me').json()['user']['id']
    assert c.delete(f'/api/team/projects/{pid}/members/{uid}').status_code==200
    assert other.get(f'/api/team/projects/{pid}').status_code==403


def test_notifications_are_recipient_scoped_and_persist(team):
    c,app=team;account(c,'owner');pid=project(c)
    field,_=member(c,app,pid,'field','contributor')
    peer,_=member(c,app,pid,'peer','contributor')
    donor,_=member(c,app,pid,'donor','donor')
    eid=expense(field,pid)
    state=c.get(f'/api/team/projects/{pid}').json()
    assert any(e['id']==eid for e in state['expenses'])
    notes=c.get('/api/team/notifications').json()['notifications']
    note=next(n for n in notes if n['kind']=='expense_added')
    assert not note['read_at']
    assert donor.get(f'/api/team/projects/{pid}').json()['expenses']==[]
    assert peer.get(f'/api/team/projects/{pid}').json()['expenses']==[]
    assert donor.post(f"/api/team/notifications/{note['id']}/read").status_code==404
    assert c.post(f"/api/team/notifications/{note['id']}/read").status_code==200
    assert next(n for n in c.get('/api/team/notifications').json()['notifications'] if n['id']==note['id'])['read_at']


def test_multiple_currencies_never_sum_without_reviewed_rate(team):
    c,app=team;account(c,'owner');pid=project(c)
    a=expense(c,pid,'100','USD');b=expense(c,pid,'80','EUR');d=expense(c,pid,'20','USD')
    for eid in [a,b,d]:
        assert c.post(f'/api/team/projects/{pid}/expenses/{eid}/review',json={'action':'accept','amount':'80' if eid==b else '100' if eid==a else '20','currency':'EUR' if eid==b else 'USD','note':'Compared with contributor statement; receipt missing','confirmed':True}).status_code==200
    s=c.get(f'/api/team/projects/{pid}').json()
    assert s['totals']['USD']['reported']=='120.00'
    assert s['totals']['EUR']['reported']=='80.00'
    assert s['base_total'] is None
    r=c.put(f'/api/team/projects/{pid}/expenses/{b}/fx',json={'rate':'1.10','date':'2026-09-14','source':'Finance recorded transaction rate','confirmed':True})
    assert r.status_code==200,r.text
    assert c.get(f'/api/team/projects/{pid}').json()['base_total']=='208.00'
    assert c.put(f'/api/team/projects/{pid}/expenses/{b}/fx',json={'rate':'0','date':'2026-09-14','source':'source','confirmed':True}).status_code==409


def test_snapshot_freshness_and_donor_visibility(team):
    c,app=team;account(c,'owner');pid=project(c)
    donor,_=member(c,app,pid,'donor','donor')
    eid=expense(c,pid)
    assert c.post(f'/api/team/projects/{pid}/reports').status_code==409
    c.post(f'/api/team/projects/{pid}/expenses/{eid}/review',json={'action':'accept','amount':'60','currency':'USD','note':'Reported only; no receipt','confirmed':True})
    draft=c.post(f'/api/team/projects/{pid}/reports').json()
    assert donor.get(f'/api/team/projects/{pid}').json()['reports']==[]
    assert c.post(f'/api/team/projects/{pid}/reports/{draft["id"]}/approve',json={'hash':draft['hash'],'acknowledge':True}).status_code==200
    original=donor.get(f'/api/team/projects/{pid}').json()['reports'][0]
    expense(c,pid,'30','EUR')
    assert c.post(f'/api/team/projects/{pid}/reports/{draft["id"]}/approve',json={'hash':draft['hash'],'acknowledge':True}).status_code==409
    assert donor.get(f'/api/team/projects/{pid}').json()['reports'][0]==original


def test_bank_image_cannot_be_accepted_as_receipt(team,monkeypatch):
    from basketbrief.documents import failure
    c,app=team;account(c,'owner');pid=project(c)
    monkeypatch.setattr('basketbrief.vision.read_receipt',lambda _:failure('Bank statement','bank_statement','unsupported'))
    b=io.BytesIO();Image.new('RGB',(20,20)).save(b,format='PNG')
    r=c.post(f'/api/team/projects/{pid}/upload',files={'file':('card.png',b.getvalue(),'image/png')})
    assert r.status_code==201,r.text
    eid=r.json()['id']
    assert c.post(f'/api/team/projects/{pid}/expenses/{eid}/review',json={'action':'accept','amount':'114.90','currency':'USD','note':'Tried accepting a bank statement','confirmed':True}).status_code==409


def test_no_mail_provider_or_mailbox_access_is_claimed(team):
    c,app=team;account(c,'owner')
    data=c.get('/api/team/me').json()
    assert data['mail']['configured'] is False
    assert data['mail']['mailbox_connected'] is False
    assert c.post('/api/team/email/verify').status_code==409


def test_csrf_and_sessions(team):
    c,app=team;account(c,'owner')
    assert c.post('/api/team/projects',json={'name':'Evil','base_currency':'USD'},headers={'Origin':'https://evil.example'}).status_code==403
    c.post('/api/team/logout')
    assert c.get('/api/team/me').status_code==403


def test_pdf_original_preview_privacy_and_duplicate(team,monkeypatch):
    import pypdfium2
    from basketbrief.documents import failure
    c,app=team;account(c,'owner');pid=project(c)
    monkeypatch.setattr('basketbrief.vision.read_receipt',lambda _:failure('Full PDF needs review'))
    doc=pypdfium2.PdfDocument.new();doc.new_page(300,300);doc.new_page(300,300)
    out=io.BytesIO();doc.save(out);doc.close();raw=out.getvalue()
    r=c.post(f'/api/team/projects/{pid}/upload',files={'file':('receipt.pdf',raw,'application/pdf')})
    assert r.status_code==201,r.text
    eid=r.json()['id'];base=f'/api/team/projects/{pid}/expenses/{eid}'
    assert c.get(base+'/image').content==raw
    assert c.get(base+'/preview').content.startswith(b'\x89PNG')
    duplicate=c.post(f'/api/team/projects/{pid}/upload',files={'file':('renamed.pdf',raw,'application/pdf')}).json()
    assert duplicate=={'id':eid,'duplicate':True}
    state=c.get(f'/api/team/projects/{pid}').json()['expenses'][0]
    assert state['reading']['pages']==2 and state['reading']['verification'] is False
    peer,_=member(c,app,pid,'peer','contributor')
    donor,_=member(c,app,pid,'donor','donor')
    for other in [peer,donor]:
        assert other.get(base+'/image').status_code==403
        assert other.get(base+'/preview').status_code==403


@pytest.mark.parametrize('provider',['gmail','outlook'])
def test_oauth_state_identity_replay_and_encryption(team,monkeypatch,provider):
    from urllib.parse import urlparse,parse_qs
    from basketbrief import team_mailbox as mailbox
    from basketbrief.store import Conflict
    c,app=team;account(c,'owner');uid=c.get('/api/team/me').json()['user']['id']
    for k,v in {f'BASKETBRIEF_{provider.upper()}_CLIENT_ID':'test-client',f'BASKETBRIEF_{provider.upper()}_CLIENT_SECRET':'test-secret','BASKETBRIEF_PUBLIC_URL':'https://example.test'}.items():monkeypatch.setenv(k,v)
    url=mailbox.oauth_start(app.state.team,uid,provider);args=parse_qs(urlparse(url).query);state=args['state'][0]
    assert args['code_challenge_method']==['S256']
    assert ('gmail.readonly' if provider=='gmail' else 'Mail.Read') in args['scope'][0]
    with pytest.raises(Conflict):mailbox.oauth_finish(app.state.team,'another-user',provider,state,'code')
    replies=iter([{'access_token':'private-access','refresh_token':'private-refresh','expires_in':3600},{'emailAddress':'owner@example.test','mail':'owner@example.test'}])
    monkeypatch.setattr(mailbox,'provider_json',lambda *a,**k:next(replies))
    mailbox.oauth_finish(app.state.team,uid,provider,state,'code')
    with app.state.team.db() as db:
        credential=db.execute('SELECT credential FROM team_mailboxes').fetchone()[0]
        assert 'private-access' not in credential and 'private-refresh' not in credential
    assert c.get('/api/team/me').json()['user']['verified']==1
    with pytest.raises(Conflict):mailbox.oauth_finish(app.state.team,uid,provider,state,'code')
    assert c.delete('/api/team/mail/'+provider).json()['provider_access_revoked'] is False
    with pytest.raises(Conflict):mailbox.load(app.state.team,uid,provider)


def test_mail_import_checks_membership_before_provider_access(team,monkeypatch):
    from basketbrief import team_mailbox as mailbox
    c,app=team;account(c,'owner');pid=project(c)
    donor,_=member(c,app,pid,'donor','donor')
    monkeypatch.setattr(mailbox,'attachments',lambda *a,**k:pytest.fail('Unauthorized import reached provider'))
    assert donor.post('/api/team/mail/gmail/import',json={'project':pid,'message_id':'123','attachment_id':'0'}).status_code==403


def test_agent_prepares_but_does_not_publish_or_invent_receipts(team):
    from basketbrief.team_agent import run_one,link
    c,app=team;account(c,'owner');pid=project(c)
    donor,_=member(c,app,pid,'donor','donor');expense(c,pid)
    run_one(app.state.team,'local')
    state=c.get(f'/api/team/projects/{pid}').json()
    assert state['expenses'][0]['status']=='accepted'
    assert state['expenses'][0]['supported']==0
    assert state['reports'][0]['status']=='draft'
    assert state['jobs'][0]['status']=='done'
    assert donor.get(f'/api/team/projects/{pid}').json()['reports']==[]
    other=project(c);foreign=expense(c,other)
    assert link(app.state.team,pid,foreign)=={'linked':False}


def test_agent_questions_uncertain_source_and_notifies_actual_owner(team,monkeypatch):
    from basketbrief.documents import failure
    from basketbrief.team_agent import run_one
    c,app=team;account(c,'owner');pid=project(c)
    field,_=member(c,app,pid,'field','contributor')
    monkeypatch.setattr('basketbrief.vision.read_receipt',lambda _:failure('unclear'))
    out=io.BytesIO();Image.new('RGB',(20,20)).save(out,format='PNG')
    field.post(f'/api/team/projects/{pid}/upload',files={'file':('unclear.png',out.getvalue(),'image/png')})
    run_one(app.state.team,'local')
    state=c.get(f'/api/team/projects/{pid}').json()
    assert state['expenses'][0]['status']=='needs_info' and not state['reports']
    assert any(n['kind']=='clarification_needed' for n in field.get('/api/team/notifications').json()['notifications'])


def test_concurrent_human_review_rejects_stale_form(team):
    c,app=team;account(c,'owner');pid=project(c);eid=expense(c,pid)
    stamp=c.get(f'/api/team/projects/{pid}').json()['expenses'][0]['updated']
    body={'action':'accept','amount':'60','currency':'USD','note':'No receipt; explicitly reported only','confirmed':True,'expected_updated':stamp}
    assert c.post(f'/api/team/projects/{pid}/expenses/{eid}/review',json=body).status_code==200
    body['amount']='600'
    assert c.post(f'/api/team/projects/{pid}/expenses/{eid}/review',json=body).status_code==409


def test_requested_receipt_completes_existing_expense_without_double_count(team,monkeypatch):
    from basketbrief.team_agent import run_one,clarify
    c,app=team;account(c,'owner');pid=project(c)
    field,_=member(c,app,pid,'field','contributor');peer,_=member(c,app,pid,'peer','contributor')
    eid=expense(field,pid)
    monkeypatch.setattr('basketbrief.vision.read_receipt',lambda _:dict(ok=True,verification=True,document_type='receipt',currency='USD',stated_total='65.00',status='extracted'))
    out=io.BytesIO();Image.new('RGB',(20,20)).save(out,format='PNG');raw=out.getvalue()
    url=f'/api/team/projects/{pid}/expenses/{eid}/upload'
    assert peer.post(url,files={'file':('receipt.png',raw,'image/png')}).status_code==403
    r=field.post(url,files={'file':('receipt.png',raw,'image/png')})
    assert r.status_code==200,r.text
    assert r.json()['id']==eid
    refused=clarify(app.state.team,pid,eid,'Please upload your receipt again.')
    assert refused['asked'] is False
    run_one(app.state.team,'local')
    state=c.get(f'/api/team/projects/{pid}').json()
    assert len(state['expenses'])==1
    assert state['totals']['USD']['reported']=='65.00'
    assert state['totals']['USD']['supported']=='65.00'
    assert state['reports'][0]['status']=='draft'
    other=expense(field,pid)
    assert field.post(f'/api/team/projects/{pid}/expenses/{other}/upload',files={'file':('same.png',raw,'image/png')}).status_code==409


def test_email_outbox_failure_is_not_delivery_and_revocation_cancels(team,monkeypatch):
    from basketbrief import team_mail
    c,app=team;account(c,'owner');pid=project(c)
    field,_=member(c,app,pid,'field','contributor')
    uid=field.get('/api/team/me').json()['user']['id']
    for k,v in {'BASKETBRIEF_SMTP_HOST':'test.invalid','BASKETBRIEF_MAIL_FROM':'app@example.test','BASKETBRIEF_PUBLIC_URL':'https://example.test'}.items():monkeypatch.setenv(k,v)
    with app.state.team.db() as db:db.execute('UPDATE team_users SET verified=1,email_notifications=1 WHERE id=?',(uid,))
    eid=expense(field,pid)
    c.post(f'/api/team/projects/{pid}/expenses/{eid}/review',json={'action':'needs_info','note':'Please upload the receipt','confirmed':False})
    def fail(*a,**k):raise OSError('Synthetic SMTP outage')
    monkeypatch.setattr(team_mail.smtplib,'SMTP',fail)
    team_mail.send_one(app.state.team)
    with app.state.team.db() as db:
        row=db.execute('SELECT status,attempts,error FROM team_mail_outbox WHERE user_id=?',(uid,)).fetchone()
        assert tuple(row)==('queued',1,'OSError')
    c.delete(f'/api/team/projects/{pid}/members/{uid}')
    with app.state.team.db() as db:assert db.execute('SELECT count(*) FROM team_mail_outbox WHERE user_id=? AND status IN (\'queued\',\'sending\')',(uid,)).fetchone()[0]==0
