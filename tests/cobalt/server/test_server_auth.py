import asyncio

import pytest
from fastapi import HTTPException

from cobalt.server.auth import API_KEYS_ENV, ApiKeyAuth, build_auth, parse_api_keys
from cobalt.server.users import UserStore


def test_parse_api_keys():
    assert parse_api_keys(" k1, k2 ,,k3, ") == ["k1", "k2", "k3"]
    assert parse_api_keys("") == []


def test_api_key_auth_requires_keys():
    with pytest.raises(ValueError):
        ApiKeyAuth([])


def test_build_auth_none():
    assert build_auth("none", environ={}) is None


def test_build_auth_api_key_without_keys():
    with pytest.raises(ValueError, match=API_KEYS_ENV):
        build_auth("api-key", environ={API_KEYS_ENV: " , "})


def test_build_auth_api_key():
    assert isinstance(build_auth("api-key", environ={API_KEYS_ENV: "k1,k2"}), ApiKeyAuth)


def test_build_auth_unknown_mode():
    with pytest.raises(ValueError, match="unknown auth mode"):
        build_auth("jwt", environ={})


def run_auth(auth, key):
    return asyncio.run(auth(key))


def test_api_key_auth_user_key():
    users = UserStore()
    user, key = users.add_user("ada")
    assert run_auth(ApiKeyAuth(users=users), key) == user


def test_api_key_auth_shared_key_has_no_user():
    users = UserStore()
    users.add_user("ada")
    assert run_auth(ApiKeyAuth(["k1"], users), "k1") is None


@pytest.mark.parametrize("key", [None, "", "wrong"])
def test_api_key_auth_rejects(key):
    users = UserStore()
    users.add_user("ada")
    with pytest.raises(HTTPException) as info:
        run_auth(ApiKeyAuth(["k1"], users), key)
    assert info.value.status_code == 401


def test_build_auth_api_key_with_user_keys_only():
    users = UserStore()
    users.add_user("ada")
    assert isinstance(build_auth("api-key", users, environ={}), ApiKeyAuth)


def test_build_auth_api_key_without_any_keys():
    with pytest.raises(ValueError, match=f"users add NAME.*{API_KEYS_ENV}"):
        build_auth("api-key", UserStore(), environ={})
