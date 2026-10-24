"""
Console I/O as a cognition Actuator, plus operator tracing.

Operators never print or read directly; they send a request to the
``console`` actuator (``io.o.console(...)``) and get the answer back.
That keeps the decision process testable with a scripted console.

With tracing on, each decision cycle prints the operator chosen (pink if
it calls the LLM, blue otherwise) and the others that applied.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from cognition import OPERATOR_SELF_PARAM, Actuator, NamedObject
from rich.console import Console
from rich.text import Text

LLM_STYLE = "hot_pink"
"""trace color of operators that call the LLM"""

OPERATOR_STYLE = "dodger_blue1"
"""trace color of all other operators"""

# === requests the console actuator understands


@dataclass(frozen=True)
class Say:
    """Show the agent's message"""

    text: str


@dataclass(frozen=True)
class Listen:
    """Wait for the user's next line; the reply is the line, or ``None`` if they left (Ctrl-C / Ctrl-D)"""


type ConsoleRequest = Say | Listen
type ConsoleReply = str | None


class RichConsole(Actuator[ConsoleRequest, ConsoleReply]):
    """Terminal console"""

    def __init__(self, out: Console | None = None) -> None:
        self.out = out or Console(highlight=False)

    @property
    def name(self) -> str:
        return "console"

    def actuate(self, param: ConsoleRequest) -> ConsoleReply:
        match param:
            case Say(text=t):
                for line in t.splitlines():
                    self.out.print(Text.assemble(("bot> ", "bold cyan"), line))
                return None
            case Listen():
                try:
                    return self.out.input("\n[bold green]you>[/] ").strip()
                except (EOFError, KeyboardInterrupt):
                    return None

    # === tracing

    def show_step(self, chosen: str, proposed: list[str], uses_llm: bool) -> None:
        """Show one decision cycle: the operator chosen, and the others that applied"""

        self.out.print(trace_line(chosen, proposed, uses_llm))

    def trace(self, agent: Any) -> Callable[[], None]:
        """
        Show each decision cycle of the agent from now on

        :param agent: the payments cogent
        :return: stops tracing
        """

        console = self

        class _Trace(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                if "apply phase started" not in record.getMessage():
                    return
                dp = agent.dp
                proposed = dp._potential_actions  # noqa: SLF001
                action = next(a for a in proposed if str(a) == dp.chosen_action)  # chosen_action is its str()
                chosen = cast(NamedObject, action).params[OPERATOR_SELF_PARAM]
                others = [str(a).split("[")[0] for a in proposed if a is not action]
                console.show_step(chosen.name, others, getattr(chosen, "uses_llm", False))

        log = logging.getLogger("cognition.decision.core")
        handler, level = _Trace(), log.level
        log.setLevel(logging.INFO)
        log.addHandler(handler)

        def stop() -> None:
            log.removeHandler(handler)
            log.setLevel(level)

        return stop


def trace_line(chosen: str, others: list[str], uses_llm: bool) -> Text:
    """``  ⟳ interpret (llm)   also: wrap_up``, colored by whether the chosen operator calls the LLM"""

    line = Text(f"  ⟳ {chosen}" + (" (llm)" if uses_llm else ""), style=LLM_STYLE if uses_llm else OPERATOR_STYLE)
    if others:
        line.append(f"   also: {', '.join(others)}", style="dim")
    return line
