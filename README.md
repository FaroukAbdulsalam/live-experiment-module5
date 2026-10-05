
# NorthStar Module 5 Live Experiments

This Streamlit app runs the two Module 5 classroom experiments:

1. **Productivity and Incentives**
   - Random assignment to Control, Quantity, or Balanced incentive arms.
   - Students triage 8 short, deliberately simple NorthStar service cases.
   - Outcomes: cases attempted, accuracy, errors, elapsed time, and quality-adjusted value.

2. **Customer Margin Test**
   - Instructor assigns students to Group A (Opt-In, control) or Group B (Opt-Out, treatment) warranty default.
   - Primary outcome: protection-plan adoption.
   - Secondary outcome: perceived fairness/transparency.

3. **Product Color Preference** (see below).

4. **Gains vs. Losses (framing)**
   - Instructor assigns students to Group X (Gain frame) or Group Y (Loss frame).
   - Outcomes: EcoSeries upgrade rate, message persuasiveness, and share choosing the risky recovery plan.

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
- 1 minute: explain the four triage rules
- 90 seconds–2 minutes: students work through 8 cases
- 1 minute: submit
- 5–7 minutes: reveal and debrief

Do **not** reveal the scoring logic across arms before the activity beyond what each student sees on their own screen.

### Experiment 2
- Tell half the class to select **Group A** and half **Group B**. Students see neutral group names, not "Opt-In/Opt-Out", so the label does not prime them. The group locks once the student presses Start.
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


## Manual treatment assignment for Experiment 1

Experiment 1 now displays all three treatment options:
- Control
- Quantity
- Balanced

The instructor tells students which treatment to select before they start. A simple approach is to split the class into roughly equal thirds.

The treatment selection locks once the student starts the experiment.

## Where to see the data

Open the **Instructor Results & Data** tab and enter the instructor code.

Default code: `northstar`

The dashboard shows live summaries and provides buttons to download the raw data as CSV.

The underlying submissions are also stored in:
`northstar_experiments.db`

This database file is created in the same folder where the Streamlit app is running.


## Experiment 3: Product Color Preference

Students see the same NorthStar appliance mock-up in four finishes:
- White
- Black
- Silver
- Navy Blue

The order is randomized across participants to reduce position bias.

Students report:
- preferred color;
- purchase likelihood (1–5); and
- whether they would pay CAD 50 more for their preferred color.

The Instructor Results & Data tab reports class choice shares, average purchase likelihood, and the share willing to pay the premium by selected color.

Students pick a finish by pressing **Choose** under the appliance; the selected card is highlighted and the others dim, so the choice is visible before submitting.

This is mainly a **preference test**, rather than a clean causal experiment. It is useful for design and marketing decisions. To turn it into a causal experiment, the instructor could later randomize a feature such as the color label, price premium, or marketing message.


## Experiment 4: Gains vs. Losses (framing)

Same facts, different wording. Group X sees gain frames; Group Y sees loss frames. Group labels are neutral on the student screen and the group locks once the student presses Start.

**Decision 1 (marketing message).** The EcoSeries costs CAD 120 more and saves about CAD 60 a year. Gain frame: "Save about CAD 60 every year." Loss frame: "Stop losing about CAD 60 every year." Layout and colour are identical across arms, so only the wording differs. Outcomes: upgrade rate and rated persuasiveness.

**Decision 2 (risky choice).** A business version of Tversky & Kahneman (1981): 600 customers at risk; a sure plan vs. a 1-in-3 gamble with the same expected outcome, described as customers *retained* (gain) or *lost* (loss). Prediction: risk-averse choices under the gain frame, risk-seeking choices under the loss frame.

Suggested timing: 1 minute to choose, 3–5 minutes to reveal and debrief. The dashboard reports Loss-minus-Gain effects with 95% confidence intervals, plus debrief notes.

Use a different splitting rule than in Experiment 2 (e.g., seat rows vs. birth month) so the same students are not always treated together.
