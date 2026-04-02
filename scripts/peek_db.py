import os
from pathlib import Path
from pymongo import MongoClient
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
load_dotenv(BACKEND_DIR / ".env")

MONGO_URI = os.getenv("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["FakeNewsDB"]
collection = db["CacheLogs"]

print("--- 5 documents in CacheLogs ---")
for doc in collection.find().limit(5):
    query = doc.get("query", "N/A")
    full_resp = doc.get("full_response", {})
    verdict = full_resp.get("verdict", "N/A")
    print(f"Query: {query[:50]}...")
    print(f"Verdict: {verdict}")
    print("-" * 20)

print("\n--- All distinct verdicts ---")
print(collection.distinct("full_response.verdict"))
client.close()
