import pytest
import json
import os
from memory.memory_manager import _empty_memory, _truncate_value, _recursive_update, should_extract_memory_local, format_memory_for_prompt

def test_empty_memory():
    mem = _empty_memory()
    assert "identity" in mem
    assert "preferences" in mem
    assert isinstance(mem["identity"], dict)

def test_truncate_value():
    val = "A" * 500
    truncated = _truncate_value(val)
    assert len(truncated) <= 401
    assert truncated.endswith("…")

def test_recursive_update_new_field():
    target = {}
    updates = {"identity": {"name": {"value": "Sahil"}}}
    changed = _recursive_update(target, updates)
    assert changed == True
    assert target["identity"]["name"]["value"] == "Sahil"

def test_recursive_update_no_change():
    target = {"identity": {"name": {"value": "Sahil", "updated": "2024-01-01"}}}
    updates = {"identity": {"name": {"value": "Sahil"}}}
    changed = _recursive_update(target, updates)
    assert changed == False

def test_should_extract_memory_local():
    assert should_extract_memory_local("My name is Sahil") == True
    assert should_extract_memory_local("Mujhe music pasand hai") == True
    assert should_extract_memory_local("What is the weather?") == False

def test_format_memory_for_prompt():
    mem = {
        "identity": {"name": {"value": "Sahil"}},
        "preferences": {"food": {"value": "Pizza"}}
    }
    formatted = format_memory_for_prompt(mem)
    assert "Sahil" in formatted
    assert "Food: Pizza" in formatted
