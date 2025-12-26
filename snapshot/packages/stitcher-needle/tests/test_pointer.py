from stitcher.needle import L, SemanticPointer

def test_root_pointer_is_empty():
    assert str(L) == ""

def test_attribute_access_builds_path():
    p = L.auth.login
    assert str(p) == "auth.login"
    assert isinstance(p, SemanticPointer)

def test_deep_nesting():
    p = L.a.b.c.d.e.f
    assert str(p) == "a.b.c.d.e.f"

def test_equality_with_string():
    assert L.user.name == "user.name"
    assert "user.name" == L.user.name

def test_equality_with_pointer():
    p1 = L.system.error
    p2 = SemanticPointer("system.error")
    assert p1 == p2

def test_representation():
    p = L.debug
    assert repr(p) == "<SemanticPointer: 'debug'>"

def test_hashability():
    # Pointers should be usable as dictionary keys
    d = {L.key: "value"}
    assert d["key"] == "value"
    assert d[L.key] == "value"