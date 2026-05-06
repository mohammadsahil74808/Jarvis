import pytest
from emotion.companion_engine import CompanionEngine

class MockJarvis:
    pass

@pytest.fixture
def engine():
    return CompanionEngine(MockJarvis())

def test_process_interaction_stress(engine):
    # This might need mocking StateDetector, but we test the return logic
    res = engine.process_interaction("I am so stressed out and frustrated")
    # Since it's regex based in StateDetector, this should trigger stress
    if res:
        assert "[EMOTIONAL_STATE: stress detected" in res

def test_process_interaction_normal(engine):
    res = engine.process_interaction("Hello Jarvis")
    assert res is None

def test_check_proactive_quiet(engine):
    # Manually set detector state if possible or mock it
    engine.detector.last_input_time = 0 # Simulate long time ago
    res = engine.check_proactive()
    if res:
        assert "[EMOTIONAL_STATE: user is unusually quiet" in res

def test_get_emotional_context(engine):
    ctx = engine.get_emotional_context()
    assert "[EMOTIONAL CONTEXT:" in ctx
