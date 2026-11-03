"""macOS Vision OCR, through the small `ocrmac` wrapper.

Vision is built into macOS, so there is no Tesseract download or language-data
file to bundle for the Mac prototype. Windows will need a different OCR
backend behind the same `recognize()` function.
"""
from __future__ import annotations

from PIL import Image

from .model import TextLine


class OCRUnavailable(RuntimeError):
    pass


def recognize(image: Image.Image, languages: tuple[str, ...] = ("en-US",)) -> list[TextLine]:
    """Read the text in an image, top to bottom."""
    try:
        from ocrmac import ocrmac
    except Exception as exc:  # pragma: no cover - depends on the machine
        raise OCRUnavailable(f"macOS Vision OCR isn't available: {exc}") from exc

    try:
        raw = ocrmac.OCR(image.convert("RGB"), language_preference=list(languages)).recognize()
    except Exception as exc:  # pragma: no cover - depends on the machine
        raise OCRUnavailable(f"macOS Vision OCR failed: {exc}") from exc

    lines: list[TextLine] = []
    for text, confidence, box in raw:
        cleaned = " ".join(str(text).split())
        if not cleaned:
            continue
        lines.append(TextLine(
            text=cleaned,
            confidence=float(confidence or 0.0),
            box=tuple(float(v) for v in box),  # type: ignore[arg-type]
        ))
    # Vision's y grows upwards; the item name is the highest line.
    return sorted(lines, key=lambda line: -(line.box[1] + line.box[3]))
