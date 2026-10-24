# `payments/agent.py`

## Purpose

Assemble the agent: state, operators, ranking, sensors and actuators, wired into a cognition
`Cogent`. It holds no logic of its own.

## `build_agent(console, service, clock=date.today)`

1. **State:** an empty `PaymentState()`. The customer isn't copied in: `FetchCustomer` queries
   the bank payment service for it when the session starts. The same state object is given to
   the `DecisionProcess` and survives every turn.
2. **Operators:** each one is constructed and added with `dp.add_operator`, listed by phase
   (start & end, verification, understanding, settling, assessing, the agenda, end of turn). The
   explicit list is the table of contents of the decision process.
3. **Ranking:** `sorting_evaluator(by_priority)` picks the applicable operator with the lowest
   `Priority`. `by_priority` reads the operator instance from the action's parameters
   (`OPERATOR_SELF_PARAM`).
4. **Sensors** (read at the start of every turn):

   | Sensor | Source | Read by operators as |
   |---|---|---|
   | `today` | `clock` | `io.i.today` |
   | `plan` | `service.plan` | `io.i.plan` |

5. **Actuators:**

   | Actuator | Target | Used by |
   |---|---|---|
   | `console` | the given console | every turn-ending operator |
   | `get_customer` | `BankPaymentService.get_customer` | `FetchCustomer` |
   | `set_amount` / `set_date` / `set_card` | `BankPaymentService` | confirm operators |
   | `authenticate` | `BankPaymentService.require_authentication` | `Authenticate` |

## `run(agent)`

`agent(lambda c: not c.dp.state.closed)`: one cogent loop per user turn, until `SayGoodbye`
closes the session. Returns the final state (useful in tests).

## Design decisions

- **Imports point one way,** so each layer can be read and tested on its own:
  `config ← policy ← bank_payment_service ← language ← state ← operators ← agent ← __main__`
  (and `console ← operators`).

- **Dependencies come in as arguments** (console, payment system, clock), and the LLM is built
  inside `Interpret`, so tests can replace every external piece.
- **The payment system is reached only through sensors and actuators.** Operators can't call it
  directly, so the boundary between agent and backend is visible here in one place.
- **Plan reads are refreshed each turn** by the `plan` sensor. Within a turn, a confirm operator
  stores the plan returned by `set_*` in `state.plan`, so the same turn sees the change.
