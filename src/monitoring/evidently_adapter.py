"""Evidently sobre bins reales agregados: ninguna fila representa un viaje ficticio."""

import os

os.environ.setdefault("DO_NOT_TRACK", "1")

import pandas as pd  # noqa: E402
from evidently import DataDefinition, Dataset, Report  # noqa: E402
from evidently.core.metric_types import SingleValueCalculation, SingleValueMetric  # noqa: E402

from src.monitoring.drift import psi  # noqa: E402
from src.monitoring.protocol import POLICY  # noqa: E402


class HistogramPSI(SingleValueMetric):
    feature: str


class HistogramPSICalculation(SingleValueCalculation[HistogramPSI]):
    def calculate(self, context, current_data, reference_data):
        selected = current_data.column("feature").data == self.metric.feature
        left = current_data.column("reference_count").data[selected].to_numpy()
        right = current_data.column("current_count").data[selected].to_numpy()
        if min(left.sum(), right.sum()) < POLICY["minimum_rows"]:
            raise ValueError("No publicar PSI sin suficientes viajes")
        return self.result(value=psi(left, right, alpha=POLICY["smoothing_alpha"]))

    def display_name(self):
        return f"PSI (conteos completos, alpha=0.5): {self.metric.feature}"


class PopulationRows(SingleValueMetric):
    population: str


class PopulationRowsCalculation(SingleValueCalculation[PopulationRows]):
    def calculate(self, context, current_data, reference_data):
        selected = current_data.column("feature").data == "pickup_month"
        return self.result(
            value=int(current_data.column(self.metric.population + "_count").data[selected].sum())
        )

    def display_name(self):
        return f"Viajes representados por bins agregados: {self.metric.population}"


def render(drift, destination):
    dataset = Dataset.from_pandas(
        pd.DataFrame(drift["bins"]),
        data_definition=DataDefinition(
            categorical_columns=["feature", "category"],
            numerical_columns=["reference_count", "current_count"],
        ),
    )
    metrics = [PopulationRows(population="reference"), PopulationRows(population="current")]
    metrics.extend(
        HistogramPSI(feature=name)
        for name, value in drift["features"].items()
        if value["status"] != "NOT_AVAILABLE"
    )
    snapshot = Report(metrics).run(dataset, None)
    for name in ("evidently.json", "evidently.html"):
        if (destination / name).exists():
            raise ValueError("No sobrescribir reporte Evidently")
    snapshot.save_json(str(destination / "evidently.json"))
    snapshot.save_html(str(destination / "evidently.html"))
