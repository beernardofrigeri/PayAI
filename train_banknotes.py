"""Treina um detector YOLO para as denominações das cédulas."""

from pathlib import Path

from ultralytics import YOLO


ROOT = Path(__file__).resolve().parent
DATASET_YAML = ROOT / "dataset_yolo" / "data.yaml"


def main():
    if not DATASET_YAML.exists():
        raise SystemExit(
            "Execute primeiro: python prepare_yolo_dataset.py"
        )

    model = YOLO("yolo11n.pt")
    model.train(
        data=str(DATASET_YAML),
        epochs=50,
        imgsz=640,
        batch=4,
        patience=15,
        project=str(ROOT / "runs"),
        name="banknotes",
    )


if __name__ == "__main__":
    main()