# `payments/language.py`

## Purpose

The **only** place an LLM is used: turn one user utterance into structured terms. The LLM never
changes the plan, never decides what happens next, and its output is never trusted as a fact
without a check or a human yes.

## What's in it

- **`load_model()`**: the pydantic-ai `Model` for the `[llm]` profile in `config.toml`
  (see [config.md](config.md)).
- **`Intent`** (`DocEnum`): `VIEW_PLAN`, `CHANGE_AMOUNT`, `CHANGE_DATE`, `CHANGE_CARD`.
- **`Reply`** (`DocEnum`): `YES`, `NO`.
- **`Interpretation`**: what one utterance says.

  | Field | Meaning |
  |---|---|
  | `intents` | every task asked for, in order |
  | `amount` | an amount stated, sign kept |
  | `payment_date` | a date stated, looked up in the calendar |
  | `card_id` | the id of a card on file the user wants to pay with |
  | `reply` | yes/no to a pending question |

- **`InterpretRequest`**: the utterance plus context (today, the assistant's last message, the
  current plan, the cards on file).
- **`LLMInterpreter.interpret(req)`**: calls cognition's `ModelPopulator` to fill an
  `Interpretation`; raises if the model fails.

## Design decisions

- **Docstrings are prompts.** cognition puts the `DocEnum` member descriptions and the pydantic
  field descriptions into the LLM prompt, so they're written as definitions ("change which card
  the payment is made with (the payment method)").
- **One structured call per utterance.** Multiple intents and details come back together, which
  is what lets the user say "move it to the 20th and make it $75" in one line.
- **Context the model needs, and nothing more:**
  - **A calendar** (45 days of `Mon Oct 26 = 2026-10-26`). Small models are unreliable at date
    math, so the model looks dates up instead of computing them.
  - **The last assistant message**, so "yes" or "make it 60" can be understood.
  - **The cards on file** by id, kind, network and last four digits, so "my Visa debit"
    resolves to an id. Full card numbers don't exist, and the account number is never sent.
- **The model returns ids, code resolves them.** `card_id` is looked up in `PaymentState.absorb`;
  an id that isn't on file is dropped, and the agent asks which card.
- **Raw values, checked later.** `amount` keeps its sign and precision ("exactly as said") so the
  policy, not the model, rejects `-40` or `10.005`.
- **Failure is an outcome, not a crash.** `interpret` raises; the `Interpret` operator catches
  it, sets `state.misunderstood`, and `AskToRephrase` handles it. Pending work survives.
- **Swappable in tests.** `Interpret` builds `LLMInterpreter()` in its constructor, so tests
  patch the class with a fake that returns canned interpretations.

## Extending

A new kind of request needs an `Intent` member (its description is the prompt), a field on
`Interpretation` if it carries a value, any context the model needs in `_context`, and the
mapping from field to detail in `PaymentState.absorb`.
