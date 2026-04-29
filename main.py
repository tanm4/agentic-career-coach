from fastapi import FastAPI, Request
from google.cloud import firestore
import os

app = FastAPI()

# ---------------- FIRESTORE ---------------- #

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

# ---------------- TOOL LOGIC ---------------- #

def fetch_jobs(params):
    role = (params.get("role") or "").lower()
    location = (params.get("location") or "").lower()

    filtered = []

    for job in JOBS:
        if role in job["title"].lower() and location in job["location"].lower():
            filtered.append(job)

    return {"jobs": filtered}


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

# ---------------- MCP TOOL REGISTRY ---------------- #

@app.get("/tools")
def tools():
    return {
        "tools": [
            {
                "name": "fetch_jobs",
                "description": "Fetch jobs filtered by role and location",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "role": {"type": "string"},
                        "location": {"type": "string"}
                    }
                }
            },
            {
                "name": "sync_pipeline",
                "description": "Create, update, or list job applications in Firestore",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "job_id": {"type": "string"},
                        "company": {"type": "string"},
                        "title": {"type": "string"},
                        "status": {"type": "string"}
                    }
                }
            }
        ]
    }

# ---------------- MCP TOOL EXECUTION ---------------- #

@app.post("/invoke")
async def invoke(request: Request):
    body = await request.json()

    tool = body.get("tool")
    params = body.get("params", {})

    if tool == "fetch_jobs":
        return fetch_jobs(params)

    if tool == "sync_pipeline":
        return sync_pipeline(params)

    return {"error": f"Unknown tool: {tool}"}

# ---------------- HEALTH CHECK ---------------- #

@app.get("/")
def root():
    return {"status": "MCP Server Running"}