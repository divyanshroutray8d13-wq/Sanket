import pandas as pd

COLS = ["train_no", "train_category", "run_date", "step_seq",
        "from_station", "to_station", "booked_srt_min", "actual_srt_min",
        "minutes_lost", "length_km", "dep_delay_min"]

REJECT = {"DIVERTED", "PARTIALLY_CANCELLED"}


def minutes_between(start, end):
    return (pd.to_datetime(end) - pd.to_datetime(start)).total_seconds() / 60

def departed_observed(s):
    return (s.get("status") == "departed"
            and s.get("actualDeparture") is not None
            and s.get("delayDeparture") is not None)


def arrived_observed(s):
    return (s.get("status") in ("departed", "at-station")
            and s.get("actualArrival") is not None
            and s.get("delayArrival") is not None)
def route_to_observations(payload):
    empty = pd.DataFrame(columns=COLS)
    if payload.get("success") is not True:
        return empty
    d = payload["data"]
    exceptions = d.get("exceptions") or []
    if any(e.get("type") in REJECT for e in exceptions):
        return empty
    route = [s for s in (d.get("route") or []) if s.get("isHalt")]
    rows = []
    for A, B in zip(route, route[1:]):
         if not (departed_observed(A) and arrived_observed(B)):
            continue
         if not (A.get("scheduledDeparture") and B.get("scheduledArrival")):
            continue
         booked = minutes_between(A.get("scheduledDeparture"), B.get("scheduledArrival"))
         actual = minutes_between(A.get("actualDeparture"), B.get("actualArrival"))
         length = B.get("distance", 0) - A.get("distance", 0)
         if booked <= 0 or booked > 720 or length <= 0:
            continue
         append_row =[d["trainNumber"], d["train"]["category"], d["startDate"], 0,
                      A["stationCode"], B["stationCode"],
                      round(booked), round(actual), round(actual - booked),
                      length, A.get("delayDeparture") or 0]
         rows.append(append_row)
    if not rows:
        return empty

    out = pd.DataFrame(rows, columns=COLS)
    out["step_seq"] = range(len(out))
    return out