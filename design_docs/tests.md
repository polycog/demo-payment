# `tests/test_agent.py`

## Purpose

Exercise the whole decision process offline and deterministically: no LLM, no terminal, no real
date, no key-phrase prompt. Run with `uv run --group dev pytest`.

## The test harness

| Piece | Stands in for | How |
|---|---|---|
| `ScriptedConsole` | the user | an actuator named `console`: replies to `Listen` with the next scripted line (then `None`, so the user leaves); records every `Say` |
| `FakeInterpreter` | the LLM | maps `"utterance 0"`, `"utterance 1"`, … to canned `Interpretation`s (`None` → raise, like a failed model call); records what it was asked |
| `make_service()` | the payment system | a `BankPaymentService` with a fixed `TODAY` and an `authenticate` function that the test supplies |
| `interp(...)` | an LLM answer | builds an `Interpretation` (`YES` and `NO` are shortcuts) |

Two runners:

- **`converse(lines, turns)`** runs any typed lines and returns everything said, the final
  state, and the fake interpreter. Use it for verification and edge cases.
- **`chat(*turns)`** verifies with the account number first, runs one turn per interpretation,
  checks the greeting, verification reply and goodbye, and returns one bot message per turn
  plus the payment system. Most conversation tests use it.

The LLM is replaced by patching `payments.operators.LLMInterpreter`, the class `Interpret`
instantiates.

## What is covered

- **Policy data:** every term has rules, and every limit and placeholder resolves.
- **Verification:** any digit format is accepted; wrong then right works; the session ends
  after too many wrong tries; nothing reaches the LLM before verification.
- **Conversations:** view, multi-intent, details reused across turns, invalid amounts and
  dates, window edges, decline, revision, interruption by a view, unrelated replies, LLM
  failure.
- **Authentication:**
  - The mechanism is tested through the `proposals_need_authentication` fixture, which makes
    every proposal set the flag: failure, retry, decline after failure, once per session, only
    after a yes, revision.
  - The real rule: switching to a high-limit debit card needs it; a debit card at the
    threshold, a credit card over it and a credit card under it don't; failure keeps the card;
    revising to another card drops it.
- **Cards:** an unknown card makes the agent ask which; declining keeps the card; the backend
  rejects a card that isn't on file.
- **Tracing:** pink/blue styles; the sequence of chosen operators in a real session.
- **Data and backend:** immutability, a plan for the wrong account or card, loading
  `customer.json` (relative and fixed dates, invalid files), unique card ids, the backend's own
  policy check, changes without authentication.
- **Saving:** the `account_file` fixture copies `customer.json` to a temp folder. Amount and card
  changes are saved and keep `payment_in_days`; a date change is saved as a fixed date; a refused
  change writes nothing; a whole conversation saves its change and leaves no temp file.

## Conventions

- One test per WHEN/THEN path; names say the behaviour (`test_failed_authentication_keeps_card`).
- Assert on what the user sees (exact messages where the wording matters) and on the payment
  system's final plan, not on internal state, unless the state is the point.
- The tests' customer is defined in the test file, independent of `customer.json`, so editing
  demo data never breaks tests. One test checks the shipped `customer.json` loads.
