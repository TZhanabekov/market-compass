"""Unit tests for LLM parser helpers (no network calls)."""

from app.services.llm_parser import _extract_first_json_object, _validate_choice


def test_extract_first_json_object_direct() -> None:
    payload = _extract_first_json_object('{"match": {"sku_key": "a", "match_confidence": 0.9}}')
    assert isinstance(payload, dict)
    assert payload["match"]["sku_key"] == "a"


def test_extract_first_json_object_embedded() -> None:
    text = "some preface\n{ \"is_accessory\": false, \"is_bundle\": false, \"is_contract\": false, \"match\": {\"sku_key\": \"x\", \"match_confidence\": 0.5} }\ntrailing"
    payload = _extract_first_json_object(text)
    assert isinstance(payload, dict)
    assert payload["match"]["sku_key"] == "x"


def test_validate_choice_accepts_candidate() -> None:
    candidates = ["iphone-17-pro-256gb-black-new", "iphone-17-pro-512gb-black-new"]
    payload = {
        "is_accessory": False,
        "is_bundle": False,
        "is_contract": False,
        "match": {"sku_key": "iphone-17-pro-256gb-black-new", "match_confidence": 0.8, "reason": "ok"},
    }
    res = _validate_choice(payload, candidates)
    assert res is not None
    assert res.sku_key == "iphone-17-pro-256gb-black-new"


def test_validate_choice_rejects_non_candidate() -> None:
    candidates = ["a", "b"]
    payload = {
        "is_accessory": False,
        "is_bundle": False,
        "is_contract": False,
        "match": {"sku_key": "c", "match_confidence": 0.8},
    }
    assert _validate_choice(payload, candidates) is None

