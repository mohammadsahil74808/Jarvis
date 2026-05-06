import pytest
from core.local_router import LocalRouter
import re

class MockJarvis:
    def __init__(self):
        self.ui = MockUI()
        self.spoken = []
    
    def speak(self, text):
        self.spoken.append(text)

class MockUI:
    def write_log(self, msg):
        pass
    def show_suggestion(self, msg):
        pass

@pytest.fixture
def router():
    return LocalRouter(MockJarvis())

def test_route_chrome(router):
    assert router.route("open chrome") == True

def test_route_notepad(router):
    assert router.route("open notepad") == True

def test_route_calculator(router):
    assert router.route("open calc") == True

def test_route_spotify(router):
    assert router.route("open spotify") == True

def test_route_vscode(router):
    assert router.route("open vscode") == True

def test_route_ip(router):
    assert router.route("what is my ip") == True

def test_route_time(router):
    assert router.route("what time is it") == True

def test_route_volume(router):
    assert router.route("volume up") == True

def test_route_invalid(router):
    assert router.route("this is not a command") == False

def test_sanitize(router):
    assert router._sanitize("hello; rm -rf /") == "hello rm -rf /"
