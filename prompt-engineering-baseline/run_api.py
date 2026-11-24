# Source history: Raj Kumar (a3ef3a6); see source-history.json.
import uvicorn
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

if __name__ == "__main__":
    uvicorn.run("app.api.main:app", host="127.0.0.1", port=int(os.getenv("BASELINE_API_PORT", "8001")), reload=True)
