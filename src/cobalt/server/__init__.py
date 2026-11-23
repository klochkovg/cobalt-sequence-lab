"""The cobalt REST API server (`cobalt-server`), built on the shared core (`cobalt.core`).

Needs the optional `server` dependencies (fastapi, uvicorn, pydantic). It must not import the
CLI (`cobalt.cli`): clients reach the server over HTTP only.
"""
