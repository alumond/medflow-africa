"""Reproduce the entire deterministic training/evaluation artifact."""

from scripts.train_model import train

if __name__ == "__main__":
    evaluation = train()
    print(
        "Reproduced model_artifacts/evaluation.json; synthetic test observations:",
        evaluation["test"]["sample_count"],
    )
