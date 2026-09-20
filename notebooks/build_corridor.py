import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.graph.build_graph import (
    load_schedule,
    add_absolute_minutes,
    build_routes,
    build_sections,
)

DATA_PATH = "data/raw/trains.csv"
DELHI_STATIONS = {"NDLS", "DLI", "NZM"}
MUMBAI_STATIONS = {"BCT", "BVI", "ST"}


def main():
    df = load_schedule(DATA_PATH)
    print(f"Loaded {df.train_no.nunique()} trains and {len(df)} stops.")

    available_codes = set(df["station_code"].dropna().astype(str))
    available_delhi = sorted(DELHI_STATIONS & available_codes)
    available_mumbai = sorted(MUMBAI_STATIONS & available_codes)
    print(f"Delhi-end codes found: {available_delhi}")
    print(f"Mumbai-end codes found: {available_mumbai}")

    if not available_delhi:
        raise RuntimeError("None of the Delhi-end station codes were found.")
    if not available_mumbai:
        raise RuntimeError("None of the Mumbai-end station codes were found.")

    train_stations = df.groupby("train_no")["station_code"].apply(set)
    corridor_trains = sorted(
        train_stations[
            train_stations.apply(
                lambda stations: bool(stations & DELHI_STATIONS)
                and bool(stations & MUMBAI_STATIONS)
            )
        ].index
    )

    print(f"Corridor trains: {len(corridor_trains)}")
    if not corridor_trains:
        raise RuntimeError("No trains were found touching both corridor ends.")

    corridor_df = df[df["train_no"].isin(corridor_trains)].copy()
    corridor_df = add_absolute_minutes(corridor_df)
    routes = build_routes(corridor_df)
    sections = build_sections(routes)

    output_dir = Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    routes.to_csv(output_dir / "corridor_routes.csv", index=False)
    sections.to_csv(output_dir / "corridor_sections.csv", index=False)
    (output_dir / "corridor_trains.txt").write_text(
        "".join(f"{train_no}\n" for train_no in corridor_trains),
        encoding="utf-8",
    )

    print(f"Route steps: {len(routes)}")
    print(f"Unique sections: {len(sections)}")
    print(f"Trains busiest section carries: {int(sections.n_trains.max())}")
    print(f"Busiest section: {sections.iloc[0].section_id}")


if __name__ == "__main__":
    main()
