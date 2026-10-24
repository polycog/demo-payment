"""
Offline tests: a scripted console and a fake interpreter stand in
for the user and the LLM, so the decision process is exercised
deterministically. Each scripted turn is what the interpreter
"understood" (``None`` = the LLM failed).
"""

from __future__ import annotations

import json
from collections import deque
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from cognition import Actuator
from rich.console import Console
from pydantic import ValidationError

from payments.agent import build_agent, run
from payments.operators import ProposeChange
from payments.console import LLM_STYLE, OPERATOR_STYLE, Listen, RichConsole, Say, trace_line
from payments.language import Intent, Interpretation, InterpretRequest, Reply
from payments.policy import POLICY, PolicySettings, Term
from payments.state import PaymentState
from payments.bank_payment_service import AuthenticationFailed, Card, CardKind, Customer, PaymentPlan, BankPaymentService, PolicyViolation, load_account

TODAY = date(2026, 10, 8)
ACCT = "4417-2290-0381"
CUSTOMER = Customer(
    name="Sam Lee",
    account_number=ACCT,
    cards=(
        Card(id="card1", kind=CardKind.CREDIT, network="Visa", last_four="4242", payment_limit=Decimal("5000.00")),
        Card(id="card2", kind=CardKind.DEBIT, network="Mastercard", last_four="5454", payment_limit=Decimal("1500.00")),
        Card(id="card3", kind=CardKind.DEBIT, network="Visa", last_four="1881", payment_limit=Decimal("10000.00")),
        Card(id="card4", kind=CardKind.DEBIT, network="Discover", last_four="6011", payment_limit=Decimal("5000.00")),
        Card(id="card5", kind=CardKind.CREDIT, network="Mastercard", last_four="2222", payment_limit=Decimal("9000.00")),
    ),
)


def interp(
    *intents: Intent,
    amount: str | None = None,
    payment_date: date | None = None,
    card: str | None = None,
    reply: Reply | None = None,
) -> Interpretation:
    return Interpretation(
        intents=list(intents),
        amount=Decimal(amount) if amount is not None else None,
        payment_date=payment_date,
        card_id=card,
        reply=reply,
    )


YES = interp(reply=Reply.YES)
NO = interp(reply=Reply.NO)


class ScriptedConsole(Actuator[object, object]):
    """Types the given lines, one per turn, then leaves; records what the agent says"""

    def __init__(self, lines: list[str]) -> None:
        self.lines = deque(lines)
        self.said: list[str] = []

    @property
    def name(self) -> str:
        return "console"

    def actuate(self, param: object) -> object:
        if isinstance(param, Say):
            self.said.append(param.text)
            return None
        assert isinstance(param, Listen)
        return self.lines.popleft() if self.lines else None


class FakeInterpreter:
    """Answers from the scripted turns, keyed by utterance"""

    def __init__(self, turns: tuple[Interpretation | None, ...]) -> None:
        self.understood = {f"utterance {i}": t for i, t in enumerate(turns)}
        self.asked: list[str] = []

    def interpret(self, req: InterpretRequest) -> Interpretation:
        self.asked.append(req.utterance)
        if (understood := self.understood[req.utterance]) is None:
            raise RuntimeError("model failed")
        return understood


def make_service(authenticate=lambda _purpose: True) -> BankPaymentService:
    return BankPaymentService(
        CUSTOMER,
        PaymentPlan(account_number=ACCT, amount=Decimal("250.00"), payment_date=date(2026, 10, 22), card_id="card2"),
        today=lambda: TODAY,
        authenticate=authenticate,
    )


def converse(
    lines: list[str], turns: tuple[Interpretation | None, ...] = (), service: BankPaymentService | None = None
) -> tuple[list[str], PaymentState, FakeInterpreter]:
    """
    Run the agent over the typed lines; ``turns`` are what the interpreter
    understands from ``utterance 0``, ``utterance 1``, ...

    :return: everything the agent said, final state, and the fake interpreter
    """

    service = service or make_service()
    console = ScriptedConsole(lines)
    interpreter = FakeInterpreter(turns)
    with patch("payments.operators.LLMInterpreter", return_value=interpreter):
        agent = build_agent(console, service, clock=lambda: TODAY)
    state = run(agent)
    assert state.customer == service.get_customer()
    return console.said, state, interpreter


def chat(*turns: Interpretation | None, service: BankPaymentService | None = None) -> tuple[list[str], BankPaymentService]:
    """
    Verify with the account number, then run the agent over scripted turns

    :return: bot messages (one per turn, without greeting/verification/goodbye) + final backend
    """

    service = service or make_service()
    said, _, _ = converse([ACCT, *(f"utterance {i}" for i in range(len(turns)))], turns, service)

    greeting, verified, *out, goodbye = said
    assert greeting == "Hi! Before I can help, please confirm your account number."
    assert verified.startswith("Thanks, Sam Lee. I can show your payment plan")
    assert goodbye == "Goodbye!"
    assert len(out) == len(turns)
    return out, service


# ===


def test_policy_is_well_formed() -> None:
    assert set(POLICY) == set(Term)
    settings = PolicySettings()
    limits = settings.limits(TODAY)
    for rules in POLICY.values():
        for _must_be, limit, message in rules:
            assert limit in limits
            message.format(**settings.message_values(TODAY))  # every {placeholder} has a value


def test_account_number_accepted_in_any_format() -> None:
    for typed in (ACCT, "441722900381", "it's 4417 2290 0381"):
        said, state, _ = converse([typed])
        assert state.verified and said[1].startswith("Thanks, Sam Lee.")


def test_wrong_account_number_then_right() -> None:
    said, state, _ = converse(["1234", ACCT])

    assert said[1] == "That doesn't match our records (2 tries left). Please restate your account number."
    assert said[2].startswith("Thanks, Sam Lee.") and state.verified


def test_too_many_wrong_account_numbers_ends_session() -> None:
    said, state, _ = converse(["1", "2", "3", ACCT])

    assert "(1 try left)" in said[2]
    assert said[3] == "That doesn't match our records. For your security, I can't continue this session.\nGoodbye!"
    assert state.closed and not state.verified
    assert len(said) == 4  # the fourth line was never read


def test_nothing_is_interpreted_before_verification() -> None:
    _, state, interpreter = converse(["show me my plan"], (interp(Intent.VIEW_PLAN),))

    assert not state.verified and not state.agenda
    assert interpreter.asked == []  # the line went to verification, not to the LLM


def test_view_plan() -> None:
    out, _ = chat(interp(Intent.VIEW_PLAN))

    assert "$250.00" in out[0] and "Thu, Oct 22, 2026" in out[0] and ACCT in out[0]
    assert "paid with your Mastercard debit card ending 5454" in out[0]
    assert out[0].endswith("anything else I can help with?")


def test_nothing_recognized_offers_help() -> None:
    out, _ = chat(interp())

    assert out[0].startswith("I can show your payment plan")


def test_multi_intent_handled_one_at_a_time() -> None:
    out, service = chat(
        interp(Intent.CHANGE_AMOUNT, Intent.CHANGE_DATE, amount="75", payment_date=date(2026, 10, 20)),
        YES,
        YES,
    )

    assert out[0] == "Change your payment amount from $250.00 to $75.00? (yes/no)"
    assert out[1].startswith("Done: your payment amount is now $75.00.")
    assert out[1].endswith("Change your payment date from Thu, Oct 22, 2026 to Tue, Oct 20, 2026? (yes/no)")
    assert out[2].startswith("Done: your payment date is now Tue, Oct 20, 2026.")
    assert service.plan.amount == Decimal("75") and service.plan.payment_date == date(2026, 10, 20)


def test_pending_intent_asks_for_missing_detail() -> None:
    out, service = chat(
        interp(Intent.CHANGE_AMOUNT, Intent.CHANGE_DATE, amount="75"),
        YES,
        interp(payment_date=date(2026, 10, 30)),
        YES,
    )

    assert out[1].startswith("Done: your payment amount is now $75.00.")
    assert "What date should the payment be sent?" in out[1]
    assert out[2].startswith("Change your payment date")
    assert service.plan.payment_date == date(2026, 10, 30)


def test_detail_from_earlier_turn_is_reused() -> None:
    out, service = chat(
        interp(Intent.CHANGE_DATE),
        # answers the date question, and volunteers an amount for later
        interp(payment_date=date(2026, 10, 15), amount="80"),
        YES,
        YES,
    )

    assert "What date" in out[0]
    assert out[1].startswith("Change your payment date")
    assert out[2].endswith("Change your payment amount from $250.00 to $80.00? (yes/no)")
    assert service.plan.amount == Decimal("80") and service.plan.payment_date == date(2026, 10, 15)


@pytest.mark.parametrize(
    ("amount", "why"),
    [("-40", "greater than $0.00"), ("0", "greater than $0.00"), ("20000", "at most"), ("10.005", "whole cents")],
)
def test_invalid_amount_rejected_then_retried(amount: str, why: str) -> None:
    out, service = chat(interp(Intent.CHANGE_AMOUNT, amount=amount), interp(amount="50"), YES)

    assert why in out[0] and "What would you like your new payment amount" in out[0]
    assert out[1].startswith("Change your payment amount from $250.00 to $50.00?")
    assert service.plan.amount == Decimal("50")


@pytest.mark.parametrize(
    ("bad", "why"),
    [(date(2026, 10, 8), "after today"), (date(2026, 11, 8), "within 30 days")],
)
def test_invalid_date_rejected(bad: date, why: str) -> None:
    out, service = chat(interp(Intent.CHANGE_DATE, payment_date=bad))

    assert why in out[0]
    assert service.plan.payment_date == date(2026, 10, 22)


def test_window_edges_allowed() -> None:
    _, service = chat(interp(payment_date=date(2026, 11, 7)), YES)
    assert service.plan.payment_date == date(2026, 11, 7)


def test_decline_leaves_plan_and_moves_on() -> None:
    out, service = chat(
        interp(Intent.CHANGE_AMOUNT, Intent.CHANGE_DATE, amount="75", payment_date=date(2026, 10, 20)),
        NO,
        YES,
    )

    assert out[1].startswith("Okay, I left your payment amount at $250.00.")
    assert service.plan.amount == Decimal("250.00")
    assert service.plan.payment_date == date(2026, 10, 20)


def test_revision_while_confirming_reproposes() -> None:
    out, service = chat(
        interp(Intent.CHANGE_AMOUNT, amount="75"),
        interp(amount="60", reply=Reply.NO),  # "no, make it 60"
        YES,
    )

    assert out[1] == "Change your payment amount from $250.00 to $60.00? (yes/no)"
    assert service.plan.amount == Decimal("60")


def test_view_interrupts_pending_confirmation() -> None:
    out, service = chat(
        interp(Intent.CHANGE_AMOUNT, amount="75"),
        interp(Intent.VIEW_PLAN),
        YES,
    )

    assert out[1].startswith("Your payment plan: $250.00")
    assert "Before we move on: Change your payment amount from $250.00 to $75.00?" in out[1]
    assert service.plan.amount == Decimal("75")


def test_confirm_then_view_shows_updated_plan() -> None:
    out, _ = chat(interp(Intent.CHANGE_AMOUNT, amount="75"), interp(Intent.VIEW_PLAN, reply=Reply.YES))

    assert out[1].startswith("Done: your payment amount is now $75.00.")
    assert "Your payment plan: $75.00" in out[1]


def test_unrelated_reply_reasks_confirmation() -> None:
    out, service = chat(interp(Intent.CHANGE_AMOUNT, amount="75"), interp())

    assert out[1].startswith("Before we move on:")
    assert service.plan.amount == Decimal("250.00")


def test_interpreter_failure_is_graceful() -> None:
    out, service = chat(interp(Intent.CHANGE_AMOUNT, amount="75"), None, YES)

    assert out[1].startswith("Sorry, I had trouble understanding")
    assert service.plan.amount == Decimal("75")  # pending work survived the failed turn


def test_changes_need_no_authentication() -> None:
    asked: list[str] = []
    service = make_service(lambda purpose: asked.append(purpose) or True)
    chat(interp(amount="75", payment_date=date(2026, 10, 20)), YES, YES, service=service)

    assert asked == []
    assert service.plan.amount == Decimal("75") and service.plan.payment_date == date(2026, 10, 20)


@pytest.fixture
def proposals_need_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stands in for an operator whose proposal needs authentication: every proposal sets the flag"""

    perform = ProposeChange.perform

    def perform_needing_authentication(self, state, io) -> None:  # type: ignore[no-untyped-def]
        state.needs_authentication = True
        perform(self, state, io)

    monkeypatch.setattr(ProposeChange, "perform", perform_needing_authentication)


@pytest.mark.usefixtures("proposals_need_authentication")
def test_failed_authentication_keeps_proposal() -> None:
    out, service = chat(interp(Intent.CHANGE_AMOUNT, amount="75"), YES, service=make_service(lambda _: False))

    assert out[1].startswith("I couldn't make that change. Extra authentication failed.")
    assert out[1].endswith("Change your payment amount from $250.00 to $75.00? (yes/no)")
    assert service.plan.amount == Decimal("250.00")


@pytest.mark.usefixtures("proposals_need_authentication")
def test_failed_authentication_can_be_retried() -> None:
    attempts = iter([False, True])
    _, service = chat(interp(Intent.CHANGE_AMOUNT, amount="75"), YES, YES, service=make_service(lambda _: next(attempts)))

    assert service.plan.amount == Decimal("75")


@pytest.mark.usefixtures("proposals_need_authentication")
def test_failed_authentication_then_no_drops_change() -> None:
    out, service = chat(interp(Intent.CHANGE_AMOUNT, amount="75"), YES, NO, service=make_service(lambda _: False))

    assert out[2].startswith("Okay, I left your payment amount at $250.00.")
    assert service.plan.amount == Decimal("250.00")


@pytest.mark.usefixtures("proposals_need_authentication")
def test_authentication_asked_once_per_session() -> None:
    asked: list[str] = []
    service = make_service(lambda purpose: asked.append(purpose) or True)
    chat(interp(amount="75", payment_date=date(2026, 10, 20)), YES, YES, service=service)

    assert asked == ["change your payment amount"]


@pytest.mark.usefixtures("proposals_need_authentication")
def test_authentication_only_after_yes_to_a_change() -> None:
    asked: list[str] = []
    service = make_service(lambda purpose: asked.append(purpose) or True)
    chat(interp(Intent.VIEW_PLAN), interp(amount="75"), NO, service=service)

    assert asked == []  # viewing doesn't ask, and a declined change never reaches authentication


@pytest.mark.usefixtures("proposals_need_authentication")
def test_revised_proposal_still_needs_authentication() -> None:
    asked: list[str] = []
    service = make_service(lambda purpose: asked.append(purpose) or True)
    chat(interp(amount="75"), interp(amount="60", reply=Reply.NO), YES, service=service)

    assert asked == ["change your payment amount"]
    assert service.plan.amount == Decimal("60")


def recording_service(asked: list[str]) -> BankPaymentService:
    return make_service(lambda purpose: asked.append(purpose) or True)


def test_change_to_high_limit_debit_card_needs_authentication() -> None:
    asked: list[str] = []
    out, service = chat(interp(Intent.CHANGE_CARD, card="card3"), YES, service=recording_service(asked))

    assert out[0] == (
        "Change your payment card from your Mastercard debit card ending 5454"
        " to your Visa debit card ending 1881? (yes/no)"
    )
    assert out[1].startswith("Done: your payment card is now your Visa debit card ending 1881.")
    assert asked == ["change your payment card"]
    assert service.plan.card_id == "card3"


@pytest.mark.parametrize(
    "card",
    ["card4", "card5", "card1"],  # debit at the threshold (not over it), credit over it, credit under it
)
def test_other_card_changes_need_no_authentication(card: str) -> None:
    asked: list[str] = []
    _, service = chat(interp(card=card), YES, service=recording_service(asked))

    assert asked == []
    assert service.plan.card_id == card


def test_failed_authentication_keeps_card() -> None:
    out, service = chat(interp(card="card3"), YES, service=make_service(lambda _: False))

    assert out[1].startswith("I couldn't make that change. Extra authentication failed.")
    assert service.plan.card_id == "card2"


def test_revising_to_a_card_without_the_need_drops_authentication() -> None:
    asked: list[str] = []
    out, service = chat(interp(card="card3"), interp(card="card1", reply=Reply.NO), YES, service=recording_service(asked))

    assert out[1].endswith("to your Visa credit card ending 4242? (yes/no)")
    assert asked == []
    assert service.plan.card_id == "card1"


def test_unknown_card_asks_which_card() -> None:
    out, service = chat(interp(Intent.CHANGE_CARD, card="card9"), interp(card="card1"), YES)

    assert out[0].startswith("Which card should the payment be made with? (your Visa credit card ending 4242;")
    assert service.plan.card_id == "card1"


def test_declined_card_change_leaves_card() -> None:
    out, service = chat(interp(card="card3"), NO)

    assert out[1].startswith("Okay, I left your payment card at your Mastercard debit card ending 5454.")
    assert service.plan.card_id == "card2"


def test_backend_rejects_card_not_on_file() -> None:
    stranger = Card(id="card1", kind=CardKind.DEBIT, network="Visa", last_four="0000", payment_limit=Decimal("1"))
    with pytest.raises(PolicyViolation):
        make_service().set_card(stranger)


def test_trace_line_colors_llm_operators_pink_and_others_blue() -> None:
    llm = trace_line("interpret", ["wrap_up"], uses_llm=True)
    other = trace_line("show_plan", [], uses_llm=False)

    assert llm.plain == "  ⟳ interpret (llm)   also: wrap_up" and llm.style == LLM_STYLE
    assert other.plain == "  ⟳ show_plan" and other.style == OPERATOR_STYLE


def test_trace_shows_each_cycle() -> None:
    tracer = RichConsole(Console(record=True, width=200))
    console = ScriptedConsole([ACCT, "utterance 0"])
    with patch("payments.operators.LLMInterpreter", return_value=FakeInterpreter((interp(Intent.VIEW_PLAN),))):
        agent = build_agent(console, make_service(), clock=lambda: TODAY)
    stop = tracer.trace(agent)
    try:
        run(agent)
    finally:
        stop()

    chosen = [line.split()[1] for line in tracer.out.export_text().splitlines()]
    assert chosen == ["fetch_customer", "greet", "accept_account_number", "interpret", "show_plan", "wrap_up", "say_goodbye"]


def test_backend_changes_without_authentication() -> None:
    service = make_service(lambda _: False)
    service.set_amount(Decimal("75"))
    assert service.plan.amount == Decimal("75")
    with pytest.raises(AuthenticationFailed):
        service.require_authentication("change your payment amount")


def test_account_number_immutable() -> None:
    plan = PaymentPlan(account_number=ACCT, amount=Decimal("1"), payment_date=TODAY, card_id="card1")
    with pytest.raises(ValidationError):
        plan.account_number = "0000"  # type: ignore[misc]


def test_plan_must_belong_to_the_customer() -> None:
    with pytest.raises(ValueError):
        BankPaymentService(CUSTOMER, PaymentPlan(account_number="0000", amount=Decimal("1"), payment_date=TODAY, card_id="card1"))


def test_plan_card_must_be_the_customers() -> None:
    with pytest.raises(ValueError, match="card9"):
        BankPaymentService(CUSTOMER, PaymentPlan(account_number=ACCT, amount=Decimal("1"), payment_date=TODAY, card_id="card9"))


def test_customer_file_loads() -> None:
    customer, plan = load_account()
    assert customer.account_number and customer.cards
    assert plan.account_number == customer.account_number


def test_relative_payment_date(tmp_path) -> None:
    path = tmp_path / "customer.json"
    path.write_text(CUSTOMER.model_dump_json()[:-1] + ', "plan": {"amount": "250.00", "payment_in_days": 14, "card_id": "card1"}}')
    _, plan = load_account(path, today=lambda: TODAY)

    assert plan.payment_date == date(2026, 10, 22)


def test_account_read_from_json(tmp_path) -> None:
    path = tmp_path / "customer.json"
    path.write_text(
        CUSTOMER.model_dump_json()[:-1] + ', "plan": {"amount": "250.00", "payment_date": "2026-10-22", "card_id": "card2"}}'
    )
    customer, plan = load_account(path)

    assert customer == CUSTOMER
    assert plan == PaymentPlan(account_number=ACCT, amount=Decimal("250.00"), payment_date=date(2026, 10, 22), card_id="card2")


def test_invalid_customer_file_rejected(tmp_path) -> None:
    path = tmp_path / "customer.json"
    path.write_text(
        '{"name": "Sam Lee", "account_number": "1",'
        ' "cards": [{"id": "card1", "kind": "credit", "network": "Visa", "last_four": "42", "payment_limit": "1"}],'
        ' "plan": {"amount": "1", "payment_date": "2026-10-22", "card_id": "card1"}}'
    )
    with pytest.raises(ValidationError):
        load_account(path)


@pytest.fixture
def account_file(tmp_path):
    """A copy of the shipped customer.json, and the service that saves to it"""

    path = tmp_path / "customer.json"
    path.write_text((Path(__file__).resolve().parent.parent / "customer.json").read_text())
    return path, BankPaymentService.from_file(path, today=lambda: TODAY, authenticate=lambda _: True)


def test_amount_and_card_changes_saved_keeping_relative_date(account_file) -> None:
    path, service = account_file
    service.set_amount(Decimal("75"))
    service.set_card(service.get_customer().cards[0])

    saved = json.loads(path.read_text())["plan"]
    assert saved == {"amount": "75.00", "payment_in_days": 14, "card_id": service.get_customer().cards[0].id}
    assert load_account(path, today=lambda: TODAY)[1] == service.plan


def test_date_change_saved_as_fixed_date(account_file) -> None:
    path, service = account_file
    service.set_date(date(2026, 10, 20))

    saved = json.loads(path.read_text())["plan"]
    assert saved["payment_date"] == "2026-10-20" and "payment_in_days" not in saved
    assert load_account(path, today=lambda: date(2027, 1, 1))[1].payment_date == date(2026, 10, 20)


def test_refused_change_not_saved(account_file) -> None:
    path, service = account_file
    before = path.read_text()
    with pytest.raises(PolicyViolation):
        service.set_amount(Decimal("-1"))

    assert path.read_text() == before


def test_conversation_saves_to_account_file(account_file) -> None:
    path, service = account_file
    chat(interp(amount="75"), YES, service=service)

    assert json.loads(path.read_text())["plan"]["amount"] == "75.00"
    assert not path.with_name("customer.json.tmp").exists()


def test_customer_fetched_from_the_service_when_the_session_starts() -> None:
    service = make_service()
    calls: list[str] = []
    get_customer = service.get_customer
    service.get_customer = lambda: calls.append("get_customer") or get_customer()  # type: ignore[method-assign]

    console = ScriptedConsole([ACCT])
    with patch("payments.operators.LLMInterpreter", return_value=FakeInterpreter(())):
        agent = build_agent(console, service, clock=lambda: TODAY)
    state = run(agent)

    assert calls == ["get_customer"]  # queried once, before the greeting
    assert state.customer == CUSTOMER and console.said[1].startswith("Thanks, Sam Lee.")


def test_customer_unavailable_before_it_is_fetched() -> None:
    with pytest.raises(RuntimeError):
        PaymentState().customer


def test_customer_is_immutable() -> None:
    with pytest.raises(ValidationError):
        CUSTOMER.account_number = "0000"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        Card(id="card1", kind=CardKind.CREDIT, network="Visa", last_four="42", payment_limit=Decimal("100"))
    with pytest.raises(ValidationError):
        Card(id="card1", kind="prepaid", network="Visa", last_four="4242", payment_limit=Decimal("100"))  # type: ignore[arg-type]


def test_card_ids_unique_and_found_by_id() -> None:
    assert CUSTOMER.card("card2") == CUSTOMER.cards[1] and CUSTOMER.card("card2").kind is CardKind.DEBIT  # type: ignore[union-attr]
    assert CUSTOMER.card("nope") is None
    with pytest.raises(ValidationError):
        Customer(name="Sam Lee", account_number=ACCT, cards=(CUSTOMER.cards[0], CUSTOMER.cards[0]))


def test_backend_enforces_policy_independently() -> None:
    service = make_service()
    with pytest.raises(PolicyViolation):
        service.set_amount(Decimal("-1"))
    with pytest.raises(PolicyViolation):
        service.set_date(date(2027, 1, 1))
