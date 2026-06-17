VALID_STATUSES = {"new", "in_progress", "done", "cancelled"}

STATUS_LABELS = {
    "new": "Новый",
    "in_progress": "В работе",
    "done": "Готово",
    "cancelled": "Отменен",
}

ADMIN_STATUS_ACTIONS = [
    ("in_progress", "В работу"),
    ("done", "Готово"),
    ("cancelled", "Отменить"),
]
