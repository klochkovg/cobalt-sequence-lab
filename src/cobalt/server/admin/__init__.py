"""Service commands of the cobalt server (`cobalt-admin`), for an admin on the server host.

They work on the server's files directly (found like `cobalt-server` finds them, see
`cobalt.server.config.resolve_config`), also while the server runs, e.g. over ssh or
`docker exec`. They don't need the optional `server` dependencies (fastapi, uvicorn).
"""
