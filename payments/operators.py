"""
The decision process: a set of independent WHEN/THEN operators.

Each cycle, every operator whose WHEN holds is proposed; the one with
the lowest :class:`Priority` value is applied. There is no hard-coded
flow -- "what happens next" falls out of the state. One user turn ends
when an operator marked ``ends_turn`` runs: it says this turn's
messages and waits for the user's next line (``SayGoodbye`` instead
ends the session).

The LLM is only consulted by ``Interpret``. The plan only changes in
``ConfirmAmountChange`` / ``ConfirmDateChange`` / ``ConfirmCardChange``,
after the user says yes to a change the policy allows (and passes extra
authentication, if an operator asked for it) -- and the payment system
checks the policy again.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from enum import IntEnum
from typing import ClassVar, cast

from cognition import IOContainer, Operator

from .console import Listen, Say
from .language import Intent, InterpretRequest, LLMInterpreter, Reply
from .policy import PolicySettings, date_window, day, money
from .bank_payment_service import AuthenticationFailed, Card, CardKind, Customer, PaymentPlan, PolicyViolation
from .state import CHANGES, Detail, PaymentState, Proposal

# ===

_logger = logging.getLogger(__name__)


class Priority(IntEnum):
    """
    When several operators apply, the lowest value wins. Work left over
    from the last turn is still in the state, so ACT operators can apply
    alongside anything new; within a level, operators never apply together.
    """

    INPUT = 1
    """first deal with the session and the user's new input: fetch the
    customer, greet, verify the account number (before verification) or
    interpret (after), ask to rephrase, or say goodbye (the customer is
    fetched before anything is said; input is one line, or the user leaving)"""

    SETTLE = 2
    """then settle a proposal the user said yes/no to, before it is
    re-asked: authenticate if its intent needs it, confirm, or decline
    (an answer is either yes or no; a yes is either cleared or not)"""

    ASSESS = 3
    """then, before a change is proposed, decide what it needs (e.g. extra
    authentication); this overlaps with proposing it, so it comes first"""

    ACT = 4
    """then act on the agenda: show the plan, work on the change in
    focus, or wrap up (each needs a different focus, or none)"""


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


class PaymentOperator(Operator[PaymentState]):
    """Base: named after the class, ranked by ``priority``"""

    priority: ClassVar[Priority]
    ends_turn: ClassVar[bool] = False
    uses_llm: ClassVar[bool] = False
    """calls the LLM (shown in pink when tracing)"""

    def __init__(self) -> None:
        super().__init__(_snake(type(self).__name__), **({"terminal": True} if self.ends_turn else {}))

    def sort_key(self) -> int:
        """Ranking used by the decision process (lower first)"""

        return self.priority


# === io helpers (sensors: io.i.today, io.i.plan; actuators: io.o.console, io.o.get_customer,
# io.o.set_amount, io.o.set_date, io.o.set_card, io.o.authenticate)


def today(io: IOContainer) -> date:
    return cast(date, io.i.today)


def end_turn(state: PaymentState, io: IOContainer, *lines: str) -> None:
    """Say this turn's messages, then wait for the user's next line"""

    state.say(*lines)
    state.last_message = "\n".join(state.outbox)
    state.outbox.clear()
    io.o.console(Say(state.last_message))
    state.hear(cast(str | None, io.o.console(Listen())))


# === how the plan and changes are described

HELP = (
    "I can show your payment plan, change your payment amount, change your payment date,"
    " or change the card you pay with. What would you like to do?"
)

LABEL = {
    Intent.CHANGE_AMOUNT: "payment amount",
    Intent.CHANGE_DATE: "payment date",
    Intent.CHANGE_CARD: "payment card",
}


def card_name(card: Card) -> str:
    return f"your {card.network} {card.kind} card ending {card.last_four}"


def show(value: Detail) -> str:
    if isinstance(value, Card):
        return card_name(value)
    return money(value) if isinstance(value, Decimal) else day(value)


def current(intent: Intent, plan: PaymentPlan, customer: Customer) -> Detail:
    if intent is Intent.CHANGE_CARD:
        return cast(Card, customer.card(plan.card_id))
    return plan.amount if intent is Intent.CHANGE_AMOUNT else plan.payment_date


def describe_plan(plan: PaymentPlan, card: Card) -> str:
    return (
        f"Your payment plan: {money(plan.amount)} will be sent on"
        f" {day(plan.payment_date)} from account {plan.account_number},"
        f" paid with {card_name(card)}."
    )


def ask_for(intent: Intent, today: date, policy: PolicySettings, cards: tuple[Card, ...]) -> str:
    if intent is Intent.CHANGE_AMOUNT:
        return "What would you like your new payment amount to be?"

    if intent is Intent.CHANGE_CARD:
        return f"Which card should the payment be made with? ({'; '.join(card_name(c) for c in cards)})"

    earliest, latest = date_window(today, policy)
    return f"What date should the payment be sent? (any day from {day(earliest)} through {day(latest)})"


def confirm_question(p: Proposal, plan: PaymentPlan, customer: Customer) -> str:
    return (
        f"Change your {LABEL[p.intent]} from {show(current(p.intent, plan, customer))}"
        f" to {show(p.value)}? (yes/no)"
    )


###################################################
# Start & end of the session
###################################################


class FetchCustomer(PaymentOperator):
    """
    WHEN: the session has just started, and the customer's information
          hasn't been fetched
    THEN: query the bank payment service for it
    """

    priority = Priority.INPUT

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        return state.customer_record is None

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        state.customer_record = cast(Customer, io.o.get_customer(None))  # the API takes no arguments


class Greet(PaymentOperator):
    """
    WHEN: the session has just started, and the customer's information
          has been fetched
    THEN: greet the user and ask them to confirm their account number
    """

    priority = Priority.INPUT
    ends_turn = True

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        return not state.greeted and state.customer_record is not None

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        state.greeted = True
        end_turn(state, io, "Hi! Before I can help, please confirm your account number.")


class SayGoodbye(PaymentOperator):
    """
    WHEN: the user left (typed an exit word, or closed the input)
    THEN: say goodbye and end the session
    """

    priority = Priority.INPUT
    ends_turn = True

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        return state.leaving

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        io.o.console(Say("\n".join([*state.outbox, "Goodbye!"])))
        state.outbox.clear()
        state.closed = True


###################################################
# Verifying the user (before anything is interpreted,
# so the account number never reaches the LLM)
###################################################


class AcceptAccountNumber(PaymentOperator):
    """
    WHEN: the user, not yet verified, restated the customer's account number
    THEN: mark them verified, and say what the assistant can do
    """

    priority = Priority.INPUT
    ends_turn = True

    customer_name: str
    """the customer's name (set by ``can_perform``)"""

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        if not state.verified and state.heard is not None and state.customer.is_account_number(state.heard):
            self.customer_name = state.customer.name
            return True

        return False

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        state.heard = None
        state.verified = True
        end_turn(state, io, f"Thanks, {self.customer_name}. {HELP}")


class RejectAccountNumber(PaymentOperator):
    """
    WHEN: the user, not yet verified, said something other than the
          customer's account number, and has tries left
    THEN: say it doesn't match, and ask again
    """

    priority = Priority.INPUT
    ends_turn = True

    tries_left: int
    """tries left after this one (set by ``can_perform``)"""

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        if not state.verified and state.heard is not None and not state.customer.is_account_number(state.heard):
            tries_left = state.policy.max_verification_attempts - state.failed_verifications - 1
            if tries_left > 0:
                self.tries_left = tries_left
                return True

        return False

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        state.heard = None
        state.failed_verifications += 1
        tries = "try" if self.tries_left == 1 else "tries"
        end_turn(
            state, io,
            f"That doesn't match our records ({self.tries_left} {tries} left). Please restate your account number.",
        )


class EndUnverifiedSession(PaymentOperator):
    """
    WHEN: the user, not yet verified, said something other than the
          customer's account number, on their last try
    THEN: explain the session can't continue, and end it
    """

    priority = Priority.INPUT

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        return (
            not state.verified
            and state.heard is not None
            and not state.customer.is_account_number(state.heard)
            and state.failed_verifications + 1 >= state.policy.max_verification_attempts
        )

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        state.heard = None
        state.failed_verifications += 1
        state.say("That doesn't match our records. For your security, I can't continue this session.")
        state.leaving = True


###################################################
# Understanding the user (LLM)
###################################################


class Interpret(PaymentOperator):
    """
    WHEN: the verified user said something that has not been interpreted yet
    THEN: ask the LLM which tasks, details, and yes/no it contains,
          and merge them into the agenda (stated details imply
          their change; plan views jump the queue)
    """

    priority = Priority.INPUT
    uses_llm = True

    utterance: str
    """what the user said (set by ``can_perform``)"""

    today: date
    """today's date (set by ``can_perform``)"""

    plan: PaymentPlan
    """the plan of record (set by ``can_perform``)"""

    cards: tuple[Card, ...]
    """the customer's cards, so the LLM can tell which one is meant (set by ``can_perform``)"""

    def __init__(self) -> None:
        super().__init__()
        self.interpreter = LLMInterpreter()

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        if state.verified and state.heard is not None:
            self.utterance = state.heard
            self.today = today(io)
            self.plan = cast(PaymentPlan, io.i.plan)
            self.cards = state.customer.cards
            return True

        return False

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        state.heard = None
        state.plan = self.plan

        try:
            interp = self.interpreter.interpret(
                InterpretRequest(self.utterance, self.today, state.last_message, self.plan, self.cards)
            )
        except Exception:  # pylint: disable=broad-exception-caught
            _logger.exception("Interpretation failed: %s", self.utterance)
            state.misunderstood = True
            return

        state.absorb(interp)


class AskToRephrase(PaymentOperator):
    """
    WHEN: the LLM could not interpret what the user said
    THEN: ask them to rephrase (pending tasks are kept)
    """

    priority = Priority.INPUT
    ends_turn = True

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        return state.misunderstood

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        state.misunderstood = False
        end_turn(state, io, "Sorry, I had trouble understanding that. Could you rephrase?")


###################################################
# Settling a proposal (the user's yes/no)
###################################################


def user_confirmed(state: PaymentState, intent: Intent) -> bool:
    """The user said yes to a proposed ``intent`` change that still stands"""

    return state.answer is Reply.YES and cast(Proposal, state.proposal).intent is intent


class Authenticate(PaymentOperator):
    """
    WHEN: the user said yes to a proposed change that still stands, and
          it needs extra authentication
    THEN: ask the payment system to authenticate them (it only prompts
          once per session); if they fail, keep the proposal so it is
          asked again (yes retries, no drops it)
    """

    priority = Priority.SETTLE

    p: Proposal
    """the confirmed proposal (set by ``can_perform``)"""

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        if state.answer is Reply.YES and state.needs_authentication:
            self.p = cast(Proposal, state.proposal)
            return True

        return False

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        try:
            io.o.authenticate(f"change your {LABEL[self.p.intent]}")
        except AuthenticationFailed as err:
            state.say(f"I couldn't make that change. {err}")
            state.reply = None  # the yes was used up; the proposal stands
            return

        state.needs_authentication = False


def make_change(state: PaymentState, p: Proposal, change: Callable[[Detail], PaymentPlan]) -> None:
    """
    Make the confirmed change in the payment system; if the system refuses
    (it re-checks policy, e.g. the date window moved), explain and forget
    the detail so it is asked for again
    """

    try:
        state.plan = change(p.value)
    except PolicyViolation as err:
        state.say(f"I couldn't make that change. {err}")
        state.forget(p.intent)
        return

    state.say(f"Done: your {LABEL[p.intent]} is now {show(p.value)}.")
    state.finish(p.intent)


class ConfirmAmountChange(PaymentOperator):
    """
    WHEN: the user said yes to a proposed amount change that still stands,
          and needs no (more) authentication
    THEN: set the new amount in the payment system (which may refuse)
    """

    priority = Priority.SETTLE

    p: Proposal
    """the confirmed proposal (set by ``can_perform``)"""

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        if user_confirmed(state, Intent.CHANGE_AMOUNT) and not state.needs_authentication:
            self.p = cast(Proposal, state.proposal)
            return True

        return False

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        make_change(state, self.p, io.o.set_amount)


class ConfirmDateChange(PaymentOperator):
    """
    WHEN: the user said yes to a proposed date change that still stands,
          and needs no (more) authentication
    THEN: set the new date in the payment system (which may refuse)
    """

    priority = Priority.SETTLE

    p: Proposal
    """the confirmed proposal (set by ``can_perform``)"""

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        if user_confirmed(state, Intent.CHANGE_DATE) and not state.needs_authentication:
            self.p = cast(Proposal, state.proposal)
            return True

        return False

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        make_change(state, self.p, io.o.set_date)


class ConfirmCardChange(PaymentOperator):
    """
    WHEN: the user said yes to a proposed card change that still stands,
          and needs no (more) authentication
    THEN: set the new card in the payment system (which may refuse)
    """

    priority = Priority.SETTLE

    p: Proposal
    """the confirmed proposal (set by ``can_perform``)"""

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        if user_confirmed(state, Intent.CHANGE_CARD) and not state.needs_authentication:
            self.p = cast(Proposal, state.proposal)
            return True

        return False

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        make_change(state, self.p, io.o.set_card)


class DeclineChange(PaymentOperator):
    """
    WHEN: the user said no to a proposed change that still stands
    THEN: leave the plan as it is and drop that change
    """

    priority = Priority.SETTLE

    p: Proposal
    """the declined proposal (set by ``can_perform``)"""

    plan: PaymentPlan
    """the plan it would have changed (set by ``can_perform``)"""

    customer: Customer
    """whose cards the plan may be paid with (set by ``can_perform``)"""

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        if state.answer is Reply.NO:
            self.p = cast(Proposal, state.proposal)
            self.plan = cast(PaymentPlan, state.plan)
            self.customer = state.customer
            return True

        return False

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        was = show(current(self.p.intent, self.plan, self.customer))
        state.say(f"Okay, I left your {LABEL[self.p.intent]} at {was}.")
        state.finish(self.p.intent)


###################################################
# Working through the agenda
###################################################


class ShowPlan(PaymentOperator):
    """
    WHEN: the user asked to see the plan
    THEN: describe it
    """

    priority = Priority.ACT

    plan: PaymentPlan
    """the plan to describe (set by ``can_perform``)"""

    card: Card
    """the card it is paid with (set by ``can_perform``)"""

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        if state.focus is Intent.VIEW_PLAN:
            self.plan = cast(PaymentPlan, state.plan)
            self.card = cast(Card, state.customer.card(self.plan.card_id))
            return True

        return False

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        state.say(describe_plan(self.plan, self.card))
        state.finish(Intent.VIEW_PLAN)


class RequestValue(PaymentOperator):
    """
    WHEN: the change in focus has no detail yet
    THEN: ask for it
    """

    priority = Priority.ACT
    ends_turn = True

    intent: Intent
    """the change in focus (set by ``can_perform``)"""

    today: date
    """today's date, for the allowed date window (set by ``can_perform``)"""

    cards: tuple[Card, ...]
    """the customer's cards, to choose from (set by ``can_perform``)"""

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        if state.focus in CHANGES and state.focus_value is None:
            self.intent = cast(Intent, state.focus)
            self.today = today(io)
            self.cards = state.customer.cards
            return True

        return False

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        end_turn(state, io, ask_for(self.intent, self.today, state.policy, self.cards))


class RejectValue(PaymentOperator):
    """
    WHEN: the detail for the change in focus breaks policy
    THEN: explain why, forget it, and ask again
    """

    priority = Priority.ACT
    ends_turn = True

    intent: Intent
    """the change in focus (set by ``can_perform``)"""

    value: Detail
    """its detail (set by ``can_perform``)"""

    issue: str
    """why the detail breaks policy (set by ``can_perform``)"""

    today: date
    """today's date, for the allowed date window (set by ``can_perform``)"""

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        if (issue := state.violates_policy(today(io))) is not None:
            self.intent = cast(Intent, state.focus)
            self.value = cast(Detail, state.focus_value)
            self.issue = issue
            self.today = today(io)
            return True

        return False

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        state.say(f"I can't use {show(self.value)}. {self.issue}")
        state.forget(self.intent)
        end_turn(state, io, ask_for(self.intent, self.today, state.policy, state.customer.cards))


def _valid_detail(state: PaymentState, io: IOContainer) -> bool:
    return state.focus_value is not None and state.violates_policy(today(io)) is None


class RequireAuthenticationForHighLimitDebit(PaymentOperator):
    """
    WHEN: the change in focus switches the payment card to a debit card whose
          payment limit is over the policy's threshold, and it hasn't been
          proposed yet (nor marked)
    THEN: mark that it needs extra authentication before it is carried out
    """

    priority = Priority.ASSESS

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        card = state.focus_value
        return (
            state.focus is Intent.CHANGE_CARD
            and isinstance(card, Card)
            and card.kind is CardKind.DEBIT
            and card.payment_limit > state.policy.authenticate_debit_limit_over
            and not state.proposed
            and not state.needs_authentication
        )

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        state.needs_authentication = True


class ProposeChange(PaymentOperator):
    """
    WHEN: the change in focus has a valid detail not yet put to the user
    THEN: ask the user to confirm it
    """

    priority = Priority.ACT
    ends_turn = True

    p: Proposal
    """the change to propose (set by ``can_perform``)"""

    plan: PaymentPlan
    """the plan it would change (set by ``can_perform``)"""

    customer: Customer
    """whose cards the plan may be paid with (set by ``can_perform``)"""

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        if _valid_detail(state, io) and not state.proposed:
            self.p = Proposal(cast(Intent, state.focus), cast(Detail, state.focus_value))
            self.plan = cast(PaymentPlan, state.plan)
            self.customer = state.customer
            return True

        return False

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        state.proposal = self.p
        end_turn(state, io, confirm_question(self.p, self.plan, self.customer))


class AwaitConfirmation(PaymentOperator):
    """
    WHEN: the change in focus was put to the user, who didn't answer yes or no
    THEN: ask again
    """

    priority = Priority.ACT
    ends_turn = True

    p: Proposal
    """the proposal still awaiting an answer (set by ``can_perform``)"""

    plan: PaymentPlan
    """the plan it would change (set by ``can_perform``)"""

    customer: Customer
    """whose cards the plan may be paid with (set by ``can_perform``)"""

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        if _valid_detail(state, io) and state.proposed:
            self.p = cast(Proposal, state.proposal)
            self.plan = cast(PaymentPlan, state.plan)
            self.customer = state.customer
            return True

        return False

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        end_turn(state, io, f"Before we move on: {confirm_question(self.p, self.plan, self.customer)}")


class WrapUp(PaymentOperator):
    """
    WHEN: the agenda is empty (fallback: nothing more urgent applies)
    THEN: ask if there is anything else (or offer help if nothing was done)
    """

    priority = Priority.ACT
    ends_turn = True

    def can_perform(self, state: PaymentState, io: IOContainer) -> bool:
        return state.focus is None

    def perform(self, state: PaymentState, io: IOContainer) -> None:
        end_turn(state, io, "Is there anything else I can help with?" if state.outbox else HELP)
