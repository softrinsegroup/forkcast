import re

URL_PATTERN = re.compile(r"https?://\S+")


def extract_url(text: str) -> str | None:
    match = URL_PATTERN.search(text)

    # No URL found in text
    if not match:
        return None

    url = match.group()
    return url
