# `payments/bank_payment_service.py` and `customer.json`

## Purpose

A stand-in for the bank's payment service: it **reads the customer and their plan from
`customer.json`**, answers the agent's queries, and is the **only** way to change the plan,
saving every change back to the file. The agent talks to it through sensors and actuators; it
never reads the file or edits the plan itself.

## How the agent uses it

1. `__main__` creates the service with `BankPaymentService.from_file()`, which reads
   `customer.json` (`load_account`) and remembers the file for saving.
2. When the session starts, the `FetchCustomer` operator **queries the API** with
   `io.o.get_customer`, which calls `get_customer()`, and stores the answer in the agent's state.
   Nothing is said to the user before that.
3. Each turn the agent reads the plan of record through the `plan` sensor, and changes it only
   through the `set_*` and `authenticate` actuators.

## Data model

```python
Card          # frozen: id, kind (CardKind.CREDIT / DEBIT), network, last_four, payment_limit
Customer      # frozen: name, account_number, cards (unique ids)
PaymentPlan   # account_number (frozen), amount, payment_date, card_id
```

- **Immutable where it should be.** `Customer` and `Card` are frozen; the plan's
  `account_number` is frozen while amount, date and card can change (`validate_assignment=True`
  re-validates on each change).
- **Only the last four digits** of a card are stored, so full card numbers can't leak into logs,
  state or the LLM prompt.
- `Customer.card(id)` looks a card up; `Customer.is_account_number(text)` compares digits only,
  so `4417-2290-0381` and `4417 2290 0381` both match.
- `check_plan(customer, plan)` enforces that a plan belongs to the customer's account and pays
  with one of their cards. It runs both when the file is loaded and when the service is built.

## `customer.json`

```json
{
  "name": "...", "account_number": "...",
  "cards": [{"id": "card1", "kind": "credit", "network": "Visa", "last_four": "4242", "payment_limit": "5000.00"}, ...],
  "plan": {"amount": "250.00", "payment_in_days": 14, "card_id": "card2"}
}
```

`load_account(path, today)` returns `(Customer, PaymentPlan)`:

- **No duplicated account number.** The plan takes it from the customer, so the two can't
  disagree.
- **Relative dates.** `payment_in_days` is turned into a date from today, so the demo never
  shows a past payment date. A fixed `payment_date` is also accepted.
- **Fail fast.** Missing or invalid data raises at startup (pydantic validation, unique card ids,
  `check_plan`).

## `BankPaymentService`

| Method | Does | Raises |
|---|---|---|
| `from_file(path)` | builds the service from an account file, saving changes back to it | `ValueError` / validation errors on a bad file |
| `get_customer()` | the account holder: name, account number, cards (queried at session start) | |
| `plan` | the plan of record (returned as a copy) | |
| `set_amount(amount)` | re-checks `POLICY`, changes the amount | `PolicyViolation` |
| `set_date(date)` | re-checks `POLICY`, changes the date | `PolicyViolation` |
| `set_card(card)` | checks the card is on file, changes the card | `PolicyViolation` |
| `require_authentication(purpose)` | simulated key-phrase check, once per session | `AuthenticationFailed` |

Given an `account_file`, every successful `set_*` saves the plan back to it with
`save_plan(path, plan, date_changed)`.

Design decisions:

- **The backend re-checks the policy independently.** It never trusts that the agent checked.
  If the two disagree (e.g. the date window moved past midnight), the backend wins and the
  agent recovers (see `make_change` in [operators.md](operators.md)).
- **Authentication is a separate call, not part of `set_*`.** Operators decide *when* a change
  needs it (by setting `state.needs_authentication`); the service only performs it. The
  trade-off: a caller using `set_*` directly skips authentication.
- **Two exception types for two recoveries.** `PolicyViolation` means the value is no longer
  allowed (forget it and ask again); `AuthenticationFailed` means the value was fine but the
  user wasn't (keep the proposal and re-ask).
- **Everything interactive or time-dependent is injected:** `today` (clock) and `authenticate`
  (the prompt, `ask_key_phrase` by default), so tests never touch stdin or the real date.
- **The agent asks; it isn't handed the customer.** `build_agent` creates an empty state, and
  the customer arrives through the same actuator boundary as every other call to the bank. A
  real deployment could swap in a service that looks the customer up remotely without any change
  to the agent.
- **Changes persist.** `from_file` sets `account_file` to the file it read, so a confirmed change is
  still there next session. Only the `plan` entry is rewritten; the customer and cards are left
  as they are. The file is written to `customer.json.tmp` and then swapped in, so a crash can't
  leave it half-written, and a refused change writes nothing.
- **Relative dates survive amount and card changes.** `payment_in_days` is kept until the date
  itself changes; then the chosen date is saved as a fixed `payment_date`, because the user
  picked a day, not an offset.
- **Persistence is opt-in.** Without `account_file` (the tests' default) changes stay in memory,
  so tests never touch the shipped `customer.json`.
- The `print("API CALLED: …")` lines are deliberate demo output showing when the backend is
  actually called.

## Extending

A new kind of change needs a `set_*` method that re-checks the policy for its `Term`, an
actuator in `agent.py`, and a confirm operator.
