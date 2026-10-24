"""draws the payment-plan assistant's decision process, operator by operator, with the calls each operator makes
to the bank payment service's APIs (the cogent's tools)

the text on the figure is written here by hand from the operators' WHEN/THEN docstrings, so redraw it after
changing an operator:

    uv run python design_docs/figures/draw.py

writes decision-process.svg next to this script, or into the directory given as the first argument; uses only the
standard library
"""

import sys
import textwrap
from html import escape
from pathlib import Path

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent

SANS = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

INK, MUTED, FAINT, LINE = "#0f172a", "#475569", "#64748b", "#94a3b8"
BANK, BANK_BG, BANK_LINE = "#15803d", "#f0fdf4", "#86efac"
BADGES = {
    "llm": ("#ede9fe", "#6d28d9"),
    "bank": ("#dcfce7", "#15803d"),
    "turn": ("#fef3c7", "#b45309"),
    "flag": ("#fce7f3", "#be185d"),
}
CHAR = 6.5  # width of a 12px sans character, generously


def wrap(text: str, width: float, char: float = CHAR) -> list[str]:
    return textwrap.wrap(text, max(8, int(width / char)))


class Box:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h

    @property
    def cy(self):
        return self.y + self.h / 2

    @property
    def right(self):
        return self.x + self.w


class Fig:
    def __init__(self, width: int, title: str, subtitle: str):
        self.w = width
        self.parts: list[str] = []
        self.overlay: list[str] = []
        self.bottom = 0
        self.text(24, 36, title, 20, INK, weight="700")
        y = 60
        for line in wrap(subtitle, width - 48, 7.0):
            self.text(24, y, line, 13, MUTED)
            y += 18
        self.top = y + 8

    # --- primitives

    def text(self, x, y, s, size=12, fill=INK, weight="400", family=SANS, anchor="start", italic=False, layer=None):
        style = ' font-style="italic"' if italic else ""
        (layer if layer is not None else self.parts).append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{style}>{escape(s)}</text>'
        )

    def rect(self, x, y, w, h, fill="#fff", stroke=LINE, rx=8, dash=None, width=1.2):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{width}"{d}/>'
        )
        self.bottom = max(self.bottom, y + h)

    def badges(self, x, y, items):
        cx = x
        for kind, label in items:
            bw = len(label) * 6.1 + 16
            bg, fg = BADGES[kind]
            self.rect(cx, y, bw, 19, fill=bg, stroke=bg, rx=9.5)
            self.text(cx + 8, y + 13.5, label, 11, fg, weight="600")
            cx += bw + 6

    def arrow(self, points, color=FAINT, dash=False, marker="head"):
        d = "M " + " L ".join(f"{px:.1f} {py:.1f}" for px, py in points)
        da = ' stroke-dasharray="5 4"' if dash else ""
        self.overlay.append(
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.6"{da} marker-end="url(#{marker})"/>'
        )

    # --- composites

    @staticmethod
    def card_height(w, when, then, badges) -> float:
        lines = len(wrap(when, w - 70)) + len(wrap(then, w - 70))
        return 30 + lines * 16 + 12 + 14 + (26 if badges else 0)

    def card(self, x, y, w, h, name, when, then, badges=()) -> Box:
        """an operator: its name, WHEN it applies and THEN what it does, and badges for what it uses"""
        self.rect(x, y, w, h, fill="#f8fafc", stroke=LINE)
        self.parts.append(
            f'<path d="M {x} {y + 26} V {y + 8} a 8 8 0 0 1 8 -8 H {x + w - 8} a 8 8 0 0 1 8 8 V {y + 26} Z" '
            f'fill="#e2e8f0"/>'
        )
        self.text(x + 12, y + 18, name, 12.5, INK, weight="700", family=MONO)
        cy = y + 46
        for label, text in (("WHEN", when), ("THEN", then)):
            self.text(x + 12, cy, label, 10, FAINT, weight="700")
            for line in wrap(text, w - 70):
                self.text(x + 58, cy, line, 12, INK)
                cy += 16
            cy += 6
        if badges:
            self.badges(x + 12, y + h - 29, badges)
        return Box(x, y, w, h)

    def note(self, x, y, w, title, steps) -> Box:
        """a dashed reference box: a title and numbered steps, as tall as its text"""
        lines = [(i + 1, j, line) for i, step in enumerate(steps) for j, line in enumerate(wrap(step, w - 50, 6.4))]
        h = 34 + len(lines) * 16 + 4 * len(steps) + 8
        self.rect(x, y, w, h, fill="#ffffff", stroke="#cbd5e1", dash="4 3")
        self.text(x + 14, y + 22, title, 12, INK, weight="700")
        cy = y + 44
        for n, j, line in lines:
            if j == 0:
                cy += 4 if n > 1 else 0
                self.text(x + 14, cy, f"{n}.", 11.5, FAINT, weight="700")
            self.text(x + 32, cy, line, 11.5, MUTED)
            cy += 16
        return Box(x, y, w, h)

    def section(self, x, y, w, title, note):
        self.text(x, y, title, 12, FAINT, weight="700")
        self.parts.append(f'<line x1="{x}" y1="{y + 8}" x2="{x + w}" y2="{y + 8}" stroke="#e2e8f0" stroke-width="1"/>')
        self.text(x + len(title) * 8.4 + 12, y, note, 11.5, MUTED, italic=True)

    def legend(self, y):
        x = 24
        self.text(x, y + 13.5, "Uses:", 11.5, MUTED, weight="600")
        x += 42
        for kind, label in (("llm", "language model"), ("bank", "bank payment service API"),
                            ("flag", "sets a state flag"), ("turn", "ends the turn")):
            bg, fg = BADGES[kind]
            bw = len(label) * 6.1 + 16
            self.rect(x, y, bw, 19, fill=bg, stroke=bg, rx=9.5)
            self.text(x + 8, y + 13.5, label, 11, fg, weight="600")
            x += bw + 8
        self.text(x + 8, y + 13.5, "Green arrows: tool calls to the bank payment service.", 11.5, MUTED, italic=True)

    def save(self, name: str):
        h = self.bottom + 28
        marker = (
            '<marker id="{id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            'orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{fill}"/></marker>'
        )
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{h:.0f}" '
            f'viewBox="0 0 {self.w} {h:.0f}" role="img" aria-label="{escape(name)}">\n'
            f"<defs>{marker.format(id='head', fill=FAINT)}{marker.format(id='bank', fill=BANK)}</defs>\n"
            f'<rect width="100%" height="100%" fill="#ffffff"/>\n'
            + "\n".join(self.parts + self.overlay)
            + "\n</svg>\n"
        )
        (OUT / name).write_text(svg)


# --- layout: three columns of operators, and the bank payment service on the right

W = 1240
COL_W = 276
COLS = (24, 24 + COL_W + 14, 24 + 2 * (COL_W + 14))
OPS_RIGHT = COLS[2] + COL_W
LANE = OPS_RIGHT + 24
BANK_X, BANK_W = 944, 272


def row(f: Fig, y: float, cards: dict[int, tuple]) -> tuple[dict[int, Box], float]:
    """draws one row of operator cards (column -> card spec), all as tall as the tallest; returns them and the
    bottom of the row"""
    h = max(Fig.card_height(COL_W, spec[1], spec[2], spec[3] if len(spec) > 3 else ()) for spec in cards.values())
    boxes = {col: f.card(COLS[col], y, COL_W, h, *spec) for col, spec in cards.items()}
    return boxes, y + h


def decision_process():
    f = Fig(W, "Payment-plan assistant  ·  the decision process",
            "Each cycle, every operator whose WHEN holds is proposed, and the one in the highest priority level "
            "runs; within a level, operators never apply together. Operators that need the bank call the bank "
            "payment service's APIs, its tools, which own customer.json. One user turn ends when an operator "
            "speaks to the user and waits for the next line.")
    f.legend(f.top)
    y = f.top + 44

    # --- a turn
    f.section(24, y, W - 48, "A TURN", "one cogent loop: the user's line is handled level by level")
    y += 22
    steps = [("the user's line", "#f1f5f9", INK), ("1 · INPUT", "#f1f5f9", INK), ("2 · SETTLE", "#f1f5f9", INK),
             ("3 · ASSESS", "#f1f5f9", INK), ("4 · ACT", "#f1f5f9", INK), ("speak, then listen", INK, "#ffffff")]
    sw, gap = 168, 34
    for i, (label, fill, fg) in enumerate(steps):
        x = 24 + i * (sw + gap)
        f.rect(x, y, sw, 34, fill=fill, stroke=INK if fill == INK else LINE, rx=17)
        f.text(x + sw / 2, y + 22, label, 12.5, fg, weight="700", anchor="middle")
        if i:
            f.arrow([(x - gap + 2, y + 17), (x - 3, y + 17)])
    f.arrow([(24 + 5 * (sw + gap) + sw / 2, y + 36), (24 + 5 * (sw + gap) + sw / 2, y + 52),
             (24 + sw / 2, y + 52), (24 + sw / 2, y + 38)], dash=True)
    f.text(24 + 2.5 * (sw + gap) + sw / 2, y + 66, "the next line starts the next turn", 11.5, MUTED,
           italic=True, anchor="middle")
    y += 96

    calls: list[tuple[Box, str]] = []  # (calling card, API it calls)

    # --- 1 · INPUT
    f.section(24, y, OPS_RIGHT - 24, "1 · INPUT", "the session, verification, and the LLM")
    y += 20
    b, y = row(f, y, {
        0: ("Greet", "the customer has been fetched, and the user hasn't been greeted",
            "greet the user and ask them to confirm their account number", [("turn", "ends turn")]),
        1: ("SayGoodbye", "the user left (an exit word, or closed the input)",
            "say any queued message and goodbye; end the session", [("turn", "ends session")]),
        2: ("FetchCustomer", "the session has just started, and no customer has been fetched",
            "query the bank for the customer: name, account number, cards", [("bank", "get_customer")]),
    })
    calls.append((b[2], "get_customer"))
    y += 14
    b, y = row(f, y, {
        0: ("AcceptAccountNumber", "the unverified user restated the account number (digits compared by code)",
            "mark them verified and say what the assistant can do", [("turn", "ends turn")]),
        1: ("RejectAccountNumber", "the unverified user said something else, and has tries left",
            "say it doesn't match, how many tries are left, and ask again", [("turn", "ends turn")]),
        2: ("Interpret", "the verified user said something not yet interpreted",
            "the LLM reads the tasks, any amount, date or card, and a yes/no; merge them into the agenda",
            [("llm", "language model"), ("bank", "plan")]),
    })
    calls.append((b[2], "plan"))
    y += 14
    b, y = row(f, y, {
        0: ("EndUnverifiedSession", "the unverified user said something else, on their last try",
            "explain the session can't continue, and end it", [("flag", "leaving")]),
        1: ("AskToRephrase", "the LLM couldn't interpret what the user said",
            "ask them to rephrase; pending tasks are kept", [("turn", "ends turn")]),
    })
    y += 34

    # --- 2 · SETTLE
    f.section(24, y, OPS_RIGHT - 24, "2 · SETTLE", "the user's yes/no to a proposal that still stands")
    y += 20
    b, y_after = row(f, y, {
        0: ("DeclineChange", "the user said no to a proposed change",
            "leave the plan as it is, and drop that change"),
        2: ("Authenticate", "the user said yes, and needs_authentication is set",
            "ask the bank to authenticate them; if they fail, keep the proposal and ask again",
            [("bank", "authenticate")]),
    })
    calls.append((b[2], "authenticate"))
    decline_bottom = b[0].y + b[0].h
    y = y_after + 14
    confirm_h = Fig.card_height(COL_W, "x" * 120, "x" * 150, [("bank", "")])
    confirm = f.card(COLS[2], y, COL_W, confirm_h,
                     "Confirm{Amount,Date,Card}Change",
                     "the user said yes to a proposed amount, date or card change, and no authentication is pending",
                     "ask the bank to make the change; if it refuses (policy re-check), forget the value and ask again",
                     [("bank", "set_amount / set_date / set_card")])
    calls.append((confirm, "set"))
    f.note(COLS[0], decline_bottom + 14, COL_W * 2 + 14, "A change, end to end", [
        "ProposeChange (4 · ACT) asks \"Change your X from A to B? (yes/no)\", and the turn ends.",
        "Next turn, Interpret reads the answer.",
        "Yes: Authenticate runs first if needs_authentication is set, then the Confirm operator for that "
        "change calls the bank.",
        "No: DeclineChange. A revised value voids the proposal, and it is proposed again.",
    ])
    y = confirm.y + confirm.h + 34

    # --- 3 · ASSESS
    f.section(24, y, OPS_RIGHT - 24, "3 · ASSESS", "what a change needs, before it is proposed")
    y += 20
    wide = COL_W * 2 + 14
    h = Fig.card_height(wide, "x" * 140, "x" * 100, [("flag", "")])
    f.card(COLS[0], y, wide, h, "RequireAuthenticationForHighLimitDebit",
           "the change in focus switches the payment card to a debit card whose limit is over $5,000 "
           "(authenticate_debit_limit_over), and it hasn't been proposed yet",
           "set needs_authentication, so Authenticate runs after the user says yes",
           [("flag", "needs_authentication")])
    assess_bottom = y + h
    y = assess_bottom + 34

    # --- 4 · ACT
    f.section(24, y, OPS_RIGHT - 24, "4 · ACT", "the agenda: the first task is in focus")
    y += 20
    _, y = row(f, y, {
        0: ("ShowPlan", "the user asked to see the plan (views jump the queue)",
            "describe the amount, date, account and card"),
        1: ("RequestValue", "the change in focus has no value yet",
            "ask for it (for a card, list the cards on file)", [("turn", "ends turn")]),
        2: ("RejectValue", "the value for the change in focus breaks the policy",
            "explain why, forget it, and ask again", [("turn", "ends turn")]),
    })
    y += 14
    _, y = row(f, y, {
        0: ("ProposeChange", "the change in focus has a valid value not yet put to the user",
            "ask \"Change your X from A to B? (yes/no)\"", [("turn", "ends turn")]),
        1: ("AwaitConfirmation", "the change was proposed, and the reply was neither yes nor no",
            "ask the same question again", [("turn", "ends turn")]),
        2: ("WrapUp", "the agenda is empty (the fallback)",
            "ask \"anything else?\", or offer help if nothing was done", [("turn", "ends turn")]),
    })

    # --- the bank payment service, with an API box beside each operator that calls it
    by_api = {api: box for box, api in calls}
    top = by_api["get_customer"].y - 6
    api_boxes: dict[str, Box] = {}

    def api(name, kind, call, does, cy, h=58):
        bx = Box(BANK_X + 14, cy - h / 2, BANK_W - 28, h)
        f.rect(bx.x, bx.y, bx.w, bx.h, fill="#ffffff", stroke=BANK_LINE, rx=6)
        f.text(bx.x + 10, bx.y + 18, name, 12, BANK, weight="700", family=MONO)
        f.text(bx.x + 10, bx.y + 34, call, 11, MUTED, family=MONO)
        f.text(bx.x + bx.w - 10, bx.y + 34, kind, 9.5, FAINT, weight="700", anchor="end")
        f.text(bx.x + 10, bx.y + 50, does, 11.5, INK)
        return bx

    json_y = confirm.y + confirm.h + 40
    panel_bottom = json_y + 92
    f.rect(BANK_X, top, BANK_W, panel_bottom - top, fill=BANK_BG, stroke=BANK, rx=12, width=1.6)
    f.text(BANK_X + 14, top + 24, "BankPaymentService", 14, BANK, weight="700", family=MONO)
    f.text(BANK_X + 14, top + 42, "bank_payment_service.py", 11, MUTED, family=MONO)
    f.text(BANK_X + 14, top + 58, "owns customer.json; its APIs are tools", 11.5, MUTED, italic=True)

    api_boxes["get_customer"] = api("get_customer()", "ACTUATOR", "io.o.get_customer", "the customer and cards",
                                    max(by_api["get_customer"].cy, top + 104))
    api_boxes["plan"] = api("plan", "SENSOR", "io.i.plan", "the plan of record, read every turn", by_api["plan"].cy)
    api_boxes["authenticate"] = api("require_authentication()", "ACTUATOR", "io.o.authenticate",
                                    "key phrase, once per session", by_api["authenticate"].cy)
    set_names = [("set_amount()", "io.o.set_amount"), ("set_date()", "io.o.set_date"), ("set_card()", "io.o.set_card")]
    for i, (name, call) in enumerate(set_names):
        api_boxes[name] = api(name, "ACTUATOR", call, "re-check policy, change, save",
                              confirm.y + 28 + i * 64, h=56)

    # customer.json
    jb = Box(BANK_X + 14, json_y, BANK_W - 28, 66)
    f.rect(jb.x, jb.y, jb.w, jb.h, fill="#ffffff", stroke=BANK, rx=6, width=1.4)
    f.parts.append(f'<ellipse cx="{jb.x + jb.w / 2:.1f}" cy="{jb.y:.1f}" rx="{jb.w / 2 - 1:.1f}" ry="7" '
                   f'fill="#ffffff" stroke="{BANK}" stroke-width="1.4"/>')
    f.text(jb.x + jb.w / 2, jb.y + 28, "customer.json", 12.5, INK, weight="700", family=MONO, anchor="middle")
    f.text(jb.x + jb.w / 2, jb.y + 46, "read at startup (from_file);", 11, MUTED, anchor="middle")
    f.text(jb.x + jb.w / 2, jb.y + 60, "saved after every change", 11, MUTED, anchor="middle")
    last = api_boxes["set_card()"]
    f.arrow([(jb.x + jb.w / 2, last.y + last.h + 2), (jb.x + jb.w / 2, jb.y - 9)], color=BANK, marker="bank")

    # tool calls: from each operator to the API it calls (the plan sensor flows the other way)
    def call(src: Box, dst: Box, sy=None, reverse=False):
        sy = src.cy if sy is None else sy
        pts = [(src.right + 2, sy), (LANE, sy), (LANE, dst.cy), (dst.x - 2, dst.cy)]
        f.arrow(list(reversed(pts)) if reverse else pts, color=BANK, marker="bank", dash=reverse)

    call(by_api["get_customer"], api_boxes["get_customer"])
    call(by_api["plan"], api_boxes["plan"], reverse=True)
    call(by_api["authenticate"], api_boxes["authenticate"])
    for i, (name, _) in enumerate(set_names):
        call(confirm, api_boxes[name], sy=confirm.y + confirm.h * (0.35 + 0.15 * i))

    f.save("decision-process.svg")


decision_process()
