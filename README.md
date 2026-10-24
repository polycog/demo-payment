# Payment-plan assistant

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)
[![Built with cognition](https://img.shields.io/badge/cognition-inside-7b2fbe?labelColor=f3effa&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjIgMCAzNiAzNiIgZmlsbD0ibm9uZSI+PHBvbHlnb24gcG9pbnRzPSIyMCw0IDM0LjMsMTQuNCAyOC44LDMxLjYgMTEuMiwzMS42IDUuNywxNC40IiBzdHJva2U9IiM3YjJmYmUiIHN0cm9rZS13aWR0aD0iMi4yIi8+PGcgc3Ryb2tlPSIjYzQ3ZDIwIiBzdHJva2Utd2lkdGg9IjIiPjxsaW5lIHgxPSIyMCIgeTE9IjIwIiB4Mj0iMjAiIHkyPSI0Ii8+PGxpbmUgeDE9IjIwIiB5MT0iMjAiIHgyPSIzNC4zIiB5Mj0iMTQuNCIvPjxsaW5lIHgxPSIyMCIgeTE9IjIwIiB4Mj0iMjguOCIgeTI9IjMxLjYiLz48bGluZSB4MT0iMjAiIHkxPSIyMCIgeDI9IjExLjIiIHkyPSIzMS42Ii8+PGxpbmUgeDE9IjIwIiB5MT0iMjAiIHgyPSI1LjciIHkyPSIxNC40Ii8+PC9nPjxnIGZpbGw9IiM3YjJmYmUiPjxjaXJjbGUgY3g9IjIwIiBjeT0iNCIgcj0iMy4yIi8+PGNpcmNsZSBjeD0iMzQuMyIgY3k9IjE0LjQiIHI9IjMuMiIvPjxjaXJjbGUgY3g9IjI4LjgiIGN5PSIzMS42IiByPSIzLjIiLz48Y2lyY2xlIGN4PSIxMS4yIiBjeT0iMzEuNiIgcj0iMy4yIi8+PGNpcmNsZSBjeD0iNS43IiBjeT0iMTQuNCIgcj0iMy4yIi8+PC9nPjxjaXJjbGUgY3g9IjIwIiBjeT0iMjAiIHI9IjQuNiIgZmlsbD0iI2M0N2QyMCIvPjwvc3ZnPgo=)](https://github.com/polycog/cognition)
[![cognition on PyPI](https://img.shields.io/pypi/v/polycog-cognition?label=cognition%20on%20PyPI&color=c47d20&labelColor=f3effa&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjIgMCAzNiAzNiIgZmlsbD0ibm9uZSI+PHBvbHlnb24gcG9pbnRzPSIyMCw0IDM0LjMsMTQuNCAyOC44LDMxLjYgMTEuMiwzMS42IDUuNywxNC40IiBzdHJva2U9IiM3YjJmYmUiIHN0cm9rZS13aWR0aD0iMi4yIi8+PGcgc3Ryb2tlPSIjYzQ3ZDIwIiBzdHJva2Utd2lkdGg9IjIiPjxsaW5lIHgxPSIyMCIgeTE9IjIwIiB4Mj0iMjAiIHkyPSI0Ii8+PGxpbmUgeDE9IjIwIiB5MT0iMjAiIHgyPSIzNC4zIiB5Mj0iMTQuNCIvPjxsaW5lIHgxPSIyMCIgeTE9IjIwIiB4Mj0iMjguOCIgeTI9IjMxLjYiLz48bGluZSB4MT0iMjAiIHkxPSIyMCIgeDI9IjExLjIiIHkyPSIzMS42Ii8+PGxpbmUgeDE9IjIwIiB5MT0iMjAiIHgyPSI1LjciIHkyPSIxNC40Ii8+PC9nPjxnIGZpbGw9IiM3YjJmYmUiPjxjaXJjbGUgY3g9IjIwIiBjeT0iNCIgcj0iMy4yIi8+PGNpcmNsZSBjeD0iMzQuMyIgY3k9IjE0LjQiIHI9IjMuMiIvPjxjaXJjbGUgY3g9IjI4LjgiIGN5PSIzMS42IiByPSIzLjIiLz48Y2lyY2xlIGN4PSIxMS4yIiBjeT0iMzEuNiIgcj0iMy4yIi8+PGNpcmNsZSBjeD0iNS43IiBjeT0iMTQuNCIgcj0iMy4yIi8+PC9nPjxjaXJjbGUgY3g9IjIwIiBjeT0iMjAiIHI9IjQuNiIgZmlsbD0iI2M0N2QyMCIvPjwvc3ZnPgo=)](https://pypi.org/project/polycog-cognition/)

**A neurosymbolic agent: the LLM interprets, and the symbolic system decides.**

A demo for [`polycog-cognition`](https://github.com/polycog/cognition): an interactive CLI that
shows a customer's payment plan and changes its amount, date or payment card. It never changes the
plan without an explicit yes.

**Demo:** [watch the assistant verify a customer and change their payment plan](https://drive.google.com/file/d/1-BZmGtRpowki8eMzQMdGZUuYepCaSUcr/view?usp=sharing)

> [!TIP]
> **The design is documented in [`design_docs/`](design_docs)**, one doc per file: what it does,
> why it is built that way, and how to extend it. Start with
> [the decision process](design_docs/operators.md).

## Quick start

**Requirements:** Python 3.13+, [uv](https://docs.astral.sh/uv/), and either a local
OpenAI-compatible server or an OpenAI API key.

```bash
uv sync
uv run python -m payments             # add --trace to see which operator runs each cycle
uv run --group dev pytest             # offline tests: fake LLM, scripted user, no API key needed
```

The assistant first asks you to confirm the account number in [`customer.json`](customer.json)
(`4417-2290-0381`). Then view your plan, or change the amount, date or card, e.g. "move it to the
20th and make it $75". Each change is put to you as a yes/no question. Switching to a debit card
with a limit over $5,000 also asks for a key phrase: `neurosymbolic`. Type `quit` to leave.

## Configuration

All settings are in [`config.toml`](config.toml).

**Language model.** Choose a profile by setting `use` under `[llm]`:

| Profile | Model | Needs |
|---|---|---|
| `local` (default) | `openai/gpt-oss-20b` | An OpenAI-compatible server at `http://localhost:1234/v1` (such as LM Studio) |
| `openai` | `gpt-4o` | `OPENAI_API_KEY` |

**Policy.** `[policy]` sets the payment limits and when extra authentication is needed.

**Customer.** `customer_file` (default [`customer.json`](customer.json)) holds the customer, their
cards and their plan. Confirmed changes are saved back to it; to start over, run
`git checkout customer.json`.

## How it works

![The decision process, operator by operator, with tool calls to the bank payment service](design_docs/figures/decision-process.svg)

- **Neural:** the LLM reads each line into structured terms: the tasks asked for, any amount, date
  or card, and a yes/no.
- **Symbolic:** WHEN/THEN operators, ranked by priority, decide everything else: verifying the
  user, checking each change against the policy, and asking for a yes before anything changes.
- **Tools:** a simulated bank payment service owns `customer.json`. Its APIs are the cogent's
  tools, called by operators to look up the customer, change the plan and authenticate the user.

For the details, see [`design_docs/`](design_docs):
[operators](design_docs/operators.md) ·
[state](design_docs/state.md) ·
[bank payment service](design_docs/bank_payment_service.md) ·
[language](design_docs/language.md) ·
[policy](design_docs/policy.md) ·
[console](design_docs/console.md) ·
[agent](design_docs/agent.md) ·
[config](design_docs/config.md) ·
[main](design_docs/main.md) ·
[tests](design_docs/tests.md)

## License

Released under the [Apache License 2.0](LICENSE). Copyright (c) 2026 Polycog Inc.
