import json
from decimal import Decimal
from pathlib import Path
import pytest
from basketbrief.documents import validate_reading, read_document

VERIFIED = {'matches': True, 'issues': []}

def receipt():
    return {'document_type':'receipt', 'complete':True, 'currency':'USD',
            'stated_total':'60', 'items_complete':True,
            'items':[{'name':'Transport','qty':None,'unit_price':None,'line_total':'60'}]}

class Fake:
    def __init__(self, responses): self.responses=iter(responses); self.calls=0
    def converse(self, **kwargs):
        self.calls+=1
        return {'stopReason':'end_turn','output':{'message':{'content':[{'text':json.dumps(next(self.responses))}]}}}

@pytest.mark.parametrize('kind',['bank_statement','transfer_receipt','transfer_batch','other'])
def test_non_purchase_rejected_before_extracting_or_summing(kind):
    c=Fake([{'document_type':kind}]);r=read_document(b'x',c,'test')
    assert c.calls==1 and not r['ok'] and not r['eligible_for_expense']
    assert r['status']=='unsupported' and r['items']==[] and r['summed_total'] is None

def test_card_cannot_bypass_gate():
    d=receipt();d.update(document_type='bank_statement',stated_total='114.90')
    r=validate_reading(d,VERIFIED)
    assert not r['ok'] and r['stated_total'] is None and r['summed_total'] is None

@pytest.mark.parametrize('value',['NaN','Infinity','-12',True,'12,34','1.2345'])
def test_invalid_amount_fails_closed(value):
    d=receipt();d['stated_total']=value
    assert not validate_reading(d,VERIFIED)['eligible_for_expense']

def test_utility_due_only_not_meter_sum():
    d=receipt();d.update(document_type='utility_bill',stated_total='11620',currency=None)
    d['items']=[{'qty':'150','unit_price':'108','line_total':'42'}]
    r=validate_reading(d,VERIFIED)
    assert r['stated_total']==Decimal('11620.00')
    assert r['summed_total'] is None and r['items']==[] and not r['eligible_for_expense']

def test_cropped_total_is_not_computed():
    d=receipt();d.update(document_type='utility_bill',complete=False,stated_total=None)
    r=validate_reading(d,VERIFIED)
    assert not r['ok'] and r['stated_total'] is None

def test_equal_fabricated_totals_do_not_override_verification():
    r=validate_reading(receipt(),{'matches':False,'issues':['Not in image']})
    assert not r['ok'] and not r['eligible_for_expense'] and r['status']=='needs_review'

def test_missing_verification_or_invoice_does_not_authorize_expense():
    assert not validate_reading(receipt())['eligible_for_expense']
    d=receipt();d['document_type']='invoice'
    assert not validate_reading(d,VERIFIED)['eligible_for_expense']

def test_missing_currency_or_total_blocks_expense():
    d=receipt();d['currency']='ريال'
    assert not validate_reading(d,VERIFIED)['eligible_for_expense']
    d=receipt();d['stated_total']=None
    assert not validate_reading(d,VERIFIED)['eligible_for_expense']

def test_partial_items_no_arithmetic_claim():
    d=receipt();d['items_complete']=False;r=validate_reading(d,VERIFIED)
    assert r['summed_total'] is None and not r['eligible_for_expense']

def test_summary_row_is_not_added_as_an_item():
    d=receipt();d['items'].append({'name':'Total','line_total':'60'})
    r=validate_reading(d,VERIFIED)
    assert r['stated_total']==Decimal('60') and r['summed_total'] is None
    assert not r['eligible_for_expense']

def test_mismatch_preserves_total_blocks_expense():
    d=receipt();d['stated_total']='70';r=validate_reading(d,VERIFIED)
    assert r['stated_total']==Decimal('70.00') and r['mismatch'] and not r['eligible_for_expense']

def test_pipeline_classifies_extracts_checks_pixels():
    r=read_document(b'x',Fake([{'document_type':'receipt'},receipt(),VERIFIED]),'test')
    assert r['eligible_for_expense'] and r['schema_version']==2

@pytest.mark.parametrize('payload',[[],None,'nonsense',{'document_type':'made_up'}])
def test_bad_shapes_fail_closed(payload):
    assert not read_document(b'x',Fake([payload]),'test')['ok']

def test_runtime_uses_same_reader():
    root=Path(__file__).resolve().parents[1]
    assert (root/'basketbrief/documents.py').read_bytes()==(root/'runtime/app/receiptreader/document_reader.py').read_bytes()

def test_rejected_image_remains_visible_and_cannot_be_recorded(tmp_path):
    from basketbrief.store import Store, Conflict
    s=Store(tmp_path/'db');p=s.create_project('local');pid=p['id']
    from basketbrief.agent import process_project
    process_project(s,pid,'local')
    eid=s.submit(pid,'finance','Receipt image attached.','receipt',attachment='card.png')['id']
    (tmp_path/'card.png').write_bytes(b'image')
    s.transcribe_attachment(pid,eid,tmp_path,reader=lambda _:validate_reading({'document_type':'bank_statement'}))
    s.prepare(pid)
    state=s.state(pid,'coordinator')
    assert any(e['id']==eid and e['status']=='review' for e in state['evidence'])
    assert any(i['id']==eid for i in state['report']['payload']['issues'])
    with pytest.raises(Conflict):s.record_expense(pid,eid,'transport','114.90','USD',True)

def test_image_guard_pins_the_amount_even_if_transcript_is_replaced(tmp_path):
    from basketbrief.store import Store, Conflict
    s=Store(tmp_path/'db');pid=s.create_project('local')['id']
    eid=s.submit(pid,'finance','Receipt image attached.','receipt',attachment='receipt.png')['id']
    (tmp_path/'receipt.png').write_bytes(b'image')
    s.transcribe_attachment(pid,eid,tmp_path,reader=lambda _:validate_reading(receipt(),VERIFIED))
    with s.db() as c:c.execute('UPDATE evidence SET text=? WHERE id=?',('Total USD 114.90',eid))
    with pytest.raises(Conflict):s.record_expense(pid,eid,'transport','114.90','USD',True)
