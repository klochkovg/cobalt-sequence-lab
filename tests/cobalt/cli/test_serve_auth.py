import pytest

from cobalt.cli.serve_auth import API_KEYS_ENV, ApiKeyAuth, build_auth, parse_api_keys


def test_parse_api_keys():
    assert parse_api_keys(" k1, k2 ,,k3, ") == ["k1", "k2", "k3"]
    assert parse_api_keys("") == []


def test_api_key_auth_requires_keys():
    with pytest.raises(ValueError):
        ApiKeyAuth([])


def test_build_auth_none():
    assert build_auth("none", {}) is None


def test_build_auth_api_key_without_keys():
    with pytest.raises(ValueError, match=API_KEYS_ENV):
        build_auth("api-key", {API_KEYS_ENV: " , "})


def test_build_auth_api_key():
    assert isinstance(build_auth("api-key", {API_KEYS_ENV: "k1,k2"}), ApiKeyAuth)


def test_build_auth_unknown_mode():
    with pytest.raises(ValueError, match="unknown auth mode"):
        build_auth("jwt", {})
