from needle.pointer import L, SemanticPointer, PointerSet


# --- SemanticPointer (L) Tests ---


def test_pointer_core_behavior():
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
    d = {L.user.name: "Alice", L.user.id: 123}
    assert d[L.user.name] == "Alice"
    assert d[SemanticPointer("user.id")] == 123


def test_pointer_dynamic_composition_operators():
    base = L.payment
    method = "credit_card"
    status_code = 200

    # Using +
    p1 = base + method + "success"
    assert p1 == "payment.credit_card.success"

    # Using /
    p2 = base / method / "error" / str(status_code)
    assert p2 == "payment.credit_card.error.200"

    # Mixing operators
    p3 = L / "user" + "profile"
    assert p3 == "user.profile"

    # Using __radd__
    p4 = "prefix" + L.auth.login
    assert p4 == "prefix.auth.login"

    # Using __radd__ with integer/non-string (tests str() fallback)
    p5 = 404 + L.error.code
    assert p5 == "404.error.code"

    # Edge case: Empty prefix
    p6 = "" + L.error
    assert p6 == "error"


def test_pointer_multiplication_distributes_to_set():
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
    s1 = PointerSet([L.a, L.b])
    s2 = PointerSet([L.b, L.c])

    assert len(s1) == 2
    assert L.a in s1
    assert L.c not in s1

    # Union
    union = s1 | s2
    assert union == {L.a, L.b, L.c}


def test_pointer_set_broadcasting_operators():
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
    roles = L * {"admin", "guest"}
    actions = {"read", "write"}

    permissions = roles * actions

    expected = {L.admin.read, L.admin.write, L.guest.read, L.guest.write}
    assert permissions == expected


def test_pointer_getitem_for_non_identifiers():
    p = L.errors[404]
    assert p == "errors.404"

    p2 = L.config["user-settings"]
    assert p2 == "config.user-settings"

    p3 = L.a[1]["b"]
    assert p3 == "a.1.b"


def test_pointer_set_chained_broadcasting():
    # This test now passes because __getitem__ is implemented.
    result = (L * {"http", "ftp"}) / "errors" * {"404", "500"}

    expected = {
        L.http.errors["404"],
        L.http.errors["500"],
        L.ftp.errors["404"],
        L.ftp.errors["500"],
    }

    assert result == expected


def test_pointer_multiplication_is_flexible_and_chainable():
    # 1. Chaining with strings and sets
    result1 = L.api * {"v1", "v2"} * "users"
    expected1 = {L.api.v1.users, L.api.v2.users}
    assert result1 == expected1

    # 2. Chaining with another pointer
    base_set = L * {"admin", "guest"}
    suffix = L.permissions
    result2 = base_set * suffix
    expected2 = {L.admin.permissions, L.guest.permissions}
    assert result2 == expected2

    # 3. Chaining a set multiplication with a pointer resolves the bug
    result3 = L.api * {"users", "products"} * L.errors
    expected3 = {L.api.users.errors, L.api.products.errors}
    assert result3 == expected3

    # 4. Using non-string, non-pointer objects (fallback to str)
    result4 = L.status * 200
    expected4 = {L.status["200"]}
    assert result4 == expected4

    # 5. PointerSet with non-string, non-pointer objects
    result5 = (L * {"http", "ftp"}) * 404
    expected5 = {L.http["404"], L.ftp["404"]}
    assert result5 == expected5
