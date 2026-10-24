"""
Assembling the cognitive agent (Cogent):

* sensor   ``today``      -> io.i.today      (calendar date, read each turn)
* sensor   ``plan``       -> io.i.plan       (the plan of record, read each turn)
* actuator ``console``    -> io.o.console    (all user interaction)
* actuator ``get_customer`` -> io.o.get_customer (bank payment service: the account holder)
* actuator ``set_amount`` -> io.o.set_amount (payment system)
* actuator ``set_date``   -> io.o.set_date   (payment system)
* actuator ``set_card``   -> io.o.set_card   (payment system)
* actuator ``authenticate`` -> io.o.authenticate (payment system's extra authentication)
* decision process        -> the operators in ``operators.py``,
                             ranked by ``Priority``

``run`` loops one turn at a time until the user leaves.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any, cast

from cognition import (
    Actuator,
    Cogent,
    DecisionProcess,
    NamedObject,
    OPERATOR_SELF_PARAM,
    create_actuator,
    create_sensor,
    sorting_evaluator,
)

from .operators import (
    AcceptAccountNumber,
    AskToRephrase,
    Authenticate,
    AwaitConfirmation,
    ConfirmAmountChange,
    ConfirmCardChange,
    ConfirmDateChange,
    DeclineChange,
    EndUnverifiedSession,
    FetchCustomer,
    Greet,
    Interpret,
    ProposeChange,
    RejectAccountNumber,
    RejectValue,
    RequestValue,
    RequireAuthenticationForHighLimitDebit,
    SayGoodbye,
    ShowPlan,
    WrapUp,
)
from .bank_payment_service import BankPaymentService
from .state import PaymentState

type PaymentAgent = Cogent[DecisionProcess[PaymentState]]


def by_priority(action: Any, _state: PaymentState, _io: Any) -> int:
    """Ranking key: each operator's priority"""

    return cast(NamedObject, action).params[OPERATOR_SELF_PARAM].sort_key()


def build_agent(
    console: Actuator[Any, Any],
    service: BankPaymentService,
    clock: Callable[[], date] = date.today,
) -> PaymentAgent:
    """Wire state, operators, ranking, sensors, and actuators together"""

    state = PaymentState()  # the customer is fetched from the service when the session starts
    dp = DecisionProcess(state)  # same state object survives each per-turn reinit

    operators = (
        # start & end
        FetchCustomer(),
        Greet(),
        SayGoodbye(),
        # verifying the user
        AcceptAccountNumber(),
        RejectAccountNumber(),
        EndUnverifiedSession(),
        # understanding
        Interpret(),
        AskToRephrase(),
        # settling a proposal
        Authenticate(),
        ConfirmAmountChange(),
        ConfirmDateChange(),
        ConfirmCardChange(),
        DeclineChange(),
        # what a change needs, before it is proposed
        RequireAuthenticationForHighLimitDebit(),
        # the agenda
        ShowPlan(),
        RequestValue(),
        RejectValue(),
        ProposeChange(),
        AwaitConfirmation(),
        # end of turn
        WrapUp(),
    )
    for op in operators:
        dp.add_operator(op)
    dp.add_action_evaluator(sorting_evaluator(by_priority, name="policy_priority"))

    agent: PaymentAgent = Cogent(dp, name="payments")
    agent.add_sensor(create_sensor("today", clock))
    agent.add_sensor(create_sensor("plan", lambda: service.plan))
    agent.add_actuator(console)
    agent.add_actuator(create_actuator("get_customer", lambda _: service.get_customer()))
    agent.add_actuator(create_actuator("set_amount", service.set_amount))
    agent.add_actuator(create_actuator("set_date", service.set_date))
    agent.add_actuator(create_actuator("set_card", service.set_card))
    agent.add_actuator(create_actuator("authenticate", service.require_authentication))
    return agent


def run(agent: PaymentAgent) -> PaymentState:
    """One cogent loop per user turn, until the user leaves"""

    agent(lambda c: not c.dp.state.closed)
    return agent.dp.state
