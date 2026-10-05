
import streamlit as st
import pandas as pd
import sqlite3
import uuid
import hashlib
import os
from datetime import datetime, timezone

st.set_page_config(page_title="NorthStar Live Experiments", page_icon="🧪", layout="centered")

DB_PATH = "northstar_experiments.db"
INSTRUCTOR_CODE = os.environ.get("INSTRUCTOR_CODE", "northstar")

def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exp1 (
            participant_id TEXT PRIMARY KEY,
            submitted_at TEXT,
            arm TEXT,
            attempted INTEGER,
            correct INTEGER,
            incorrect INTEGER,
            accuracy REAL,
            quality_value REAL,
            elapsed_seconds REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exp2 (
            participant_id TEXT PRIMARY KEY,
            submitted_at TEXT,
            arm TEXT,
            chose_plan INTEGER,
            trust_rating INTEGER
        )
    """)
    conn.commit()
    return conn

def stable_arm(participant_id, n):
    h = int(hashlib.sha256(participant_id.encode()).hexdigest(), 16)
    return h % n

if "participant_id" not in st.session_state:
    st.session_state.participant_id = str(uuid.uuid4())[:8]
if "exp1_start" not in st.session_state:
    st.session_state.exp1_start = None
if "exp1_submitted" not in st.session_state:
    st.session_state.exp1_submitted = False
if "exp2_submitted" not in st.session_state:
    st.session_state.exp2_submitted = False

participant_id = st.session_state.participant_id
exp1_arm = ["Control", "Quantity", "Balanced"][stable_arm(participant_id + "exp1", 3)]
exp2_arm = ["Opt-In", "Opt-Out"][stable_arm(participant_id + "exp2", 2)]

CASES = [
    ("A customer says the appliance works normally, but the mobile app will not pair with Wi-Fi.", "Remote fix"),
    ("The door will not latch properly. There is no smoke, smell, or visible electrical issue.", "Technician visit"),
    ("The customer reports sparks from the appliance when it is switched on.", "Safety escalation"),
    ("The appliance was delivered yesterday and has never powered on, even after basic checks.", "Replace"),
    ("A filter-maintenance alert appears after three months of use; the unit otherwise works normally.", "Remote fix"),
    ("The drum makes a loud grinding noise during operation, but there are no safety symptoms.", "Technician visit"),
    ("The same drainage fault has returned after two prior technician repairs.", "Replace"),
    ("A burning smell appears whenever the heating cycle begins.", "Safety escalation"),
    ("The phone app shows the appliance as offline, but the appliance itself operates normally.", "Remote fix"),
    ("Water is leaking from an internal hose. There are no sparks, shocks, or burning smells.", "Technician visit"),
    ("The unit becomes unusually hot and repeatedly shuts itself down.", "Safety escalation"),
    ("The control panel remains unresponsive after a reset. The unit is 18 months old and shows no safety symptoms.", "Technician visit"),
    ("The display language changed after a software update; all appliance functions still work.", "Remote fix"),
    ("A compressor fault has returned after two previous repairs for the same problem.", "Replace"),
    ("The customer receives a setup error while registering the appliance account; the machine itself works.", "Remote fix"),
]

ACTIONS = ["—", "Remote fix", "Technician visit", "Replace", "Safety escalation"]

st.title("NorthStar Live Experiments")
st.caption(f"Anonymous participant code: {participant_id}")

tab1, tab2, tab3 = st.tabs(["Experiment 1", "Experiment 2", "Instructor Dashboard"])

with tab1:
    st.header("Experiment 1: Productivity and Incentives")
    st.write("**Question:** Can NorthStar reduce service cost per resolved customer problem without reducing quality?")

    st.info(
        "Triage rule: Remote fix = setup/software/maintenance issue; "
        "Technician visit = repair needed but no safety issue; "
        "Replace = dead-on-arrival or same fault after two prior repairs; "
        "Safety escalation = smoke, sparks, burning smell, shock, or overheating."
    )

    if exp1_arm == "Control":
        st.subheader("Your incentive")
        st.write("**Complete the task carefully.** Your objective is to make sound service decisions.")
    elif exp1_arm == "Quantity":
        st.subheader("Your incentive")
        st.write("**You earn 1 point for every case you complete.** Try to process as many cases as possible.")
    else:
        st.subheader("Your incentive")
        st.write("**You earn 2 points for each correct case and lose 2 points for each incorrect case.** Balance speed and accuracy.")

    if st.session_state.exp1_start is None and not st.session_state.exp1_submitted:
        if st.button("Start Experiment 1", type="primary"):
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

            conn = get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO exp1 VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    participant_id,
                    datetime.now(timezone.utc).isoformat(),
                    exp1_arm,
                    attempted,
                    correct,
                    incorrect,
                    accuracy,
                    quality_value,
                    elapsed,
                ),
            )
            conn.commit()
            conn.close()
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
        with st.expander("Why this matters"):
            st.write(
                "A quantity incentive may increase throughput, but NorthStar ultimately cares about "
                "correctly resolved customer problems, rework, customer experience, and cost. "
                "The class comparison will show whether the incentive changed the metric or the underlying value."
            )

with tab2:
    st.header("Experiment 2: Customer Margin Test")
    st.write("**Question:** Can NorthStar increase warranty contribution margin without cutting the appliance price?")
    st.write(
        "Imagine you are buying a **NorthStar SmartWash appliance for CAD 899**. "
        "The manufacturer warranty covers the first year. An optional **3-year NorthStar Protection Plan costs CAD 79** "
        "and covers parts and labour after the first year. Accidental damage is not covered. "
        "The plan can be cancelled within 30 days for a full refund."
    )

    with st.form("exp2_form"):
        if exp2_arm == "Opt-In":
            st.subheader("Protection Plan — CAD 79")
            chose_plan = st.checkbox("Add the NorthStar Protection Plan", value=False)
        else:
            st.subheader("Protection Plan — CAD 79")
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

    if submitted2 and not st.session_state.exp2_submitted:
        conn = get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO exp2 VALUES (?,?,?,?,?)",
            (
                participant_id,
                datetime.now(timezone.utc).isoformat(),
                exp2_arm,
                int(chose_plan),
                int(trust),
            ),
        )
        conn.commit()
        conn.close()
        st.session_state.exp2_submitted = True
        st.session_state.exp2_choice = int(chose_plan)
        st.session_state.exp2_trust = int(trust)
        st.rerun()

    if st.session_state.exp2_submitted:
        st.success("Experiment 2 submitted. Please do not discuss your screen with classmates until the instructor reveals the results.")
        st.metric("Your choice", "Protection plan" if st.session_state.exp2_choice else "No protection plan")

with tab3:
    st.header("Instructor Dashboard")
    code = st.text_input("Instructor access code", type="password")
    if code == INSTRUCTOR_CODE:
        conn = get_conn()
        e1 = pd.read_sql_query("SELECT * FROM exp1", conn)
        e2 = pd.read_sql_query("SELECT * FROM exp2", conn)
        conn.close()

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
            st.dataframe(summary1, use_container_width=True, hide_index=True)
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
            st.dataframe(summary2, use_container_width=True, hide_index=True)

            optin = e2.loc[e2["arm"] == "Opt-In", "chose_plan"].mean()
            optout = e2.loc[e2["arm"] == "Opt-Out", "chose_plan"].mean()
            if pd.notna(optin) and pd.notna(optout):
                default_effect = optout - optin
                st.metric("Default effect (percentage points)", f"{default_effect*100:.1f} pp")

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

        st.divider()
        st.caption(
            "Default instructor code is 'northstar'. For classroom use, set an environment variable "
            "INSTRUCTOR_CODE to your preferred code before launching the app."
        )
    elif code:
        st.error("Incorrect instructor code.")
