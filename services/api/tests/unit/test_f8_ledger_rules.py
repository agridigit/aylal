"""T015 - G10: append-only correction rules shared by expenses, sales, harvests and stock movements: reverse = opposite amounts, original kept,
double reversal refused, replace = reversal + a linked new entry (R1-A7, R2-A5, R4-A7, FR-007)."""
import copy
import uuid

import pytest

ENTRIES = {
    "expense": {"id": uuid.uuid4(), "kind": "entry", "amount_cents": 12500, "category": "fuel"},
    "sale": {"id": uuid.uuid4(), "kind": "entry", "quantity_milli": 2500, "unit_price_cents": 1250, "total_cents": 3125, "buyer": "Ali"},
    "harvest": {"id": uuid.uuid4(), "kind": "entry", "quantity_milli": 40000, "unit": "kg"},
    "stock_movement": {"id": uuid.uuid4(), "kind": "purchase", "qty_milli": 10000, "unit_cost_cents": 200, "total_cost_cents": 2000},
}
SIGNED = {"expense": ["amount_cents"], "sale": ["quantity_milli", "total_cents"], "harvest": ["quantity_milli"], "stock_movement": ["qty_milli", "total_cost_cents"]}
UNSIGNED = {"expense": ["category"], "sale": ["unit_price_cents", "buyer"], "harvest": ["unit"], "stock_movement": ["unit_cost_cents"]}


@pytest.mark.parametrize("register", sorted(ENTRIES))
def test_given_an_entry_when_reversing_then_signed_amounts_are_opposite_and_the_original_is_untouched(register):
    from app.domain.ledger_rules import reverse_entry

    original = ENTRIES[register]
    before = copy.deepcopy(original)
    new_id = uuid.uuid4()
    rev = reverse_entry(register, original, new_id=new_id)
    assert original == before
    assert rev["id"] == new_id and rev["reverses_id"] == original["id"]
    if register != "stock_movement":
        assert rev["kind"] == "reversal"
    for f in SIGNED[register]:
        assert rev[f] == -original[f]
    for f in UNSIGNED[register]:
        assert rev[f] == original[f]


@pytest.mark.parametrize("register", sorted(ENTRIES))
def test_given_an_already_reversed_entry_when_reversing_again_then_it_is_refused(register):
    from app.domain.ledger_rules import AlreadyReversed, ensure_reversible

    entry = ENTRIES[register]
    ensure_reversible(entry, reversed_ids=set())
    with pytest.raises(AlreadyReversed):
        ensure_reversible(entry, reversed_ids={entry["id"]})


@pytest.mark.parametrize("register", sorted(ENTRIES))
def test_given_a_reversal_when_reversing_it_then_it_is_refused(register):
    from app.domain.ledger_rules import AlreadyReversed, ensure_reversible, reverse_entry

    rev = reverse_entry(register, ENTRIES[register], new_id=uuid.uuid4())
    with pytest.raises(AlreadyReversed):
        ensure_reversible(rev, reversed_ids=set())


def test_given_an_expense_when_replacing_it_then_a_reversal_and_a_linked_new_entry_are_produced():
    from app.domain.ledger_rules import replace_entry

    original = ENTRIES["expense"]
    rev_id, new_id = uuid.uuid4(), uuid.uuid4()
    reversal, new = replace_entry("expense", original, {"amount_cents": 9900, "category": "fuel"}, reversal_id=rev_id, new_id=new_id)
    assert reversal["amount_cents"] == -12500 and reversal["reverses_id"] == original["id"]
    assert new["id"] == new_id and new["replaces_id"] == original["id"] and new["amount_cents"] == 9900 and new["kind"] == "entry"
    assert reversal["amount_cents"] + original["amount_cents"] + new["amount_cents"] == 9900  # the net effect is the new amount


def test_given_a_replacement_when_the_new_values_are_not_positive_then_it_is_refused():
    from app.domain.ledger_rules import replace_entry

    with pytest.raises(ValueError):
        replace_entry("expense", ENTRIES["expense"], {"amount_cents": -1}, reversal_id=uuid.uuid4(), new_id=uuid.uuid4())


def test_given_the_registers_then_none_offers_an_update_or_delete_rule():
    import app.domain.ledger_rules as rules

    assert not [n for n in dir(rules) if n.startswith(("update_", "delete_", "remove_"))]
    assert callable(rules.reverse_entry)
