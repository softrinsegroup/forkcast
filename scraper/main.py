import os
from dotenv import load_dotenv
import uvicorn

load_dotenv()

if __name__ == "__main__":
    print("Starting Forkcast scraper 🕷️")
    reload = os.getenv("HOT_RELOAD", "false") == "true"
    uvicorn.run(
        "app:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")), reload=reload
    )
