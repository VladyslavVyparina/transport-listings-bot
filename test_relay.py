#!/usr/bin/env python3
import unittest

from relay_filters import is_transport_promo


PROMO = (
    "🚛 Маєте вільний транспорт?\n\n"
    "У нас завжди є актуальні вантажі для перевізників!\n\n"
    "Залиште заявку в боті — вкажіть тип авто, напрямок та дату готовності.\n\n"
    "📲 Ми підберемо для вас актуальний вантаж і зв’яжемося з вами в найближчий час!\n\n"
    "Працюємо швидко. Завантажуємо регулярно. Надійно!"
)


class RelayTests(unittest.TestCase):
    def test_skips_scheduled_promo(self):
        self.assertTrue(is_transport_promo(PROMO))
        self.assertTrue(
            is_transport_promo(
                "🚛 Маєте вільний транспорт?\n"
                "У нас завжди є актуальні вантажі для перевізників!\n"
                "Працюємо швидко. Завантажуємо регулярно. Надійно!"
            )
        )
        self.assertTrue(
            is_transport_promo(
                "🚛 <b>Маєте вільний транспорт?</b>\n\n"
                "У нас завжди є актуальні вантажі для перевізників!\n\n"
                "Працюємо швидко. Завантажуємо регулярно. Надійно!"
            )
        )

    def test_does_not_skip_listings_or_other_posts(self):
        self.assertFalse(is_transport_promo(""))
        self.assertFalse(
            is_transport_promo(
                "🚛 ВІЛЬНИЙ ТРАНСПОРТ\n"
                "Місце дислокації: Одеса\n"
                "Тип авто: Тент"
            )
        )
        self.assertFalse(is_transport_promo("Шукаю машину на Київ"))


if __name__ == "__main__":
    unittest.main()
