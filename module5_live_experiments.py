"""NorthStar Module 5 live classroom experiments (v2).

Student side: four activities with neutral titles, app-assigned balanced groups,
one submission per student per activity, and a prediction step before each reveal.
Instructor side: session control, prediction gates, projector view, detailed results.
"""

import hashlib
import json
import os
import random
from datetime import datetime, timezone

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from sqlalchemy import (
    Column, Float, Integer, MetaData, String, Table, create_engine, event,
    func, inspect, select, text,
)
from sqlalchemy.exc import IntegrityError

st.set_page_config(page_title="NorthStar Live Activities", page_icon="🧪", layout="centered")


# ---------------------------------------------------------------------------
# Settings (environment variable first, then Streamlit secrets, then default)
# ---------------------------------------------------------------------------
def get_setting(name, default=None):
    if os.environ.get(name):
        return os.environ[name]
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return default


INSTRUCTOR_CODE = get_setting("INSTRUCTOR_CODE", "northstar")
DATABASE_URL = get_setting("DATABASE_URL", "sqlite:///northstar_experiments.db")
ID_SALT = get_setting("ID_SALT", "northstar-default-salt")
DEFAULT_SESSION = get_setting("SESSION_CODE", "class-1")
EXP1_SECONDS = int(get_setting("EXP1_SECONDS", "90"))
EXP1_GRACE_SECONDS = 20  # submissions later than limit + grace are flagged
# Hosted providers hand out postgres:// or postgresql:// URLs; pin the driver in requirements.txt.
for _prefix in ("postgres://", "postgresql://"):
    if DATABASE_URL.startswith(_prefix):
        DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len(_prefix):]
USING_SQLITE = DATABASE_URL.startswith("sqlite")

# Experiment keys, student-facing titles (neutral), and arms.
ACTIVITIES = {
    "framing":    {"student_title": "Two quick decisions", "instructor_title": "Gain vs. loss framing",
                   "arms": ["Gain frame", "Loss frame"]},
    "incentives": {"student_title": "Service desk", "instructor_title": "Incentives and productivity",
                   "arms": ["Control", "Quantity", "Balanced"]},
    "defaults":   {"student_title": "Checkout", "instructor_title": "Defaults and warranty margin",
                   "arms": ["Opt-In", "Opt-Out", "Active choice"]},
    "finish":     {"student_title": "Choose a finish", "instructor_title": "Social proof (bestseller badge)",
                   "arms": ["No badge", "Bestseller badge"]},
}
ACTIVITY_ORDER = ["framing", "incentives", "defaults", "finish"]

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
metadata = MetaData()

def _pk_cols():
    return [Column("session", String(64), primary_key=True),
            Column("participant_id", String(32), primary_key=True)]

TABLES = {
    "assignments": Table(
        "assignments", metadata,
        *_pk_cols(), Column("experiment", String(32), primary_key=True),
        Column("arm", String(32)), Column("assigned_at", String(40)),
    ),
    "framing": Table(
        "framing", metadata, *_pk_cols(),
        Column("submitted_at", String(40)), Column("arm", String(32)),
        Column("chose_upgrade", Integer), Column("persuasiveness", Integer), Column("chose_risky", Integer),
    ),
    "incentives": Table(
        "incentives", metadata, *_pk_cols(),
        Column("submitted_at", String(40)), Column("arm", String(32)),
        Column("n_cases", Integer), Column("attempted", Integer), Column("correct", Integer),
        Column("incorrect", Integer), Column("accuracy", Float), Column("quality_value", Float),
        Column("points", Float), Column("elapsed_seconds", Float), Column("over_time", Integer),
        Column("leaderboard_name", String(40)),
    ),
    "defaults": Table(
        "defaults", metadata, *_pk_cols(),
        Column("submitted_at", String(40)), Column("arm", String(32)),
        Column("chose_plan", Integer), Column("would_cancel", Integer), Column("trust_rating", Integer),
    ),
    "finish": Table(
        "finish", metadata, *_pk_cols(),
        Column("submitted_at", String(40)), Column("arm", String(32)),
        Column("preferred_color", String(32)), Column("chose_badged", Integer),
        Column("purchase_likelihood", Integer), Column("would_pay_premium", Integer),
    ),
    "predictions": Table(
        "predictions", metadata, *_pk_cols(),
        Column("experiment", String(32), primary_key=True), Column("arm", String(32), primary_key=True),
        Column("predicted_pct", Float), Column("submitted_at", String(40)),
    ),
    "settings": Table(
        "settings", metadata,
        Column("key", String(128), primary_key=True), Column("value", String(512)),
    ),
}


@st.cache_resource
def get_engine():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    if USING_SQLITE:
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL;")
            cur.execute("PRAGMA busy_timeout=30000;")
            cur.close()
    # Archive any table whose columns do not match this version (data kept).
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    with engine.begin() as conn:
        for name, table in TABLES.items():
            if name in existing:
                cols = [c["name"] for c in insp.get_columns(name)]
                if cols != [c.name for c in table.columns]:
                    conn.execute(text(f'ALTER TABLE "{name}" RENAME TO "{name}_archived_{stamp}"'))
    metadata.create_all(engine)
    return engine


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_flag(key, default=None):
    t = TABLES["settings"]
    with get_engine().connect() as conn:
        row = conn.execute(select(t.c.value).where(t.c.key == key)).first()
    return row[0] if row else default


def set_flag(key, value):
    t = TABLES["settings"]
    with get_engine().begin() as conn:
        conn.execute(t.delete().where(t.c.key == key))
        conn.execute(t.insert().values(key=key, value=str(value)))


def active_session():
    return get_flag("active_session", DEFAULT_SESSION)


def has_submitted(table_name, session, pid):
    t = TABLES[table_name]
    with get_engine().connect() as conn:
        n = conn.execute(
            select(func.count()).select_from(t).where(t.c.session == session, t.c.participant_id == pid)
        ).scalar()
    return n > 0


def save_once(table_name, row):
    """Insert one row. Returns 'ok', 'duplicate', or an error message. Never overwrites."""
    try:
        with get_engine().begin() as conn:
            conn.execute(TABLES[table_name].insert().values(**row))
        return "ok"
    except IntegrityError:
        return "duplicate"
    except Exception as e:  # noqa: BLE001 - surface any storage problem to the user
        return f"error: {e}"


def get_assignment(session, pid, experiment):
    t = TABLES["assignments"]
    with get_engine().connect() as conn:
        row = conn.execute(
            select(t.c.arm, t.c.assigned_at).where(
                t.c.session == session, t.c.participant_id == pid, t.c.experiment == experiment)
        ).first()
    return (row[0], row[1]) if row else (None, None)


def assign_balanced(session, pid, experiment):
    """Assign to the arm with the fewest participants so far (random tie-break). Idempotent."""
    arm, at = get_assignment(session, pid, experiment)
    if arm:
        return arm, at
    t = TABLES["assignments"]
    arms = ACTIVITIES[experiment]["arms"]
    with get_engine().connect() as conn:
        rows = conn.execute(
            select(t.c.arm, func.count()).where(t.c.session == session, t.c.experiment == experiment)
            .group_by(t.c.arm)
        ).all()
    counts = {a: 0 for a in arms}
    counts.update({a: n for a, n in rows if a in counts})
    fewest = min(counts.values())
    choice = random.choice([a for a in arms if counts[a] == fewest])
    try:
        with get_engine().begin() as conn:
            conn.execute(t.insert().values(session=session, participant_id=pid, experiment=experiment,
                                           arm=choice, assigned_at=now_iso()))
    except IntegrityError:
        pass  # a double click already assigned this student; read it back
    return get_assignment(session, pid, experiment)


def read_table(name, session=None):
    t = TABLES[name]
    q = select(t) if session is None else select(t).where(t.c.session == session)
    with get_engine().connect() as conn:
        return pd.read_sql(q, conn)


def prop_diff(treat, ctrl):
    """Difference in proportions (treat - ctrl) with a normal-approximation 95% CI."""
    n1, n0 = len(treat), len(ctrl)
    if n1 == 0 or n0 == 0:
        return None
    p1, p0 = treat.mean(), ctrl.mean()
    se = ((p1 * (1 - p1)) / n1 + (p0 * (1 - p0)) / n0) ** 0.5
    d = p1 - p0
    return d, d - 1.96 * se, d + 1.96 * se


def show_effect(label, result):
    if result is None:
        st.caption(f"{label}: needs submissions in both groups.")
        return
    d, lo, hi = result
    st.metric(label, f"{d*100:+.1f} pp")
    st.caption(f"95% CI: {lo*100:+.1f} to {hi*100:+.1f} pp (normal approximation; wide with small groups).")


ADJECTIVES = ["Swift", "Quiet", "Bold", "Clever", "Steady", "Bright", "Lucky", "Brave", "Calm", "Keen",
              "Sharp", "Nimble", "Witty", "Sunny", "Rapid", "Noble"]
ANIMALS = ["Falcon", "Otter", "Lynx", "Heron", "Badger", "Orca", "Marten", "Puffin", "Bison", "Raven",
           "Gecko", "Moose", "Beaver", "Loon", "Cougar", "Eagle"]


def leaderboard_name(pid):
    h = int(hashlib.sha256((pid + "lb").encode()).hexdigest(), 16)
    return f"{ADJECTIVES[h % 16]} {ANIMALS[(h // 16) % 16]} {h % 90 + 10}"


# ---------------------------------------------------------------------------
# Entry gate: consent + student code (prevents duplicate submissions on refresh)
# ---------------------------------------------------------------------------
st.title("NorthStar Live Activities")

session = active_session()

if "pid" not in st.session_state or st.session_state.get("pid_session") != session:
    st.session_state.pid = None

if st.session_state.pid is None:
    st.write("Welcome. Today's class includes four short activities. Each takes one to two minutes.")
    st.info(
        "Your responses are anonymous. Your code is converted into a scrambled ID before anything is stored. "
        "Answers are used for teaching in this course, and pooled anonymously across course sections. "
        "Participation does not affect your grade."
    )
    with st.form("gate"):
        raw_code = st.text_input(
            "Your student number (or the code your instructor gives you)",
            help="Use the same code if you reload the page, so you can continue where you left off.",
        )
        agree = st.checkbox("I understand how my responses will be used.")
        go = st.form_submit_button("Continue", type="primary")
    if go:
        if not raw_code.strip():
            st.error("Enter your code to continue.")
        elif not agree:
            st.error("Tick the box to continue.")
        else:
            digest = hashlib.sha256(f"{ID_SALT}|{session}|{raw_code.strip().lower()}".encode()).hexdigest()
            st.session_state.pid = digest[:16]
            st.session_state.pid_session = session
            st.rerun()
    st.caption("Instructor: enter any code here (e.g., 'instructor'), then open the Instructor tab.")
    st.stop()

pid = st.session_state.pid
st.caption(f"Session {session}. Anonymous ID {pid[:6]}.")

tab_labels = [f"Activity {i}" for i in range(1, 5)] + ["Predictions", "Instructor"]
tabs = st.tabs(tab_labels)
TAB = dict(zip(ACTIVITY_ORDER + ["predictions", "instructor"], tabs))


def submitted_banner(what):
    st.success(f"{what} submitted. Please don't discuss your screen with classmates until the reveal.")


# ---------------------------------------------------------------------------
# Activity 1: Framing (run first, before students have seen other manipulations)
# ---------------------------------------------------------------------------
with TAB["framing"]:
    st.header(ACTIVITIES["framing"]["student_title"])
    st.caption("Two short business decisions. There are no right or wrong answers.")

    if has_submitted("framing", session, pid):
        submitted_banner("Your decisions were")
    else:
        arm, _ = get_assignment(session, pid, "framing")
        if arm is None:
            if st.button("Start", type="primary", key="framing_start"):
                assign_balanced(session, pid, "framing")
                st.rerun()
        else:
            gain = arm == "Gain frame"
            if gain:
                ad_head = "Save about CAD 60 every year."
                ad_body = "Choose EcoSeries and keep roughly CAD 60 a year in your pocket through lower energy and water bills."
                plan_a = "Plan A: 400 of the 1,200 accounts will be kept for sure."
                plan_b = "Plan B: a 1-in-3 chance that all 1,200 accounts are kept, and a 2-in-3 chance that none are kept."
            else:
                ad_head = "Stop losing about CAD 60 every year."
                ad_body = "With the standard model, you lose roughly CAD 60 a year to higher energy and water bills."
                plan_a = "Plan A: 800 of the 1,200 accounts will be lost for sure."
                plan_b = "Plan B: a 1-in-3 chance that no accounts are lost, and a 2-in-3 chance that all 1,200 are lost."
            # Identical layout, colour and length in both arms: only the wording changes.
            ad_html = (
                '<div style="border:2px solid #1F3557;border-radius:14px;padding:16px 18px;margin:6px 0 14px;'
                'background:rgba(31,53,87,.06);">'
                '<div style="font-size:12px;font-weight:700;color:#1F3557;">NorthStar EcoSeries</div>'
                f'<div style="font-size:22px;font-weight:800;margin:4px 0 6px;">{ad_head}</div>'
                f'<div style="font-size:15px;">{ad_body}</div></div>'
            )
            with st.form("framing_form"):
                st.markdown("#### Decision 1: Which model would you buy?")
                st.write(
                    "You are buying a **NorthStar SmartWash for CAD 899**. The **EcoSeries** version is identical, "
                    "except that it costs **CAD 120 more** and uses less energy and water. You see this message:"
                )
                st.markdown(ad_html, unsafe_allow_html=True)
                upgrade = st.radio("Your choice", ["Standard SmartWash (CAD 899)", "EcoSeries SmartWash (CAD 1,019)"],
                                   index=None, key="framing_upgrade")
                persuasive = st.slider("How persuasive is the NorthStar message?", 1, 5, 3,
                                       help="1 = not at all persuasive; 5 = very persuasive")
                st.markdown("#### Decision 2: Distributor accounts")
                st.write(
                    "A regional distributor that sells NorthStar products is failing. **1,200 small-business accounts** "
                    "it serves may move to a competitor. You can fund only one retention plan."
                )
                plan = st.radio("Which plan do you fund?", [plan_a, plan_b], index=None, key="framing_plan")
                go4 = st.form_submit_button("Submit decisions", type="primary")
            if go4:
                if upgrade is None or plan is None:
                    st.error("Answer both decisions before submitting.")
                else:
                    res = save_once("framing", dict(
                        session=session, participant_id=pid, submitted_at=now_iso(), arm=arm,
                        chose_upgrade=int(upgrade.startswith("EcoSeries")), persuasiveness=int(persuasive),
                        chose_risky=int(plan == plan_b)))
                    if res.startswith("error"):
                        st.error(f"Your answers could not be saved ({res[7:]}). Please tell your instructor.")
                    else:
                        st.rerun()


# ---------------------------------------------------------------------------
# Activity 2: Incentives (service desk)
# ---------------------------------------------------------------------------
CASES = [
    ("The customer cannot connect the mobile app to their home Wi-Fi.", "Remote fix"),
    ("The door will not latch. There is no smoke, smell, or electrical danger.", "Technician visit"),
    ("Sparks appear from the back panel when the unit is switched on.", "Safety escalation"),
    ("Delivered this morning; the unit does not power on at all.", "Replace"),
    ("Delivered three weeks ago and worked fine until today; now it does not power on.", "Technician visit"),
    ("A software update switched the display to French; everything else works.", "Remote fix"),
    ("Loud grinding noise during the spin cycle; no safety issue.", "Technician visit"),
    ("The same leak has returned after two previous technician repairs.", "Replace"),
    ("The app shows an error code, and the customer also reports a burning smell.", "Safety escalation"),
    ("The drum light flickers after a firmware update; the unit runs normally.", "Remote fix"),
    ("A technician repaired the pump once; the same pump fault is back.", "Technician visit"),
    ("Water pools under the unit after each wash; there is no electrical issue.", "Technician visit"),
    ("Delivered today; it powers on, but none of the control-panel buttons respond.", "Replace"),
    ("The control panel becomes too hot to touch during every cycle.", "Safety escalation"),
    ("The customer forgot their app password and cannot log in.", "Remote fix"),
    ("Third breakdown of the same motor fault, and this time the customer got a mild shock.", "Safety escalation"),
    ("Delivered yesterday; it works, but scheduling stays greyed out until the account is set up in the app.", "Remote fix"),
    ("The rubber door seal is torn; the appliance otherwise works.", "Technician visit"),
    ("Smoke came from the plug once, then stopped; the unit now runs normally.", "Safety escalation"),
    ("The same heating fault has been repaired twice before and has now returned.", "Replace"),
]
ACTIONS = ["—", "Remote fix", "Technician visit", "Replace", "Safety escalation"]

ARM_TEXT = {
    "Control": "Work through the cases below.",
    "Quantity": "You earn **1 point for every case you complete**. Top scores go on the class leaderboard.",
    "Balanced": "You earn **2 points for each correct case** and **lose 2 points for each incorrect case**. "
                "Top scores go on the class leaderboard.",
}


def points_for(arm, attempted, correct, incorrect):
    if arm == "Quantity":
        return float(attempted)
    if arm == "Balanced":
        return float(2 * correct - 2 * incorrect)
    return None


def countdown(deadline_iso):
    deadline_ms = int(datetime.fromisoformat(deadline_iso).timestamp() * 1000)
    components.html(
        f"""<div id="cd" style="font:600 18px system-ui,sans-serif;padding:8px 12px;border-radius:10px;
        background:rgba(46,134,222,.12);color:#1F3557;text-align:center;"></div>
        <script>
        const end={deadline_ms};const el=document.getElementById('cd');
        function tick(){{const s=Math.max(0,Math.round((end-Date.now())/1000));
        el.textContent = s>0 ? ('Time left: '+s+' s') : 'Time is up. Submit now.';
        if(s===0){{el.style.background='rgba(228,87,46,.15)';el.style.color='#9b2c12';}}}}
        tick();setInterval(tick,500);
        </script>""",
        height=50,
    )


with TAB["incentives"]:
    st.header(ACTIVITIES["incentives"]["student_title"])
    st.caption("You are a NorthStar service agent. Decide how to handle each customer case.")
    st.info(
        "Rules\n"
        "1. App, software, or account setup problem → Remote fix\n"
        "2. Physical repair needed, no danger → Technician visit\n"
        "3. Does not work on the day it is delivered, OR the same fault after two or more previous repairs → Replace\n"
        "4. Sparks, smoke, burning smell, shock, or overheating → Safety escalation\n"
        "5. If more than one rule applies, Safety escalation comes first, then Replace."
    )

    if has_submitted("incentives", session, pid):
        t = TABLES["incentives"]
        with get_engine().connect() as conn:
            r = conn.execute(select(t).where(t.c.session == session, t.c.participant_id == pid)).mappings().first()
        submitted_banner("Your cases were")
        c1, c2, c3 = st.columns(3)
        c1.metric("Cases completed", f'{r["attempted"]} of {r["n_cases"]}')
        c2.metric("Accuracy", f'{r["accuracy"]:.0%}')
        if r["points"] is not None:
            c3.metric("Your points", f'{r["points"]:.0f}')
            st.caption(f'Leaderboard name: **{r["leaderboard_name"]}**')
    else:
        arm, started_at = get_assignment(session, pid, "incentives")
        if arm is None:
            st.write(f"You will have **{EXP1_SECONDS} seconds**. You are not expected to finish every case.")
            if st.button("Start", type="primary", key="inc_start"):
                assign_balanced(session, pid, "incentives")
                st.rerun()
        else:
            st.markdown(ARM_TEXT[arm])
            start_dt = datetime.fromisoformat(started_at)
            deadline = datetime.fromtimestamp(start_dt.timestamp() + EXP1_SECONDS, tz=timezone.utc)
            countdown(deadline.isoformat())
            order = list(range(len(CASES)))
            random.Random(pid + "cases").shuffle(order)  # reduces copying from neighbours
            with st.form("inc_form"):
                choices = {}
                for n, idx in enumerate(order, start=1):
                    st.markdown(f"**Case {n}.** {CASES[idx][0]}")
                    choices[idx] = st.selectbox(f"Decision for case {n}", ACTIONS, index=0,
                                                key=f"case_{idx}", label_visibility="collapsed")
                go1 = st.form_submit_button("Submit cases", type="primary")
            if go1:
                attempted = sum(c != "—" for c in choices.values())
                correct = sum(c != "—" and c == CASES[i][1] for i, c in choices.items())
                incorrect = attempted - correct
                elapsed = (datetime.now(timezone.utc) - start_dt).total_seconds()
                res = save_once("incentives", dict(
                    session=session, participant_id=pid, submitted_at=now_iso(), arm=arm,
                    n_cases=len(CASES), attempted=attempted, correct=correct, incorrect=incorrect,
                    accuracy=(correct / attempted) if attempted else 0.0,
                    # Value to NorthStar: a correct resolution creates 10; a wrong one costs 6 in rework.
                    quality_value=10 * correct - 6 * incorrect,
                    points=points_for(arm, attempted, correct, incorrect),
                    elapsed_seconds=elapsed, over_time=int(elapsed > EXP1_SECONDS + EXP1_GRACE_SECONDS),
                    leaderboard_name=leaderboard_name(pid)))
                if res.startswith("error"):
                    st.error(f"Your answers could not be saved ({res[7:]}). Please tell your instructor.")
                else:
                    st.rerun()


# ---------------------------------------------------------------------------
# Activity 3: Defaults (checkout)
# ---------------------------------------------------------------------------
with TAB["defaults"]:
    st.header(ACTIVITIES["defaults"]["student_title"])
    st.caption("Complete this purchase as you would in real life.")

    if has_submitted("defaults", session, pid):
        submitted_banner("Your order was")
    else:
        arm, _ = get_assignment(session, pid, "defaults")
        if arm is None:
            if st.button("Start", type="primary", key="def_start"):
                assign_balanced(session, pid, "defaults")
                st.rerun()
        else:
            st.write(
                "You are buying a **NorthStar SmartWash appliance for CAD 899**. "
                "The manufacturer warranty covers the first year. An optional **3-year NorthStar Protection Plan "
                "costs CAD 79** and covers parts and labour after the first year. Accidental damage is not covered. "
                "The plan can be cancelled within 30 days for a full refund."
            )
            with st.form("def_form"):
                st.subheader("Protection Plan — CAD 79")
                if arm == "Opt-In":
                    chose = st.checkbox("Add the NorthStar Protection Plan", value=False)
                elif arm == "Opt-Out":
                    chose = st.checkbox("NorthStar Protection Plan included — uncheck to remove", value=True)
                else:
                    active = st.radio("Do you want the NorthStar Protection Plan?",
                                      ["Yes, add the plan", "No, thanks"], index=None, key="def_active")
                    chose = None if active is None else active.startswith("Yes")
                cancel = st.radio(
                    "If the plan ends up on your order, would you cancel it within the 30-day full-refund window?",
                    ["No, I would keep it", "Yes, I would cancel it"], index=None, key="def_cancel")
                trust = st.slider("How fair and transparent does this purchase experience feel?", 1, 5, 3,
                                  help="1 = not at all fair/transparent; 5 = very fair/transparent")
                go2 = st.form_submit_button("Place order", type="primary")
            if go2:
                if chose is None or cancel is None:
                    st.error("Answer every question before placing the order.")
                else:
                    res = save_once("defaults", dict(
                        session=session, participant_id=pid, submitted_at=now_iso(), arm=arm,
                        chose_plan=int(chose), would_cancel=int(cancel.startswith("Yes")),
                        trust_rating=int(trust)))
                    if res.startswith("error"):
                        st.error(f"Your order could not be saved ({res[7:]}). Please tell your instructor.")
                    else:
                        st.rerun()


# ---------------------------------------------------------------------------
# Activity 4: Finish choice with randomized bestseller badge (social proof)
# ---------------------------------------------------------------------------
COLORS = [("White", "#F4F4F2"), ("Black", "#1E1E1E"), ("Silver", "#B9BEC4"), ("Navy Blue", "#1F3557")]
BADGED_COLOR = "Navy Blue"
PICK_ACCENT = "#2E86DE"


def appliance_svg(fill):
    # Built as one line: indented multi-line HTML is read by st.markdown as a code block.
    trim = "#8A9096"
    return "".join([
        '<svg viewBox="0 0 120 150" xmlns="http://www.w3.org/2000/svg" '
        'style="width:100%;max-width:120px;height:auto;display:block;margin:0 auto;">',
        f'<rect x="10" y="8" width="100" height="132" rx="12" fill="{fill}" stroke="{trim}" stroke-width="2"/>',
        '<rect x="10" y="8" width="100" height="26" rx="12" fill="#FFFFFF" fill-opacity=".14"/>',
        f'<line x1="10" y1="34" x2="110" y2="34" stroke="{trim}" stroke-opacity=".7"/>',
        f'<circle cx="26" cy="21" r="7" fill="#FFFFFF" fill-opacity=".35" stroke="{trim}"/>',
        '<rect x="52" y="15" width="34" height="12" rx="3" fill="#0F2430"/>',
        '<rect x="56" y="19" width="14" height="4" rx="1" fill="#5FE3A1"/>',
        f'<circle cx="95" cy="21" r="3" fill="{trim}"/><circle cx="103" cy="21" r="3" fill="{trim}"/>',
        f'<circle cx="60" cy="87" r="38" fill="#FFFFFF" fill-opacity=".22" stroke="{trim}" stroke-width="2"/>',
        '<circle cx="60" cy="87" r="28" fill="#7FA3BD" fill-opacity=".6" stroke="#5B6B78"/>',
        '<path d="M44 78 A20 20 0 0 1 62 63" stroke="#FFFFFF" stroke-opacity=".75" stroke-width="4" fill="none" stroke-linecap="round"/>',
        f'<rect x="99" y="80" width="4" height="15" rx="2" fill="{trim}"/>',
        '<rect x="20" y="140" width="14" height="5" rx="2" fill="#555"/><rect x="86" y="140" width="14" height="5" rx="2" fill="#555"/>',
        "</svg>",
    ])


def color_card(name, fill, chosen, badged):
    selected = chosen == name
    dimmed = chosen is not None and not selected
    border = f"3px solid {PICK_ACCENT}" if selected else "3px solid transparent"
    shadow = f"0 6px 18px {PICK_ACCENT}55" if selected else "none"
    pill = ("height:22px;line-height:22px;font-size:12px;font-weight:700;border-radius:11px;"
            "width:fit-content;padding:0 10px;margin:0 auto 6px;")
    if selected:
        top = f'<div style="{pill}color:#fff;background:{PICK_ACCENT};">&#10003; Your pick</div>'
    elif badged:
        top = f'<div style="{pill}color:#7A4B00;background:#FFD66B;">&#9733; Bestseller</div>'
    else:
        top = '<div style="height:22px;margin-bottom:6px;"></div>'
    # When the badged colour is selected, keep the badge visible under the name.
    sub = ('<div style="font-size:11px;font-weight:700;color:#7A4B00;">&#9733; Bestseller</div>'
           if badged and selected else "")
    return (
        f'<div style="border:{border};border-radius:18px;padding:10px 8px 8px;background:rgba(128,128,128,.07);'
        f'box-shadow:{shadow};text-align:center;opacity:{0.45 if dimmed else 1};'
        f'transform:{"scale(1.03)" if selected else "none"};transition:all .2s ease;">'
        f'{top}{appliance_svg(fill)}<div style="font-weight:600;margin-top:6px;">{name}</div>{sub}</div>'
    )


with TAB["finish"]:
    st.header(ACTIVITIES["finish"]["student_title"])
    st.caption("The four models below have the same price and features.")

    if has_submitted("finish", session, pid):
        submitted_banner("Your choice was")
    elif get_assignment(session, pid, "finish")[0] is None:
        if st.button("Start", type="primary", key="fin_start"):
            assign_balanced(session, pid, "finish")
            st.rerun()
    else:
        arm, _ = get_assignment(session, pid, "finish")
        badge_on = arm == "Bestseller badge"
        ordered = COLORS.copy()
        random.Random(pid + "finish").shuffle(ordered)  # position bias

        def pick_color(name):
            st.session_state.finish_choice = name

        chosen = st.session_state.get("finish_choice")
        st.markdown("**Which finish would you choose?**")
        cols = st.columns(4)
        for col, (name, fill) in zip(cols, ordered):
            with col:
                st.markdown(color_card(name, fill, chosen, badge_on and name == BADGED_COLOR),
                            unsafe_allow_html=True)
                st.button("Selected" if chosen == name else "Choose", key=f"finish_pick_{name}",
                          on_click=pick_color, args=(name,), width="stretch",
                          type="primary" if chosen == name else "secondary")
        with st.form("finish_form"):
            likelihood = st.slider("How likely would you be to buy your selected finish?", 1, 5, 3,
                                   help="1 = very unlikely; 5 = very likely")
            premium = st.radio("Would you pay CAD 50 more to get your preferred finish rather than your second choice?",
                               ["No", "Yes"], horizontal=True)
            go3 = st.form_submit_button("Submit choice", type="primary")
        if go3:
            if chosen is None:
                st.error("Choose one finish above before submitting.")
            else:
                res = save_once("finish", dict(
                    session=session, participant_id=pid, submitted_at=now_iso(), arm=arm,
                    preferred_color=chosen, chose_badged=int(chosen == BADGED_COLOR),
                    purchase_likelihood=int(likelihood), would_pay_premium=int(premium == "Yes")))
                if res.startswith("error"):
                    st.error(f"Your choice could not be saved ({res[7:]}). Please tell your instructor.")
                else:
                    st.rerun()


# ---------------------------------------------------------------------------
# Predictions (opened by the instructor after explaining each design, before the reveal)
# ---------------------------------------------------------------------------
PREDICTIONS = {
    "framing": ("Out of 100 classmates, how many chose the **sure plan (Plan A)** in Decision 2 when the plans were described as...",
                {"Gain frame": "accounts kept", "Loss frame": "accounts lost"}),
    "incentives": ("What was the **average accuracy (%)** of completed cases in each group?",
                   {"Control": "no points", "Quantity": "1 point per case completed",
                    "Balanced": "+2 correct, −2 incorrect"}),
    "defaults": ("Out of 100 classmates, how many ended up **with the protection plan** when...",
                 {"Opt-In": "they had to tick a box to add it", "Opt-Out": "it was pre-ticked",
                  "Active choice": "they had to answer yes or no"}),
    "finish": ("Out of 100 classmates, how many chose **Navy Blue** when...",
               {"No badge": "no badge was shown", "Bestseller badge": "Navy Blue had a Bestseller badge"}),
}

# Actual outcome used to compare against predictions (per arm, as %).
def actual_by_arm(experiment, df):
    if df.empty:
        return pd.Series(dtype=float)
    if experiment == "framing":
        s = 1 - df.groupby("arm")["chose_risky"].mean()          # share choosing sure Plan A
    elif experiment == "incentives":
        s = df[df["attempted"] > 0].groupby("arm")["accuracy"].mean()
    elif experiment == "defaults":
        s = df.groupby("arm")["chose_plan"].mean()
    else:
        s = df.groupby("arm")["chose_badged"].mean()
    return s * 100


with TAB["predictions"]:
    st.header("Predictions")
    st.caption("Your instructor will open each prediction after explaining that activity's design, "
               "and before showing the results.")
    st.button("Check for open predictions", key="pred_refresh")
    any_open = False
    for exp in ACTIVITY_ORDER:
        if get_flag(f"{session}:predict_open:{exp}") != "1":
            continue
        any_open = True
        question, arm_desc = PREDICTIONS[exp]
        st.subheader(ACTIVITIES[exp]["student_title"])
        pt = TABLES["predictions"]
        with get_engine().connect() as conn:
            done = conn.execute(select(func.count()).select_from(pt).where(
                pt.c.session == session, pt.c.participant_id == pid, pt.c.experiment == exp)).scalar()
        if done:
            st.success("Prediction submitted.")
            continue
        with st.form(f"pred_{exp}"):
            st.markdown(question)
            vals = {a: st.slider(f"...{d}", 0, 100, 50, key=f"pred_{exp}_{a}") for a, d in arm_desc.items()}
            gop = st.form_submit_button("Submit prediction", type="primary")
        if gop:
            try:
                with get_engine().begin() as conn:
                    for a, v in vals.items():
                        conn.execute(pt.insert().values(session=session, participant_id=pid, experiment=exp,
                                                        arm=a, predicted_pct=float(v), submitted_at=now_iso()))
                st.rerun()
            except IntegrityError:
                st.info("You already submitted this prediction.")
    if not any_open:
        st.info("No predictions are open yet.")


# ---------------------------------------------------------------------------
# Instructor
# ---------------------------------------------------------------------------
with TAB["instructor"]:
    st.header("Instructor")
    code = st.text_input("Instructor access code", type="password", key="instr_code")
    if code and code != INSTRUCTOR_CODE:
        st.error("Incorrect instructor code.")
    if code == INSTRUCTOR_CODE:
        if USING_SQLITE:
            st.warning(
                "Storage is a local SQLite file. On Streamlit Community Cloud this is wiped on reboot or redeploy. "
                "Set DATABASE_URL in the app's secrets to a Postgres database for persistent, pooled data, "
                "or download the CSVs before you close the app."
            )

        view = st.radio("View", ["Class control", "Projector", "Detailed results"], horizontal=True,
                        key="instr_view")

        # ---- Class control -------------------------------------------------
        if view == "Class control":
            st.subheader("Session")
            st.write(f"Active session: **{session}**")
            new_session = st.text_input("Start a new session (e.g., 2027S-sec1)", key="new_session")
            if st.button("Set active session", key="set_session") and new_session.strip():
                set_flag("active_session", new_session.strip())
                st.success(f"Active session is now {new_session.strip()}. Students who join from now on are tagged with it.")
                st.rerun()
            st.caption("Change sessions only between classes. Students mid-activity keep their original session.")

            st.subheader("Progress and predictions")
            st.caption("Suggested flow for each activity: students submit → you explain the design → "
                       "open predictions → students predict → reveal results on the projector.")
            for exp in ACTIVITY_ORDER:
                df = read_table(exp, session)
                assigned = read_table("assignments", session)
                n_assigned = int((assigned["experiment"] == exp).sum()) if not assigned.empty else 0
                key = f"{session}:predict_open:{exp}"
                is_open = get_flag(key) == "1"
                c1, c2 = st.columns([3, 2])
                c1.markdown(f"**{ACTIVITIES[exp]['instructor_title']}** ({ACTIVITIES[exp]['student_title']})  \n"
                            f"{len(df)} submitted of {n_assigned} started")
                if c2.toggle("Predictions open", value=is_open, key=f"toggle_{exp}") != is_open:
                    set_flag(key, "0" if is_open else "1")
                    st.rerun()

        # ---- Projector -----------------------------------------------------
        elif view == "Projector":
            all_sessions = st.checkbox("Pool all sessions", key="proj_pool")
            scope = None if all_sessions else session
            exp = st.selectbox("Activity", ACTIVITY_ORDER, format_func=lambda e: ACTIVITIES[e]["instructor_title"],
                               key="proj_exp")
            df = read_table(exp, scope)
            preds = read_table("predictions", scope)
            preds = preds[preds["experiment"] == exp] if not preds.empty else preds
            reveal = st.toggle("Reveal results", key=f"reveal_{exp}")

            question, arm_desc = PREDICTIONS[exp]
            st.markdown(f"## {ACTIVITIES[exp]['instructor_title']}")
            st.markdown(question.replace("**", ""))
            chart = pd.DataFrame(index=ACTIVITIES[exp]["arms"])
            if not preds.empty:
                chart["Class prediction"] = preds.groupby("arm")["predicted_pct"].mean()
            if reveal:
                chart["Actual"] = actual_by_arm(exp, df)
            chart.index = [f"{a} ({arm_desc[a]})" for a in chart.index]
            if chart.shape[1]:
                st.bar_chart(chart, stack=False, y_label="%", height=420)
            else:
                st.info("No predictions yet.")
            n_pred = preds["participant_id"].nunique() if not preds.empty else 0
            st.caption(f"{len(df)} responses; {n_pred} predictions.")

            if reveal and exp == "incentives" and not df.empty:
                st.markdown("### Value created for NorthStar")
                st.caption("Each correct case is worth 10; each wrong case costs 6 in rework.")
                st.bar_chart(df.groupby("arm")["quality_value"].mean().reindex(ACTIVITIES[exp]["arms"]),
                             horizontal=True, height=220)
                st.markdown("### Leaderboard")
                lc = st.columns(2)
                for col, a in zip(lc, ["Quantity", "Balanced"]):
                    top = df[df["arm"] == a].nlargest(5, "points")[["leaderboard_name", "points"]]
                    col.markdown(f"**{a}**")
                    col.dataframe(top.rename(columns={"leaderboard_name": "Name", "points": "Points"}),
                                  hide_index=True, width="stretch")

        # ---- Detailed results ---------------------------------------------
        else:
            all_sessions = st.checkbox("Pool all sessions", key="det_pool")
            scope = None if all_sessions else session
            data = {e: read_table(e, scope) for e in ACTIVITY_ORDER + ["predictions", "assignments"]}
            if all_sessions and not data["framing"].empty:
                st.caption(f"Sessions included: {', '.join(sorted(data['assignments']['session'].unique()))}")

            # Framing
            st.subheader("Gain vs. loss framing")
            e = data["framing"]
            if e.empty:
                st.info("No submissions yet.")
            else:
                s = e.groupby("arm").agg(students=("participant_id", "count"),
                                         ecoseries_rate=("chose_upgrade", "mean"),
                                         avg_persuasiveness=("persuasiveness", "mean"),
                                         risky_plan_share=("chose_risky", "mean")).reset_index()
                st.dataframe(s.style.format({"ecoseries_rate": "{:.1%}", "risky_plan_share": "{:.1%}",
                                             "avg_persuasiveness": "{:.2f}"}), hide_index=True, width="stretch")
                loss, gain = e[e["arm"] == "Loss frame"], e[e["arm"] == "Gain frame"]
                c1, c2 = st.columns(2)
                with c1:
                    show_effect("EcoSeries uptake: Loss minus Gain",
                                prop_diff(loss["chose_upgrade"], gain["chose_upgrade"]))
                with c2:
                    show_effect("Risky Plan B: Loss minus Gain", prop_diff(loss["chose_risky"], gain["chose_risky"]))
                with st.expander("Debrief notes"):
                    st.markdown(
                        "- **Decision 1:** both messages state the same CAD 60/year saving. Loss aversion predicts the "
                        "loss frame is at least as persuasive; field evidence is mixed, which is worth discussing.\n"
                        "- **Decision 2:** the plans have the same expected outcome (400 kept / 800 lost). Tversky & "
                        "Kahneman (1981) found people are risk-averse over gains and risk-seeking over losses, so expect "
                        "more Plan B choices under the loss frame. The numbers differ from the classic 600-person version "
                        "so that students who know it are less likely to recognise it.\n"
                        "- **Managerial angle:** presentation alone can flip a board's or customer's choice. When is that "
                        "persuasion, and when is it manipulation?"
                    )

            # Incentives
            st.subheader("Incentives and productivity")
            e = data["incentives"]
            if e.empty:
                st.info("No submissions yet.")
            else:
                exclude = st.checkbox(f"Exclude late submissions (over {EXP1_SECONDS + EXP1_GRACE_SECONDS} s)",
                                      value=True, key="excl_late")
                if exclude:
                    st.caption(f"{int(e['over_time'].sum())} late submission(s) excluded.")
                    e = e[e["over_time"] == 0]
                s = e.groupby("arm").agg(students=("participant_id", "count"),
                                         avg_completed=("attempted", "mean"),
                                         avg_accuracy=("accuracy", "mean"),
                                         avg_value=("quality_value", "mean")).reindex(ACTIVITIES["incentives"]["arms"]).reset_index()
                st.dataframe(s.style.format({"avg_completed": "{:.1f}", "avg_accuracy": "{:.1%}", "avg_value": "{:.1f}"},
                                            na_rep="–"), hide_index=True, width="stretch")
                st.caption(f"{len(CASES)} cases, {EXP1_SECONDS}-second limit. Value = 10 per correct case − 6 per wrong case.")
                with st.expander("Debrief notes"):
                    st.markdown(
                        "- Quantity rewards completions only, so expect more cases completed and lower accuracy.\n"
                        "- Several cases are traps for rushing (delivered weeks ago is not dead on arrival; one previous "
                        "repair is not two; safety overrides everything).\n"
                        "- Compare **value created**, not cases completed: is NorthStar paying for the metric or the outcome?"
                    )

            # Defaults
            st.subheader("Defaults and warranty margin")
            e = data["defaults"]
            if e.empty:
                st.info("No submissions yet.")
            else:
                e = e.assign(kept_plan=e["chose_plan"] * (1 - e["would_cancel"]))
                s = e.groupby("arm").agg(students=("participant_id", "count"),
                                         adoption_rate=("chose_plan", "mean"),
                                         kept_after_30_days=("kept_plan", "mean"),
                                         avg_trust=("trust_rating", "mean")).reindex(ACTIVITIES["defaults"]["arms"]).reset_index()
                st.dataframe(s.style.format({"adoption_rate": "{:.1%}", "kept_after_30_days": "{:.1%}",
                                             "avg_trust": "{:.2f}"}, na_rep="–"), hide_index=True, width="stretch")
                base = e[e["arm"] == "Opt-In"]
                c1, c2 = st.columns(2)
                with c1:
                    show_effect("Opt-Out minus Opt-In (adoption)",
                                prop_diff(e[e["arm"] == "Opt-Out"]["chose_plan"], base["chose_plan"]))
                with c2:
                    show_effect("Active choice minus Opt-In (adoption)",
                                prop_diff(e[e["arm"] == "Active choice"]["chose_plan"], base["chose_plan"]))

                st.markdown("**Translate into margin (net of 30-day cancellations)**")
                c1, c2, c3 = st.columns(3)
                net_contribution = c1.number_input("Net contribution per kept plan (CAD)", min_value=0.0,
                                                   value=40.0, step=5.0, key="net_contrib")
                cancel_cost = c2.number_input("Cost per cancelled plan (CAD)", min_value=0.0, value=8.0,
                                              step=1.0, key="cancel_cost",
                                              help="Processing, refund handling, and service time.")
                volume = c3.number_input("Customer volume", min_value=1, value=10000, step=1000, key="volume")
                rows = []
                for a in ACTIVITIES["defaults"]["arms"]:
                    g = e[e["arm"] == a]
                    if g.empty:
                        continue
                    kept = g["kept_plan"].mean()
                    cancelled = (g["chose_plan"] * g["would_cancel"]).mean()
                    rows.append({"arm": a, "margin_CAD": volume * (kept * net_contribution - cancelled * cancel_cost),
                                 "avg_trust": g["trust_rating"].mean()})
                if rows:
                    m = pd.DataFrame(rows)
                    st.dataframe(m.style.format({"margin_CAD": "CAD {:,.0f}", "avg_trust": "{:.2f}"}),
                                 hide_index=True, width="stretch")
                    st.caption("Does not include complaint, regulatory, or longer-run trust costs. "
                               "Compare the margin ranking with the trust ranking.")

            # Finish
            st.subheader("Social proof (bestseller badge)")
            e = data["finish"]
            if e.empty:
                st.info("No submissions yet.")
            else:
                s = e.groupby("arm").agg(students=("participant_id", "count"),
                                         navy_share=("chose_badged", "mean"),
                                         premium_share=("would_pay_premium", "mean")).reindex(ACTIVITIES["finish"]["arms"]).reset_index()
                st.dataframe(s.style.format({"navy_share": "{:.1%}", "premium_share": "{:.1%}"}, na_rep="–"),
                             hide_index=True, width="stretch")
                show_effect(f"{BADGED_COLOR} share: Badge minus No badge",
                            prop_diff(e[e["arm"] == "Bestseller badge"]["chose_badged"],
                                      e[e["arm"] == "No badge"]["chose_badged"]))
                shares = e.groupby(["arm", "preferred_color"]).size().unstack(fill_value=0)
                st.dataframe(shares.div(shares.sum(axis=1), axis=0).style.format("{:.0%}"), width="stretch")

            # Downloads
            st.subheader("Download data")
            dc = st.columns(3)
            for i, name in enumerate(ACTIVITY_ORDER + ["predictions", "assignments"]):
                dc[i % 3].download_button(f"{name}.csv", data[name].to_csv(index=False).encode("utf-8"),
                                          f"{name}.csv", "text/csv", key=f"dl_{name}")
