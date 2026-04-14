import uuid
from pathlib import Path

import cv2


def preprocess_image(input_path: Path, output_dir: Path) -> Path:
    image = cv2.imread(str(input_path))
    if image is None:
        raise ValueError("Unable to read the uploaded image")

    h, w = image.shape[:2]
    max_size = 1024
    scale = min(max_size / w, max_size / h, 1.0)
    if scale < 1.0:
        new_w = int(w * scale)
        new_h = int(h * scale)
        image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    processed = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{uuid.uuid4().hex}_processed.jpg"
    cv2.imwrite(str(output_path), processed)
    return output_path

