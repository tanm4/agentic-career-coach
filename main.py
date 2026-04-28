from fastapi import FastAPI, Request
from google.cloud import firestore
import os

app = FastAPI()

# Firestore Client
db = firestore.Client()

# ---------------- MOCK JOB DATA ---------------- #

JOBS = [
    {
        "id": "1",
        "company": "Google",
        "title": "Software Intern",
        "location": "NYC",
        "url": "https://careers.google.com"
    },
    {
        "id": "2",
        "company": "Amazon",
        "title": "SDE Intern",
        "location": "Seattle",
        "url": "https://amazon.jobs"
    },
    {
        "id": "3",
        "company": "Meta",
        "title": "ML Intern",
        "location": "NYC",
        "url": "https://www.metacareers.com"
    }
]

# ---------------- TOOL 1 ---------------- #

def fetch_jobs(params):
    role = params.get("role", "").lower()
    location = params.get("location", "").lower()

    filtered = []

    for job in JOBS:
        if role in job["title"].lower() and location in job["location"].lower():
            filtered.append(job)

    return {"jobs": filtered}

# ---------------- TOOL 2 ---------------- #

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

    elif action == "update":
        ref.update({
            "status": params.get("status", "updated")
        })
        return {"status": "updated"}

    elif action == "list":
        docs = db.collection("applications").stream()
        return {
            "applications": [doc.to_dict() for doc in docs]
        }

    return {"error": "Invalid action"}

# ---------------- MCP ROUTE ---------------- #

@app.post("/mcp")
async def mcp(request: Request):
    body = await request.json()

    method = body.get("method")
    params = body.get("params", {})

    if method == "fetch_jobs":
        return fetch_jobs(params)

    elif method == "sync_pipeline":
        return sync_pipeline(params)

    return {"error": "Unknown method"}

# ---------------- HEALTH CHECK ---------------- #

@app.get("/")
def root():
    return {
        "status": "MCP Server Running"
    }