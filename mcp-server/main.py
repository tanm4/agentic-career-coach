from fastapi import FastAPI, Request
from google.cloud import firestore
import json

app = FastAPI()
db = firestore.Client()

# ---------------- MOCK JOB DATA ---------------- #

JOBS = [
    {"id": "1", "company": "Google", "title": "Software Intern", "location": "NYC", "url": "google.com"},
    {"id": "2", "company": "Amazon", "title": "SDE Intern", "location": "Seattle", "url": "amazon.jobs"},
    {"id": "3", "company": "Meta", "title": "ML Intern", "location": "NYC", "url": "meta.com"}
]

# ---------------- TOOL 1: FETCH JOBS ---------------- #

def fetch_jobs(params):
    role = params.get("role", "").lower()
    location = params.get("location", "").lower()

    return {
        "jobs": [
            j for j in JOBS
            if role in j["title"].lower()
            and location in j["location"].lower()
        ]
    }

# ---------------- TOOL 2: FIRESTORE PIPELINE ---------------- #

def sync_pipeline(params):
    action = params.get("action")
    job_id = params.get("job_id")

    ref = db.collection("applications").document(job_id)

    if action == "create":
        ref.set({
            "job_id": job_id,
            "company": params.get("company"),
            "title": params.get("title"),
            "status": "saved"
        })
        return {"status": "created"}

    if action == "update":
        ref.update({"status": params.get("status")})
        return {"status": "updated"}

    if action == "list":
        docs = db.collection("applications").stream()
        return {"applications": [d.to_dict() for d in docs]}

    return {"error": "invalid action"}

# ---------------- MCP ENDPOINT ---------------- #

@app.post("/mcp")
async def mcp(request: Request):
    body = await request.json()

    method = body.get("method")
    params = body.get("params", {})

    if method == "fetch_jobs":
        return fetch_jobs(params)

    if method == "sync_pipeline":
        return sync_pipeline(params)

    return {"error": "unknown method"}

# ---------------- HEALTH CHECK ---------------- #

@app.get("/")
def home():
    return {"status": "MCP server running"}