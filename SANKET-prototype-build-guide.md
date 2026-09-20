# SANKET — Prototype Build Guide

**SIH 26028 · Dynamic ETA Forecasting for Coaching Trains**
A plan your team implements. Nothing here is finished code — it is the design, the algorithms, and the reasoning behind them, so that whoever writes each piece understands it well enough to defend it.

---

## 0. Working in a way that survives scrutiny

The rule against AI-generated projects is really a rule about ownership. A judge will point at a function and ask what it does and why you chose it. Protect yourselves:

- **Write the code yourselves.** Use references, docs and Stack Overflow the way any engineer does. If you paste something you don't understand, delete it.
- **Commit as you go, from your own accounts.** A repo with three commits on the last night looks exactly like what it looks like. Forty small commits across three weeks from six people tells a true story.
- **Every person must be able to explain their own module end to end**, and roughly explain everyone else's.
- **Keep a decisions log.** A `NOTES.md` where you record "tried X, it was slow, switched to Y." That file is worth a lot in Q&A.
- **Write your own README.** In your own voice, including what does not work yet.

The strongest defence against the accusation is a working demo plus six people who can each answer questions about it.

---

## 1. Scope — decide what you are NOT building

The single biggest risk is attempting the whole system. Build the spine first; everything else is optional.

**Must exist (the spine):**
1. Real railway network graph, built from public schedule data
2. Running-data generator with the cascade physics in it
3. Feature builder that includes network state
4. Section model (LightGBM, quantile)
5. Chaining loop producing ETAs at every station
6. Baseline implementation for comparison
7. Evaluation that proves the network features help
8. A dashboard that shows one train, its band, and its causes

**Only after all eight work:**
- SHAP attribution panel
- Cascade animation
- Connection-risk feature
- What-if console

A finished spine beats a half-built cathedral. Cut ruthlessly.

---

## 2. The data problem, handled honestly

You cannot get live RTIS or COA. Here is the split that is both achievable and defensible.

### Real data you genuinely can get

**Train schedules.** Public datasets of Indian Railways schedules exist on data.gov.in and Kaggle — roughly 11,000 trains with every stop, arrival and departure time, and cumulative distance. This is real and it gives you almost everything structural:

- Every **station** = a node
- Every **consecutive pair of stops** for a train = a **section** (an edge)
- `departure(A) → arrival(B)` = the **booked Sectional Running Time**
- `distance(B) − distance(A)` = section length
- Crucially: **many trains use the same section**, which is exactly the shared network you are claiming to model

Build your graph from this. It is real, verifiable, and a judge can check it.

**Live running data.** Start scraping whatever public running information you can reach, today, and let it accumulate. Even two or three weeks of real data across a handful of trains lets you say "we validated against real observations on this corridor," which is far stronger than pure simulation.

### Simulated data, declared as such

You will not have enough real delay history to train on. So write a simulator that generates running data from your real graph, with the actual operating physics:

- Each train traverses its sections, taking booked SRT plus noise
- Only one train may occupy a block section at a time
- A train arriving at an occupied section **waits** (this creates the cascade)
- Higher-priority trains get precedence at conflicts
- Caution orders are injected on random sections for random windows
- Weather and time-of-day effects shift the noise distribution

**Be transparent in your demo and README:** the network is real, the running data is simulated, and here is why. Teams that hide this get caught. Teams that state it plainly look rigorous.

> **The honest caveat you must understand:** if you simulate a cascade and then show your model detects it, you have proved your *method* works — not that the effect is large in real Indian Railways data. Say exactly that. Then point to whatever real scraped data you have as partial corroboration. That is a genuinely strong scientific position for a prototype.

---

## 3. Repository structure

```
sanket/
├── README.md
├── NOTES.md                  # decisions log — keep this honest
├── docker-compose.yml
├── data/
│   ├── raw/                  # downloaded schedule files
│   └── processed/            # graph, training tables
├── src/
│   ├── graph/
│   │   ├── build_graph.py    # schedules → stations, sections, SRT
│   │   └── graph_api.py      # lookups: route of a train, neighbours
│   ├── sim/
│   │   └── simulator.py      # generates running data with cascade physics
│   ├── features/
│   │   └── build_features.py # one row per (train, section, day)
│   ├── model/
│   │   ├── train.py          # LightGBM quantile models
│   │   └── predict.py        # single-section prediction
│   ├── forecast/
│   │   ├── chain.py          # the propagation loop
│   │   └── baseline.py       # today's schedule + delay − recovery
│   ├── eval/
│   │   └── evaluate.py       # MAE by horizon, calibration, ablation
│   └── api/
│       └── main.py           # FastAPI endpoints
├── frontend/                 # React dashboard
└── tests/
```

---

## 4. The six components

Pseudocode below is deliberately incomplete — it shows the shape of each algorithm. You write the implementation.

### 4.1 Network graph

**Input:** schedule CSV. **Output:** stations table, sections table, train routes table.

```
for each train in schedule:
    stops = rows for this train, ordered by stop_sequence
    for i in 0 .. len(stops)-2:
        A, B = stops[i], stops[i+1]
        section_id   = (A.station_code, B.station_code)
        booked_srt   = B.arrival_time - A.departure_time      # handle day rollover
        length_km    = B.distance_km  - A.distance_km
        record section(section_id, length_km)
        record route_step(train_no, seq=i, section_id, booked_srt)
```

Things that will bite you and that you should handle explicitly:
- Multi-day journeys: the `day` column matters, times wrap past midnight
- Source stations have no arrival; terminals have no departure
- Some SRTs will be nonsense (negative, or 400 minutes) — clean and log how many you dropped

**Sanity check to run and keep:** how many distinct sections? How many trains share the busiest section? That second number is your project's premise in one statistic — put it on a slide.

### 4.2 Simulator

This is the piece most worth getting right, because the model can only learn what the simulator puts in.

```
for each day being simulated:
    events = priority queue ordered by time
    section_free_at = {}          # section_id -> time it becomes free
    for each train: push(departure event at origin, scheduled time)

    while events not empty:
        train, section, ready_time = pop()

        # headway: cannot enter an occupied section
        entry = max(ready_time, section_free_at.get(section, 0))
        wait  = entry - ready_time

        # traversal time
        base  = booked_srt(train, section)
        noise = sample_noise(section, hour_of_day, weather)
        tsr   = tsr_penalty(section, entry)        # active caution orders
        actual = base + noise + tsr

        exit_time = entry + actual
        section_free_at[section] = exit_time + min_headway

        record observation(train, section, entry, exit_time,
                           actual - base)          # this is your label
        push(train, next_section, exit_time + dwell)
```

Precedence: when two trains contend, let the higher-priority one through first and make the other wait. That single rule is what produces realistic cascades.

**Calibrate, don't invent.** Pick noise parameters so that overall punctuality roughly matches published Indian Railways figures. Write down in `NOTES.md` what you targeted and why.

### 4.3 Feature builder

One row per (train, section, occasion). Columns grouped by what they capture:

| Group | Features |
|---|---|
| Section | `booked_srt`, `length_km`, `section_mean_loss_90d`, `section_loss_std`, `section_mean_loss_this_hour` |
| Train | `current_delay`, `loss_prev_section`, `loss_prev_3_sections`, `train_priority`, `sections_remaining` |
| **Network** | `trains_in_section`, `trains_in_next_2_sections`, `headway_km_to_train_ahead`, `preceding_train_delay`, `preceding_train_priority` |
| Time | `hour`, `day_of_week`, `month`, `is_holiday` |
| Conditions | `tsr_active`, `rainfall`, `visibility` |

**Label:** `minutes_lost = actual_traversal − booked_srt`

**The rule that will make or break your evaluation:** every feature must be computable from information available *before the train enters the section*. If you accidentally include something known only afterwards, your model will look brilliant and be worthless. Write a test that asserts this.

Build the network features with a **strict one-flag switch**, because you need to train with and without them:

```
def build_features(obs, include_network=True):
    ...
```

### 4.4 Section model

Three LightGBM regressors, identical except for the quantile:

```
for q in [0.1, 0.5, 0.9]:
    model[q] = LGBMRegressor(objective='quantile', alpha=q, ...)
    model[q].fit(X_train, y_train)
```

Split **by time**, not randomly — train on earlier days, test on later ones. A random split leaks future information and inflates your numbers.

Start with default hyperparameters. Tune only if you have spare time; it is worth far less than the ablation experiment below.

### 4.5 Chaining loop

```
def forecast(train, from_section_index, now, network_state):
    clock = now
    results = []
    for step in route(train)[from_section_index:]:
        feats = build_features_for(train, step.section, clock, network_state)
        lo, mid, hi = model.predict(feats)          # three quantiles
        clock = clock + step.booked_srt + mid
        results.append((step.section, clock, lo, hi))
        network_state.advance(train, step.section, clock)
    return results
```

For the confidence band, run the loop many times, sampling a loss from the quantile spread at each step:

```
runs = [forecast_with_sampling(...) for _ in range(300)]
band = percentile([r.final_arrival for r in runs], [10, 90])
```

Two notes. First, 300 runs is plenty for a demo; 500 was illustrative. Second, keep a fast non-sampling path that just uses the median — that is your "two-tier forecasting" claim, and you should be able to show both.

### 4.6 Baseline

Fifteen lines, and the most important fifteen in the project:

```
def baseline_eta(train, station, current_delay, now):
    return scheduled_arrival(train, station) + current_delay - recovery_time(...)
```

Every accuracy claim you make is relative to this.

---

## 5. The experiment that is your actual result

Not "our model is accurate." The claim is "**network features matter**." So run the ablation:

| Model | Features | Report |
|---|---|---|
| A | Baseline formula | MAE by horizon |
| B | ML, **no** network features | MAE by horizon |
| C | ML, **with** network features | MAE by horizon |

B versus C isolates your contribution. A versus C is your headline.

Report three things:

**MAE by horizon** — next station, 3 stations ahead, 6 hours ahead, destination. Separately. A single averaged number hides where you actually help.

**Calibration** — do your 80% bands contain the truth 80% of the time? Plot predicted-interval coverage against nominal. A sharp judge will ask this, and an uncalibrated probabilistic model is worse than a point estimate.

**Cascade case study** — pick one simulated disruption. Show the baseline calling a downstream train on time while your model predicts the inherited delay, and the truth landing near your prediction. That single chart is your best slide.

---

## 6. Who does what

Six people, six lanes, minimal blocking.

| Person | Owns | First deliverable |
|---|---|---|
| 1 | Graph — schedule parsing, sections, SRT | Stations + sections tables, sanity stats |
| 2 | Simulator | One day of running data from the real graph |
| 3 | Features + evaluation harness | Training table with the network-feature switch |
| 4 | Model + ablation experiment | Three trained quantile models, A/B/C table |
| 5 | Chaining loop + FastAPI | `/eta/{train_no}` returning band and per-section breakdown |
| 6 | Frontend + demo | Train view: band, causes, map |

**Dependency order:** 1 → 2 → 3 → 4 → 5 → 6. So people 5 and 6 must not wait. Person 5 builds against a **stub** that returns fake predictions in the right JSON shape on day one. Person 6 builds against person 5's stub. Agree the JSON contract in the first hour and freeze it.

```json
{
  "train_no": "12155",
  "stations": [
    {"code": "ET", "eta_median": "11:11", "eta_low": "11:02", "eta_high": "11:26"}
  ],
  "attribution": [
    {"cause": "caution order BZU-AMLA", "minutes": 12},
    {"cause": "held for precedence", "minutes": 18}
  ]
}
```

---

## 7. Three-week plan

Adjust to your actual deadline; the ordering matters more than the dates.

**Week 1 — foundations**
Graph built from real schedules and sanity-checked. Simulator producing a day of data. JSON contract frozen; API and frontend stubs running. Baseline implemented and measured. Repo, README, NOTES started.

**Week 2 — the core**
Feature builder with the network switch. Models trained. **Ablation run and the A/B/C table produced** — this is the week's real goal. Chaining loop working end to end. API serving real predictions.

**Week 3 — proving and polishing**
Calibration plot. Cascade case study. Dashboard finished. SHAP attribution if time allows. Docker Compose so it runs from one command. Rehearse the demo at least five times.

**Rule for week 3:** no new features. If the ablation is not done by the end of week 2, cut the frontend polish, not the experiment.

---

## 8. The demo

Eight minutes, in this order:

1. **The baseline failing.** Show today's formula predicting a downstream train on time.
2. **Your prediction for the same train.** Band, and the causes named.
3. **Wind the clock forward.** Truth lands inside your band. Baseline was wrong.
4. **The cascade.** Inject a caution order, show the ripple across trains.
5. **The numbers.** A/B/C table and the calibration plot.
6. **One command.** `docker compose up` — say it runs anywhere.

Run the whole thing from pre-generated data on disk. Never depend on a live scrape or a network call during judging.

---

## 9. Questions you will be asked

**"Is this real data?"**
> The network is — stations, sections and booked running times come from published Indian Railways schedules. The running data is simulated, because live feeds are internal to Railways. We're saying that openly. We also scraped real running data over [N] weeks on [corridor] as partial validation.

**"Then haven't you just proved your own simulator?"**
> For the cascade magnitude, partly — and we say so. What the experiment proves is that when delay propagates through shared track, a model with network features captures it and one without cannot. The mechanism is real; the size of the effect in production data is what we'd measure in a pilot.

**"What would you need from Railways?"**
> COA access for one division, and the caution order feed. Two things.

**"Why LightGBM and not deep learning?"**
> Published comparisons on rail delay data found gradient boosting competitive with or better than neural networks, and it trains in seconds, which let us run the ablation properly. A spatio-temporal GNN is our phase two.

**"Did you write this?"**
> Answer by demonstrating. Have each person open their own module and walk through it.

---

## 10. Where to ask for help

Bring me anything: a design you are unsure about, a bug you cannot find, a result that looks wrong, code you want reviewed, a concept that has not clicked. Explaining, debugging and reviewing is help you can accept and still own the work.

What you should not do is ask anyone — me included — to write the modules for you. You will be standing in front of that code.
