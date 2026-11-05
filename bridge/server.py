"""The nurse worklist.

A single file web application on the Python standard library, so it runs with
no install step. Five names, a reason for each, the evidence one click away,
and an approval queue for anything about to reach a patient.
"""

import html
import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List

from . import config
from .store import Store

STORE: Store = None  # set in serve()

CSS = """
:root{--bg:#f4f7fb;--card:#fff;--ink:#161616;--muted:#5a6872;--line:#d6e0ef;
--blue:#0f62fe;--deep:#002d9c;--red:#da1e28;--redbg:#fff1f1;--amber:#8e6a03;
--amberbg:#fff8e1;--green:#0e6027;--greenbg:#defbe6;--purple:#6929c4}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}
header{background:var(--deep);color:#fff;padding:18px 24px}
header h1{margin:0;font-size:19px;letter-spacing:.2px}
header p{margin:4px 0 0;opacity:.8;font-size:13px}
.wrap{max-width:1100px;margin:0 auto;padding:22px 16px 60px}
.bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:16px}
.pill{background:#fff;border:1px solid var(--line);border-radius:999px;
padding:5px 13px;font-size:12.5px;color:var(--muted)}
.pill b{color:var(--ink)}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:16px 18px;margin-bottom:12px}
.row{display:flex;gap:14px;align-items:flex-start}
.rank{width:30px;height:30px;flex:none;border-radius:50%;background:var(--blue);
color:#fff;display:flex;align-items:center;justify-content:center;
font-weight:700;font-size:14px}
.rank.urgent{background:var(--red)}
.name{font-weight:650;font-size:16px}
.meta{color:var(--muted);font-size:12.5px;margin-top:2px}
.reason{margin-top:7px}
.tags{margin-top:9px;display:flex;gap:6px;flex-wrap:wrap}
.tag{font-size:11.5px;padding:3px 9px;border-radius:5px;background:#eef3fb;
color:var(--deep);border:1px solid var(--line)}
.tag.red{background:var(--redbg);color:var(--red);border-color:#ffb3b8}
.tag.green{background:var(--greenbg);color:var(--green);border-color:#a7f0ba}
.tag.amber{background:var(--amberbg);color:var(--amber);border-color:#f1c21b}
a.btn,button{font:inherit;font-size:13px;padding:7px 14px;border-radius:6px;
border:1px solid var(--blue);background:var(--blue);color:#fff;cursor:pointer;
text-decoration:none;display:inline-block}
a.btn.ghost,button.ghost{background:#fff;color:var(--blue)}
h2{font-size:15px;margin:22px 0 10px;color:var(--deep);
text-transform:uppercase;letter-spacing:.6px}
.banner{border-radius:10px;padding:12px 16px;margin-bottom:14px;font-size:14px}
.banner.red{background:var(--redbg);border:1px solid #ffb3b8;color:#750e13}
.banner.amber{background:var(--amberbg);border:1px solid #f1c21b;color:#6a4c02}
.banner.grey{background:#eef3fb;border:1px solid var(--line);color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:13.5px}
td,th{text-align:left;padding:7px 8px;border-bottom:1px solid var(--line);
vertical-align:top}
th{color:var(--muted);font-weight:600;font-size:12px;text-transform:uppercase}
.trail{font-size:13.5px}
.trail .ev{padding:9px 0;border-bottom:1px dashed var(--line)}
.trail .ev:last-child{border-bottom:none}
.who{font-size:11.5px;color:var(--muted);text-transform:uppercase;
letter-spacing:.5px}
form.inline{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
input[type=text]{font:inherit;padding:7px 10px;border:1px solid var(--line);
border-radius:6px;min-width:220px;flex:1}
.foot{color:var(--muted);font-size:12px;margin-top:26px;line-height:1.6}
@media(max-width:640px){.wrap{padding:14px 10px 50px}}
"""

DISCLAIMER = ("Bridge ranks and raises. It does not diagnose, it does not give "
              "clinical advice, and it never decides that a patient is safe. "
              "Synthetic data only.")


def esc(s: Any) -> str:
    return html.escape(str(s))


def page(title: str, body: str) -> bytes:
    return ("""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s</title><style>%s</style></head><body>
<header><h1>Bridge, post-discharge worklist</h1>
<p>FDU AI Experiential Learning Lab team &nbsp;&middot;&nbsp; IBM SkillsBuild AI Experiential Learning Lab</p></header>
<div class="wrap">%s<p class="foot">%s</p></div></body></html>"""
            % (esc(title), CSS, body, esc(DISCLAIMER))).encode()


def _age(day: int, ev_day: int) -> str:
    d = day - ev_day
    if d <= 0:
        return "today"
    if d == 1:
        return "yesterday"
    return "%d days ago" % d


def worklist_html() -> str:
    day = STORE.latest_cycle_day() or 0
    rows = STORE.ranking(day)
    cases = {c["patient_id"]: c for c in STORE.open_cases()}
    pending = STORE.pending_messages()
    degraded = any(r.get("degraded") for r in rows)

    out = []
    out.append('<div class="bar">'
               '<span class="pill">Cycle day <b>%d</b></span>'
               '<span class="pill">Cohort <b>%d</b></span>'
               '<span class="pill">Open cases <b>%d</b></span>'
               '<span class="pill">Awaiting approval <b>%d</b></span>'
               '<a class="btn ghost" href="/audit">Audit log</a>'
               '<a class="btn ghost" href="/approvals">Approvals</a>'
               '</div>' % (day, len(STORE.all_patients()), len(cases), len(pending)))

    if degraded:
        out.append('<div class="banner amber">This list is degraded. One or more '
                   'patients could not be assessed this cycle and have been raised '
                   'for manual review rather than skipped.</div>')

    urgent = [c for c in STORE.open_cases() if c["trigger"] == "urgent_reply"]
    if urgent:
        out.append('<div class="banner red"><b>%d urgent case%s open.</b> '
                   'Emergency guidance has been shown to the sender and these are '
                   'at the top of the list.</div>'
                   % (len(urgent), "" if len(urgent) == 1 else "s"))

    out.append("<h2>Call these first</h2>")
    if not rows:
        out.append('<div class="card">Nothing ranked yet. Run a cycle first.</div>')

    for row in rows[:config.WORKLIST_SIZE]:
        rec = STORE.get_patient(row["patient_id"])
        plan = STORE.get_plan(row["patient_id"])
        case = cases.get(row["patient_id"])
        is_urgent = bool(case and case["trigger"] == "urgent_reply")
        replies = STORE.replies_for(row["patient_id"])
        last_day = replies[-1]["day"] if replies else None

        tags = []
        if case:
            cls = "red" if is_urgent else "amber"
            tags.append('<span class="tag %s">%s</span>'
                        % (cls, esc(case["trigger"].replace("_", " "))))
        tags.append('<span class="tag">confidence %.2f</span>' % row["confidence"])
        tags.append('<span class="tag">%s</span>' % esc(
            plan["condition"].replace("_", " ")))
        if plan.get("acuity") == "high":
            tags.append('<span class="tag amber">high acuity</span>')
        for step in plan["steps"]:
            if step["status"] == "failed":
                tags.append('<span class="tag red">%s overdue</span>'
                            % esc(step["label"].lower()))

        out.append(
            '<div class="card"><div class="row">'
            '<div class="rank%s">%d</div><div style="flex:1">'
            '<div class="name">%s</div>'
            '<div class="meta">%s &middot; day %d after discharge &middot; '
            'last reply %s</div>'
            '<div class="reason">%s</div>'
            '<div class="tags">%s</div>'
            '<form class="inline" method="post" action="/action">'
            '<input type="hidden" name="patient_id" value="%s">'
            '<input type="hidden" name="day" value="%d">'
            '<input type="text" name="note" placeholder="What did you do?">'
            '<button name="action" value="called">Record call</button>'
            '<a class="btn ghost" href="/patient?id=%s">Evidence</a>'
            '</form></div></div></div>'
            % ("" if not is_urgent else " urgent", row["position"],
               esc(rec["name"]), esc(rec["age_band"]), day,
               _age(day, last_day) if last_day is not None else "none yet",
               esc(row["reason"]), "".join(tags), esc(row["patient_id"]), day,
               esc(row["patient_id"])))

    if len(rows) > config.WORKLIST_SIZE:
        out.append("<h2>Below the line (%d more ranked)</h2>" % (
            len(rows) - config.WORKLIST_SIZE))
        out.append('<div class="card"><table><tr><th>#</th><th>Patient</th>'
                   '<th>Reason</th><th>Conf</th></tr>')
        for row in rows[config.WORKLIST_SIZE:config.WORKLIST_SIZE + 12]:
            rec = STORE.get_patient(row["patient_id"])
            out.append('<tr><td>%d</td><td><a href="/patient?id=%s">%s</a></td>'
                       '<td>%s</td><td>%.2f</td></tr>'
                       % (row["position"], esc(row["patient_id"]),
                          esc(rec["name"]), esc(row["reason"]),
                          row["confidence"]))
        out.append("</table></div>")
    return "".join(out)


def patient_html(pid: str) -> str:
    rec = STORE.get_patient(pid)
    if not rec:
        return '<div class="card">No such patient.</div>'
    plan = STORE.get_plan(pid)
    day = STORE.latest_cycle_day() or 0
    interps = {i["reply_id"]: i for i in STORE.interpretations_for(pid)}

    out = ['<a class="btn ghost" href="/">Back to worklist</a>']
    out.append('<div class="card"><div class="name">%s</div>'
               '<div class="meta">%s &middot; %s &middot; discharged %s &middot; '
               '%s</div></div>'
               % (esc(rec["name"]), esc(rec["condition"].replace("_", " ")),
                  esc(rec["age_band"]), esc(rec["discharge_date"]),
                  "lives alone" if rec["lives_alone"] else "lives with others"))

    out.append("<h2>Plan</h2><div class='card'><table>"
               "<tr><th>Step</th><th>Due</th><th>Status</th></tr>")
    for s in plan["steps"]:
        cls = {"complete": "green", "failed": "red"}.get(s["status"], "")
        out.append('<tr><td>%s</td><td>day %d</td>'
                   '<td><span class="tag %s">%s</span></td></tr>'
                   % (esc(s["label"]), s["due_day"], cls, esc(s["status"])))
    out.append("</table></div>")

    out.append("<h2>Warning signs tracked, with their source</h2><div class='card'>")
    for w in plan["warning_signs"][:8]:
        out.append('<div class="ev"><div class="who">%s</div>%s</div>'
                   % (esc(w["source_id"]), esc(w["text"])))
    out.append("</div>")

    out.append("<h2>Evidence trail</h2><div class='card trail'>")
    events = []
    for m in STORE.messages_for(pid):
        events.append((m["day"], "bridge", "Asked: %s" % m["text"],
                       "%s, %s" % (m["probing_step"], m["status"])))
    for r in STORE.replies_for(pid):
        i = interps.get(r["reply_id"], {})
        extra = "concern %s, confidence %s%s" % (
            i.get("concern_level", "?"), i.get("confidence", "?"),
            ", ambiguous" if i.get("ambiguity_flag") else "")
        events.append((r["day"], r["author"], r["text"], extra))
    for c in STORE.cases_for(pid):
        events.append((c["day"], "escalation", "Case raised: %s" % c["trigger"],
                       c["evidence"]))
    for a in STORE.actions_for(pid):
        events.append((a["cycle_day"], "nurse", "%s. %s" % (a["action"], a["note"]),
                       a["recorded_at"]))
    for d, who, text, extra in sorted(events, key=lambda e: e[0]):
        out.append('<div class="ev"><div class="who">day %d &middot; %s</div>'
                   '%s<div class="meta">%s</div></div>'
                   % (d, esc(who), esc(text), esc(extra)))
    out.append("</div>")

    open_cases = [c for c in STORE.cases_for(pid) if c["closed_by"] is None]
    if open_cases:
        out.append("<h2>Open cases</h2>")
        for c in open_cases:
            out.append('<div class="card"><b>%s</b><div class="meta">%s</div>'
                       '<div class="reason">%s</div>'
                       '<form class="inline" method="post" action="/close">'
                       '<input type="hidden" name="case_id" value="%d">'
                       '<input type="hidden" name="patient_id" value="%s">'
                       '<input type="text" name="note" placeholder="Outcome of the call">'
                       '<button>Close case</button></form></div>'
                       % (esc(c["trigger"].replace("_", " ")), esc(c["evidence"]),
                          esc(c["recommended_action"]), c["case_id"], esc(pid)))
    return "".join(out)


def approvals_html() -> str:
    pending = STORE.pending_messages()
    out = ['<a class="btn ghost" href="/">Back to worklist</a>',
           '<div class="banner grey">Nothing reaches a patient without a nurse '
           'approving it. This is the approval queue.</div>']
    if not pending:
        out.append('<div class="card">Nothing waiting.</div>')
    for m in pending:
        rec = STORE.get_patient(m["patient_id"])
        out.append('<div class="card"><div class="name">%s</div>'
                   '<div class="meta">day %d &middot; %s</div>'
                   '<div class="reason">%s</div>'
                   '<form class="inline" method="post" action="/approve">'
                   '<input type="hidden" name="message_id" value="%d">'
                   '<button>Approve and send</button></form></div>'
                   % (esc(rec["name"]), m["day"], esc(m["timing_reason"]),
                      esc(m["text"]), m["message_id"]))
    return "".join(out)


def audit_html() -> str:
    out = ['<a class="btn ghost" href="/">Back to worklist</a>',
           '<div class="banner grey">Append only. Every message, rank change, '
           'escalation and nurse action is attributable.</div>',
           '<div class="card"><table><tr><th>When</th><th>Actor</th>'
           '<th>Event</th><th>Patient</th><th>Detail</th></tr>']
    for r in STORE.audit_tail(120):
        out.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>"
                   "<td>%s</td></tr>"
                   % (esc(r["at"][11:19]), esc(r["actor"]), esc(r["event"]),
                      esc(r["patient_id"] or ""),
                      esc(r["detail_json"][:120])))
    out.append("</table></div>")
    return "".join(out)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep the console readable during a demo
        pass

    def _send(self, body: bytes, code: int = 200):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, to: str):
        self.send_response(303)
        self.send_header("Location", to)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        if parsed.path == "/":
            self._send(page("Bridge worklist", worklist_html()))
        elif parsed.path == "/patient":
            self._send(page("Patient", patient_html(qs.get("id", [""])[0])))
        elif parsed.path == "/approvals":
            self._send(page("Approvals", approvals_html()))
        elif parsed.path == "/audit":
            self._send(page("Audit log", audit_html()))
        elif parsed.path == "/api/worklist":
            day = STORE.latest_cycle_day() or 0
            body = json.dumps({"day": day, "rows": STORE.ranking(day)},
                              indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._send(page("Not found", '<div class="card">Not found.</div>'), 404)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        form = urllib.parse.parse_qs(self.rfile.read(length).decode())
        path = urllib.parse.urlparse(self.path).path
        if path == "/action":
            STORE.record_action(form["patient_id"][0], int(form["day"][0]),
                                form.get("action", ["called"])[0],
                                form.get("note", [""])[0])
            self._redirect("/")
        elif path == "/approve":
            STORE.approve_message(int(form["message_id"][0]), "nurse")
            self._redirect("/approvals")
        elif path == "/close":
            STORE.close_case(int(form["case_id"][0]), "nurse",
                             form.get("note", [""])[0])
            self._redirect("/patient?id=%s" % form["patient_id"][0])
        else:
            self._redirect("/")


def serve(db_path=None, port: int = 8000):
    global STORE
    STORE = Store(db_path or config.DB_PATH)
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("Bridge worklist on http://localhost:%d" % port)
    server.serve_forever()


if __name__ == "__main__":
    import sys
    serve(port=int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
