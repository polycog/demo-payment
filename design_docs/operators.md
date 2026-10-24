# `payments/operators.py`

## Purpose

The decision process: independent WHEN/THEN rules. Each cycle every operator whose WHEN holds is
proposed, and the one with the lowest `Priority` runs. There is no hard-coded flow: what happens
next follows from the state.

## Priority levels

| Level | Operators | Why it outranks the next |
|---|---|---|
| 1 `INPUT` | `FetchCustomer`, `Greet`, `SayGoodbye`, `AcceptAccountNumber`, `RejectAccountNumber`, `EndUnverifiedSession`, `Interpret`, `AskToRephrase` | new input must be understood before acting on old work |
| 2 `SETTLE` | `Authenticate`, `ConfirmAmountChange`, `ConfirmDateChange`, `ConfirmCardChange`, `DeclineChange` | a yes/no must be settled before the proposal would be re-asked |
| 3 `ASSESS` | `RequireAuthenticationForHighLimitDebit` | what a change needs must be decided before it is proposed |
| 4 `ACT` | `ShowPlan`, `RequestValue`, `RejectValue`, `ProposeChange`, `AwaitConfirmation`, `WrapUp` | the fallback: work on the agenda |

**Levels exist only where operators can apply at the same time.** Work left from the last turn
is still in the state when new input arrives, so an `ACT` operator (re-ask a pending proposal)
can apply alongside `Interpret` or a confirm. Within a level the operators are mutually
exclusive: input is one line or the user leaving, an answer is yes or no, each `ACT` operator
needs a different focus or detail state. Running the tests with all priorities equal fails most
of them; that's how to check a level is still needed.

## Every operator has the same shape

```python
class DeclineChange(PaymentOperator):
    """
    WHEN: the user said no to a proposed change that still stands
    THEN: leave the plan as it is and drop that change
    """

    priority = Priority.SETTLE

    p: Proposal
    """the declined proposal (set by ``can_perform``)"""

    def can_perform(self, state, io) -> bool:
        if state.answer is Reply.NO:
            self.p = cast(Proposal, state.proposal)
            ...
            return True

        return False

    def perform(self, state, io) -> None:
        state.say(f"Okay, I left your {LABEL[self.p.intent]} at ...")
        state.finish(self.p.intent)
```

- **WHEN/THEN docstring first**, in domain terms; the code should read like it.
- **Positive guards**: `if <WHEN>: bind…; return True`, then `return False`.
- **`can_perform` binds, `perform` uses.** Values `perform` needs are bound as instance
  attributes, declared on the class with a type and a docstring. `can_perform` never changes
  state.
- **One decision per operator.** If `perform` would branch on something known in `can_perform`,
  it's two operators (`ConfirmAmountChange` / `ConfirmDateChange` / `ConfirmCardChange`;
  `AcceptAccountNumber` / `RejectAccountNumber` / `EndUnverifiedSession`).
- **All I/O through actuators** (`io.o.console`, `io.o.set_*`, `io.o.authenticate`).

`PaymentOperator` (the base) names each operator after its class in snake_case, ranks it by
`priority`, makes it terminal when `ends_turn = True`, and marks LLM callers with
`uses_llm = True` (pink in `--trace`).

## The operators by phase

**Start and end.** `FetchCustomer` queries the bank payment service for the customer
(`io.o.get_customer`) before anything is said; `Greet` then asks for the account number. `SayGoodbye` flushes any queued message,
says goodbye and closes the session.

**Verification** (before anything reaches the LLM). The unverified user's line is compared, by
code, with the account number: `AcceptAccountNumber` (match), `RejectAccountNumber` (no match,
tries left), `EndUnverifiedSession` (no match on the last try; sets `leaving`).

**Understanding.** `Interpret` (verified users only) calls the LLM and `absorb`s the result; on
failure it sets `misunderstood`, and `AskToRephrase` asks again.

**Settling.**
- `Authenticate`: yes + `needs_authentication` → call `io.o.authenticate`; on failure, keep the
  proposal and clear the yes so it's re-asked.
- `Confirm*Change`: yes + no authentication pending → `make_change`, which calls the payment
  system, and on `PolicyViolation` forgets the value so it's asked for again.
- `DeclineChange`: no → leave the plan, drop the change.

**Assessing.** `RequireAuthenticationForHighLimitDebit`: the change in focus switches to a debit
card whose limit is over `authenticate_debit_limit_over`, not yet proposed → set
`needs_authentication`. Other "this change needs X" rules belong here.

**Acting on the agenda.**
- `ShowPlan` describes the plan, including the card.
- `RequestValue` asks for a missing detail; for cards it lists them.
- `RejectValue` explains a policy violation and asks again.
- `ProposeChange` asks "Change your X from A to B? (yes/no)".
- `AwaitConfirmation` re-asks when the reply was neither yes nor no.
- `WrapUp` asks "anything else?", or offers help if nothing was done.

## Ending a turn

`end_turn(state, io, *lines)` joins `state.outbox`, says it, records it as `last_message` (LLM
context for the next turn), and reads the next line with `state.hear(...)`. Operators that end a
turn set `ends_turn = True`, which makes them terminal for this decision-process run.

## Example: "pay with my Visa debit instead"

```
INPUT   interpret (llm)            → agenda [CHANGE_CARD], details {card3}
ASSESS  require_authentication_... → needs_authentication = True
ACT     propose_change             → "Change your payment card from … to your Visa debit card ending 1881? (yes/no)"
        (turn ends; user says "yes")
INPUT   interpret (llm)            → reply YES
SETTLE  authenticate               → key phrase OK → needs_authentication = False
SETTLE  confirm_card_change        → set_card → "Done: …"
ACT     wrap_up                    → "Is there anything else I can help with?"
```

## Extending

Write the WHEN/THEN docstring first, pick the level whose members it can never co-occur with
(add a level only for a real overlap, and document why), register it in `agent.py`, and add a
test per path. The shared skill at `~/polycog/skills/cognition-operators` has the full checklist.
