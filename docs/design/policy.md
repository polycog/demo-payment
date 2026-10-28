# `payments/policy.py`

## Purpose

The payment rules, written as data, plus the settings that parameterize them. Nothing about the
policy is hard-coded anywhere else.

## What's in it

- **`PolicySettings`** (from `[policy]` in `config.toml`): `max_amount`, `date_window_days`,
  `max_verification_attempts`, `authenticate_debit_limit_over`.
  - `limits(today)` resolves each named `Limit` to a value as of today.
  - `message_values(today)` fills the `{placeholders}` in rule messages.
- **`Term`**: the plan terms a user can change, named as on `PaymentPlan` (`amount`,
  `payment_date`, `card_id`).
- **`Limit`**: named values rules compare against (`ZERO`, `MAX_AMOUNT`, `CENT`, `TOMORROW`,
  `LAST_DAY`).
- **`POLICY`**: term → ordered tuple of rules.
- **`violation(term, value, today, settings)`**: the first rule the value breaks, as a message,
  or `None`.
- Formatting helpers `money()` and `day()`, and `date_window()`.

## Rules as tuples

```python
POLICY: dict[Term, tuple[Rule, ...]] = {
    Term.AMOUNT: (
        (gt, Limit.ZERO, "The payment amount must be greater than $0.00."),
        (le, Limit.MAX_AMOUNT, "The payment amount can be at most {max_amount}."),
        (multiple_of, Limit.CENT, "The payment amount must be in whole cents."),
    ),
    Term.PAYMENT_DATE: (
        (ge, Limit.TOMORROW, "The payment date must be after today ({today})."),
        (le, Limit.LAST_DAY, "The payment date must be within {date_window_days} days (no later than {last_day})."),
    ),
    Term.CARD: (),
}
```

A rule `(must_be, limit, message)` reads "the new value must be `must_be` the limit, or the
change is refused with `message`". `must_be` is a plain function (`operator.gt`, `le`, `ge`, or
`multiple_of`).

Why this shape:

- **One table to read.** The whole policy fits on a screen and can be checked against the
  written rules line by line.
- **Limits are names, not numbers.** `Limit.LAST_DAY` depends on today and on configuration;
  resolving names at check time keeps the table static and the dates current.
- **Order matters.** The first broken rule wins, so the user hears the most basic problem first
  (e.g. "must be greater than $0.00" before "whole cents").
- **One checker, two callers.** The agent (`PaymentState.violates_policy`) and the payment
  system (`BankPaymentService.set_*`) both call `violation()`, so they can never disagree, yet the
  backend still enforces the rules on its own.
- **`Term.CARD` has no rules** because the agent only ever proposes a card on file, and the
  payment system checks that anyway. It is listed so every term has an entry (a test checks this).

## Not here (on purpose)

- **Who needs extra authentication** is decided by an operator
  (`RequireAuthenticationForHighLimitDebit`), with only its threshold
  (`authenticate_debit_limit_over`) in `PolicySettings`. Rules here say whether a value is
  *allowed*; operators decide what a change *needs*.
- **Card payment limits** are stored on each `Card` but not yet enforced against the amount.

## Extending

- **A new rule** for an existing term: one tuple in `POLICY`. If it needs a new limit, add a
  `Limit` member, its value in `limits()`, and a setting in `PolicySettings`/`config.toml`.
- **A new term**: a `Term` member, its rules, and a mapping from the intent that changes it
  (`TERMS` in `state.py`).
- Comparisons are Python functions, so `POLICY` itself can't move into `config.toml`; only the
  limits can.
