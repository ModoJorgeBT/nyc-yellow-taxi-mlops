"""Descargas Q2 2026 con reservas persistentes conservadoras antes de cada lectura."""

import argparse
import json
import os
from pathlib import Path

from src.ingestion.download import DownloadBudget, ingest, month_lock
from src.ingestion.manifest import utc_now
from src.retraining.protocol import DOWNLOADS, exclusive_json, inside, load_profile, read_json
from src.validation.schema import fingerprint


class PersistentBudget(DownloadBudget):
    """Un crash puede sobrecontar la ultima reserva; nunca devuelve su capacidad."""

    def __init__(self, path, *, profile_sha256, limit=2**30):
        self.path, self.profile_sha256 = Path(path), profile_sha256
        self.path.parent.mkdir(parents=True, exist_ok=True)
        pending = self.path.with_suffix(".pending")
        states = [read_json(p) for p in (self.path, pending) if p.exists()]
        if any(
            s.get("limit_bytes") != limit or s.get("profile_sha256") != profile_sha256
            for s in states
        ):
            raise ValueError("Contador pertenece a otro presupuesto/protocolo")
        used = max((s["reserved_bytes"] for s in states), default=0)
        super().__init__(limit, used)
        self.persist()

    def persist(self):
        temporary = self.path.with_suffix(".pending")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(
                {
                    "limit_bytes": self.limit_bytes,
                    "reserved_bytes": self.used_bytes,
                    "profile_sha256": self.profile_sha256,
                    "updated_at_utc": utc_now(),
                    "semantics": "CONSERVATIVE_RESERVED_BEFORE_READ_NOT_REFUNDED",
                },
                stream,
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.path)

    def read(self, response, size):
        self.consume(size)
        self.persist()
        return response.read(size)


def download(profile_path, *, root=None, raw_dir=None):
    root = Path(root or Path.cwd()).resolve()
    profile = load_profile(profile_path)
    receipt_root = inside(root, "reports/retraining/downloads")
    receipt_root.mkdir(parents=True, exist_ok=True)
    raw = inside(root, raw_dir or "data/raw")
    with month_lock(receipt_root):
        budget = PersistentBudget(
            receipt_root / "transfer-budget.json", profile_sha256=fingerprint(profile)
        )
        results = []
        for month in DOWNLOADS["months"]:
            result = ingest(
                2026,
                month,
                raw_dir=raw,
                retries=2,
                timeout=30,
                max_download_bytes=DOWNLOADS["max_file_bytes"],
                download_budget=budget,
            )
            results.append(result)
        receipt = {
            "status": "Q2_2026_OFFICIAL_DOWNLOADS_VERIFIED",
            "results": results,
            "profile_sha256": fingerprint(profile),
            "reserved_bytes": budget.used_bytes,
            "limit_bytes": budget.limit_bytes,
            "timestamp_utc": utc_now(),
        }
        destination = receipt_root / ("downloads-" + str(os.getpid()) + ".json")
        exclusive_json(destination, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/retraining.yaml"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--raw-dir", type=Path)
    args = parser.parse_args()
    result = download(args.config, root=args.root, raw_dir=args.raw_dir)
    print(
        json.dumps(
            {
                "status": result["status"],
                "reserved_bytes": result["reserved_bytes"],
                "months": [e["month"] for e in result["results"]],
            }
        )
    )


if __name__ == "__main__":
    main()
