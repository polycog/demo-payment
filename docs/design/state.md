# `payments/state.py`

## Purpose

Everything the agent remembers about the conversation, and the queries operators ask of it.
Operators read and change `PaymentState`; it never does I/O itself.

## Lifetime

`PaymentState` is a `@dataclass` subclassing cognition's `SelfReinitState`. The decision process
"reinitializes" its state at the start of every cogent loop (one user turn); a
`SelfReinitState` handles that itself, so **the same instance survives every turn**. `_reinit`
resets only what is per-turn: `reply`.

## Fields

| Group | Field | Meaning |
|---|---|---|
| context | `customer_record` | the account holder as returned by the bank payment service; `None` until `FetchCustomer` runs (read it through the `customer` property, which raises if it's missing) |
| | `policy` | `PolicySettings` from `config.toml` |
| | `plan` | the plan as last read from, or returned by, the payment system |
| conversation | `agenda` | tasks still to do; the first is **in focus** |
| | `details` | values given for changes not yet made (amount, date or `Card`) |
| | `proposal` | the change put to the user, awaiting yes/no |
| | `reply` | the user's yes/no this turn |
| | `needs_authentication` | the pending proposal needs extra authentication |
| input | `heard` | the user's line, not yet handled |
| | `misunderstood` | the LLM couldn't interpret it |
| session | `greeted`, `verified`, `failed_verifications`, `leaving`, `closed` | session progress |
| output | `outbox`, `last_message` | what to say at the end of the turn; what was said last |

Every field has a docstring in the code saying what it means and who sets it.

## Queries operators use

- `focus`: the first agenda item.
- `focus_value`: the detail for the change in focus.
- `violates_policy(today)`: why that detail breaks `POLICY`, or `None`.
- `proposed`: the change in focus, with its current value, has been put to the user.
- `answer`: the user's yes/no to a proposal that **still stands**. If they revised the value
  since, the proposal is void and `answer` is `None`.

These are properties and methods rather than cognition elaborators so guards read naturally
(`state.answer is Reply.NO`).

## Changes operators make

- `hear(line)`: an exit word or `None` sets `leaving`; anything else goes to `heard`.
- `say(*lines)`: queue text for the end of the turn.
- `absorb(interp)`: merge an `Interpretation`:
  - a stated value fills `details` and implies its change intent;
  - a `card_id` is kept only if the card is on file;
  - plan views jump to the front of the agenda (read-only, so safe to interleave);
  - other intents queue in the order mentioned;
  - a value that revises a standing proposal clears `needs_authentication`, so a switch from a
    high-limit debit card to a credit card doesn't still demand authentication.
- `forget(intent)`: drop a change's detail and its proposal (and the authentication it needed).
- `finish(intent)`: take a task off the agenda, then `forget` it.

## Design decisions

- **An agenda, not a script.** Multiple requests in one utterance become agenda items handled
  one at a time; details given early (even for a later task) are kept and reused.
- **Proposals are tied to values.** A yes only counts for the exact value that was proposed,
  which makes "no, make it 60" re-propose instead of confirming the wrong thing.
- **Flags are requests between operators.** `needs_authentication` is set by whichever operator
  decides a proposal needs it, and served by `Authenticate`. `misunderstood` and `leaving` work
  the same way. This keeps operators independent: none calls another.
- **`TERMS` / `CHANGES`** map each change intent to the policy `Term` it changes, which is how
  `violates_policy` finds the right rules.
