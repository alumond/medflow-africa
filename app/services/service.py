"""Application orchestration over repositories and independent analytical functions."""

from datetime import date

from app.core.config import POLICY
from app.data.generate import END, VERSION, generate
from app.data.programme import programme
from app.data.validation import checksum, validate_bundle
from app.services.analysis import analyze
from app.services.redistribution import attach_reviews, plan, validate_review


class Service:
    """A request-scoped application service; analysis caching never crosses datasets."""

    def __init__(self, store):
        self.store = store

    def import_bundle(self, bundle: dict, cutoff: date, sources: list[dict], synthetic: bool = True) -> dict:
        result = validate_bundle(bundle, cutoff)
        result.update(
            checksum=checksum(
                {
                    "bundle": bundle,
                    "cutoff": cutoff,
                    "schema": POLICY["schema_version"],
                    "synthetic": synthetic,
                }
            ),
            cutoff=cutoff.isoformat(),
            sources=sources,
            schema_version=POLICY["schema_version"],
            config_version=POLICY["version"],
            synthetic=synthetic,
            generator_version=VERSION if synthetic else None,
        )
        saved = self.store.save_import(result)
        return {key: value for key, value in saved.items() if key != "data"}

    def load_demo(self) -> dict:
        data = generate()
        return self.import_bundle(
            data,
            END,
            [
                {
                    "filename": key + ".csv",
                    "entity": key,
                    "rows": len(rows),
                    "checksum": checksum({key: rows}),
                }
                for key, rows in data.items()
            ],
        )

    def ensure_demo(self):
        try:
            self.store.latest()
        except LookupError:
            self.load_demo()

    def snapshot(self, window: int = 14) -> dict:
        return analyze(self.store.latest(), window)

    def planner(self, window: int = 14) -> dict:
        snapshot = self.snapshot(window)
        result = attach_reviews(plan(snapshot), self.store.reviews())
        self.store.record_analysis(
            snapshot["context"], len(result["recommendations"]), len(result["withheld"])
        )
        return result

    def overview(self, window: int = 14) -> dict:
        snapshot = self.snapshot(window)
        planner = attach_reviews(plan(snapshot), self.store.reviews())
        self.store.record_analysis(
            snapshot["context"], len(planner["recommendations"]), len(planner["withheld"])
        )
        program = programme(snapshot, planner)
        counts = {
            band: sum(p["risk"] == band for p in snapshot["pairs"])
            for band in ("high", "medium", "low", "not_assessed")
        }
        return {**snapshot, "planner": planner, "programme": program, "counts": counts}

    def review(self, recommendation_id: str, request: dict, window: int = 14) -> dict:
        found = next(
            (
                r
                for r in self.planner(window)["recommendations"]
                if r["recommendation_id"] == recommendation_id
            ),
            None,
        )
        if not found:
            raise LookupError("Recommendation not found in the current dataset and horizon")
        validate_review(found, request)
        return self.store.review(found, {**request, "provenance": self.snapshot(window)["context"]})
