from elementzero.evidence.hashing import canonical_json, sha256_hex


def test_content_hash_is_stable():
    a = {"b": 1.0, "a": [2, 3]}
    b = {"a": [2, 3], "b": 1.0}
    assert canonical_json(a) == canonical_json(b)
    assert sha256_hex(a) == sha256_hex(b)
    assert "1.000000000000e+00" in canonical_json({"x": 1.0})
