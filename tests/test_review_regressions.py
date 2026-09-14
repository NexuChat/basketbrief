"""Cases discovered by independent review, outside the original scripted journey."""
import pytest
from basketbrief.store import Store, Conflict
from basketbrief.agent import local_process, record_unambiguous_question_replies
from basketbrief.grounding import field_values

@pytest.fixture
def project(tmp_path):
    s=Store(tmp_path/'review.db');p=s.create_project('local')['id']
    return s,p

@pytest.mark.parametrize('amount',['100','12','101'])
def test_receipt_quantity_unit_price_and_identifier_are_not_total(project,amount):
    s,p=project;e=next(e for e in s.pending(p) if 'SUPPLIES RECEIPT' in e['text'])
    with pytest.raises(Conflict):s.record_expense(p,e['id'],'supplies',amount,'USD',True)

@pytest.mark.parametrize('field,value',[('delivered',92),('loaded',88),('returned',88)])
def test_a_stated_number_must_belong_to_the_requested_field(project,field,value):
    s,p=project;e=s.submit(p,'field','Correction: 88 kits were delivered, not 92.','correction')['id']
    with pytest.raises(Conflict):s.record_distribution(p,e,**{field:value})

@pytest.mark.parametrize('text',[
 'We delivered 37 kits. Household count is unknown.',
 '37 kits delivered. Families will be counted tomorrow.',
 'We did not reach 37 households.',
])
def test_nearby_household_word_is_not_a_household_count(project,text):
    s,p=project;e=s.submit(p,'field',text)['id']
    with pytest.raises(Conflict):s.record_distribution(p,e,households=37)


def test_gap_does_not_invent_households_or_registration(project):
    s,p=project;local_process(s,p)
    e=s.submit(p,'field','Correction: 88 kits were delivered, not 92.','correction')['id']
    result=s.record_distribution(p,e,delivered=88)
    assert '4 kits' in result['note']
    assert '4 households' not in result['note'] and 'registered' not in result['note']
    assert 'not established' in result['note']


def test_additional_expense_cannot_silently_replace_an_existing_transaction(project):
    s,p=project;local_process(s,p)
    e=s.submit(p,'finance','Transport receipt T1. Total USD 60.00.','receipt')['id']
    s.record_expense(p,e,'transport','60','USD',True)
    e=s.submit(p,'finance','Additional separate transport trip. Receipt T2. Total USD 25.00.','receipt')['id']
    with pytest.raises(Conflict):s.record_expense(p,e,'transport','25','USD',True)
    assert s.state(p,'coordinator')['summary']['reported']=='1260.00'


def test_supplies_followup_is_deliverable_and_idempotent(project):
    s,p=project
    e=s.submit(p,'finance','Supplies cost: USD 140.00. Receipt missing.','expense_claim')['id']
    s.record_expense(p,e,'supplies','140','USD',False)
    assert s.ask(p,'supplies_receipt','finance','Please provide the supplies receipt.')['asked']
    assert not s.ask(p,'supplies_receipt','finance','Please provide it again.')['asked']


def test_review_issue_disappears_when_a_later_correction_resolves_gap(project):
    s,p=project;local_process(s,p)
    s.submit(p,'field','Correction: 88 kits delivered.','correction');local_process(s,p)
    s.submit(p,'field','Correction: 12 kits returned.','correction');local_process(s,p)
    assert not s.state(p,'coordinator')['report']['payload']['issues']


def test_closed_unavailable_question_is_not_an_unfollowed_gap(project):
    s,p=project;local_process(s,p);q=s.state(p,'coordinator')['questions'][0]
    e=s.submit(p,'finance','I cannot find this receipt.','message',q['id'])['id'];s.defer(p,e,'Receipt unavailable; kept unsupported.')
    assert not s.unfollowed_gaps(p)


def test_agent_follows_the_arithmetic_gap_until_field_clarification(project):
    s,p=project;local_process(s,p)
    q=s.state(p,'coordinator')['questions'][0]
    s.submit(p,'finance','Transport receipt. Total USD 60.00.','receipt',q['id']);local_process(s,p)
    r=s.state(p,'coordinator')['report'];s.approve(p,'coordinator',r['id'],r['hash']);s.deliver(p)
    s.submit(p,'field','Correction: 88 kits delivered.','correction');local_process(s,p)
    questions=[q for q in s.state(p,'coordinator')['questions'] if q['status']=='open']
    assert len(questions)==1 and questions[0]['recipient']=='field'
    assert '4' in questions[0]['text']
    local_process(s,p)
    assert len(s.state(p,'field')['inbox'])==1
    s.submit(p,'field','We checked storage again: 12 kits returned.','correction',questions[0]['id']);local_process(s,p)
    st=s.state(p,'coordinator');assert not [q for q in st['questions'] if q['status']=='open']
    assert not st['report']['payload']['issues']
    assert st['summary']['delivered']==88 and st['summary']['returned']==12
    changes=st['report']['payload']['changes'];assert changes['delivered']=={'before':92,'after':88}
    assert changes['returned']=={'before':8,'after':12}
    assert s.state(p,'donor_a')['inbox'][0]['body']['summary']['delivered']==92
    r=st['report'];s.approve(p,'coordinator',r['id'],r['hash']);s.deliver(p)
    received=s.state(p,'donor_a')['inbox'][0]['body'];assert received['changes']==changes
    assert received['amends']['version']==2


def test_a_different_receipt_is_not_assumed_to_be_the_same_transaction(project):
    s,p=project;local_process(s,p)
    s.submit(p,'finance','Transport receipt T1. Total USD 60.00.','receipt');local_process(s,p)
    e=s.submit(p,'finance','Transport receipt T2. Total USD 60.00.','receipt')['id']
    with pytest.raises(Conflict):s.record_expense(p,e,'transport','60','USD',True)


def test_a_previous_return_count_named_as_wrong_cannot_be_reused(project):
    s,p=project;e=s.submit(p,'field','Storage recount confirmed: 12 kits returned. The earlier count of 8 returned was incorrect.','correction')['id']
    with pytest.raises(Conflict):s.record_distribution(p,e,returned=8)


def test_retry_after_delivery_does_not_amend_a_report_with_itself(project):
    s,p=project;local_process(s,p)
    q=s.state(p,'coordinator')['questions'][0]
    s.submit(p,'finance','Transport receipt. Total USD 60.00.','receipt',q['id']);local_process(s,p)
    r=s.state(p,'coordinator')['report'];s.approve(p,'coordinator',r['id'],r['hash']);s.deliver(p)
    local_process(s,p)
    assert s.state(p,'coordinator')['report']['id']==r['id']


def test_labelled_field_count_is_grounded():
    assert field_values('Storage recount complete. Returned kits: 12.', 'returned') == {12}


def test_unambiguous_field_reply_is_recorded_before_the_model_runs(project):
    s,p=project;local_process(s,p)
    q=s.state(p,'coordinator')['questions'][0]
    s.submit(p,'finance','Transport receipt. Total USD 60.00.','receipt',q['id']);local_process(s,p)
    r=s.state(p,'coordinator')['report'];s.approve(p,'coordinator',r['id'],r['hash']);s.deliver(p)
    s.submit(p,'field','Correction: 88 kits delivered.','correction');local_process(s,p)
    q=next(q for q in s.state(p,'coordinator')['questions'] if q['status']=='open')
    eid=s.submit(p,'field','Storage recount complete. Returned kits: 12.','correction',q['id'])['id']

    assert record_unambiguous_question_replies(s,p) == [eid]
    state=s.state(p,'coordinator')
    assert state['summary']['returned']==12
    assert next(e for e in state['evidence'] if e['id']==eid)['status']=='accepted'


def test_ambiguous_field_reply_stays_pending_for_review(project):
    s,p=project;local_process(s,p)
    q=s.state(p,'coordinator')['questions'][0]
    s.submit(p,'finance','Transport receipt. Total USD 60.00.','receipt',q['id']);local_process(s,p)
    r=s.state(p,'coordinator')['report'];s.approve(p,'coordinator',r['id'],r['hash']);s.deliver(p)
    s.submit(p,'field','Correction: 88 kits delivered.','correction');local_process(s,p)
    q=next(q for q in s.state(p,'coordinator')['questions'] if q['status']=='open')
    s.submit(p,'field','Returned kits: 12, or possibly returned kits: 10.','correction',q['id'])

    assert record_unambiguous_question_replies(s,p) == []
    assert len(s.pending(p)) == 1
