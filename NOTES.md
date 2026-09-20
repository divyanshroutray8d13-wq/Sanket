# Decisions log

Date - person - decision - reason.

2026-09-20 - team - corridor scoped to FILL_IN

2026-09-20-Divyansh-11112 trains, 186113 stops,174690 route steps,28130 unique sections also dont open csv in xlsx/excel or else we are cooked-it breaks the routing and gives garabge data cus its get modified even if u open it in excel 

2026-09-20 - Aryaman Singh - built the Delhi-Mumbai corridor extraction in notebooks/build_corridor.py. The schedule was loaded with train numbers preserved as strings, then I checked the requested endpoint station codes before filtering trains that touch at least one Delhi-end code and at least one Mumbai-end code. Found DLI, NDLS, NZM and BCT, BVI, ST in the data. Rebuilt routes and directional sections from the corridor subset and wrote corridor_routes.csv, corridor_sections.csv, and corridor_trains.txt.
Results: 46 corridor trains, 1078 route steps, 584 unique directional sections, and the busiest section carries 11 trains (BRC>ST).
Warning: do not open/resave the schedule CSV in Excel because changing its values/types can break routing. Direction matters: A>B and B>A remain separate sections. Existing pytest baseline still passes: 28 passed.

