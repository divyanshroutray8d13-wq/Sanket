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

2026-09-21 - Aaradhya - built corridor_overlap_trains.txt: 30 trains sharing >=17 sections
with the Delhi-Mumbai corridor (top: 32 shared, bottom: 17 shared). Excludes current
corridor trains, 10 never-tracked trains, and 0-prefix specials. Name-based SPECIAL
filter not yet applied - routes.csv has no train_name column, pending trains.csv access.

2026-09-21-Divyansh-specials dropped — untracked on their own run days; six weekly trains kept, fetched on run days only

2026-09-22 - Aryaman Singh - built the Delhi-Howrah corridor (corridor 2) with notebooks/build_named_corridor.py howrah. Filtered trains touching at least one Delhi-end code (NDLS, DLI, NZM, ANVT) and at least one Howrah-end code (HWH, SDAH, KOAA); all seven codes were found in the data. Kept five-digit train numbers only, dropped 0xxxx specials (untracked on their run days, per Divyansh), ranked premium > express > other > special by train name, alternated directions, capped at 20 to fit the quota (20 trains x 5 nights = 100 requests). Wrote corridor_howrah_trains.txt, corridor_howrah_routes.csv, corridor_howrah_sections.csv, and corridor_howrah_candidates.csv (all candidates, for swapping in replacements).
Results: 30 candidate trains, 0 skipped, 20 selected (10 Delhi to Howrah, 10 Howrah to Delhi; 5 premium, 7 express, 8 other), 348 route steps, 266 unique directional sections, busiest section carries 5 trains (ALD>CNB).
Not yet tested against RailRadar: check 2-3 picks before the first collection run, and swap any weekly or untracked train for the next candidate. The collector needs the corridor name option (Aaru's run_collector.py change) before Howrah can be collected.
Same script builds the third corridor: python notebooks/build_named_corridor.py chennai. Corridor 1 keeps its original script and file names. Tests: tests/test_named_corridor.py, 8 passed.