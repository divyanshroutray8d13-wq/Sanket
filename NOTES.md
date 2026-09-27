Decisions log
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

2026-09-21 - Aaradhya - built corridor_overlap_trains.txt: 30 trains sharing >=17 sections
with the Delhi-Mumbai corridor (top: 32 shared, bottom: 17 shared). Excludes current
corridor trains, 10 never-tracked trains, and 0-prefix specials. Name-based SPECIAL
filter not yet applied - routes.csv has no train_name column, pending trains.csv access.

2026-09-21-Divyansh-specials dropped — untracked on their own run days; six weekly trains kept, fetched on run days only

2026-09-22 - Aryaman Singh - built the Delhi-Howrah corridor (corridor 2) with notebooks/build_named_corridor.py howrah, at Aaru's request. Filtered trains touching at least one Delhi-end code (NDLS, DLI, NZM, ANVT) and at least one Howrah-end code (HWH, SDAH, KOAA); all seven codes were found in the data. Kept five-digit train numbers only, dropped 0xxxx specials (untracked on their run days, per Divyansh), ranked premium > express > other > special by train name, and alternated directions. Picked by that ranking, not by lowest train number. Capped at 15 per Aaru (15 trains x 5 nights = 75 requests). Wrote corridor_howrah_trains.txt, corridor_howrah_routes.csv, corridor_howrah_sections.csv, and corridor_howrah_candidates.csv (all 30 candidates, for swapping in replacements).
Results: 30 candidate trains, 0 skipped, 15 selected (8 Delhi to Howrah, 7 Howrah to Delhi; 5 premium, 7 express, 3 other), 280 route steps, 231 unique directional sections, busiest section carries 4 trains (ASN>DGR).
Not yet tested against RailRadar: check 2-3 picks before the first collection run, and swap any weekly or untracked train for the next candidate. The collector needs the corridor name option before Howrah can be collected.
Same script builds the third corridor: python notebooks/build_named_corridor.py chennai (change MAX_TRAINS to set its size). Corridor 1 keeps its original script and file names. Tests: tests/test_named_corridor.py, 8 passed. (A first run capped at 20 trains was superseded by this 15-train list.)
2026-09-22 - Aryaman Singh - added src/eval/plots.py: 10_ablation_mae.png (error per experiment, baselines grey, SANKET models blue) and 11_coverage.png (share of sections inside the window vs the 80% target, with window width beside each bar). Real runs save to docs/figures/; any folder with "fake" in its name saves to data/processed/figures_fake/ (gitignored) stamped FAKE DATA. make_fake_predictions.py now uses the four real experiment names. Tests: tests/test_eval_plots.py, 4 passed. Real charts: python -m src.eval.plots once predictions exist.

2026-09-22 - Aryaman Singh - added src/eval/compare.py: paired bootstrap (5000 resamples) of the MAE gap between experiments, resampling whole train runs rather than single sections, since sections of one train share its delays. Answers: do network features help (model_network vs model_base), and does each model beat the best baseline. Says "not distinguishable" when the 95% range crosses zero. Key point: the test day's sections come from only ~15 train runs, so more collection nights narrow the ranges more than anything else. Tests: tests/test_eval_compare.py, 8 passed.

2026-09-22 - Aaradhya - built src/eval/split.py (time_split attach_corridor corridor_holdout_split) and src/eval/baselines.py (baseline_zero baseline_section) fixed a bug where attach_corridor's glob never matched corridor_trains.txt (mumbai) leaving every row unmatched added a regression test for it scored both baselines on real observations.csv via metrics.py baseline_section MAE 6.54 coverage 0.69 width 14.0 beats baseline_zero MAE 8.14 coverage 0.84 width 28.0 crossing_rate 0.00 for both predictions written to data/processed/predictions/ whitelisted in .gitignore tests test_eval_split.py 3 passed test_eval_baselines.py 3 passed

2026-09-26 - Aryu - live data now works end to end: RailRadar's current position -> our model -> a live ETA, via GET /eta/{train}?live=true. Tested for real on train 12903, got back a real position, delay, and forecast. Added a 90-second cache so we don't hit RailRadar on every request (first call ~8s, cached call ~0.01s). Checked the ChatGPT summary against the actual code and found: CorridorsPage.jsx was claimed as updated but wasn't touched at all; two files (StationPage.jsx, States.jsx) had broken character encoding from whatever tool edited them, now fixed; deleted a stray leftover backup file.
Also: if you unzip a project and git shows ~150 files "modified" for no reason, that's just a false alarm from file timestamps, not real changes. Fix with `git add --renormalize .`, don't panic-commit everything.

2026-09-26 - Aryu - results.md was still showing old (21 Sept) numbers even after we fixed it earlier - the fix never got committed. Redid it with real 23 Sept numbers: our model beats the baseline by about 0.78 min/section, clearly (checked with 5000 resamples, not just eyeballing it). Also finally answered "does it work on other routes": tested the model on a corridor it never saw during training. Overlap corridor: works basically as well as trained routes. Howrah: works, but noticeably worse, and on a small sample - flagging that as a real but early result.

2026-09-26 - Aryu - figured out why our "80% confidence" windows were only right 60-65% of the time. Not a data problem - it's that we calibrate using just one day, and the model's mistakes point in different directions on different days. Using more days for calibration fixes it (tested: 65% -> 81% coverage, for slightly wider windows). Added this as an option (n_cal_days) but left the default as-is - needs the team to decide before we change the official numbers.
Also figured out why "section history" looks bad in one report and great in another: it's the same feature, but one report uses it for a single section and the other adds it up across many sections - summing cancels out noise, which explains the flip.

2026-09-26 - Aryu - the overlap corridor never showed up on the map because nobody had generated its route file - wrote a script for that, now it does. Also found these route files were never actually saved to git (silently ignored), so this was invisible to the whole team, not just missing on one machine - fixed that. corridors.json and the Corridors page were also out of date (still said Howrah/overlap were "coming soon" when they're already live) - updated both.

2026-09-26 - Aryu - small frontend polish: the nav bar's active tab now slides smoothly instead of snapping, the LIVE badge now pulses, and added visible keyboard focus (was missing entirely before - an actual accessibility bug, not just style).
