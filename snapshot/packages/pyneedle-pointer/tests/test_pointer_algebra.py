import pytest
from needle.pointer import L, SemanticPointer, PointerSet


# --- SemanticPointer (L) Tests ---

def test_pointer_core_behavior():
    """Tests basic path building, str, repr, and equality."""
    # Root
    assert str(L) == ""
    assert repr(L) == "<L: (root)>"

    # Attribute access
    p = L.auth.login.success
    assert isinstance(p, SemanticPointer)
    assert str(p) == "auth.login.success"
    assert repr(p) == "<L: 'auth.login.success'>"

    # Equality
    assert p == "auth.login.success"
    assert p == SemanticPointer("auth.login.success")
    assert p != L.auth.login.failure


def test_pointer_hashable():
    """Tests that pointers can be used as dict keys."""
    d = {L.user.name: "Alice", L.user.id: 123}
    assert d[L.user.name] == "Alice"
    assert d[SemanticPointer("user.id")] == 123


def test_pointer_dynamic_composition_operators():
    """Tests '+' and '/' operators for dynamic path building."""
    base = L.payment
    method = "credit_card"
    status_code = 200

    # Using +
    p1 = base + method + "success"
    assert p1 == "payment.credit_card.success"

    # Using /
    p2 = base / method / "error" / status_code
    assert p2 == "payment.credit_card.error.200"

    # Mixing operators
    p3 = L / "user" + "profile"
    assert p3 == "user.profile"


def test_pointer_multiplication_distributes_to_set():
    """Tests that '*' operator creates a PointerSet."""
    base = L.api.v1
    endpoints = {"users", "products"}

    result = base * endpoints
    assert isinstance(result, PointerSet)
    assert len(result) == 2
    assert L.api.v1.users in result
    assert L.api.v1.products in result
    assert L.api.v1.orders not in result


# --- PointerSet (Ls) Tests ---

def test_pointer_set_behaves_like_a_set():
    """Tests basic set-like behaviors."""
    s1 = PointerSet([L.a, L.b])
    s2 = PointerSet([L.b, L.c])

    assert len(s1) == 2
    assert L.a in s1
    assert L.c not in s1

    # Union
    union = s1 | s2
    assert union == {L.a, L.b, L.c}


def test_pointer_set_broadcasting_operators():
    """Tests that '/', '+' operators apply to all members."""
    base_set = L * {"user", "admin"}  # {L.user, L.admin}
    suffix = "profile"

    # Using /
    result_div = base_set / suffix
    assert isinstance(result_div, PointerSet)
    assert result_div == {L.user.profile, L.admin.profile}

    # Using +
    result_add = base_set + "dashboard"
    assert result_add == {L.user.dashboard, L.admin.dashboard}


def test_pointer_set_multiplication_cartesian_product():
    """Tests that '*' creates a cartesian product of semantics."""
    roles = L * {"admin", "guest"}
    actions = {"read", "write"}

    permissions = roles * actions

    expected = {
        L.admin.read, L.admin.write,
        L.guest.read, L.guest.write
    }
    assert permissions == expected


def test_pointer_getitem_for_non_identifiers():
    """Tests using __getitem__ for keys that are not valid Python identifiers."""
    p = L.errors[404]
    assert p == "errors.404"

    p2 = L.config["user-settings"]
    assert p2 == "config.user-settings"

    p3 = L.a[1]["b"]
    assert p3 == "a.1.b"


def test_pointer_set_chained_broadcasting():
    """Tests chaining multiple broadcast operations."""
    # This test now passes because __getitem__ is implemented.
    result = (L * {"http", "ftp"}) / "errors" * {"404", "500"}

    expected = {
        L.http.errors['404'], L.http.errors['500'],
        L.ftp.errors['404'], L.ftp.errors['500'],
    }

    assert result == expected