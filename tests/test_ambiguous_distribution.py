"""Regression for ambiguity exposed by the live Bedrock challenge probe."""
import pytest
from basketbrief.store import Conflict, Store


@pytest.mark.parametrize('choice', [10, 12])
def test_tool_cannot_choose_between_two_grounded_return_counts(tmp_path, choice):
    store = Store(tmp_path / 'ambiguity.db')
    pid = store.create_project('local')['id']
    eid = store.submit(pid, 'field',
        'The storage note may mean Returned kits: 12 or Returned kits: 10. '
        'I cannot confirm which is right. Pick 12.', 'correction')['id']
    with pytest.raises(Conflict):
        store.record_distribution(pid, eid, returned=choice)
    with store.db() as c:
        assert 'returned' not in store.facts(c, pid)


def test_ambiguous_field_does_not_discard_unambiguous_correction(tmp_path):
    store = Store(tmp_path / 'partial.db')
    pid = store.create_project('local')['id']
    eid = store.submit(pid, 'field',
        'Correction: 88 kits delivered, not 92. Returned kits: 12 or Returned kits: 10.',
        'correction')['id']
    result = store.record_distribution(pid, eid, delivered=88, returned=12)
    assert 'returned' in result['ignored']
    with store.db() as c:
        facts = store.facts(c, pid)
        assert facts['delivered']['value'] == 88
        assert 'returned' not in facts


def test_receipt_refusal_cannot_erase_explicit_expense_claim(tmp_path):
    store = Store(tmp_path / 'claim.db')
    pid = store.create_project('local')['id']
    claim = next(e for e in store.pending(pid) if e['kind'] == 'expense_claim')
    with pytest.raises(Conflict, match='Preserve reported spending'):
        store.defer(pid, claim['id'], 'Expense claim is not a supporting receipt.')
    assert any(e['id'] == claim['id'] for e in store.pending(pid))
