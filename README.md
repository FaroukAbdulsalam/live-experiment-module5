
# NorthStar Module 5 Live Experiments — Revised

This Streamlit app contains four classroom activities.

## Experiment 1 — Productivity and Incentives

Students select the treatment assigned by the instructor:

- Control
- Quantity
- Balanced

They complete eight short service-triage decisions. The dashboard compares quantity, accuracy, and quality-adjusted value.

## Experiment 2 — Customer Margin Test

Students now explicitly select the version assigned by the instructor:

- Control — Opt-In
- Treatment — Opt-Out

The assigned version is locked when they press **Start Experiment 2**. The dashboard compares warranty adoption and perceived fairness/transparency.

## Color Test — Product Color Preference

Students select among:

- White
- Black
- Silver
- Navy Blue

The appliance preview now changes immediately when the selected color changes. Raw HTML should no longer appear because the preview is rendered with `st.html`.

Students also report purchase likelihood and whether they would pay CAD 50 more for the preferred finish.

## Experiment 4 — Marketing Language and Loss Aversion

Students select one of two instructor-assigned versions:

- Control — Version A: gain frame ("save CAD 180")
- Treatment — Version B: loss frame ("lose CAD 180")

Both versions describe the same estimated annual energy-cost difference. Students then choose between a Standard and EcoSmart appliance.

The dashboard compares the EcoSmart choice rate across gain and loss framing.

This activity is best described as a **framing / loss-aversion experiment** rather than a generic risk-aversion experiment.

## Instructor Dashboard

Open the **Instructor Results & Data** tab.

Default code:

`northstar`

The dashboard shows live summaries and lets you download each experiment as CSV.

The underlying data are also stored locally in:

`northstar_experiments.db`

## Run locally

```bash
pip install -r requirements.txt
streamlit run module5_live_experiments.py
```

## Suggested class splits for 68 students

- Experiment 1: about 23 Control / 23 Quantity / 22 Balanced
- Experiment 2: about 34 Control / 34 Treatment
- Experiment 4: about 34 Version A / 34 Version B
