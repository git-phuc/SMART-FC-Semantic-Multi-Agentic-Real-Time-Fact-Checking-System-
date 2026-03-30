from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from graph.workflow import run_verification_with_cache

app = FastAPI()

# Allow cross-origin requests from React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    text: str

@app.post("/verify")
def verify_article(query: QueryRequest):
    try:
        # Gọi thẳng vào logic Multi-Agent thay vì chạy Streamlit
        result = run_verification_with_cache(query.text)
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
