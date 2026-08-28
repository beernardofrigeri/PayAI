"""Prepara o dataset organizado por pastas para treinamento YOLO.

As imagens atuais mostram uma cédula ocupando o quadro inteiro. Por isso,
este utilitário cria uma caixa inicial cobrindo toda a imagem. Essas caixas
servem para validar o pipeline; para uso em câmera, substitua-as por caixas
anotadas em fotos variadas.
"""

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "dataset"
OUTPUT = ROOT / "dataset_yolo"
CLASS_NAMES = ("2", "5", "10", "20", "50", "100", "200")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


def prepare_split(split):
    source_split = SOURCE / split
    image_dir = OUTPUT / "images" / split
    label_dir = OUTPUT / "labels" / split
    image_dir.mkdir(parents=True, exist_ok=True)
    label_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for class_id, class_name in enumerate(CLASS_NAMES):
        for source_image in sorted((source_split / class_name).iterdir()):
            if source_image.suffix.lower() not in IMAGE_SUFFIXES:
                continue

            destination_name = f"{class_name}_{source_image.name}"
            destination_image = image_dir / destination_name
            destination_label = label_dir / f"{Path(destination_name).stem}.txt"
            shutil.copy2(source_image, destination_image)

            # class x_center y_center width height, normalizados entre 0 e 1.
            destination_label.write_text(
                f"{class_id} 0.5 0.5 1.0 1.0\n",
                encoding="utf-8",
            )
            copied += 1

    return copied


def write_yaml():
    yaml_path = OUTPUT / "data.yaml"
    yaml_path.write_text(
        "path: dataset_yolo\n"
        "train: images/train\n"
        "val: images/val\n\n"
        f"names: {list(CLASS_NAMES)!r}\n",
        encoding="utf-8",
    )
    return yaml_path


def main():
    if not SOURCE.exists():
        raise SystemExit(f"Dataset não encontrado: {SOURCE}")

    train_count = prepare_split("train")
    val_count = prepare_split("val")
    yaml_path = write_yaml()
    print(f"Dataset YOLO criado em: {OUTPUT}")
    print(f"Imagens: {train_count} treino, {val_count} validação")
    print(f"Configuração: {yaml_path}")


if __name__ == "__main__":
    main()