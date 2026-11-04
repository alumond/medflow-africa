"""District supply briefs with explicit facts, boxed risks and separate email drafts."""

from datetime import date, timedelta
from email.message import EmailMessage
from html import escape

from app.data.programme import programme

SECTIONS = [
    "Executive Summary",
    "Project Metadata & Governance Context",
    "Activity Implementation Analysis",
    "Workplan Analysis",
    "Logframe Performance Analysis",
    "Indicator Performance Analysis",
    "Risk & Bottleneck Analysis",
    "Issues Log Analysis",
    "Budget & Resource Utilization",
    "Data Quality Assessment",
    "Dependency & Impact Analysis",
    "Forecasting & Predictive Insights",
    "Recommendations & Corrective Action Plan",
]


def table(headers: list[str], rows: list[list]) -> str:
    """Escape every source-derived value before writing export HTML."""
    return (
        "<div class='table-wrap'><table><thead><tr>"
        + "".join(f"<th>{escape(str(h))}</th>" for h in headers)
        + "</tr></thead><tbody>"
        + "".join("<tr>" + "".join(f"<td>{escape(str(v))}</td>" for v in row) + "</tr>" for row in rows)
        + "</tbody></table></div>"
    )


def indicator_rows(program: dict) -> str:
    rows = []
    for i in program["indicators"]:
        achieved = (
            f"{i['achievement']:.1f}% achievement"
            if i["achievement"] is not None
            else "No eligible denominator"
        )
        rows.append(
            [
                i["name"],
                f"{i['actual']:g}{'%' if i['unit'] == '%' else ' ' + i['unit']}",
                f"{i['target']:g}{'%' if i['unit'] == '%' else ' ' + i['unit']} · {achieved}",
                i["status"].replace("_", " ").title(),
                i["basis"],
            ]
        )
    return table(["Indicator", "Actual", "Performance vs target", "Status", "Evidence"], rows)


def build_report(snapshot: dict, planner: dict, request: dict, narrative=None) -> str:
    """Create all thirteen sections without a generative model or invented factual claims."""
    context, quality = snapshot["context"], snapshot["quality"]
    program = programme(snapshot, planner)
    selected = request.get("selected_findings")
    pairs = [p for p in snapshot["pairs"] if selected is None or p["finding_id"] in selected]
    high = [p for p in pairs if p["risk"] == "high"]
    plans = [r for r in planner["recommendations"] if selected is None or r["finding_id"] in selected]
    totals = program["budget_totals"]
    due = (date.fromisoformat(context["cutoff"]) + timedelta(days=5)).isoformat()
    body = []

    def section(index: int, content: str):
        if narrative and narrative["mode"] == "gemini":
            key = {0: "executive_summary", 6: "risks", 12: "recommendations"}.get(index)
            if key:
                content = (
                    "<div class='ai-narrative'><small>WORKING DRAFT · REVIEW REQUIRED</small>"
                    + "".join(f"<p>{escape(p['text'])}</p>" for p in narrative["sections"].get(key, []))
                    + "</div>"
                    + content
                )
        body.append(
            f"<section id='section-{index + 1}'><div class='section-label'>{index + 1:02}</div><h2>{SECTIONS[index]}</h2>{content}</section>"
        )

    section(
        0,
        f"<p class='lead'>{len(high)} high-risk facility–medicine pairs require review within the {context['window']}-day horizon. {len(plans)} feasible redistribution proposals are available for human review.</p><p>The immediate priority is to verify overdue deliveries and stock balances, then review the constrained proposals. {quality['blocked_pairs']} pairs have insufficient evidence for redistribution. Improving those records is a separate management action; their absence from the risk queue does not indicate adequate stock.</p>"
        + (
            f"<blockquote><strong>Management note</strong><p>{escape(request.get('management_note', ''))}</p></blockquote>"
            if request.get("management_note")
            else ""
        ),
    )
    section(
        1,
        table(
            ["Field", "Context"],
            [
                ["Project", program["project"]["title"]],
                ["Funding partner", program["project"]["donor"]],
                ["Reporting cut-off", context["cutoff"]],
                ["Forecast window", f"{context['window']} days"],
                ["Governance", program["project"]["governance"]],
                [
                    "Data / analysis provenance",
                    f"{context['import_id']} · data {context['data_version']} · {context['model']} · {context['config_version']}",
                ],
                ["Prepared by", request.get("prepared_by", "District supply team")],
                [
                    "Data status",
                    "Illustrative inventory and programme records"
                    if context["synthetic"]
                    else "Anonymised operational import; resource and activity ledgers are illustrative",
                ],
            ],
        ),
    )
    activities = program["activities"]
    section(
        2,
        "<p><small>Source: illustrative project activity ledger; these records are not derived from inventory imports.</small></p><p>The planning ledger covers stock mapping, reporting procedures, review protocols and the next district supply decision review. Use the live stock-risk and evidence-quality queues to prioritise operational follow-through.</p>"
        + table(
            ["Activity", "Actual", "Performance vs target", "Owner", "Status"],
            [
                [
                    a["name"],
                    f"{a['actual']} {a['unit']}",
                    f"{a['planned']} · {a['actual'] / a['planned'] * 100:.0f}% achievement",
                    a["owner"],
                    a["status"].replace("_", " "),
                ]
                for a in activities
            ],
        ),
    )
    section(
        3,
        "<p>The next district supply decision review depends on the agreed reporting and redistribution procedures. Confirm the review date, unresolved delivery issues and evidence-recovery actions with their owners.</p>"
        + table(
            ["Milestone", "Start", "Due", "Dependency", "Delivery status"],
            [
                [a["name"], a["start"], a["due"], a["dependency"], a["status"].replace("_", " ")]
                for a in activities
            ],
        ),
    )
    section(
        4,
        "<p><strong>Service objective:</strong> keep essential medicines available without creating new shortages at supplying facilities. Patient outcomes are outside this stock dataset.</p><p><strong>Availability:</strong> medicine stocks meet the safety buffer. <strong>Readiness:</strong> balances reconcile and complete reports arrive on time. <strong>Follow-through:</strong> feasible transfers receive a recorded review.</p>"
        + table(
            ["Results level", "Indicator", "Actual", "Target / achievement", "Verification"],
            [
                [
                    i["level"],
                    i["name"],
                    f"{i['actual']:g} {i['unit']}",
                    f"{i['target']:g} · {i['achievement']}%"
                    if i["achievement"] is not None
                    else "Not assessed",
                    i["basis"],
                ]
                for i in program["indicators"]
            ],
        ),
    )
    section(
        5,
        indicator_rows(program)
        + "<p>Status policy: Green / on track ≥100% of target; Amber / at risk ≥85% and &lt;100%; Red / off track &lt;85%. A missing denominator is not assessed. Percent achievement is actual divided by target.</p>"
        + "".join(
            f"<div class='status {i['status']}'><strong>{escape(i['name'])}</strong> — {i['actual']:g} {escape(i['unit'])}; {i['achievement']}% achievement against {i['target']:g} target. {i['status'].replace('_', ' ').title()}.</div>"
            for i in program["indicators"]
        ),
    )
    risk_boxes = "".join(
        f"<blockquote class='critical'><strong>HIGH RISK · {escape(p['facility'])} / {escape(p['medicine'])}</strong><p>{p['stock']:,} usable units; {p['cover']:.1f} days of cover against {p['safety_days']} days required ({p['cover'] / p['safety_days'] * 100:.1f}% achievement; {p['safety_days'] - p['cover']:.1f}-day shortfall). {escape('; '.join(c['label'] + ' [' + c['type'] + ']' for c in p['causes']))}.</p><p><strong>Action:</strong> District pharmacist to validate balances and review redistribution by {due}; logistics lead to confirm the delivery schedule. No transfer is executed by this report.</p><small>Finding {p['finding_id']}</small></blockquote>"
        for p in high
    )
    section(
        6,
        (
            risk_boxes
            or "<p>No high-risk items in the selected findings. Check the unassessed queue separately.</p>"
        )
        + f"<blockquote><strong>EVIDENCE BOTTLENECK</strong><p>{quality['blocked_pairs']} pairs are withheld from redistribution because evidence is limited or blocked. Data officer to reconcile missing reports and rejected balances by {due}.</p></blockquote>",
    )
    section(
        7,
        table(
            ["Issue", "Severity", "Status", "Owner", "Due", "Corrective action"],
            [
                [
                    i["id"] + " · " + i["issue"],
                    i["severity"],
                    i["status"].replace("_", " "),
                    i["owner"],
                    i["due"],
                    i["action"],
                ]
                for i in program["issues"]
            ],
        ),
    )
    section(
        8,
        f"<p class='lead'>US${totals['spent']:,.0f} spent — {totals['spent'] / totals['planned_to_date'] * 100:.1f}% of the US${totals['planned_to_date']:,.0f} planned to date.</p><p>{totals['spent'] / totals['allocated'] * 100:.1f}% of the US${totals['allocated']:,.0f} total allocation is spent; US${totals['committed']:,.0f} is committed; US${totals['allocated'] - totals['spent'] - totals['committed']:,.0f} remains uncommitted. These illustrative USD logistics accounts do not price individual medicine units.</p>"
        + table(
            [
                "Budget line",
                "Actual spent (USD)",
                "Planned to date / achievement",
                "Allocation (USD)",
                "Commitments (USD)",
            ],
            [
                [
                    b["line"],
                    f"{b['spent']:,.0f}",
                    f"{b['planned_to_date']:,.0f} · {b['spent'] / b['planned_to_date'] * 100:.1f}%",
                    f"{b['allocated']:,.0f}",
                    f"{b['committed']:,.0f}",
                ]
                for b in program["budget"]
            ],
        )
        + "<blockquote><strong>RESOURCE BOTTLENECK</strong><p>Facility stock-information support is behind its phased plan while last-mile logistics is ahead. Finance manager and district supply manager should review the remaining commitments before reallocating funds. Higher expenditure alone does not demonstrate stronger results.</p></blockquote>",
    )
    section(
        9,
        table(
            ["Dimension", "Actual", "Target / achievement", "Denominator"],
            [
                [
                    "Completeness",
                    f"{quality['completeness']:.1%}",
                    f"95% · {quality['completeness'] / 0.95 * 100:.1f}% achievement",
                    f"{quality['received_reports']} / {quality['expected_reports']} expected reports",
                ],
                [
                    "Timeliness",
                    f"{quality['timeliness']:.1%}",
                    f"95% · {quality['timeliness'] / 0.95 * 100:.1f}% achievement",
                    "Expected reports, latest 12 weeks",
                ],
                [
                    "Validity",
                    f"{quality['validity']:.2%}",
                    f"100% · {quality['validity'] * 100:.2f}% achievement",
                    f"{quality['accepted']} / {quality['total']} source rows",
                ],
                [
                    "Balance consistency",
                    f"{quality['consistency']:.2%}",
                    f"100% · {quality['consistency'] * 100:.2f}% achievement",
                    "Inventory source rows",
                ],
            ],
        )
        + f"<p>{quality['rejected_count']} source rows are quarantined and excluded from analysis. Missing periods are excluded from observed consumption days rather than treated as zero demand. Critical balance failures and stale stock override aggregate quality scores.</p>",
    )
    section(
        10,
        "<p><strong>Reliable stock records → safe redistribution review → medicine availability.</strong> Missing reports and inconsistent balances constrain the evidence required for action. Reporting recovery at Gidan must precede redistribution decisions there.</p><p><strong>Delivery confirmation → replenishment planning.</strong> Pending orders are not assumed to arrive in the stock-cover scenario. Logistics follow-up and donor validation should proceed in parallel, with the district pharmacist reviewing the resulting proposal.</p>",
    )
    section(
        11,
        f"<p>Under a constant-consumption, no-new-receipts scenario, {sum(p['cover'] is not None and p['cover'] < 14 for p in pairs if p['risk'] != 'not_assessed')} assessed pairs exhaust current stock within 14 days and {sum(p['cover'] is not None and p['cover'] < 30 for p in pairs if p['risk'] != 'not_assessed')} within 30 days. These are conditional stock-cover scenarios, not guaranteed future events.</p><p>Model status: {escape(context['model_note'])}. Synthetic holdout evaluation is available in the model evidence panel. It does not establish real-world effectiveness. Unassessed pairs remain outside the numerical projection.</p>"
        + table(
            [
                "Facility / medicine",
                "Actual stock",
                f"Projected stock after {context['window']} days",
                "Assumption",
            ],
            [
                [
                    p["facility"] + " / " + p["medicine"],
                    f"{p['stock']:,}",
                    f"{max(0, round(p['stock'] - p['adc'] * context['window'])):,}",
                    "Observed daily consumption; no incoming receipts",
                ]
                for p in high
            ],
        ),
    )
    actions = request.get("actions", [])
    action_rows = [
        [a["finding_id"], a["action"], a["owner"], str(a["due_date"]), a["status"].replace("_", " ")]
        for a in actions
    ]
    if not action_rows:
        action_rows = [
            [
                p["finding_id"],
                "Validate balance, confirm overdue delivery and review feasible redistribution",
                "District pharmacist / logistics lead",
                due,
                "Suggested · awaiting assignment",
            ]
            for p in high
        ]
    section(
        12,
        table(["Finding", "Corrective action", "Owner", "Due", "Status"], action_rows)
        + "<h3>Redistribution decision register</h3>"
        + table(
            [
                "Recipient / medicine",
                "Donor",
                "Actual proposed units",
                "Recipient cover before → after",
                "Donor cover after / safety",
                "Review",
            ],
            [
                [
                    r["recipient"] + " / " + r["medicine"],
                    r["donor"],
                    r.get("reviewed_quantity", r["quantity"]),
                    f"{r['recipient_before']:.1f} → {r.get('reviewed_recipient_after', r['recipient_after']):.1f} days",
                    f"{r.get('reviewed_donor_after', r['donor_after']):.1f} / {r['safety_days']} days",
                    r["status"],
                ]
                for r in plans
            ],
        )
        + "<p>Recommendations require human validation and the authorised external operational process. This report records proposed and reviewed actions only.</p>",
    )
    css = (__import__("pathlib").Path(__file__).with_name("report.css")).read_text()
    import base64
    from app.core.config import ROOT

    font = base64.b64encode((ROOT / "app/web/assets/garamond.ttf").read_bytes()).decode()
    css = "@font-face{font-family:Garamond;src:url(data:font/ttf;base64," + font + ")}\n" + css
    if narrative and narrative["mode"] == "deterministic":
        pass  # Provider status is shown in the builder, not in the operational brief.
    label = "DISTRICT SUPPLY REVIEW"
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>MedFlow Africa | District action report</title><style>{css}</style></head><body><header><div class='brand'>MEDFLOW AFRICA <span> / DISTRICT INTELLIGENCE</span></div><p class='eyebrow'>{label}</p><h1>Evidence into action.</h1><p class='subtitle'>District medicine-supply brief</p><div class='cover-meta'>{escape(context['district'])} · Reporting cut-off {context['cutoff']} · {context['window']}-day horizon</div></header><main>{''.join(body)}</main><footer>MedFlow Africa · Supply decisions for human review · {escape(context['data_version'])}</footer></body></html>"


def escalation(snapshot: dict, planner: dict, request: dict) -> dict:
    """Produce an exact, reviewable escalation draft; never send an email."""
    selected = request.get("selected_findings")
    high = [
        p
        for p in snapshot["pairs"]
        if p["risk"] == "high" and (selected is None or p["finding_id"] in selected)
    ]
    cutoff = date.fromisoformat(snapshot["context"]["cutoff"])
    program = programme(snapshot, planner)
    missed = [i for i in program["indicators"] if i["achievement"] is not None and i["achievement"] < 85]
    if not high and not missed:
        return {
            "warranted": False,
            "subject": "No critical escalation triggered",
            "body": "No high-risk stock findings or critical readiness gaps in the current selection.",
        }
    subject = f"Action required by {cutoff + timedelta(days=5)}: {len(high)} priority medicine shortages and delivery gaps | Kawara"
    lines = [
        "Dear District Supply Manager,",
        "",
        f"The district review at {cutoff} identifies {len(high)} high-risk stock findings in the {snapshot['context']['window']}-day horizon. Please review the following evidence and confirm the corrective actions below.",
        "",
        "Stock position — actual, required cover and shortfall:",
    ]
    for p in high:
        cause = "; ".join(c["label"] + " (" + c["type"].lower() + ")" for c in p["causes"])
        lines.append(
            f"• {p['facility']} — {p['medicine']}: {p['stock']:,} usable units; {p['cover']:.1f} days of cover versus {p['safety_days']} days required ({p['cover'] / p['safety_days'] * 100:.1f}% achievement; {p['cover'] - p['safety_days']:.1f}-day variance). Evidence: {cause}; delivery delay {p['delivery_delay']} days. Potential impact: stock exhaustion before the safety buffer is restored if consumption continues and no stock arrives. [{p['finding_id']}]"
        )
    lines.extend(["", "Supply-readiness gaps:"])
    for i in missed:
        lines.append(
            f"• {i['name']}: {i['actual']:g} {i['unit']} versus {i['target']:g} target ({i['achievement']:.1f}% achievement; {i['actual'] - i['target']:g} variance). Source: {i['basis']}. Review the cited inventory and decision records to confirm the operational cause."
        )
    lines.extend(
        [
            "",
            "Recommended actions and ownership:",
            f"1. District pharmacist: validate the flagged usable balances and review the feasible donor proposals by {cutoff + timedelta(days=5)}. Confirm expiry, transport and storage constraints before any external approval.",
            f"2. Logistics lead: obtain confirmed delivery dates for all overdue flagged orders by {cutoff + timedelta(days=4)}; escalate unresolved dispatches to the medical stores lead.",
            f"3. Data officer: reconcile Gidan reporting gaps and the rejected balance by {cutoff + timedelta(days=4)}. Keep weak-evidence transfers withheld until validated.",
            f"4. District supply manager: confirm the review owner, unresolved dependencies and recovery dates by {cutoff + timedelta(days=5)}.",
            "",
            f"Please confirm the named owners and recovery dates by {cutoff + timedelta(days=4)}, and convene a 30-minute district supply review by {cutoff + timedelta(days=5)}. Record agreed actions and any revised dates in the action report.",
            "",
            "Kind regards,",
            request.get("prepared_by", "District supply team"),
            "",
            "Source: illustrative inventory and readiness records. Review before operational use. This email does not authorise stock movement.",
        ]
    )
    return {"warranted": True, "subject": subject, "body": "\n".join(lines)}


def email_file(draft: dict) -> bytes:
    """RFC email draft without invented recipient addresses or sending side effects."""
    msg = EmailMessage()
    msg["Subject"] = draft["subject"]
    msg["X-Unsent"] = "1"
    msg.set_content(draft["body"])
    return msg.as_bytes()


def validate_narrative(draft: list[dict], facts: dict[str, str]) -> bool:
    """Optional narrative adapters may only return approved fact-bound sentences."""
    return bool(draft) and all(
        set(item) == {"fact_id", "text"}
        and item["fact_id"] in facts
        and item["text"] == facts[item["fact_id"]]
        for item in draft
    )
