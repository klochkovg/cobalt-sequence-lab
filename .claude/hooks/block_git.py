#!/usr/bin/env python3
"""PreToolUse hook: block every git operation performed by Claude Code.

Version control is handled by the human only. This hook rejects:

- any Bash command that invokes `git` (or `git-*` helpers) or the GitHub CLI `gh`,
  anywhere in the command line: pipelines, `&&` chains, subshells, `bash -c "..."`, etc.;
- any Write/Edit/MultiEdit/NotebookEdit that targets a path inside a `.git` directory.

The check is intentionally conservative: a command that merely mentions `git` as a
separate word (e.g. `echo git`) is blocked too. Exit code 2 tells Claude Code to block
the tool call and show stderr to the model.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import PurePath

# `git`, `/usr/bin/git`, `git-lfs`, `gh` as a standalone word (delimited by shell syntax or quotes).
_DELIM = r"""\s;&|()`'"<>{}="""
GIT_RE = re.compile(rf"(?:^|[{_DELIM}])(?:[\w.~/-]*/)?(git(?:-[\w-]+)?|gh)(?=$|[{_DELIM}])")

FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}


def block(reason: str) -> None:
    print(f"Blocked by .claude/hooks/block_git.py: {reason}", file=sys.stderr)
    print("Git operations are reserved for the user. Ask them to run it instead.", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        block("could not parse hook input")

    tool = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}

    if tool == "Bash":
        command = tool_input.get("command", "")
        match = GIT_RE.search(command)
        if match:
            block(f"command invokes '{match.group(1)}': {command!r}")

    elif tool in FILE_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if ".git" in PurePath(path).parts:
            block(f"{tool} targets the git directory: {path}")

    sys.exit(0)


if __name__ == "__main__":
    main()
