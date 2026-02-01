import pytest
from backend.utils.jinja_renderer import render_template

def test_render_simple():
    text = "Hello {{ name }}!"
    ctx = {"name": "World"}
    assert render_template(text, ctx) == "Hello World!"

def test_render_missing_var():
    text = "Hello {{ name }}!"
    ctx = {}
    # Jinja2 by default returns empty string for missing vars
    assert render_template(text, ctx) == "Hello !"

def test_render_complex():
    text = "{% if show %}Shown{% else %}Hidden{% endif %}"
    assert render_template(text, {"show": True}) == "Shown"
    assert render_template(text, {"show": False}) == "Hidden"