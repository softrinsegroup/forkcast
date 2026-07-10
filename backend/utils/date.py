from datetime import date, timedelta


def this_monday() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


def last_monday() -> date:
    today = date.today()
    this_monday = today - timedelta(days=today.weekday())
    return this_monday - timedelta(weeks=1)
