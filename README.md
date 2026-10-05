
# NorthStar Module 5 Live Experiments

This Streamlit app runs the two Module 5 classroom experiments:

1. **Productivity and Incentives**
   - Random assignment to Control, Quantity, or Balanced incentive arms.
   - Students triage NorthStar service cases.
   - Outcomes: cases attempted, accuracy, errors, elapsed time, and quality-adjusted value.

2. **Customer Margin Test**
   - Random assignment to Opt-In or Opt-Out warranty default.
   - Primary outcome: protection-plan adoption.
   - Secondary outcome: perceived fairness/transparency.

The **Instructor Dashboard** aggregates submissions live and allows CSV download.

## Run locally

```bash
pip install -r requirements.txt
streamlit run module5_live_experiments.py
```

Then open the local URL Streamlit provides.

## Instructor code

The default dashboard code is:

`northstar`

For class use, set your own code before launching:

macOS/Linux:
```bash
export INSTRUCTOR_CODE="your-code"
streamlit run module5_live_experiments.py
```

Windows PowerShell:
```powershell
$env:INSTRUCTOR_CODE="your-code"
streamlit run module5_live_experiments.py
```

## Suggested classroom timing

### Experiment 1
- 1 minute: explain the triage rules
- 2 minutes: students work
- 1 minute: submit
- 5–7 minutes: reveal and debrief

Do **not** reveal the scoring logic across arms before the activity beyond what each student sees on their own screen.

### Experiment 2
- 1 minute: ask students to make the purchase decision silently
- 1 minute: submit
- 3–5 minutes: reveal opt-in vs opt-out adoption rates
- Debrief: default effects, inertia, implied recommendation, trust, ethics

## Data

Results are stored in a local SQLite database named:

`northstar_experiments.db`

The database is created automatically in the same folder as the app.

For a one-class session, local SQLite is adequate. If you deploy to a cloud host that can restart or use ephemeral storage, download the CSVs after class or connect the app to a persistent database.


## Turning Experiment 2 into a true margin test

The dashboard lets the instructor enter:
- net contribution per protection plan; and
- the customer volume to which the intervention might be scaled.

It then translates the observed adoption-rate difference into an estimated incremental contribution margin. The app explicitly notes that this first-pass estimate does not subtract possible complaint, cancellation, regulatory, or trust costs.
