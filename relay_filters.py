"""Визначення планового транспортного пуша, який ретранслятор не копіює."""

from __future__ import annotations

import re

PROMO_MARKERS = (
    "Маєте вільний транспорт?",
    "У нас завжди є актуальні вантажі для перевізників",
    "Працюємо швидко. Завантажуємо регулярно. Надійно!",
)


def is_transport_promo(text: str) -> bool:
    value = re.sub(r"<[^>]+>", "", text or "").strip()
    if not value:
        return False
    return all(marker in value for marker in PROMO_MARKERS)
