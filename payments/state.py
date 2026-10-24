"""
Decision-process state: the plan as last read, the policy, and the
conversation so far -- an agenda of tasks still to do, details the user
has already given, and a change waiting on the user's yes/no.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import cast

from cognition import SelfReinitState

from .language import Intent, Interpretation, Reply
from .policy import PolicySettings, Term, load_policy_settings, violation
from .bank_payment_service import Card, Customer, PaymentPlan

# ===

type Detail = Decimal | date | Card
"""a value the user gave for a change: an amount, a date, or one of the customer's cards"""

TERMS: dict[Intent, Term] = {
    Intent.CHANGE_AMOUNT: Term.AMOUNT,
    Intent.CHANGE_DATE: Term.PAYMENT_DATE,
    Intent.CHANGE_CARD: Term.CARD,
}
"""the plan term each change intent changes"""

CHANGES: tuple[Intent, ...] = tuple(TERMS)
"""intents that change the plan (and so need a detail and a yes)"""

EXIT_WORDS = frozenset({"quit", "exit", "bye", "done"})
"""lines that end the session"""


@dataclass(frozen=True)
class Proposal:
    """A plan change awaiting the user's confirmation"""

    intent: Intent
    value: Detail


@dataclass
class PaymentState(SelfReinitState):
    """
    State of the conversation.

    As a :class:`SelfReinitState`, the same instance survives each
    decision-process restart, so one cogent loop = one user turn.
    """

    customer_record: Customer | None = None
    """the account holder, as returned by the bank payment service
    (``None`` until ``FetchCustomer`` queries it)"""

    policy: PolicySettings = field(default_factory=load_policy_settings)
    """limits on plan changes"""

    plan: PaymentPlan | None = None
    """the plan as last read from (or returned by) the payment system"""

    agenda: list[Intent] = field(default_factory=list)
    """tasks still to do; the first is in focus"""

    details: dict[Intent, Detail] = field(default_factory=dict)
    """values the user has given for changes not yet made"""

    proposal: Proposal | None = None
    """change put to the user, awaiting yes/no"""

    reply: Reply | None = None
    """the user's yes/no this turn (reset each turn)"""

    heard: str | None = None
    """what the user just said, not yet interpreted"""

    misunderstood: bool = False
    """the last utterance could not be interpreted"""

    greeted: bool = False
    """the user has been greeted"""

    verified: bool = False
    """the user restated the customer's account number"""

    failed_verifications: int = 0
    """times the user stated a wrong account number"""

    needs_authentication: bool = False
    """the pending proposal needs the payment system's extra authentication
    before it is carried out (set by any operator whose proposal needs it;
    amount and date changes don't)"""

    leaving: bool = False
    """the user asked to end the session"""

    closed: bool = False
    """the session has ended"""

    outbox: list[str] = field(default_factory=list)
    """what to say at the end of this turn"""

    last_message: str | None = None
    """what was said at the end of the last turn (context for the LLM)"""

    def _reinit(self) -> None:
        self.reply = None

    # === queries

    @property
    def customer(self) -> Customer:
        """The account holder (only once ``FetchCustomer`` has queried the bank payment service)"""

        if self.customer_record is None:
            raise RuntimeError("the customer hasn't been fetched from the bank payment service yet")
        return self.customer_record

    @property
    def focus(self) -> Intent | None:
        """The task being worked on"""

        return self.agenda[0] if self.agenda else None

    @property
    def focus_value(self) -> Detail | None:
        """The detail given for the change in focus (``None`` if not a change, or none given)"""

        return self.details.get(self.focus) if self.focus in CHANGES else None

    def violates_policy(self, today: date) -> str | None:
        """Why the detail for the change in focus breaks policy (``None`` if it doesn't, or there is none)"""

        value = self.focus_value
        if value is None:
            return None
        return violation(TERMS[cast(Intent, self.focus)], value, today, self.policy)

    @property
    def proposed(self) -> bool:
        """The change in focus, with its current detail, has been put to the user"""

        return self.focus is not None and self.proposal == Proposal(self.focus, self.focus_value)  # type: ignore[arg-type]

    @property
    def answer(self) -> Reply | None:
        """The user's yes/no to a proposal that still stands (revising its detail voids it)"""

        if self.proposal is None or self.details.get(self.proposal.intent) != self.proposal.value:
            return None
        return self.reply

    # === changes

    def hear(self, line: str | None) -> None:
        """Take the user's next line (``None`` if they left)"""

        if line is None or line.lower() in EXIT_WORDS:
            self.leaving = True
        else:
            self.heard = line

    def say(self, *lines: str) -> None:
        """Add to what is said at the end of this turn"""

        self.outbox.extend(lines)

    def absorb(self, interp: Interpretation) -> None:
        """
        Merge an interpretation into the agenda:

        * stated details are kept (and imply the matching change); a card
          is kept only if it is one of the customer's
        * a detail that revises a standing proposal voids it, along with
          any authentication it needed
        * plan views jump the queue (read-only, so safe to interleave)
        * other tasks queue in the order mentioned
        """

        card = self.customer.card(interp.card_id) if interp.card_id is not None else None
        intents = list(interp.intents)
        for intent, value in (
            (Intent.CHANGE_AMOUNT, interp.amount),
            (Intent.CHANGE_DATE, interp.payment_date),
            (Intent.CHANGE_CARD, card),
        ):
            if value is not None:
                self.details[intent] = value
                intents.append(intent)
                if self.proposal is not None and self.proposal.intent is intent and self.proposal.value != value:
                    self.needs_authentication = False

        for intent in dict.fromkeys(intents):
            if intent in self.agenda:
                continue
            if intent is Intent.VIEW_PLAN:
                self.agenda.insert(0, intent)
            else:
                self.agenda.append(intent)

        self.reply = interp.reply

    def forget(self, intent: Intent) -> None:
        """Drop the detail (and any proposal) for a change, so it is asked for again"""

        self.details.pop(intent, None)
        if self.proposal is not None and self.proposal.intent is intent:
            self.proposal = None
            self.reply = None
            self.needs_authentication = False

    def finish(self, intent: Intent) -> None:
        """Retire a completed or cancelled task"""

        self.agenda.remove(intent)
        self.forget(intent)
