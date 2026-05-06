import os
from anthropic import AsyncAnthropic


_client: AsyncAnthropic | None = None


def init() -> None:
    global _client
    # Reads ANTHROPIC_API_KEY from env by default
    _client = AsyncAnthropic()


# Throws error if client has not been initialized.
def get_client() -> AsyncAnthropic:
    if _client is None:
        raise RuntimeError("Call client.init() before get_client()")
    return _client
