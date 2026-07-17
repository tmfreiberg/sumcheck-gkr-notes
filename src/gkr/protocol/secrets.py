"""
The prover's private channel, for live presentations.

The use case: the presenter plays prover, the audience plays verifier, and both
look at the same screen. The prover is entitled to their own secrets -- the
true H, the mid-run cheat advice (which depends on challenges the audience just
called out, so it cannot be precomputed) -- but the shared screen must not show
them. One output stream cannot serve both, so the secrets go to a file, and the
presenter watches it on a second device:

    sum_check(secrets_to="prover.txt")          # then, elsewhere:
    tail -f prover.txt                          #   or Get-Content -Wait on Windows

`SecretsChannel` is a minimal TerminalOutput look-alike (print/input/flush)
whose print appends to the file, unbuffered, so `tail -f` sees each line as it
is emitted. Its `input` raises: nothing should ever prompt on this channel --
prompts belong to the keyboard, which is the shared screen. ANSI colour is
stripped, since the file may be watched by tools that do not render it.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Union

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


class SecretsChannel:
    """A file-backed output channel for PROVER_PRIVATE events."""

    def __init__(self, path: Union[str, Path]):
        self.path = Path(path)
        # line-buffered append; created eagerly so `tail -f` can attach at once
        self._fh = open(self.path, "a", encoding="utf-8", buffering=1)
        self._fh.write("=== prover's private channel ===\n")

    def print(self, text: str = "") -> None:
        self._fh.write(_ANSI.sub("", str(text)) + "\n")

    def input(self, prompt: str = "", *, hidden: bool = False) -> str:
        raise RuntimeError(
            "the secrets channel is write-only: prompts belong to the shared screen"
        )

    def flush(self) -> None:
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()