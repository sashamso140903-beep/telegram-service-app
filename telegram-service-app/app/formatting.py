def format_rub(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " ₽"
