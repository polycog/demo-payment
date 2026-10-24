"""
Language understanding: the ONLY place an LLM is used.

``LLMInterpreter`` turns one utterance into an :class:`Interpretation`:
the tasks the user asks for, any amount, date or card they state, and
their answer to a pending yes/no question. Interpretations are only inputs:
the LLM never changes the plan or decides what happens next -- operators
do that, and every change needs the user's explicit yes.
The model comes from the ``[llm]`` profile in config.toml (``load_model``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from cognition import DocEnum, ModelPopulator
from pydantic import BaseModel, Field
from pydantic_ai.models import Model, infer_model
from pydantic_ai.models.openai import OpenAIChatModel, OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from .config import load_config
from .bank_payment_service import Card, PaymentPlan

# ===


def load_model() -> Model:
    """
    The model for the config.toml ``[llm]`` profile named by ``use``:
    an OpenAI-compatible server if it sets ``base_url``, else a pydantic-ai model id
    """

    llm = load_config()["llm"]
    profile = llm["profiles"][llm["use"]]
    if base_url := profile.get("base_url"):
        api_key = os.environ.get(profile.get("api_key_env", ""), "not-needed")
        model_class = OpenAIResponsesModel if profile.get("responses") else OpenAIChatModel
        return model_class(profile["model"], provider=OpenAIProvider(base_url=base_url, api_key=api_key))
    return infer_model(profile["model"])


class Intent(DocEnum):
    """A task the user wants performed"""

    VIEW_PLAN = (
        "view_plan",
        "see or ask about the current payment plan"
        " (e.g., 'what is my plan', 'how much do I pay', 'when is it sent', 'my account number')",
    )
    CHANGE_AMOUNT = "change_amount", "change how much is paid"
    CHANGE_DATE = "change_date", "change when the payment is sent"
    CHANGE_CARD = "change_card", "change which card the payment is made with (the payment method)"


class Reply(DocEnum):
    """Answer to a pending yes/no confirmation question"""

    YES = "yes", "agrees / confirms"
    NO = "no", "declines / cancels / never mind"


class Interpretation(BaseModel):
    """Interpretation of a single user utterance"""

    intents: list[Intent] = Field(
        description="every task the user asks for, in the order mentioned; empty if none"
    )
    amount: Decimal | None = Field(
        description="payment amount the user states, exactly as said (keep sign); null if none"
    )
    payment_date: date | None = Field(
        description="payment date the user states, looked up in the calendar; null if none"
    )
    card_id: str | None = Field(
        description="id of the card the user wants to pay with, from 'Cards on file'; null if none"
    )
    reply: Reply | None = Field(
        description="answer to a pending yes/no question; null if not answering one"
    )


@dataclass(frozen=True)
class InterpretRequest:
    """An utterance plus the context needed to interpret it"""

    utterance: str
    today: date
    last_message: str | None
    current_plan: PaymentPlan
    cards: tuple[Card, ...]


class LLMInterpreter:
    """Utterance -> :class:`Interpretation`"""

    timeout_secs = 60
    """per LLM call"""

    calendar_days = 45
    """days in the date lookup table (small models are unreliable at date math)"""

    populator = ModelPopulator(
        Interpretation,
        task_desc="You interpret messages sent to a payment plan assistant.",
    )

    def __init__(self) -> None:
        self.llm = load_model()

    @property
    def model_name(self) -> str:
        return self.llm.model_name

    def interpret(self, req: InterpretRequest) -> Interpretation:
        """Raises if the model fails"""

        return self.populator(req.utterance, self.llm, *self._context(req), timeout_secs=self.timeout_secs)

    def _context(self, req: InterpretRequest) -> list[str]:
        calendar = "; ".join(
            f"{d:%a %b %d} = {d.isoformat()}"
            for d in (req.today + timedelta(days=i) for i in range(self.calendar_days))
        )

        extra = [
            f"Current payment amount: {req.current_plan.amount}",
            f"Current payment date: {req.current_plan.payment_date:%A %Y-%m-%d}",
            f"Current payment card: {req.current_plan.card_id}",
            "Cards on file: "
            + "; ".join(f"{c.id} = {c.network} {c.kind} ending {c.last_four}" for c in req.cards),
            f"Today is {req.today:%A %Y-%m-%d}",
            f"Calendar: {calendar}",
        ]
        if req.last_message:
            extra.append(f"The assistant's previous message was: {req.last_message}")

        return extra
