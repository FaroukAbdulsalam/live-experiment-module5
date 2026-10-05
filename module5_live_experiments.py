
import streamlit as st
import pandas as pd
import sqlite3
import uuid
import hashlib
import os
import random
from datetime import datetime, timezone

st.set_page_config(
    page_title="NorthStar Live Experiments",
    page_icon="🧪",
    layout="centered",
)

DB_PATH = "northstar_experiments.db"
INSTRUCTOR_CODE = os.environ.get("INSTRUCTOR_CODE", "northstar")


# ----------------------------
# Database
# ----------------------------
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

    conn.execute("""
        CREATE TABLE IF NOT EXISTS exp3 (
            participant_id TEXT PRIMARY KEY,
            submitted_at TEXT,
            preferred_color TEXT,
            purchase_likelihood INTEGER,
            would_pay_premium INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS exp4 (
            participant_id TEXT PRIMARY KEY,
            submitted_at TEXT,
            arm TEXT,
            chose_eco INTEGER,
            purchase_likelihood INTEGER
        )
    """)

    conn.commit()
    return conn


# ----------------------------
# Session state
# ----------------------------
if "participant_id" not in st.session_state:
    st.session_state.participant_id = str(uuid.uuid4())[:8]

defaults = {
    "exp1_start": None,
    "exp1_submitted": False,
    "exp1_arm": None,
    "exp2_started": False,
    "exp2_submitted": False,
    "exp2_arm": None,
    "exp3_submitted": False,
    "exp4_started": False,
    "exp4_submitted": False,
    "exp4_arm": None,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

participant_id = st.session_state.participant_id


# ----------------------------
# Shared helpers
# ----------------------------
def render_appliance(fill_hex, label):
    # st.html renders the appliance without leaking raw HTML into the page.
    html = f"""
    <div style="display:flex;justify-content:center;margin:8px 0 14px 0;">
      <div style="
          width:250px;
          height:300px;
          border-radius:24px;
          background:{fill_hex};
          border:2px solid #8b8b8b;
          box-shadow:0 3px 12px rgba(0,0,0,.10);
          position:relative;
          overflow:hidden;">
        <div style="
            position:absolute;
            top:18px;left:18px;right:18px;
            height:38px;
            border-radius:9px;
            background:rgba(255,255,255,.22);
            border:1px solid rgba(0,0,0,.12);">
          <div style="
              width:10px;height:10px;border-radius:50%;
              background:rgba(0,0,0,.45);
              position:absolute;right:16px;top:13px;"></div>
        </div>

        <div style="
            position:absolute;
            width:150px;height:150px;
            border-radius:50%;
            left:50%;top:53%;
            transform:translate(-50%,-50%);
            border:15px solid rgba(255,255,255,.42);
            background:rgba(0,0,0,.16);
            box-shadow:inset 0 0 0 4px rgba(0,0,0,.12);">
        </div>

        <div style="
            position:absolute;
            left:0;right:0;bottom:12px;
            text-align:center;
            font-family:Arial,sans-serif;
            font-size:16px;
            font-weight:700;
            color:{'#f7f7f7' if fill_hex in ['#222222','#1F3557'] else '#333333'};">
          {label}
        </div>
      </div>
    </div>
    """
    st.html(html)


# ----------------------------
# Experiment 1 content
# ----------------------------
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


# ----------------------------
# App shell
# ----------------------------
st.title("NorthStar Live Experiments")
st.caption(f"Anonymous participant code: {participant_id}")

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    [
        "Experiment 1",
        "Experiment 2",
        "Color Test",
        "Language Test",
        "Instructor Results & Data",
    ]
)


# ============================================================
# Experiment 1: Incentives
# ============================================================
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
    treatment_choice = st.radio(
        "Assigned treatment",
        ["Control", "Quantity", "Balanced"],
        index=None,
        horizontal=True,
        disabled=st.session_state.exp1_start is not None or st.session_state.exp1_submitted,
        key="exp1_treatment_radio",
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
            for i, (case, _) in enumerate(CASES, start=1):
                st.markdown(f"**Case {i}.** {case}")
                choice = st.selectbox(
                    f"Decision for case {i}",
                    ACTIONS,
                    index=0,
                    key=f"case_{i}",
                    label_visibility="collapsed",
                )
                choices.append(choice)

            submitted = st.form_submit_button("Submit Experiment 1", type="primary")

        if submitted:
            attempted = sum(c != "—" for c in choices)
            correct = sum(
                (c != "—") and (c == CASES[i][1])
                for i, c in enumerate(choices)
            )
            incorrect = attempted - correct
            accuracy = (correct / attempted) if attempted else 0.0
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


# ============================================================
# Experiment 2: Warranty default
# ============================================================
with tab2:
    st.header("Experiment 2: Customer Margin Test")
    st.write("**Question:** Does the default change warranty take-up and contribution margin?")
    st.write(
        "Imagine you are buying a **NorthStar SmartWash appliance for CAD 899**. "
        "The manufacturer warranty covers the first year. An optional **3-year NorthStar Protection Plan costs CAD 79** "
        "and covers parts and labour after the first year. Accidental damage is not covered. "
        "The plan can be cancelled within 30 days for a full refund."
    )

    st.subheader("Select the version your instructor assigned to you")
    exp2_choice = st.radio(
        "Assigned version",
        ["Control — Opt-In", "Treatment — Opt-Out"],
        index=None,
        horizontal=True,
        disabled=st.session_state.exp2_started or st.session_state.exp2_submitted,
        key="exp2_treatment_radio",
    )

    if exp2_choice and not st.session_state.exp2_started and not st.session_state.exp2_submitted:
        st.session_state.exp2_arm = "Opt-In" if "Opt-In" in exp2_choice else "Opt-Out"

    if not st.session_state.exp2_started and not st.session_state.exp2_submitted:
        if st.session_state.exp2_arm is None:
            st.warning("Select the version assigned by your instructor before starting.")
        elif st.button("Start Experiment 2", type="primary"):
            st.session_state.exp2_started = True
            st.rerun()

    if st.session_state.exp2_started and not st.session_state.exp2_submitted:
        exp2_arm = st.session_state.exp2_arm

        with st.form("exp2_form"):
            if exp2_arm == "Opt-In":
                st.subheader("NorthStar Protection Plan — CAD 79")
                chose_plan = st.checkbox("Add the NorthStar Protection Plan", value=False)
            else:
                st.subheader("NorthStar Protection Plan — CAD 79")
                chose_plan = st.checkbox(
                    "NorthStar Protection Plan included — uncheck to remove",
                    value=True,
                )

            trust = st.slider(
                "How fair and transparent does this purchase experience feel?",
                min_value=1,
                max_value=5,
                value=3,
                help="1 = not at all fair/transparent; 5 = very fair/transparent",
            )

            submitted2 = st.form_submit_button("Submit Experiment 2", type="primary")

        if submitted2:
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
        st.success("Experiment 2 submitted.")
        st.metric(
            "Your choice",
            "Protection plan" if st.session_state.exp2_choice else "No protection plan",
        )


# ============================================================
# Experiment 3: Color preference
# ============================================================
with tab3:
    st.header("Product Color Preference Test")
    st.write("**Question:** Which appliance finish does the class prefer when price and features are identical?")
    st.caption(
        "Choose a color below. The appliance preview updates immediately. "
        "The order of the options is randomized across participants to reduce position bias."
    )

    colors = {
        "White": "#F2F2F2",
        "Black": "#222222",
        "Silver": "#B7BCC2",
        "Navy Blue": "#1F3557",
    }

    rng = random.Random(
        int(hashlib.sha256((participant_id + "exp3").encode()).hexdigest(), 16)
    )
    ordered_color_names = list(colors.keys())
    rng.shuffle(ordered_color_names)

    preferred = st.radio(
        "Select a finish",
        ordered_color_names,
        index=0,
        horizontal=True,
        disabled=st.session_state.exp3_submitted,
        key="exp3_color_radio",
    )

    render_appliance(colors[preferred], preferred)

    if not st.session_state.exp3_submitted:
        with st.form("exp3_form"):
            likelihood = st.slider(
                "How likely would you be to buy this color?",
                min_value=1,
                max_value=5,
                value=3,
                help="1 = very unlikely; 5 = very likely",
            )
            premium = st.radio(
                "Would you pay CAD 50 more to get this color rather than your second choice?",
                ["No", "Yes"],
                horizontal=True,
            )
            submit3 = st.form_submit_button("Submit Color Preference", type="primary")

        if submit3:
            conn = get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO exp3 VALUES (?,?,?,?,?)",
                (
                    participant_id,
                    datetime.now(timezone.utc).isoformat(),
                    preferred,
                    int(likelihood),
                    1 if premium == "Yes" else 0,
                ),
            )
            conn.commit()
            conn.close()

            st.session_state.exp3_submitted = True
            st.session_state.exp3_preferred = preferred
            st.rerun()

    if st.session_state.exp3_submitted:
        st.success(f"Color preference submitted: {st.session_state.exp3_preferred}")


# ============================================================
# Experiment 4: Language framing / loss aversion
# ============================================================
with tab4:
    st.header("Experiment 4: Marketing Language and Loss Aversion")
    st.write("**Question:** Can economically equivalent language change which product customers choose?")

    st.write(
        "NorthStar offers two otherwise comparable washing machines:\n\n"
        "- **Standard:** CAD 899\n"
        "- **EcoSmart:** CAD 999\n\n"
        "Independent estimates suggest EcoSmart uses about **CAD 180 less energy per year**."
    )

    st.subheader("Select the version your instructor assigned to you")
    exp4_choice = st.radio(
        "Assigned version",
        ["Control — Version A", "Treatment — Version B"],
        index=None,
        horizontal=True,
        disabled=st.session_state.exp4_started or st.session_state.exp4_submitted,
        key="exp4_treatment_radio",
    )

    if exp4_choice and not st.session_state.exp4_started and not st.session_state.exp4_submitted:
        st.session_state.exp4_arm = "Gain Frame" if "Version A" in exp4_choice else "Loss Frame"

    if not st.session_state.exp4_started and not st.session_state.exp4_submitted:
        if st.session_state.exp4_arm is None:
            st.warning("Select the version assigned by your instructor before starting.")
        elif st.button("Start Experiment 4", type="primary"):
            st.session_state.exp4_started = True
            st.rerun()

    if st.session_state.exp4_started and not st.session_state.exp4_submitted:
        exp4_arm = st.session_state.exp4_arm

        if exp4_arm == "Gain Frame":
            st.success(
                "**Marketing message:** Choose EcoSmart and **save about CAD 180 per year** in energy costs."
            )
        else:
            st.warning(
                "**Marketing message:** Choose the standard model and you could **lose about CAD 180 per year** in extra energy costs."
            )

        with st.form("exp4_form"):
            product_choice = st.radio(
                "Which model would you buy?",
                ["Standard — CAD 899", "EcoSmart — CAD 999"],
                index=None,
            )

            purchase_likelihood = st.slider(
                "How likely are you to buy the EcoSmart model?",
                min_value=1,
                max_value=5,
                value=3,
                help="1 = very unlikely; 5 = very likely",
            )

            submit4 = st.form_submit_button("Submit Experiment 4", type="primary")

        if submit4:
            if product_choice is None:
                st.error("Please choose one model before submitting.")
            else:
                chose_eco = int(product_choice.startswith("EcoSmart"))

                conn = get_conn()
                conn.execute(
                    "INSERT OR REPLACE INTO exp4 VALUES (?,?,?,?,?)",
                    (
                        participant_id,
                        datetime.now(timezone.utc).isoformat(),
                        exp4_arm,
                        chose_eco,
                        int(purchase_likelihood),
                    ),
                )
                conn.commit()
                conn.close()

                st.session_state.exp4_submitted = True
                st.session_state.exp4_chose_eco = chose_eco
                st.rerun()

    if st.session_state.exp4_submitted:
        st.success("Experiment 4 submitted.")


# ============================================================
# Instructor dashboard
# ============================================================
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
            "The app also stores all submissions in `northstar_experiments.db` "
            "in the same folder where the Streamlit app is running."
        )

        conn = get_conn()
        e1 = pd.read_sql_query("SELECT * FROM exp1", conn)
        e2 = pd.read_sql_query("SELECT * FROM exp2", conn)
        e3 = pd.read_sql_query("SELECT * FROM exp3", conn)
        e4 = pd.read_sql_query("SELECT * FROM exp4", conn)
        conn.close()

        st.subheader("Suggested classroom assignment")
        st.write(
            "- **Experiment 1:** split the class roughly into thirds: Control / Quantity / Balanced.\n"
            "- **Experiment 2:** split the class roughly in half: Control (Opt-In) / Treatment (Opt-Out).\n"
            "- **Experiment 4:** split the class roughly in half: Version A / Version B."
        )

        # Experiment 1 results
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
                "text/csv",
            )

        # Experiment 2 results
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
                st.metric(
                    "Opt-Out default effect",
                    f"{default_effect * 100:.1f} percentage points",
                )

                st.markdown("**Translate adoption into margin**")
                c1, c2 = st.columns(2)
                with c1:
                    net_contribution = st.number_input(
                        "Net contribution per protection plan (CAD)",
                        min_value=0.0,
                        value=40.0,
                        step=5.0,
                    )
                with c2:
                    customer_volume = st.number_input(
                        "Customer volume for scaling",
                        min_value=1,
                        value=10000,
                        step=1000,
                    )

                incremental_margin = (
                    default_effect * customer_volume * net_contribution
                )
                st.metric(
                    "Estimated incremental contribution margin",
                    f"CAD {incremental_margin:,.0f}",
                )

            st.download_button(
                "Download Experiment 2 CSV",
                e2.to_csv(index=False).encode("utf-8"),
                "experiment2_results.csv",
                "text/csv",
            )

        # Experiment 3 results
        st.subheader("Color preference results")
        if e3.empty:
            st.info("No color-test submissions yet.")
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
            st.dataframe(summary3, use_container_width=True, hide_index=True)

            st.download_button(
                "Download Color Test CSV",
                e3.to_csv(index=False).encode("utf-8"),
                "color_test_results.csv",
                "text/csv",
            )

        # Experiment 4 results
        st.subheader("Experiment 4 results: Language framing")
        if e4.empty:
            st.info("No Experiment 4 submissions yet.")
        else:
            summary4 = (
                e4.groupby("arm", as_index=False)
                .agg(
                    students=("participant_id", "count"),
                    eco_choice_rate=("chose_eco", "mean"),
                    avg_eco_likelihood=("purchase_likelihood", "mean"),
                )
            )
            summary4["eco_choice_rate"] = summary4["eco_choice_rate"].map(lambda x: f"{x:.1%}")
            st.dataframe(summary4, use_container_width=True, hide_index=True)

            gain = e4.loc[e4["arm"] == "Gain Frame", "chose_eco"].mean()
            loss = e4.loc[e4["arm"] == "Loss Frame", "chose_eco"].mean()

            if pd.notna(gain) and pd.notna(loss):
                st.metric(
                    "Loss-frame effect on EcoSmart choice",
                    f"{(loss - gain) * 100:.1f} percentage points",
                )

            st.caption(
                "Interpretation: Version A presents the energy-cost difference as a gain ('save'). "
                "Version B presents the same difference as a loss ('lose'). "
                "Any gap in choice is evidence of a framing effect in this class sample."
            )

            st.download_button(
                "Download Experiment 4 CSV",
                e4.to_csv(index=False).encode("utf-8"),
                "experiment4_results.csv",
                "text/csv",
            )

        st.divider()
        st.caption(
            "Default instructor code is 'northstar'. "
            "For classroom use, set the environment variable INSTRUCTOR_CODE to your preferred code."
        )

    elif code:
        st.error("Incorrect instructor code.")
