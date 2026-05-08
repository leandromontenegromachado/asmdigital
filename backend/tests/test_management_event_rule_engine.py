from types import SimpleNamespace

from app.services.management_event_rule_engine import ManagementEventRuleEngine


def test_rule_engine_matches_simple_and_nested_conditions():
    engine = ManagementEventRuleEngine(db=None)
    event = SimpleNamespace(
        severity="high",
        status="pending",
        event_type="ROUTINE_FAILED",
        payload_json={"project": "asm-dem", "days_late": 8},
    )

    assert engine._matches(event, {"severity": {"eq": "high"}})
    assert engine._matches(event, {"field": "payload_json.days_late", "op": "gte", "value": 5})
    assert engine._matches(
        event,
        {
            "all": [
                {"field": "event_type", "op": "contains", "value": "FAILED"},
                {"field": "payload_json.project", "op": "eq", "value": "asm-dem"},
            ]
        },
    )
    assert not engine._matches(event, {"status": {"eq": "processed"}})


def test_rule_engine_normalizes_single_and_multiple_actions():
    engine = ManagementEventRuleEngine(db=None)

    assert engine._normalize_actions({"type": "mark_processed"}) == [{"type": "mark_processed"}]
    assert engine._normalize_actions({"actions": [{"type": "ignore"}, {"type": "notify_responsible"}]}) == [
        {"type": "ignore"},
        {"type": "notify_responsible"},
    ]
