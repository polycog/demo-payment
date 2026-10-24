"""
The simulated bank payment service: it reads the customer and their plan
from the account file (``customer.json``), answers the agent's queries,
and is the only way to change the plan, saving every change back to the
file.

Its API, as the agent sees it:

* :meth:`BankPaymentService.get_customer`: the account holder, queried
  when the session starts
* :attr:`BankPaymentService.plan`: the plan of record
* ``set_amount`` / ``set_date`` / ``set_card``: change the plan, after
  re-checking the policy independently of the agent (raising
  :class:`PolicyViolation`)
* :meth:`BankPaymentService.require_authentication`: extra authentication,
  which the agent asks for when an operator marks a proposal as needing it
  (raising :class:`AuthenticationFailed`)
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from getpass import getpass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import DEFAULT_CONFIG_PATH, load_config
from .policy import PolicySettings, Term, load_policy_settings, violation

# ===


class CardKind(StrEnum):
    """How a card pays"""

    CREDIT = "credit"
    DEBIT = "debit"


class Card(BaseModel):
    """A card on file (only the last four digits are kept)"""

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1, description="identifies the card among the customer's cards")
    kind: CardKind = Field(description="credit or debit")
    network: str = Field(description="card network, e.g. 'Visa'")
    last_four: str = Field(pattern=r"^\d{4}$", description="last four digits of the card number")
    payment_limit: Decimal = Field(gt=0, description="largest single payment allowed on this card")


class Customer(BaseModel):
    """The account holder"""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="account holder's name")
    account_number: str = Field(description="immutable account identifier")
    cards: tuple[Card, ...] = Field(default=(), description="cards on file")

    @model_validator(mode="after")
    def _unique_card_ids(self) -> Customer:
        ids = [c.id for c in self.cards]
        if len(ids) != len(set(ids)):
            raise ValueError(f"card ids must be unique: {ids}")
        return self

    def card(self, card_id: str) -> Card | None:
        """The card with this id (``None`` if there is none)"""

        return next((c for c in self.cards if c.id == card_id), None)

    def is_account_number(self, text: str) -> bool:
        """``text`` states this customer's account number (only its digits are compared)"""

        return re.sub(r"\D", "", text) == re.sub(r"\D", "", self.account_number)


CUSTOMER_FILE = DEFAULT_CONFIG_PATH.parent / load_config().get("customer_file", "customer.json")
"""where the account holder and their plan are read from (``customer_file`` in config.toml)"""


class PaymentPlan(BaseModel):
    """A customer's scheduled payment"""

    model_config = ConfigDict(validate_assignment=True)

    account_number: str = Field(frozen=True, description="immutable account identifier")
    amount: Decimal = Field(description="how much is paid")
    payment_date: date = Field(description="when the payment is sent")
    card_id: str = Field(description="id of the customer's card the payment is made with")


def check_plan(customer: Customer, plan: PaymentPlan) -> None:
    """Raises ``ValueError`` unless the plan is for the customer's account and one of their cards"""

    if plan.account_number != customer.account_number:
        raise ValueError(f"plan is for account {plan.account_number}, not {customer.account_number}")

    if customer.card(plan.card_id) is None:
        raise ValueError(f"plan's card {plan.card_id!r} is not one of the customer's cards")


def load_account(
    path: Path = CUSTOMER_FILE, today: Callable[[], date] = date.today
) -> tuple[Customer, PaymentPlan]:
    """
    The account holder and their plan, from a JSON file: the customer's
    fields, plus a ``plan`` object whose account number is the customer's
    (raises if missing or invalid). The plan gives its amount, the ``card_id``
    of the customer's card it is paid with, and when the
    payment is sent as ``payment_in_days`` (days from today, so the demo
    never goes stale) or a fixed ``payment_date``.
    """

    data = json.loads(path.read_text())
    plan = data.pop("plan")
    if "payment_in_days" in plan:
        plan["payment_date"] = today() + timedelta(days=int(plan.pop("payment_in_days")))

    customer = Customer.model_validate(data)
    payment_plan = PaymentPlan.model_validate({**plan, "account_number": customer.account_number})
    check_plan(customer, payment_plan)
    return customer, payment_plan


def save_plan(path: Path, plan: PaymentPlan, date_changed: bool) -> None:
    """
    Write the plan back into the account file, leaving the rest of the file
    as it is. A relative ``payment_in_days`` is kept unless the date itself
    was changed, which is then stored as a fixed ``payment_date``. The file
    is replaced in one step, so a failed write can't leave it half-written.
    """

    data = json.loads(path.read_text())
    entry = data["plan"]
    entry["amount"] = f"{plan.amount:.2f}"
    entry["card_id"] = plan.card_id
    if date_changed:
        entry.pop("payment_in_days", None)
        entry["payment_date"] = plan.payment_date.isoformat()

    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)


class PolicyViolation(ValueError):
    """A requested change breaks a payment policy"""


class AuthenticationFailed(Exception):
    """The user failed the extra authentication a change requires"""


KEY_PHRASE = "neurosymbolic"
"""what the simulated extra-authentication prompt accepts"""


def ask_key_phrase(purpose: str) -> bool:
    """Extra authentication at the terminal: did the user type the key phrase?"""

    print()
    print(f"== EXTRA AUTHENTICATION REQUIRED to {purpose} ==")
    ok = getpass(f"Enter key phrase (`{KEY_PHRASE}` if you want to succeed): ") == KEY_PHRASE
    print("Success :)" if ok else "Failure :(")
    print("===================================")
    print()
    return ok


class BankPaymentService:
    """Stand-in for the bank's system of record"""

    @classmethod
    def from_file(
        cls,
        account_file: Path = CUSTOMER_FILE,
        today: Callable[[], date] = date.today,
        policy: PolicySettings | None = None,
        authenticate: Callable[[str], bool] = ask_key_phrase,
    ) -> BankPaymentService:
        """The service for the account in ``account_file``, saving every change back to it"""

        customer, plan = load_account(account_file, today)
        return cls(customer, plan, today, policy, authenticate, account_file=account_file)

    def __init__(
        self,
        customer: Customer,
        plan: PaymentPlan,
        today: Callable[[], date] = date.today,
        policy: PolicySettings | None = None,
        authenticate: Callable[[str], bool] = ask_key_phrase,
        account_file: Path | None = None,
    ) -> None:
        """
        :param account_file: where to save each change (``None``: keep changes in memory only)
        """

        check_plan(customer, plan)

        self._customer = customer
        self._plan = plan
        self._today = today
        self._policy = policy or load_policy_settings()
        self._authenticate = authenticate
        self._authenticated = False
        self._account_file = account_file
        self._date_changed = False

    def get_customer(self) -> Customer:
        """The account holder: name, account number, and cards on file"""

        return self._customer

    @property
    def plan(self) -> PaymentPlan:
        """A copy of the current plan"""

        return self._plan.model_copy()

    def set_amount(self, amount: Decimal) -> PaymentPlan:
        """Change the payment amount; raises :class:`PolicyViolation` if not allowed"""

        if issue := violation(Term.AMOUNT, amount, self._today(), self._policy):
            raise PolicyViolation(issue)

        self._plan.amount = amount
        print("API CALLED: SET AMOUNT")
        self._save()
        return self.plan

    def set_card(self, card: Card) -> PaymentPlan:
        """Change the card the payment is made with; raises :class:`PolicyViolation` if it isn't on file"""

        if self._customer.card(card.id) != card:
            raise PolicyViolation("That card is not on file.")

        self._plan.card_id = card.id
        print("API CALLED: SET CARD")
        self._save()
        return self.plan

    def set_date(self, payment_date: date) -> PaymentPlan:
        """Change the payment date; raises :class:`PolicyViolation` if not allowed"""

        if issue := violation(Term.PAYMENT_DATE, payment_date, self._today(), self._policy):
            raise PolicyViolation(issue)

        self._plan.payment_date = payment_date
        self._date_changed = True
        print("API CALLED: SET DATE")
        self._save()
        return self.plan

    def _save(self) -> None:
        """Save the plan to the account file, if there is one"""

        if self._account_file is not None:
            save_plan(self._account_file, self._plan, self._date_changed)

    def require_authentication(self, purpose: str) -> None:
        """
        Extra authentication, once per session (later calls pass)

        :param purpose: what it is for, shown to the user (e.g. "change your payment amount")
        :raises AuthenticationFailed: the user failed it
        """

        if self._authenticated:
            return

        if not self._authenticate(purpose):
            raise AuthenticationFailed("Extra authentication failed.")

        self._authenticated = True
