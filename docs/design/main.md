# `payments/__main__.py`

## Purpose

The command-line entry point: `uv run python -m payments [--trace]`.

## What it does

1. Parses `--trace`.
2. Creates a `RichConsole` and prints a banner naming the language model in use.
3. Creates the bank payment service with `BankPaymentService.from_file()`, which reads
   `customer.json` and saves confirmed changes back to it. The agent queries the service for the
   customer when the session starts.
4. Builds the agent (`build_agent`), turns on tracing if asked (`console.trace(agent)`), and runs
   it until the user leaves.

## Design decisions

- **Thin by design.** No logic, only wiring of real implementations: the terminal console, the
  JSON-backed payment system, today's date, the configured LLM. Tests wire fakes into the same
  `build_agent`.
- **All settings come from `config.toml` and `customer.json`.** The only flag is `--trace`, which
  changes what is shown, not how the agent behaves.
- **Startup fails fast.** An invalid `customer.json` or `config.toml` raises before the
  conversation starts.
