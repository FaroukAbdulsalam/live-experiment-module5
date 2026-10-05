
import streamlit as st
import pandas as pd
import sqlite3
import uuid
import hashlib
import os
import random
from datetime import datetime, timezone

st.set_page_config(page_title="NorthStar Live Experiments", page_icon="🧪", layout="centered")

DB_PATH = "northstar_experiments.db"
INSTRUCTOR_CODE = os.environ.get("INSTRUCTOR_CODE", "northstar")

TABLE_SCHEMAS = {
    "exp1": [("participant_id", "TEXT PRIMARY KEY"), ("submitted_at", "TEXT"), ("arm", "TEXT"),
             ("attempted", "INTEGER"), ("correct", "INTEGER"), ("incorrect", "INTEGER"),
             ("accuracy", "REAL"), ("quality_value", "REAL"), ("elapsed_seconds", "REAL")],
    "exp2": [("participant_id", "TEXT PRIMARY KEY"), ("submitted_at", "TEXT"), ("arm", "TEXT"),
             ("chose_plan", "INTEGER"), ("trust_rating", "INTEGER")],
    "exp3": [("participant_id", "TEXT PRIMARY KEY"), ("submitted_at", "TEXT"), ("preferred_color", "TEXT"),
             ("purchase_likelihood", "INTEGER"), ("would_pay_premium", "INTEGER")],
    "exp4": [("participant_id", "TEXT PRIMARY KEY"), ("submitted_at", "TEXT"), ("arm", "TEXT"),
             ("chose_upgrade", "INTEGER"), ("persuasiveness", "INTEGER"), ("chose_risky", "INTEGER")],
}

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    for table, cols in TABLE_SCHEMAS.items():
        existing = [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        expected = [c[0] for c in cols]
        if existing and existing != expected:
            # A table left over from an older version of the app has a different layout.
            # Archive it (data kept) rather than failing every insert.
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            conn.execute(f"ALTER TABLE {table} RENAME TO {table}_archived_{stamp}")
        col_sql = ", ".join(f"{name} {ctype}" for name, ctype in cols)
        conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({col_sql})")
    conn.commit()
    return conn

def save_row(table, values):
    """Insert one participant's row; returns True on success, shows an error otherwise."""
    cols = [c[0] for c in TABLE_SCHEMAS[table]]
    sql = (f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) "
           f"VALUES ({', '.join('?' * len(cols))})")
    try:
        conn = get_conn()
        conn.execute(sql, values)
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        st.error(f"Your response could not be saved ({e}). Please tell your instructor.")
        return False

def stable_arm(participant_id, n):
    h = int(hashlib.sha256(participant_id.encode()).hexdigest(), 16)
    return h % n

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
    d, lo, hi = result
    st.metric(label, f"{d*100:+.1f} pp")
    st.caption(f"95% CI: {lo*100:+.1f} to {hi*100:+.1f} pp (normal approximation; wide with small groups).")

# Neutral group labels so students are not primed by the treatment name.
EXP2_GROUPS = {"Group A": "Opt-In", "Group B": "Opt-Out"}
EXP4_GROUPS = {"Group X": "Gain frame", "Group Y": "Loss frame"}

if "participant_id" not in st.session_state:
    st.session_state.participant_id = str(uuid.uuid4())[:8]
if "exp1_start" not in st.session_state:
    st.session_state.exp1_start = None
if "exp1_submitted" not in st.session_state:
    st.session_state.exp1_submitted = False
if "exp1_arm" not in st.session_state:
    st.session_state.exp1_arm = None
if "exp2_submitted" not in st.session_state:
    st.session_state.exp2_submitted = False
if "exp3_submitted" not in st.session_state:
    st.session_state.exp3_submitted = False
for _k, _v in {
    "exp2_arm": None, "exp2_started": False,
    "exp3_choice": None,
    "exp4_arm": None, "exp4_started": False, "exp4_submitted": False,
}.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

participant_id = st.session_state.participant_id

CASES = [
    ("The appliance works, but the customer cannot connect the mobile app to Wi-Fi.", "Remote fix"),
    ("The door will not close properly. There is no smoke, smell, or electrical danger.", "Technician visit"),
    ("The customer sees sparks when the appliance is switched on.", "Safety escalation"),
    ("The appliance was delivered today and does not power on at all.", "Replace"),
    ("A software update caused the display language to change, but the appliance still works.", "Remote fix"),
    ("The appliance makes a loud grinding noise during use, but there is no safety issue.", "Technician visit"),
    ("The same fault has returned after two previous technician repairs.", "Replace"),
    ("A burning smell appears when the heating cycle starts.", "Safety escalation"),
]

ACTIONS = ["—", "Remote fix", "Technician visit", "Replace", "Safety escalation"]

st.title("NorthStar Live Experiments")
st.caption(f"Anonymous participant code: {participant_id}")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["Experiment 1", "Experiment 2", "Experiment 3", "Experiment 4", "Instructor Results & Data"]
)

with tab1:
    st.header("Experiment 1: Productivity and Incentives")
    st.write("**Question:** What happens when employees are rewarded for speed versus speed + accuracy?")
    st.caption("Everyone gets the same 8 customer cases. The only thing that changes is the incentive.")

    st.info(
        "Use only these four rules:\n"
        "1) App/software/setup problem → Remote fix\n"
        "2) Physical repair needed, but no danger → Technician visit\n"
        "3) Dead on arrival OR same fault after two repairs → Replace\n"
        "4) Sparks, smoke, burning smell, shock, or overheating → Safety escalation"
    )

    st.subheader("Select the treatment your instructor assigned to you")
    st.caption("Your instructor will tell you which treatment to choose. Please do not choose a different one.")

    treatment_choice = st.radio(
        "Assigned treatment",
        ["Control", "Quantity", "Balanced"],
        index=None,
        horizontal=True,
        disabled=st.session_state.exp1_start is not None or st.session_state.exp1_submitted,
        key="exp1_group",
    )

    if treatment_choice and st.session_state.exp1_start is None and not st.session_state.exp1_submitted:
        st.session_state.exp1_arm = treatment_choice

    exp1_arm = st.session_state.exp1_arm

    if exp1_arm == "Control":
        st.info("**CONTROL:** Complete the task carefully. Your objective is to make sound service decisions.")
    elif exp1_arm == "Quantity":
        st.info("**QUANTITY:** You earn 1 point for every case you complete. Try to process as many cases as possible.")
    elif exp1_arm == "Balanced":
        st.info("**BALANCED:** You earn 2 points for each correct case and lose 2 points for each incorrect case. Balance speed and accuracy.")

    if st.session_state.exp1_start is None and not st.session_state.exp1_submitted:
        if exp1_arm is None:
            st.warning("Select the treatment assigned by your instructor before starting.")
        elif st.button("Start Experiment 1", type="primary"):
            st.session_state.exp1_start = datetime.now(timezone.utc).isoformat()
            st.rerun()

    if st.session_state.exp1_start and not st.session_state.exp1_submitted:
        st.warning("The instructor controls the time. Work until you are told to stop, then submit immediately.")
        with st.form("exp1_form"):
            choices = []
            for i, (case, answer) in enumerate(CASES, start=1):
                st.markdown(f"**Case {i}.** {case}")
                choice = st.selectbox(
                    f"Decision for case {i}",
                    ACTIONS,
                    index=0,
                    key=f"case_{i}",
                    label_visibility="collapsed"
                )
                choices.append(choice)
            submitted = st.form_submit_button("Submit Experiment 1", type="primary")

        if submitted:
            attempted = sum(c != "—" for c in choices)
            correct = sum((c != "—") and (c == CASES[i][1]) for i, c in enumerate(choices))
            incorrect = attempted - correct
            accuracy = (correct / attempted) if attempted else 0.0
            # Quality-adjusted value: correct resolution creates 10 units of value;
            # an incorrect resolution imposes 6 units of rework/customer cost.
            quality_value = 10 * correct - 6 * incorrect
            start_dt = datetime.fromisoformat(st.session_state.exp1_start)
            elapsed = (datetime.now(timezone.utc) - start_dt).total_seconds()

            if not save_row("exp1", (
                    participant_id,
                    datetime.now(timezone.utc).isoformat(),
                    exp1_arm,
                    attempted,
                    correct,
                    incorrect,
                    accuracy,
                    quality_value,
                    elapsed,
                )):
                st.stop()
            st.session_state.exp1_submitted = True
            st.session_state.exp1_result = {
                "attempted": attempted,
                "correct": correct,
                "incorrect": incorrect,
                "accuracy": accuracy,
                "quality_value": quality_value,
                "elapsed": elapsed,
            }
            st.rerun()

    if st.session_state.exp1_submitted:
        r = st.session_state.exp1_result
        st.success("Experiment 1 submitted.")
        c1, c2, c3 = st.columns(3)
        c1.metric("Cases attempted", r["attempted"])
        c2.metric("Accuracy", f'{r["accuracy"]:.0%}')
        c3.metric("Quality-adjusted value", f'{r["quality_value"]:.0f}')
        with st.expander("What are we testing?"):
            st.write(
                "If people are rewarded only for finishing more cases, they may work faster but make more mistakes. "
                "If rewards also depend on accuracy, they may complete fewer cases but create more value. "
                "NorthStar should reward the outcome it truly cares about—not just the easiest metric to count."
            )

with tab2:
    st.header("Experiment 2: Customer Margin Test")
    st.write("**Question:** Can NorthStar increase warranty contribution margin without cutting the appliance price?")

    st.subheader("Select the group your instructor assigned to you")
    st.caption("Your instructor will tell you which group to choose. Please do not choose a different one.")

    exp2_locked = st.session_state.exp2_started or st.session_state.exp2_submitted
    exp2_group = st.radio(
        "Assigned group",
        list(EXP2_GROUPS),
        index=None,
        horizontal=True,
        disabled=exp2_locked,
        key="exp2_group",
    )
    if exp2_group and not exp2_locked:
        st.session_state.exp2_arm = EXP2_GROUPS[exp2_group]
    exp2_arm = st.session_state.exp2_arm

    if not exp2_locked:
        if exp2_arm is None:
            st.warning("Select the group assigned by your instructor before starting.")
        elif st.button("Start Experiment 2", type="primary"):
            st.session_state.exp2_started = True
            st.rerun()

    if st.session_state.exp2_started and not st.session_state.exp2_submitted:
        st.write(
            "Imagine you are buying a **NorthStar SmartWash appliance for CAD 899**. "
            "The manufacturer warranty covers the first year. An optional **3-year NorthStar Protection Plan costs CAD 79** "
            "and covers parts and labour after the first year. Accidental damage is not covered. "
            "The plan can be cancelled within 30 days for a full refund."
        )
        with st.form("exp2_form"):
            st.subheader("Protection Plan — CAD 79")
            if exp2_arm == "Opt-In":
                chose_plan = st.checkbox("Add the NorthStar Protection Plan", value=False)
            else:
                chose_plan = st.checkbox(
                    "NorthStar Protection Plan included — uncheck to remove",
                    value=True
                )
            trust = st.slider(
                "How fair and transparent does this purchase experience feel?",
                min_value=1,
                max_value=5,
                value=3,
                help="1 = not at all fair/transparent; 5 = very fair/transparent"
            )
            submitted2 = st.form_submit_button("Submit Experiment 2", type="primary")

        if submitted2:
            if not save_row("exp2", (
                    participant_id,
                    datetime.now(timezone.utc).isoformat(),
                    exp2_arm,
                    int(chose_plan),
                    int(trust),
                )):
                st.stop()
            st.session_state.exp2_submitted = True
            st.session_state.exp2_choice = int(chose_plan)
            st.session_state.exp2_trust = int(trust)
            st.rerun()

    if st.session_state.exp2_submitted:
        st.success("Experiment 2 submitted. Please do not discuss your screen with classmates until the instructor reveals the results.")
        st.metric("Your choice", "Protection plan" if st.session_state.exp2_choice else "No protection plan")


with tab3:
    st.header("Experiment 3: Product Color Preference")
    st.write("**Question:** Which appliance finish would customers prefer if price and features were identical?")
    st.caption(
        "This is primarily a preference test for the marketing and design teams. "
        "The order of the four options is randomized across participants to reduce position bias."
    )

    colors = [
        ("White", "#F4F4F2"),
        ("Black", "#1E1E1E"),
        ("Silver", "#B9BEC4"),
        ("Navy Blue", "#1F3557"),
    ]

    rng = random.Random(int(hashlib.sha256((participant_id + "exp3").encode()).hexdigest(), 16))
    ordered_colors = colors.copy()
    rng.shuffle(ordered_colors)

    PICK_ACCENT = "#2E86DE"

    def appliance_svg(fill):
        # Built as one line: indented multi-line HTML is read by st.markdown as a
        # code block, which is what made raw HTML appear next to the icons.
        trim = "#8A9096"
        parts = [
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
        ]
        return "".join(parts)

    def color_card(name, fill, chosen):
        selected = chosen == name
        dimmed = chosen is not None and not selected
        border = f"3px solid {PICK_ACCENT}" if selected else "3px solid transparent"
        shadow = f"0 6px 18px {PICK_ACCENT}55" if selected else "none"
        badge_style = (
            f"height:22px;line-height:22px;font-size:12px;font-weight:700;color:#fff;"
            f"background:{PICK_ACCENT};border-radius:11px;width:fit-content;padding:0 10px;margin:0 auto 6px;"
        )
        badge = f'<div style="{badge_style}">&#10003; Your pick</div>' if selected else '<div style="height:22px;margin-bottom:6px;"></div>'
        return (
            f'<div style="border:{border};border-radius:18px;padding:10px 8px 8px;'
            f'background:rgba(128,128,128,.07);box-shadow:{shadow};text-align:center;'
            f'opacity:{0.45 if dimmed else 1};transform:{"scale(1.03)" if selected else "none"};'
            f'transition:all .2s ease;">'
            f'{badge}{appliance_svg(fill)}'
            f'<div style="font-weight:600;margin-top:6px;">{name}</div></div>'
        )

    def pick_color(name):
        st.session_state.exp3_choice = name

    st.markdown("**If all four appliances had the same price and features, which color would you choose?**")
    chosen = st.session_state.exp3_choice
    card_cols = st.columns(4)
    for col, (name, fill) in zip(card_cols, ordered_colors):
        with col:
            st.markdown(color_card(name, fill, chosen), unsafe_allow_html=True)
            st.button(
                "Selected" if chosen == name else "Choose",
                key=f"exp3_pick_{name}",
                on_click=pick_color,
                args=(name,),
                type="primary" if chosen == name else "secondary",
                width="stretch",
                disabled=st.session_state.exp3_submitted,
            )

    with st.form("exp3_form"):
        likelihood = st.slider(
            "How likely would you be to buy your selected color?",
            min_value=1,
            max_value=5,
            value=3,
            help="1 = very unlikely; 5 = very likely"
        )
        premium = st.radio(
            "Would you pay CAD 50 more to get your preferred color rather than your second choice?",
            ["No", "Yes"],
            horizontal=True
        )
        submit3 = st.form_submit_button("Submit Experiment 3", type="primary")

    preferred = st.session_state.exp3_choice
    if submit3 and not st.session_state.exp3_submitted:
        if preferred is None:
            st.error("Choose one appliance color above before submitting.")
        else:
            if not save_row("exp3", (
                    participant_id,
                    datetime.now(timezone.utc).isoformat(),
                    preferred,
                    int(likelihood),
                    1 if premium == "Yes" else 0,
                )):
                st.stop()
            st.session_state.exp3_submitted = True
            st.session_state.exp3_preferred = preferred
            st.rerun()

    if st.session_state.exp3_submitted:
        st.success(f"Experiment 3 submitted. You selected {st.session_state.exp3_preferred}.")
        st.write(
            "The class results will show the design team which finish is most preferred "
            "and whether customers appear willing to pay for that preference."
        )

with tab4:
    st.header("Experiment 4: Gains vs. Losses")
    st.write("**Question:** Does describing the *same* facts as a gain or as a loss change what people choose?")
    st.caption("Two quick decisions, about one minute in total.")

    st.subheader("Select the group your instructor assigned to you")
    st.caption("Your instructor will tell you which group to choose. Please do not choose a different one.")

    exp4_locked = st.session_state.exp4_started or st.session_state.exp4_submitted
    exp4_group = st.radio(
        "Assigned group",
        list(EXP4_GROUPS),
        index=None,
        horizontal=True,
        disabled=exp4_locked,
        key="exp4_group",
    )
    if exp4_group and not exp4_locked:
        st.session_state.exp4_arm = EXP4_GROUPS[exp4_group]
    exp4_arm = st.session_state.exp4_arm

    if not exp4_locked:
        if exp4_arm is None:
            st.warning("Select the group assigned by your instructor before starting.")
        elif st.button("Start Experiment 4", type="primary"):
            st.session_state.exp4_started = True
            st.rerun()

    if st.session_state.exp4_started and not st.session_state.exp4_submitted:
        gain = exp4_arm == "Gain frame"

        # Identical layout, colour and length in both arms: only the wording changes.
        if gain:
            ad_head = "Save about CAD 60 every year."
            ad_body = "Choose EcoSeries and keep roughly CAD 60 a year in your pocket through lower energy and water bills."
        else:
            ad_head = "Stop losing about CAD 60 every year."
            ad_body = "With the standard model, you lose roughly CAD 60 a year to higher energy and water bills."
        ad_html = (
            '<div style="border:2px solid #1F3557;border-radius:14px;padding:16px 18px;margin:6px 0 14px;'
            'background:rgba(31,53,87,.06);">'
            '<div style="font-size:12px;font-weight:700;color:#1F3557;letter-spacing:.02em;">NorthStar EcoSeries</div>'
            f'<div style="font-size:22px;font-weight:800;margin:4px 0 6px;">{ad_head}</div>'
            f'<div style="font-size:15px;">{ad_body}</div></div>'
        )

        if gain:
            plan_a = "Plan A: 200 of the 600 customers will be retained for sure."
            plan_b = "Plan B: a 1-in-3 chance that all 600 customers are retained, and a 2-in-3 chance that none are retained."
        else:
            plan_a = "Plan A: 400 of the 600 customers will be lost for sure."
            plan_b = "Plan B: a 1-in-3 chance that no customers are lost, and a 2-in-3 chance that all 600 are lost."

        with st.form("exp4_form"):
            st.markdown("#### Decision 1: Which model would you buy?")
            st.write(
                "You are buying a **NorthStar SmartWash for CAD 899**. The **EcoSeries** version is identical, "
                "except that it costs **CAD 120 more** and uses less energy and water. You see this message:"
            )
            st.markdown(ad_html, unsafe_allow_html=True)
            upgrade = st.radio(
                "Your choice",
                ["Standard SmartWash (CAD 899)", "EcoSeries SmartWash (CAD 1,019)"],
                index=None,
                key="exp4_upgrade",
            )
            persuasive = st.slider(
                "How persuasive is the NorthStar message?",
                min_value=1, max_value=5, value=3,
                help="1 = not at all persuasive; 5 = very persuasive",
            )

            st.markdown("#### Decision 2: Customer recovery plan")
            st.write(
                "You run customer service. A supplier defect has put **600 NorthStar customers** at risk of "
                "switching to a competitor. You can fund only one recovery plan."
            )
            plan = st.radio("Which plan do you fund?", [plan_a, plan_b], index=None, key="exp4_plan")
            submit4 = st.form_submit_button("Submit Experiment 4", type="primary")

        if submit4:
            if upgrade is None or plan is None:
                st.error("Answer both decisions before submitting.")
            else:
                if not save_row("exp4", (
                        participant_id,
                        datetime.now(timezone.utc).isoformat(),
                        exp4_arm,
                        int(upgrade.startswith("EcoSeries")),
                        int(persuasive),
                        int(plan == plan_b),
                    )):
                    st.stop()
                st.session_state.exp4_submitted = True
                st.rerun()

    if st.session_state.exp4_submitted:
        st.success("Experiment 4 submitted. Please do not discuss your screen with classmates until the instructor reveals the results.")

with tab5:
    st.header("Instructor Results & Data")
    code = st.text_input("Instructor access code", type="password")
    if code == INSTRUCTOR_CODE:
        st.success("Instructor access granted.")
        st.write(
            "**Where the data are:** Results appear below as soon as students submit. "
            "Use the download buttons to save the raw student-level data as CSV."
        )
        st.caption(
            "The app also stores all submissions in `northstar_experiments.db` in the same folder where the Streamlit app is running."
        )

        conn = get_conn()
        e1 = pd.read_sql_query("SELECT * FROM exp1", conn)
        e2 = pd.read_sql_query("SELECT * FROM exp2", conn)
        e3 = pd.read_sql_query("SELECT * FROM exp3", conn)
        e4 = pd.read_sql_query("SELECT * FROM exp4", conn)
        conn.close()

        st.subheader("Group assignment guide")
        st.markdown(
            "- **Experiment 1:** one-third each select **Control**, **Quantity**, **Balanced**.\n"
            "- **Experiment 2:** half select **Group A** (= Opt-In, control), half **Group B** (= Opt-Out, treatment).\n"
            "- **Experiment 4:** half select **Group X** (= Gain frame), half **Group Y** (= Loss frame).\n\n"
            "Students see neutral group names so the label itself does not prime them. "
            "Use a different splitting rule for each experiment (e.g., seat rows, then odd/even birth month) "
            "so the same students are not always treated together."
        )

        st.subheader("Experiment 1 results")
        if e1.empty:
            st.info("No Experiment 1 submissions yet.")
        else:
            summary1 = (
                e1.groupby("arm", as_index=False)
                  .agg(
                      students=("participant_id", "count"),
                      avg_attempted=("attempted", "mean"),
                      avg_accuracy=("accuracy", "mean"),
                      avg_value=("quality_value", "mean"),
                  )
            )
            summary1["avg_accuracy"] = summary1["avg_accuracy"].map(lambda x: f"{x:.1%}")
            st.dataframe(summary1, width="stretch", hide_index=True)
            st.download_button(
                "Download Experiment 1 CSV",
                e1.to_csv(index=False).encode("utf-8"),
                "experiment1_results.csv",
                "text/csv"
            )

        st.subheader("Experiment 2 results")
        if e2.empty:
            st.info("No Experiment 2 submissions yet.")
        else:
            summary2 = (
                e2.groupby("arm", as_index=False)
                  .agg(
                      students=("participant_id", "count"),
                      adoption_rate=("chose_plan", "mean"),
                      avg_trust=("trust_rating", "mean"),
                  )
            )
            summary2["adoption_rate"] = summary2["adoption_rate"].map(lambda x: f"{x:.1%}")
            st.dataframe(summary2, width="stretch", hide_index=True)

            st.bar_chart(
                e2.groupby("arm")["chose_plan"].mean().rename("adoption rate"),
                horizontal=True,
            )
            effect2 = prop_diff(
                e2.loc[e2["arm"] == "Opt-Out", "chose_plan"],
                e2.loc[e2["arm"] == "Opt-In", "chose_plan"],
            )
            if effect2 is not None:
                default_effect = effect2[0]
                show_effect("Default effect (Opt-Out minus Opt-In)", effect2)

                st.markdown("**Translate adoption into margin**")
                c1, c2 = st.columns(2)
                with c1:
                    net_contribution = st.number_input(
                        "Net contribution per protection plan (CAD)",
                        min_value=0.0,
                        value=40.0,
                        step=5.0,
                        help="Enter price minus expected service/administration cost."
                    )
                with c2:
                    customer_volume = st.number_input(
                        "Customer volume for scaling",
                        min_value=1,
                        value=10000,
                        step=1000
                    )
                incremental_margin = default_effect * customer_volume * net_contribution
                st.metric(
                    "Estimated incremental contribution margin",
                    f"CAD {incremental_margin:,.0f}"
                )
                st.caption(
                    "This is a first-pass calculation. It does not subtract any additional "
                    "complaint, cancellation, regulatory, or trust costs caused by the default."
                )

            st.download_button(
                "Download Experiment 2 CSV",
                e2.to_csv(index=False).encode("utf-8"),
                "experiment2_results.csv",
                "text/csv"
            )

        st.subheader("Experiment 3 results")
        if e3.empty:
            st.info("No Experiment 3 submissions yet.")
        else:
            summary3 = (
                e3.groupby("preferred_color", as_index=False)
                  .agg(
                      students=("participant_id", "count"),
                      avg_purchase_likelihood=("purchase_likelihood", "mean"),
                      premium_share=("would_pay_premium", "mean"),
                  )
            )
            total3 = summary3["students"].sum()
            summary3["choice_share"] = summary3["students"] / total3
            summary3["choice_share"] = summary3["choice_share"].map(lambda x: f"{x:.1%}")
            summary3["premium_share"] = summary3["premium_share"].map(lambda x: f"{x:.1%}")
            st.dataframe(summary3, width="stretch", hide_index=True)
            st.download_button(
                "Download Experiment 3 CSV",
                e3.to_csv(index=False).encode("utf-8"),
                "experiment3_results.csv",
                "text/csv"
            )

        st.subheader("Experiment 4 results")
        if e4.empty:
            st.info("No Experiment 4 submissions yet.")
        else:
            summary4 = (
                e4.groupby("arm", as_index=False)
                  .agg(
                      students=("participant_id", "count"),
                      ecoseries_rate=("chose_upgrade", "mean"),
                      avg_persuasiveness=("persuasiveness", "mean"),
                      risky_plan_share=("chose_risky", "mean"),
                  )
            )
            chart4 = summary4.set_index("arm")[["ecoseries_rate", "risky_plan_share"]]
            for c in ["ecoseries_rate", "risky_plan_share"]:
                summary4[c] = summary4[c].map(lambda x: f"{x:.1%}")
            st.dataframe(summary4, width="stretch", hide_index=True)
            st.bar_chart(chart4, stack=False)

            loss = e4[e4["arm"] == "Loss frame"]
            gain = e4[e4["arm"] == "Gain frame"]
            c1, c2 = st.columns(2)
            eff_up = prop_diff(loss["chose_upgrade"], gain["chose_upgrade"])
            eff_risk = prop_diff(loss["chose_risky"], gain["chose_risky"])
            if eff_up is not None:
                with c1:
                    show_effect("EcoSeries uptake: Loss minus Gain", eff_up)
                with c2:
                    show_effect("Risky Plan B: Loss minus Gain", eff_risk)
            with st.expander("Debrief notes"):
                st.markdown(
                    "- **Decision 1 (message framing):** both messages state the same CAD 60/year saving. "
                    "Loss aversion predicts the loss-framed message is at least as persuasive, often more so. "
                    "Field evidence is mixed, which is itself a useful discussion point.\n"
                    "- **Decision 2 (risky choice):** Plans A and B have the same expected outcome (200 retained / 400 lost). "
                    "Tversky & Kahneman (1981) found people tend to be **risk-averse in gains** (pick the sure Plan A) "
                    "and **risk-seeking in losses** (gamble on Plan B). A positive Loss-minus-Gain gap on Plan B "
                    "replicates this.\n"
                    "- **Managerial angle:** how a decision is presented to a board, a customer or a team can flip "
                    "the choice without changing any fact. When is that persuasion, and when is it manipulation?"
                )
            st.download_button(
                "Download Experiment 4 CSV",
                e4.to_csv(index=False).encode("utf-8"),
                "experiment4_results.csv",
                "text/csv"
            )

        st.divider()
        st.caption(
            "Default instructor code is 'northstar'. For classroom use, set an environment variable "
            "INSTRUCTOR_CODE to your preferred code before launching the app."
        )
    elif code:
        st.error("Incorrect instructor code.")
