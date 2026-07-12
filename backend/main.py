import os
from dotenv import load_dotenv
import uvicorn

load_dotenv()

if __name__ == "__main__":
    print("Starting Forkcast 🍴")
    reload = os.getenv("HOT_RELOAD", "false") == "true"
    # log_config=None: defer to configure_logging() in api.main so Uvicorn's
    # logs share our unified format instead of its default handlers.
    uvicorn.run(
        "api.main:app", host="0.0.0.0", port=8000, reload=reload, log_config=None
    )
