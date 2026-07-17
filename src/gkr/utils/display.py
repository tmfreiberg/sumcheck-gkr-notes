from __future__ import annotations

import getpass
import os
import shutil
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol, Sequence

from sympy.core.symbol import Symbol
from sympy.polys.domains.modularinteger import ModularInteger

from ._ansi import get_colors

# ----------------------------
# ANSI colors
# ----------------------------

_colors = get_colors()
RED = _colors.RED
GREEN = _colors.GREEN
YELLOW = _colors.YELLOW
PINK = _colors.PINK
BLUE = _colors.BLUE
PURPLE = _colors.PURPLE
RESET = _colors.RESET


def _stdin_is_tty() -> bool:
    """True when stdin is an interactive terminal (i.e. a human is typing)."""
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def _in_notebook() -> bool:
    try:
        from IPython import get_ipython
        ip = get_ipython()
        return ip is not None and ip.__class__.__name__ == "ZMQInteractiveShell"
    except Exception:
        return False


# ----------------------------
# Optional IPython helpers
# ----------------------------

ipy_display: Optional[Callable[..., Any]]
try:
    from IPython.display import display as _ipy_display

    ipy_display = _ipy_display
except Exception:
    ipy_display = None


def display(*args: Any) -> None:
    if ipy_display is not None:
        for arg in args:
            if arg is not None:
                ipy_display(arg)
    else:
        for arg in args:
            if arg is not None:
                print(arg)


ipy_clear_output: Optional[Callable[..., Any]]
try:
    from IPython.display import clear_output as _ipy_clear_output

    ipy_clear_output = _ipy_clear_output
except Exception:
    ipy_clear_output = None


def clear_output() -> None:
    if ipy_clear_output is not None:
        ipy_clear_output(wait=True)
        return

    # Fallback: clear terminal
    os.system("cls" if os.name == "nt" else "clear")


# widgets/HTML are optional; keep stable stubs
widgets = None
HTML: Callable[..., Any]


def _stub_html(*args: Any, **kwargs: Any) -> None:
    print("HTML display is not available.")


HTML = _stub_html


def set_widgets(enable: bool = True, disable: bool = False) -> None:
    global widgets, HTML

    if disable:
        widgets = None
        HTML = _stub_html
        return

    if not enable:
        return

    try:
        from IPython import get_ipython

        if get_ipython() is None:
            widgets = None
            HTML = _stub_html
            return

        import ipywidgets as _widgets
        from IPython.display import HTML as _HTML

        widgets = _widgets
        HTML = _HTML
    except Exception:
        widgets = None
        HTML = _stub_html


# ----------------------------
# Pretty-print helpers
# ----------------------------

def display_aligned(*strings: str, out: Optional[SupportsPrint] = None) -> None:
    """
    Print strings containing '=' aligned on the '=' sign.
    If no string contains '=', prints all strings as-is.

    If `out` is provided, uses `out.print(...)` instead of built-in print.
    """
    printer = out.print if out is not None else print

    parts = [s.split("=", 1) for s in strings if "=" in s]
    if not parts:
        for s in strings:
            printer(s)
        return

    max_left_length = max(len(part[0].strip()) for part in parts)
    for left, right in parts:
        printer(f"{left.strip():>{max_left_length}} = {right.strip()}")


def _stdout_is_tty() -> bool:
    """True when stdout is an interactive terminal (i.e. animation is safe)."""
    try:
        return sys.stdout is not None and sys.stdout.isatty()
    except Exception:
        return False


@contextmanager
def progress(message: str, *, out: Optional[SupportsPrint] = None,
             frames: str = "|/-\\", interval: float = 0.1):
    """Announce slow work, and show that something is happening.

    Two different things, deliberately kept apart:

    * the *message* is narration -- it tells the reader why nothing is
      appearing -- so it goes through `out` like any other line, and appears
      in captured transcripts;
    * the *spinner* is presentation. It writes to sys.stdout directly, and only
      when stdout is an interactive terminal and we are not in a notebook. A
      piped run (the golden harness) or a notebook cell therefore sees exactly
      the message and nothing else, which keeps transcripts byte-deterministic
      -- an elapsed time or an animation frame in a golden would be a lie.
    """
    printer = out.print if out is not None else print
    printer(message)

    animate = _stdout_is_tty() and not _in_notebook()
    stop = threading.Event()
    thread: Optional[threading.Thread] = None

    if animate:
        def spin() -> None:
            i = 0
            while not stop.wait(interval):
                sys.stdout.write(f"\r  {frames[i % len(frames)]} ")
                sys.stdout.flush()
                i += 1

        thread = threading.Thread(target=spin, daemon=True)
        thread.start()

    started = time.perf_counter()
    try:
        yield
    finally:
        stop.set()
        if thread is not None:
            thread.join(timeout=1.0)
            elapsed = time.perf_counter() - started
            sys.stdout.write(f"\r  done in {elapsed:.1f}s\n")
            sys.stdout.flush()


def print_header(title: str, level: int = 1, *, out: Optional[SupportsPrint] = None) -> None:
    """
    Print a section header, using TerminalOutput paging if provided.

    level=1: big header with "=" bars above and below
    level=2: smaller header (no bars)
    """
    printer = out.print if out is not None else print

    # Conservative line budgeting so we don't split headers across pages.
    min_lines = 5 if level == 1 else 2

    # Paging is a TerminalOutput capability, not part of SupportsPrint: a
    # SecretsChannel (a file) has no pages to break. Use it when present.
    new_section = getattr(out, "new_section", None)
    atomic = getattr(out, "atomic", None)
    if new_section is not None and atomic is not None:
        new_section(min_lines=min_lines)
        with atomic():
            print_header_block(title, level=level, printer=printer)
    else:
        print_header_block(title, level=level, printer=printer)


def print_header_block(
    title: str,
    *,
    level: int = 1,
    printer: Callable[[str], None] = print,
) -> None:
    t = title.strip()
    if level == 1:
        line = "=" * len(t)
        printer(f"\n{PINK}{line}{RESET}")
        printer(f"{PINK}{t.upper()}{RESET}")
        printer(f"{PINK}{line}{RESET}")
    else:
        printer(f"\n{PINK}{t.upper()}{RESET}")

def stringify(*args: Sequence[Any]) -> str:
    """
    Converts one or more coordinate tuples/lists into a single formatted string.

    Args:
        *args (Union[Tuple[Symbol], List[Union[str, int, ModularInteger]]]):
              Variable-length arguments of tuples or lists containing coordinates.

    Returns:
        str: A comma-separated string representation of the coordinates.
    """
    result = []
    for coordinates in args:
        if not coordinates:
            continue  # Skip empty coordinates

        # Convert each element in the coordinates to a string
        coordinates_str = [to_string(c) for c in coordinates]

        # Join the coordinates with commas and add to the result list
        result.append(', '.join(coordinates_str))

    # Return all coordinate strings joined with commas
    return ', '.join(result)


def to_string(c):
    """
    Converts an element to its string representation based on its type.

    Args:
        c: The element to be converted (could be a Symbol, ModularInteger, or int).

    Returns:
        str: The string representation of the element.
    """
    if isinstance(c, Symbol):
        return str(c)  # Convert Symbol to string
    if isinstance(c, ModularInteger):
        return str(int(c))  # Convert ModularInteger to int, then to string
    if isinstance(c, int):
        return str(c)  # Convert int to string
    return str(c)  # Default conversion to string


# ----------------------------
# TerminalOutput
# ----------------------------

class SupportsPrint(Protocol):
    """Anywhere narration can be written.

    The renderers need exactly one thing: print(). TerminalOutput satisfies this,
    and so does gkr.protocol.secrets.SecretsChannel, which is deliberately NOT a
    TerminalOutput -- it has no pager, strips colour, and its input() raises,
    because prompts belong to the keyboard, not to a file being tailed.
    """

    def print(self, text: str = "") -> None: ...


@dataclass
class TerminalOutput:
    enable_paging: bool = True
    margin_lines: int = 2
    prompt: str = ":"          # could also use "-- More --"
    reset_on_prompt: bool = True

    _line_count: int = 0

    @contextmanager
    def atomic(self):
        old = self.enable_paging
        self.enable_paging = False
        try:
            yield
        finally:
            self.enable_paging = old

    def _term_height(self) -> int:
        return shutil.get_terminal_size(fallback=(80, 24)).lines

    def _paging_enabled_now(self) -> bool:
        if not self.enable_paging:
            return False
        if _in_notebook():
            return False
        if not sys.stdout.isatty() or not sys.stdin.isatty():
            return False
        return True

    def _available_lines(self) -> int:
        height = self._term_height()
        return max(1, height - self.margin_lines)

    def _needs_page_for(self, additional_lines: int) -> bool:
        if not self._paging_enabled_now():
            return False
        return (self._line_count + additional_lines) >= self._available_lines()

    def _pause(self) -> None:
        # Ensure we don't inherit a previous color
        if self.reset_on_prompt:
            sys.stdout.write(RESET)

        sys.stdout.write(self.prompt)
        sys.stdout.flush()

        # Read a single keypress (Windows + Unix-ish, best effort)
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.getch()
            else:
                import termios
                import tty
                fd = sys.stdin.fileno()
                old = termios.tcgetattr(fd)
                try:
                    tty.setraw(fd)
                    sys.stdin.read(1)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            # Fallback: require Enter
            try:
                sys.stdin.readline()
            except Exception:
                pass

        # Erase the prompt (":"), keep cursor clean
        sys.stdout.write("\r \r")
        sys.stdout.flush()
        self._line_count = 0

    def _count_lines(self, s: str) -> int:
        if s == "":
            return 0
        n_newlines = s.count("\n")
        if n_newlines == 0:
            return 1
        return n_newlines if s.endswith("\n") else (n_newlines + 1)

    def print(self, *args: Any, sep: str = " ", end: str = "\n") -> None:
        s = sep.join(str(a) for a in args) + end

        needed_lines = self._count_lines(s)
        if self._needs_page_for(needed_lines):
            self._pause()

        sys.stdout.write(s)
        sys.stdout.flush()

        self._line_count += needed_lines

        if self._paging_enabled_now() and self._line_count >= self._available_lines():
            self._pause()

    def input(self, prompt: str = "", *, hidden: bool = False) -> str:
        # Ensure prompt is visible and not stuck behind a pager prompt
        if self.reset_on_prompt:
            sys.stdout.write(RESET)
            sys.stdout.flush()

        # `hidden` exists to stop a live audience from reading what the user types
        # (presentation/secret mode). That only makes sense when a human is typing
        # at a terminal. When stdin is piped (tests, scripted demos), there is
        # nothing to hide, and getpass is actively harmful:
        #
        #   - On Windows, getpass reads via msvcrt.getwch() from the CONSOLE and
        #     writes the prompt via msvcrt.putwch(), so it ignores piped stdin
        #     entirely: the prompt escapes capture and the script desynchronizes.
        #   - On Unix, getpass falls back to reading stdin but emits a
        #     GetPassWarning and keeps the prompt out of stdout.
        #
        # A notebook is the third case, and the one that matters most here: stdin
        # is not a tty (ipykernel replaces it), but getpass IS the right call --
        # IPython renders it as a masked box that reads from the frontend. Testing
        # only for a tty meant secret mode silently echoed the prover's polynomial
        # into the notebook, which is precisely what it exists to prevent.
        #
        # So: hide for a real terminal or a notebook; otherwise plain input().
        if hidden and (_stdin_is_tty() or _in_notebook()):
            return getpass.getpass(prompt)
        return input(prompt)

    def new_section(self, min_lines: int = 1) -> None:
        if min_lines < 1:
            min_lines = 1
        if self._needs_page_for(min_lines):
            self._pause()

    def flush(self) -> None:
        try:
            sys.stdout.flush()
        except Exception:
            pass
        self._line_count = 0


out = TerminalOutput(enable_paging=True)