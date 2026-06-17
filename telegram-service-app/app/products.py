from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Product:
    id: str
    title: str
    price_rub: int
    category: str
    lead_time: str
    description: str

    def to_dict(self) -> dict:
        return asdict(self)


PRODUCTS: list[Product] = [
    Product(
        id="diploma_consulting",
        title="Консультация по дипломной работе",
        price_rub=30000,
        category="Работы",
        lead_time="по договоренности",
        description="Разбор темы, структуры, источников, плана и рекомендаций по подготовке материала.",
    ),
    Product(
        id="coursework_consulting",
        title="Консультация по курсовой работе",
        price_rub=5000,
        category="Работы",
        lead_time="от 3 дней",
        description="Помощь с планом, логикой разделов, списком источников и требованиями кафедры.",
    ),
    Product(
        id="antiplagiat_report_review",
        title="Анализ отчета Антиплагиат",
        price_rub=2000,
        category="Текст",
        lead_time="1-2 дня",
        description="Разбор отчета, поиск проблемных мест и рекомендации по корректной доработке текста.",
    ),
    Product(
        id="text_editing_sources",
        title="Редактура текста и работа с источниками",
        price_rub=2000,
        category="Текст",
        lead_time="1-3 дня",
        description="Редактура, вычитка, улучшение структуры и приведение ссылок к требованиям.",
    ),
    Product(
        id="coursework_gost",
        title="Оформление курсовой по ГОСТ",
        price_rub=500,
        category="ГОСТ",
        lead_time="1 день",
        description="Поля, шрифты, интервалы, заголовки, список литературы и базовое оформление.",
    ),
    Product(
        id="diploma_gost",
        title="Оформление дипломной по ГОСТ",
        price_rub=2000,
        category="ГОСТ",
        lead_time="1-2 дня",
        description="Полное оформление ВКР по требованиям ГОСТ и методическим указаниям.",
    ),
    Product(
        id="defense_speech",
        title="Текст для защиты ВКР",
        price_rub=2000,
        category="Защита",
        lead_time="1-2 дня",
        description="Краткая речь для защиты на основе вашей готовой работы и структуры презентации.",
    ),
    Product(
        id="presentation_10",
        title="Презентация 10 слайдов",
        price_rub=500,
        category="Презентации",
        lead_time="1 день",
        description="Лаконичная презентация с титульным слайдом, структурой, выводами и единым стилем.",
    ),
    Product(
        id="presentation_20",
        title="Презентация 20 слайдов",
        price_rub=1000,
        category="Презентации",
        lead_time="1-2 дня",
        description="Расширенная презентация с визуальной структурой, акцентами и финальным выводом.",
    ),
]


def list_products() -> list[dict]:
    return [product.to_dict() for product in PRODUCTS]


def get_product(product_id: str) -> Product | None:
    return next((product for product in PRODUCTS if product.id == product_id), None)
