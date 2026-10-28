# Payments assistant

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
![Python 3.13+](https://img.shields.io/badge/python-3.13%2B-blue.svg)
[![Built with cognition](https://img.shields.io/badge/cognition-inside-7b2fbe?labelColor=f3effa&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjIgMCAzNiAzNiIgZmlsbD0ibm9uZSI+PHBvbHlnb24gcG9pbnRzPSIyMCw0IDM0LjMsMTQuNCAyOC44LDMxLjYgMTEuMiwzMS42IDUuNywxNC40IiBzdHJva2U9IiM3YjJmYmUiIHN0cm9rZS13aWR0aD0iMi4yIi8+PGcgc3Ryb2tlPSIjYzQ3ZDIwIiBzdHJva2Utd2lkdGg9IjIiPjxsaW5lIHgxPSIyMCIgeTE9IjIwIiB4Mj0iMjAiIHkyPSI0Ii8+PGxpbmUgeDE9IjIwIiB5MT0iMjAiIHgyPSIzNC4zIiB5Mj0iMTQuNCIvPjxsaW5lIHgxPSIyMCIgeTE9IjIwIiB4Mj0iMjguOCIgeTI9IjMxLjYiLz48bGluZSB4MT0iMjAiIHkxPSIyMCIgeDI9IjExLjIiIHkyPSIzMS42Ii8+PGxpbmUgeDE9IjIwIiB5MT0iMjAiIHgyPSI1LjciIHkyPSIxNC40Ii8+PC9nPjxnIGZpbGw9IiM3YjJmYmUiPjxjaXJjbGUgY3g9IjIwIiBjeT0iNCIgcj0iMy4yIi8+PGNpcmNsZSBjeD0iMzQuMyIgY3k9IjE0LjQiIHI9IjMuMiIvPjxjaXJjbGUgY3g9IjI4LjgiIGN5PSIzMS42IiByPSIzLjIiLz48Y2lyY2xlIGN4PSIxMS4yIiBjeT0iMzEuNiIgcj0iMy4yIi8+PGNpcmNsZSBjeD0iNS43IiBjeT0iMTQuNCIgcj0iMy4yIi8+PC9nPjxjaXJjbGUgY3g9IjIwIiBjeT0iMjAiIHI9IjQuNiIgZmlsbD0iI2M0N2QyMCIvPjwvc3ZnPgo=)](https://github.com/polycog/cognition)
[![cognition on PyPI](https://img.shields.io/pypi/v/polycog-cognition?label=cognition%20on%20PyPI&color=c47d20&labelColor=f3effa&logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjIgMCAzNiAzNiIgZmlsbD0ibm9uZSI+PHBvbHlnb24gcG9pbnRzPSIyMCw0IDM0LjMsMTQuNCAyOC44LDMxLjYgMTEuMiwzMS42IDUuNywxNC40IiBzdHJva2U9IiM3YjJmYmUiIHN0cm9rZS13aWR0aD0iMi4yIi8+PGcgc3Ryb2tlPSIjYzQ3ZDIwIiBzdHJva2Utd2lkdGg9IjIiPjxsaW5lIHgxPSIyMCIgeTE9IjIwIiB4Mj0iMjAiIHkyPSI0Ii8+PGxpbmUgeDE9IjIwIiB5MT0iMjAiIHgyPSIzNC4zIiB5Mj0iMTQuNCIvPjxsaW5lIHgxPSIyMCIgeTE9IjIwIiB4Mj0iMjguOCIgeTI9IjMxLjYiLz48bGluZSB4MT0iMjAiIHkxPSIyMCIgeDI9IjExLjIiIHkyPSIzMS42Ii8+PGxpbmUgeDE9IjIwIiB5MT0iMjAiIHgyPSI1LjciIHkyPSIxNC40Ii8+PC9nPjxnIGZpbGw9IiM3YjJmYmUiPjxjaXJjbGUgY3g9IjIwIiBjeT0iNCIgcj0iMy4yIi8+PGNpcmNsZSBjeD0iMzQuMyIgY3k9IjE0LjQiIHI9IjMuMiIvPjxjaXJjbGUgY3g9IjI4LjgiIGN5PSIzMS42IiByPSIzLjIiLz48Y2lyY2xlIGN4PSIxMS4yIiBjeT0iMzEuNiIgcj0iMy4yIi8+PGNpcmNsZSBjeD0iNS43IiBjeT0iMTQuNCIgcj0iMy4yIi8+PC9nPjxjaXJjbGUgY3g9IjIwIiBjeT0iMjAiIHI9IjQuNiIgZmlsbD0iI2M0N2QyMCIvPjwvc3ZnPgo=)](https://pypi.org/project/polycog-cognition/)

## 1. Summary

A **neurosymbolic** payments assistant built with the [`cognition`](https://github.com/polycog/cognition) library. In a terminal conversation, it verifies the customer, shows their payment plan, and helps them change the amount, date or payment card, authenticating them with the method the bank requires. The agent's actions are computationally guaranteed never to violate the bank's policy.

### Contents

1. [Summary](#1-summary)
2. [Problem Statement](#2-problem-statement)
3. [Technical Solution and Demo](#3-technical-solution-and-demo)
4. [Install, Run, and Test](#4-install-run-and-test)
5. [License and Disclaimers](#5-license-and-disclaimers)

---

## 2. Problem Statement

Self-service banking tasks, such as reviewing a loan payment plan, moving a payment date or switching the payment card, usually mean navigating nested menus, decoding financial jargon and filling in rigid forms, and customers often give up and call support. An agent could let them simply ask, e.g. *"Can I move my upcoming payment to next Friday?"*, but only if it enforces the bank's policies absolutely: payment limits, scheduling rules, and [Strong Customer Authentication](https://en.wikipedia.org/wiki/Strong_customer_authentication) for high-risk changes, without adding friction to low-risk ones.

See [the full problem statement and opportunity](docs/usecase.md).

---

## 3. Technical Solution and Demo

Like a careful bank agent, the assistant follows the bank's procedures to the letter, while letting the customer speak naturally. An LLM only interprets what the customer types, turning it into structured proposals: the change they want, any amount, date or card, and their yes or no. Symbolic WHEN/THEN operators, written with `cognition`, decide everything else: they verify the customer, check each change against the payment policy, require extra authentication only when a change calls for it, and ask for a yes before acting through the APIs of a simulated bank payment service. With no LLM in these decisions, the same state always leads to the same action, and every step can be traced. See [the technical solution](docs/solution.md) for details.

**Demo:** [watch the assistant verify a customer and change their payment plan](https://drive.google.com/file/d/1-BZmGtRpowki8eMzQMdGZUuYepCaSUcr/view?usp=sharing)

---

## 4. Install, Run, and Test

### 4.1 Clone the repository

```bash
git clone https://github.com/polycog/demo-payment.git
cd demo-payment
```

### 4.2 Install the dependencies

`cognition` requires **Python 3.13 or later**. The project is managed with [uv](https://docs.astral.sh/uv/), which creates the environment and installs everything in [`pyproject.toml`](pyproject.toml):

```bash
uv sync
```

This installs:

- **`polycog-cognition`**, the `cognition` library, published on PyPI under that name;
- **`pydantic-ai-slim[openai]`**, which `cognition` builds on, with the OpenAI extra for the language model;
- **`rich`**, for the terminal console.

### 4.3 Choose a language model

All settings are in [`config.toml`](config.toml). Choose a profile by setting `use` under `[llm]`:

| Profile | Model | Needs |
|---|---|---|
| `local` (default) | `openai/gpt-oss-20b` | An OpenAI-compatible server at `http://localhost:1234/v1` (such as LM Studio) |
| `openai` | `gpt-4o` | `OPENAI_API_KEY` |

For the `openai` profile, export your key in the shell you run the assistant from, and keep it out of the repository:

```bash
export OPENAI_API_KEY="sk-..."
```

`[policy]` sets the payment limits and when extra authentication is needed. `customer_file` (default [`customer.json`](customer.json)) holds the customer, their cards and their plan.

### 4.4 Run the assistant

```bash
uv run python -m payments             # add --trace to see which operator runs each cycle
```

The assistant first asks you to confirm the account number in [`customer.json`](customer.json) (`4417-2290-0381`). Then view your plan, or change the amount, date or card, e.g. "move it to the 20th and make it $75". Each change is put to you as a yes/no question. Switching to a debit card with a limit over $5,000 also asks for a key phrase: `neurosymbolic`. Type `quit` to leave.

Confirmed changes are saved back to `customer.json`; to start over, run `git checkout customer.json`.

### 4.5 Run the tests

The test suite uses [pytest](https://docs.pytest.org/) and runs fully offline: it replaces the LLM with a fake and the customer with a scripted user, so it needs no API key and makes no paid calls.

```bash
uv run --group dev pytest
```

---

## 5. License and Disclaimers

This project is released under the [Apache License 2.0](LICENSE). Copyright © 2026 Polycog, Inc.

> **Disclaimer:** this project is a technical demonstration of neurosymbolic reasoning. It is not a production banking system, has not been reviewed for use with real accounts or payments, and is not financial advice. The customer in `customer.json` and the bank payment service are fictional.
