# `payments/console.py`

## Purpose

All user interaction, as a cognition **actuator** named `console`, plus the `--trace` view of
the decision process.

## Requests, not prints

Operators never call `print` or `input`. They send a request to `io.o.console(...)`:

| Request | Reply |
|---|---|
| `Say(text)` | `None`; shows the agent's message |
| `Listen()` | the user's line, stripped, or `None` if they left (Ctrl-C / Ctrl-D) |

`RichConsole.actuate` matches on the request type. Why:

- **Testable.** Tests swap in a `ScriptedConsole` that plays the user's lines and records what
  the agent says. The decision process can't tell the difference.
- **One place for presentation.** Prompts, colors and line prefixes (`bot>`, `you>`) live here,
  not in operators.
- **Small vocabulary.** Two request types are enough because operators batch what they say in
  `state.outbox` and speak once per turn.

## Tracing

`console.trace(agent)` shows each decision cycle and returns a function that stops tracing:

```
  ⟳ interpret (llm)   also: wrap_up      ← pink: the operator calls the LLM
  ⟳ show_plan                            ← blue: every other operator
```

- The chosen operator is pink (`LLM_STYLE = "hot_pink"`) if its class sets `uses_llm = True`,
  otherwise blue (`OPERATOR_STYLE = "dodger_blue1"`). The other operators that applied follow,
  dimmed.
- **The color is declared by the operator**, not by a list of names here, so a new LLM-calling
  operator shows in pink by setting one class attribute.
- The hook listens to cognition's decision-process log ("apply phase started") and finds the
  chosen action among those proposed, because `dp.chosen_action` is the action's name, not the
  action. It reads the private `_potential_actions`, the one place this code depends on
  cognition internals.
- `trace` returns a stop function so tests (and anything else) can remove the logging handler
  and restore the log level instead of leaking it.
- `trace_line()` builds the styled line as a pure function, so tests can check text and color
  without a terminal.

The `RichConsole(out=...)` parameter lets tests pass a recording `rich.console.Console`.
