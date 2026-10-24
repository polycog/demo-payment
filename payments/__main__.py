"""
Run the payment-plan assistant:  python -m payments [--trace]

``--trace`` prints, each decision cycle, the operator chosen (pink if it
calls the LLM, blue otherwise) and the others that applied. All settings
come from ``config.toml``.
"""

from __future__ import annotations

import argparse

from rich.panel import Panel

from .agent import build_agent, run
from .console import RichConsole
from .language import load_model
from .bank_payment_service import BankPaymentService


def main() -> None:
    parser = argparse.ArgumentParser(description="Payment-plan assistant")
    parser.add_argument("--trace", action="store_true", help="show each decision-process choice")
    args = parser.parse_args()

    console = RichConsole()

    console.out.print(Panel(
        "Payment-plan assistant\n"
        "[dim]Shows your plan and changes its amount, date or card, only after you confirm.[/]\n"
        f"[dim]Language model: {load_model().model_name}[/]",
        border_style="cyan",
    ))

    service = BankPaymentService.from_file()  # reads customer.json, and saves changes back to it

    agent = build_agent(console, service)
    if args.trace:
        console.trace(agent)

    run(agent)


if __name__ == "__main__":
    main()
