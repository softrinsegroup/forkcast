import os
from dotenv import load_dotenv
import uvicorn

load_dotenv()

if __name__ == "__main__":
    print("Starting Meal Prep Agent 🥞🍕🍜🤖")
    reload = os.getenv("HOT_RELOAD", "false") == "true"
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=reload)
