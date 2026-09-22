# Decisions log

Date - person - decision - reason.

2026-09-20 - team - corridor scoped to FILL_IN

2026-09-20-Divyansh-11112 trains, 186113 stops,174690 route steps,28130 unique sections also dont open csv in xlsx/excel or else we are cooked-it breaks the routing and gives garabge data cus its get modified even if u open it in excel 

2026-09-20 - Aryaman Singh - built the Delhi-Mumbai corridor extraction in notebooks/build_corridor.py. The schedule was loaded with train numbers preserved as strings, then I checked the requested endpoint station codes before filtering trains that touch at least one Delhi-end code and at least one Mumbai-end code. Found DLI, NDLS, NZM and BCT, BVI, ST in the data. Rebuilt routes and directional sections from the corridor subset and wrote corridor_routes.csv, corridor_sections.csv, and corridor_trains.txt.
Results: 46 corridor trains, 1078 route steps, 584 unique directional sections, and the busiest section carries 11 trains (BRC>ST).
Warning: do not open/resave the schedule CSV in Excel because changing its values/types can break routing. Direction matters: A>B and B>A remain separate sections. Existing pytest baseline still passes: 28 passed.

2026-09-20 - Divyansh-collector running. 46 Delhi-Mumbai trains.
  RailRadar route array returns ~300 stops per train, ~300 with actualArrival.
  Far more observations per request than estimated - not quota constrained on training data.
  Free tier: 1000/month, 10/min burst. sleep(7) between calls.
  Quota after 3 nights: ~150 used.
  Station board endpoint returns all inbound trains in one call - live dashboard affordable.
  Api requests api configured and collecting live data
  
2026-09-21-Divyansh-parser made ,26 tests passes. 3 data traps identified-trains still running when  fetched them, halts the train hadn't reached yet are marked upcoming — but still carry an actualArrival TwT
Some halts are marked departed and have an actualArrival, but delayArrival and delayDeparture are None
train rolls throught without stopping railradar  doesnt observe the trains there hence no data was formed over there

aryu/metrics
2026-09-21 - Aryaman Singh - built the React dashboard in frontend/ (merged via PR #1). Four pages: /train/:trainNo (arrival window per station, "why late" cause breakdown, current-system time on the same row), /station/:code (every corridor train due at a station, sorted by likely arrival), /corridors, /about. Runs on mock data in frontend/public/mock/ (12951, 12953, 12925, 12909); all fetching goes through frontend/src/lib/api.js, so switching to the real API means setting VITE_API_URL only.
Design: cream parchment backdrop with an original compass rose and rhumb lines (pure SVG, no image files), white cards, one moss accent for the most likely arrival and the selected station, and a railway track with the train marker down the forecast card. Theme pinned to light so it looks the same on any judge's laptop.
Open items for whoever continues it: our mock may not match VV's frozen mock_12951.json (is_live, is_mock fields) - compare before building further; negative causes (time recovered) are not handled yet; no "sample data" tag yet.

2026-09-21 - Aryaman Singh - built evaluation scoring in src/eval/metrics.py. evaluate(y, p10, p50, p90) returns n, mae, rmse, coverage, mean_width, plus bias (does the model lean late or early) and crossing_rate (share of rows where p10 > p50 or p50 > p90; must be 0). ablation_table() reads every CSV in data/processed/predictions/ and ranks experiments by MAE.
Safety checks: warns if experiments were scored on different rows (MAEs then not comparable); stops if two files disagree on y_true for the same row (means a file is misaligned); rejects missing columns and duplicate rows; pads train numbers to 5 digits.
src/eval/make_fake_predictions.py writes 3 fake experiments from the latest day of observations.csv (277 rows) to data/processed/predictions_fake/ - kept separate so fake numbers can never reach the real table or the PPT.
Fake run behaved as expected: fake_sharp MAE 3.35 / coverage 0.95, fake_noisy 7.52 / 0.63, fake_wide 8.21 / 0.91 at double width. Lesson for results: coverage must always be read next to width, since a wide enough window is always "right" and useless.
Tests: tests/test_eval_metrics.py, 18 passed; full suite 72 passed.
Notes: minutes_lost can be negative (median section is ~1 min faster than booked), so charts must say "negative = time recovered". Test set is only 277 rows today, so small MAE differences may be luck - adding a bootstrap confidence range to the ablation table before Friday. data/processed/ is gitignored, so prediction files will not reach GitHub unless !data/processed/predictions/ is added to .gitignore.
Run: python -m src.eval.make_fake_predictions, then python -m src.eval.metrics data/processed/predictions_fake. Real table: python -m src.eval.metrics once Aaru and Rivy write their files.

2026-09-22 - Aryaman Singh - built the Delhi-Howrah corridor (corridor 2) with notebooks/build_named_corridor.py howrah. Filtered trains touching at least one Delhi-end code (NDLS, DLI, NZM, ANVT) and at least one Howrah-end code (HWH, SDAH, KOAA). Found ___ and ___ in the data. Kept five-digit train numbers only, ranked premium > express > other > special, alternated directions, capped at 20 to fit the quota (20 trains x 5 nights = 100 requests). Wrote corridor_howrah_trains.txt, corridor_howrah_routes.csv, corridor_howrah_sections.csv, and corridor_howrah_candidates.csv (all candidates, for swapping in replacements).
Results: ___ candidate trains (___ skipped for not being five digits), 20 selected (___ Delhi to Howrah, ___ Howrah to Delhi; ___ premium, ___ express), ___ route steps, ___ unique directional sections, busiest section carries ___ trains (___).
Same script builds the third corridor: python notebooks/build_named_corridor.py chennai. Corridor 1 keeps its original script and file names, since the collector and observations depend on them. Tests: tests/test_named_corridor.py, 7 passed.

2026-09-21 - Aaradhya - built corridor_overlap_trains.txt: 30 trains sharing >=17 sections
with the Delhi-Mumbai corridor (top: 32 shared, bottom: 17 shared). Excludes current
corridor trains, 10 never-tracked trains, and 0-prefix specials. Name-based SPECIAL
filter not yet applied - routes.csv has no train_name column, pending trains.csv access.

2026-09-21-Divyansh-specials dropped — untracked on their own run days; six weekly trains kept, fetched on run days only

2026-09-22 - Aryaman Singh - built the Delhi-Howrah corridor (corridor 2) with notebooks/build_named_corridor.py howrah. Filtered trains touching at least one Delhi-end code (NDLS, DLI, NZM, ANVT) and at least one Howrah-end code (HWH, SDAH, KOAA); all seven codes were found in the data. Kept five-digit train numbers only, dropped 0xxxx specials (untracked on their run days, per Divyansh), ranked premium > express > other > special by train name, alternated directions, capped at 20 to fit the quota (20 trains x 5 nights = 100 requests). Wrote corridor_howrah_trains.txt, corridor_howrah_routes.csv, corridor_howrah_sections.csv, and corridor_howrah_candidates.csv (all candidates, for swapping in replacements).
Results: 30 candidate trains, 0 skipped, 20 selected (10 Delhi to Howrah, 10 Howrah to Delhi; 5 premium, 7 express, 8 other), 348 route steps, 266 unique directional sections, busiest section carries 5 trains (ALD>CNB).
Not yet tested against RailRadar: check 2-3 picks before the first collection run, and swap any weekly or untracked train for the next candidate. The collector needs the corridor name option (Aaru's run_collector.py change) before Howrah can be collected.
Same script builds the third corridor: python notebooks/build_named_corridor.py chennai. Corridor 1 keeps its original script and file names. Tests: tests/test_named_corridor.py, 8 passed.
main
