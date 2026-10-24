"""
The payment policy, encoded as data.

Each plan term has an ordered tuple of rules, and each rule is a tuple
``(must_be, limit, message)``: the term's new value must compare to the
limit as ``must_be`` says, or the change is refused with ``message``.
Limits are resolved from the ``[policy]`` settings in config.toml and
today's date; ``{placeholders}`` in messages are filled the same way.
Nothing about the policy is hard-coded elsewhere.

Both the agent (before proposing a change) and the payment system
(before making one) check these rules, so the backend never relies on
the agent having checked.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from decimal import Decimal
from enum import StrEnum
from operator import ge, gt, le
from typing import Any

from pydantic import BaseModel, Field

from .config import load_config

# ===


class PolicySettings(BaseModel):
    """Limits on plan changes"""

    max_amount: Decimal = Field(Decimal("10000.00"), gt=0, description="largest allowed payment amount")
    date_window_days: int = Field(
        30, gt=0, description="payments may be scheduled from tomorrow up to this many days out"
    )
    max_verification_attempts: int = Field(
        3, gt=0, description="tries to restate the account number before the session ends"
    )
    authenticate_debit_limit_over: Decimal = Field(
        Decimal("5000.00"),
        ge=0,
        description="switching the payment card to a debit card with a higher limit needs extra authentication",
    )

    def limits(self, today: date) -> dict[Limit, Any]:
        """The value of each limit, as of today"""

        return {
            Limit.ZERO: Decimal("0"),
            Limit.MAX_AMOUNT: self.max_amount,
            Limit.CENT: Decimal("0.01"),
            Limit.TOMORROW: today + timedelta(days=1),
            Limit.LAST_DAY: today + timedelta(days=self.date_window_days),
        }

    def message_values(self, today: date) -> dict[str, str]:
        """``{placeholder}`` values used in rule messages"""

        limits = self.limits(today)
        return {
            "today": day(today),
            "max_amount": money(self.max_amount),
            "date_window_days": str(self.date_window_days),
            "last_day": day(limits[Limit.LAST_DAY]),
        }


def load_policy_settings() -> PolicySettings:
    """The ``[policy]`` table of config.toml (defaults for anything missing)"""

    return PolicySettings.model_validate(load_config().get("policy", {}))


# === how values are written in messages


def money(amount: Decimal) -> str:
    """``$1,234.50``"""

    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"


def day(d: date) -> str:
    """``Fri, Oct 23, 2026``"""

    return d.strftime("%a, %b %-d, %Y")


# === the rules


class Term(StrEnum):
    """A plan term the user can change (named as on ``PaymentPlan``)"""

    AMOUNT = "amount"
    PAYMENT_DATE = "payment_date"
    CARD = "card_id"


class Limit(StrEnum):
    """A value rules compare against (see :meth:`PolicySettings.limits`)"""

    ZERO = "zero"
    MAX_AMOUNT = "max_amount"
    CENT = "cent"
    TOMORROW = "tomorrow"
    LAST_DAY = "last_day"


def multiple_of(value: Decimal, step: Decimal) -> bool:
    """``value`` is a whole number of ``step``s"""

    return value % step == 0


type Rule = tuple[Callable[[Any, Any], bool], Limit, str]
"""(must_be, limit, message): the value must satisfy ``must_be(value, limit)``, else ``message``"""


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
    Term.CARD: (),  # any card on file (the agent only proposes those; the payment system re-checks)
}
"""The payment policy: term -> rules, checked in order"""


def violation(term: Term, value: Any, today: date, policy: PolicySettings) -> str | None:
    """Why the new value breaks policy (the first rule it breaks), or ``None`` if it doesn't"""

    limits = policy.limits(today)
    for must_be, limit, message in POLICY[term]:
        if not must_be(value, limits[limit]):
            return message.format(**policy.message_values(today))
    return None


def date_window(today: date, policy: PolicySettings) -> tuple[date, date]:
    """Earliest and latest allowed payment dates"""

    limits = policy.limits(today)
    return limits[Limit.TOMORROW], limits[Limit.LAST_DAY]
