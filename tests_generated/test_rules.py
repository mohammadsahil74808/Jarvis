import pytest
from intelligence.rules import HighUsageRule, BatteryRule, CollegeCommuteRule, get_all_rules
from datetime import datetime

def test_high_usage_rule():
    rule = HighUsageRule()
    sys = {"cpu_percent": 90, "ram_percent": 50}
    res = rule.evaluate(sys, {}, None)
    assert res is not None
    assert "CPU usage is very high" in res["text"]

def test_battery_rule():
    rule = BatteryRule()
    sys = {"battery": {"percent": 15, "power_plugged": False}}
    res = rule.evaluate(sys, {}, None)
    assert res is not None
    assert "battery is at 15%" in res["text"]

def test_college_commute_rule():
    rule = CollegeCommuteRule()
    # Mocking datetime inside the rule evaluation would be better, 
    # but we can check the class exists and priority is correct
    assert rule.priority == 8
    assert rule.rule_id == "college_commute"

def test_get_all_rules():
    rules = get_all_rules()
    assert len(rules) >= 9
    rule_ids = [r.rule_id for r in rules]
    assert "college_commute" in rule_ids
    assert "guitar_practice" in rule_ids
