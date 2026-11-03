"""Genera casos historicos de prueba; nunca lee archivos TLC reales."""

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

CASES = (
    "valid",
    "null_zone",
    "null_timestamp",
    "nonpositive_duration",
    "pickup_outside_month",
    "duplicate",
    "invalid_passengers",
    "missing_column",
    "incompatible_type",
    "extra_column",
)

# Contrato de las fixtures historicas, no whitelist de inferencia ni gate T08.
SCHEMA = pa.schema(
    [
        ("VendorID", pa.int32()),
        ("tpep_pickup_datetime", pa.timestamp("us")),
        ("tpep_dropoff_datetime", pa.timestamp("us")),
        ("passenger_count", pa.int64()),
        ("trip_distance", pa.float64()),
        ("RatecodeID", pa.int64()),
        ("store_and_fwd_flag", pa.large_string()),
        ("PULocationID", pa.int32()),
        ("DOLocationID", pa.int32()),
        ("payment_type", pa.int64()),
        ("fare_amount", pa.float64()),
        ("extra", pa.float64()),
        ("mta_tax", pa.float64()),
        ("tip_amount", pa.float64()),
        ("tolls_amount", pa.float64()),
        ("improvement_surcharge", pa.float64()),
        ("total_amount", pa.float64()),
        ("congestion_surcharge", pa.float64()),
        ("Airport_fee", pa.float64()),
    ]
)


def make_table(case: str = "valid", *, seed: int = 42) -> pa.Table:
    """Devuelve 12 filas sinteticas, con una anomalia controlada por caso."""
    if case not in CASES:
        raise ValueError(f"Caso desconocido: {case}")
    generator = random.Random(seed)
    rows = []
    for index in range(12):
        pickup = datetime(2024, 1, index + 1, 8) + timedelta(minutes=generator.randrange(60))
        rows.append(
            {
                "VendorID": 2,
                "tpep_pickup_datetime": pickup,
                "tpep_dropoff_datetime": pickup + timedelta(minutes=generator.randrange(5, 61)),
                "passenger_count": generator.randrange(1, 5),
                "trip_distance": float(index + 1),
                "RatecodeID": 1,
                "store_and_fwd_flag": "N",
                "PULocationID": 161,
                "DOLocationID": 236,
                "payment_type": 1,
                "fare_amount": 10.0,
                "extra": 1.0,
                "mta_tax": 0.5,
                "tip_amount": 0.0,
                "tolls_amount": 0.0,
                "improvement_surcharge": 1.0,
                "total_amount": 15.0,
                "congestion_surcharge": 2.5,
                "Airport_fee": 0.0,
            }
        )
    if case == "null_zone":
        rows[0]["PULocationID"] = None
    elif case == "null_timestamp":
        rows[0]["tpep_dropoff_datetime"] = None
    elif case == "nonpositive_duration":
        rows[0]["tpep_dropoff_datetime"] = rows[0]["tpep_pickup_datetime"]
        rows[1]["tpep_dropoff_datetime"] = rows[1]["tpep_pickup_datetime"] - timedelta(minutes=1)
    elif case == "pickup_outside_month":
        rows[0]["tpep_pickup_datetime"] = datetime(2024, 2, 1, 8)
        rows[0]["tpep_dropoff_datetime"] = datetime(2024, 2, 1, 8, 15)
    elif case == "duplicate":
        rows[-1] = rows[0].copy()
    elif case == "invalid_passengers":
        rows[0]["passenger_count"] = -1

    table = pa.Table.from_pylist(rows, schema=SCHEMA)
    if case == "missing_column":
        table = table.drop_columns(["PULocationID"])
    elif case == "incompatible_type":
        index = table.schema.get_field_index("PULocationID")
        table = table.set_column(
            index, "PULocationID", pa.array(["161"] * table.num_rows, type=pa.large_string())
        )
    elif case == "extra_column":
        table = table.append_column("cbd_congestion_fee", pa.array([0.75] * table.num_rows))
    return table.replace_schema_metadata(
        {
            b"fixture_origin": b"synthetic",
            b"fixture_case": case.encode(),
            b"seed": str(seed).encode(),
        }
    )


def write_fixtures(directory: Path, *, seed: int = 42) -> list[Path]:
    """Escribe solo casos propios; se niega a sobrescribir archivos ajenos."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = [directory / f"{case}.parquet" for case in CASES]
    for path in paths:
        if path.exists():
            metadata = pq.read_schema(path).metadata or {}
            if metadata.get(b"fixture_origin") != b"synthetic":
                raise FileExistsError(f"No se sobrescribe un archivo ajeno: {path}")
    for case, path in zip(CASES, paths, strict=True):
        pq.write_table(make_table(case, seed=seed), path, compression="snappy", row_group_size=6)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("tests/fixtures"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    paths = write_fixtures(args.output_dir, seed=args.seed)
    print(f"{len(paths)} fixtures sinteticas; {sum(path.stat().st_size for path in paths)} bytes")


if __name__ == "__main__":
    main()
