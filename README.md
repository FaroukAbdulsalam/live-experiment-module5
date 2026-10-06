# NorthStar Module 5 Live Activities (v2)

A Streamlit app for four live classroom experiments in managerial economics, with a prediction step
before each reveal and a projector view for the debrief.

| Student tab | What students see | What it tests | Groups (assigned by the app) |
|---|---|---|---|
| Activity 1 | Two quick decisions | Gain vs. loss framing | Gain frame / Loss frame |
| Activity 2 | Service desk | Incentives and productivity | Control / Quantity / Balanced |
| Activity 3 | Checkout | Defaults and warranty margin | Opt-In / Opt-Out / Active choice |
| Activity 4 | Choose a finish | Social proof | No badge / Bestseller badge on Navy Blue |

Student-facing titles are deliberately neutral so they don't reveal the hypothesis. Framing runs first,
before students have seen other manipulations.

## What changed from v1

- **Neutral titles** on all student screens; the research question appears only on the instructor side.
- **Student code at entry.** The code is hashed (with a private salt) into an anonymous ID. Reloading the page
  and re-entering the same code resumes where the student left off; each activity accepts one submission only.
- **App-assigned balanced groups.** Each student is assigned to the group with the fewest members so far
  (random tie-break). Students never choose or see a group name.
- **Persistent storage** via any Postgres database (`DATABASE_URL`). Without it the app uses a local SQLite file,
  which Streamlit Community Cloud wipes on reboot; the instructor tab warns you when that's the case.
- **Service desk reworked:** 20 cases (in a random order per student), a 90-second on-screen countdown, five rules
  including a precedence rule, and trap cases that punish rushing. Quantity and Balanced students compete on a
  leaderboard (anonymous animal names). Control gets a neutral instruction. Submissions more than 20 s past the
  limit are flagged and excluded by default.
- **Checkout:** new **Active choice** arm (forced yes/no), plus a 30-day cancellation question so margin is
  computed net of cancellations.
- **Choose a finish** is now a causal test: half the class sees a Bestseller badge on Navy Blue.
- **Framing:** decision 2 uses 1,200 distributor accounts instead of the classic 600 people, so students who know
  the Asian disease problem are less likely to recognise it.
- **Predictions:** after each activity you explain the design and open predictions; students predict each group's
  outcome; the projector view shows the class prediction next to the actual result.
- **Sessions and pooling:** every row is tagged with a session code. Results can be shown for this session or
  pooled across all sessions.
- **Consent notice** at entry.
- Tables whose layout doesn't match this version are archived (renamed, data kept), never deleted.

## Running a class

1. Before class: in the Instructor tab (*Class control*), set the session code, e.g. `2027S-sec1`.
2. Students open the app, enter their student number, tick the notice, and do Activity 1.
3. When everyone has submitted (progress is shown in *Class control*), explain the design, then switch on
   **Predictions open** for that activity. Students predict in the Predictions tab
   (they press "Check for open predictions").
4. In *Projector*, select the activity. The class prediction shows first; switch on **Reveal results** to add the
   actual outcome. Use *Detailed results* for effects with confidence intervals, the margin calculator and debrief notes.
5. Repeat for Activities 2 to 4. Download CSVs from *Detailed results*.

Suggested timing per activity: 1 to 2 minutes to complete, 1 minute to predict, 3 to 5 minutes to debrief.
For the service desk, tell students to stop when the countdown ends.

Seat note: groups are assigned at random, so neighbours may be in different conditions. Ask students not to
look at each other's screens until the reveal.

## Setup

```bash
pip install -r requirements.txt
streamlit run module5_live_experiments.py
```

Settings are read from environment variables or `.streamlit/secrets.toml`
(see `.streamlit/secrets.toml.example`):

| Setting | Purpose | Default |
|---|---|---|
| `INSTRUCTOR_CODE` | Instructor tab password | `northstar` (change it) |
| `ID_SALT` | Private salt for hashing student codes. Keep it secret and never change it mid-term | built-in default (change it) |
| `DATABASE_URL` | Postgres connection string for persistent storage | local SQLite |
| `SESSION_CODE` | Initial session code (can be changed in the app) | `class-1` |
| `EXP1_SECONDS` | Service-desk time limit | `90` |

### Persistent storage on Streamlit Community Cloud

1. Create a free Postgres database (e.g., Supabase or Neon) and copy its connection string.
   `postgres://` and `postgresql://` URLs both work.
2. In Streamlit Cloud: **Manage app → Settings → Secrets**, paste the contents of `secrets.toml.example`
   with your values.
3. Reboot the app. The instructor tab no longer shows the SQLite warning.

Do not commit `northstar_experiments.db` or `secrets.toml` (both are in `.gitignore`).

## Privacy

Student codes are never stored, only a salted hash. Student numbers are short, so the hash is only as private
as `ID_SALT`. If you plan to publish anything from pooled data, get research ethics approval before collecting it.

## Data

Tables: `framing`, `incentives`, `defaults`, `finish`, `predictions`, `assignments`, `settings`. Every activity
row includes `session`, `participant_id` and `arm`. The v1 tables (`exp1` to `exp4`) are not used and are left
untouched if present.
