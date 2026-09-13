import pytest
from fastapi.testclient import TestClient
from basketbrief.web import create_app
from basketbrief.agent import process_project


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / 'api.db', engine='local', background=False)
    with TestClient(app) as c:
        yield c


def create(client):
    r = client.post('/api/projects')
    assert r.status_code == 201
    p = r.json()
    process_project(client.app.state.store, p['id'], 'local')
    return p


def headers(p, role='coordinator'):
    return {'Authorization': 'Bearer ' + p['tokens'][role]}


def test_index_and_health_are_available(client):
    assert client.get('/healthz').json()['ok']
    r = client.get('/')
    assert r.status_code == 200
    assert 'BasketBrief' in r.text
    assert 'Content-Security-Policy' in r.headers


def test_api_requires_project_scoped_capability(client):
    p = create(client); other = create(client)
    assert client.get(f"/api/projects/{p['id']}").status_code == 403
    assert client.get(f"/api/projects/{p['id']}", headers=headers(other)).status_code == 403
    assert client.get(f"/api/projects/{p['id']}", headers=headers(p)).status_code == 200


def test_api_full_journey_and_report_export(client):
    p=create(client); base=f"/api/projects/{p['id']}"
    state=client.get(base,headers=headers(p)).json()
    q=state['questions'][0]
    res=client.post(base+'/evidence',headers=headers(p,'finance'),json={'text':'Transport receipt. Total USD 60.00.','kind':'receipt','question_id':q['id']})
    assert res.status_code==201
    process_project(client.app.state.store,p['id'],'local')
    r=client.get(base,headers=headers(p)).json()['report']
    assert client.post(base+'/approve',headers=headers(p,'finance'),json={'report_id':r['id'],'hash':r['hash']}).status_code==403
    assert client.post(base+'/approve',headers=headers(p),json={'report_id':r['id'],'hash':r['hash']}).status_code==200
    inbox=client.get(base,headers=headers(p,'donor_a')).json()['inbox']
    assert len(inbox)==1
    exported=client.get(base+f"/reports/{r['id']}",headers=headers(p,'donor_a'))
    assert exported.status_code==200 and '1,260.00' in exported.text
    assert 'field-reported' in exported.text


def test_donor_cannot_submit_or_access_a_draft(client):
    p=create(client); base=f"/api/projects/{p['id']}"
    r=client.get(base,headers=headers(p)).json()['report']
    assert client.post(base+'/evidence',headers=headers(p,'donor_a'),json={'text':'Hello'}).status_code==403
    assert client.get(base+f"/reports/{r['id']}",headers=headers(p,'donor_a')).status_code==403


def test_invalid_evidence_and_hash_are_rejected(client):
    p=create(client); base=f"/api/projects/{p['id']}"
    assert client.post(base+'/evidence',headers=headers(p,'field'),json={'text':''}).status_code==422
    r=client.get(base,headers=headers(p)).json()['report']
    assert client.post(base+'/approve',headers=headers(p),json={'report_id':r['id'],'hash':'bad'}).status_code==409


def test_image_upload_validates_content_and_permission(client):
    p=create(client); base=f"/api/projects/{p['id']}"
    assert client.post(base+'/upload',headers=headers(p,'donor_a'),files={'file':('a.png',b'bad','image/png')}).status_code==403
    assert client.post(base+'/upload',headers=headers(p,'finance'),files={'file':('a.png',b'bad','image/png')}).status_code==422

