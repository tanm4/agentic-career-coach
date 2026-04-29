import os
from fastapi import FastAPI
from google.cloud import firestore

from mcp.server.fastapi import FastApiMCP

app = FastAPI()

db = firestore.Client()

# ---------------- MCP SETUP (FIXED) ---------------- #

mcp = FastApiMCP(app)

# ---------------- DATA ---------------- #

JOBS = [
    {"id": "1", "company": "Google", "title": "Software Intern", "location": "NYC"},
    {"id": "2", "company": "Amazon", "title": "SDE Intern", "location": "Seattle"},
    {"id": "3", "company": "Meta", "title": "ML Intern", "location": "NYC"},
]

# ---------------- TOOLS ---------------- #

@mcp.tool()
def fetch_jobs(role: str = "", location: str = ""):
    role = role.lower()
    location = location.lower()

    return {
        "jobs": [
            j for j in JOBS
            if role in j["title"].lower()
            and location in j["location"].lower()
        ]
    }


@mcp.tool()
def sync_pipeline(action: str, job_id: str = "", company: str = "", title: str = "", status: str = ""):
    ref = db.collection("applications").document(job_id)

    if action == "create":
        ref.set({"job_id": job_id, "company": company, "title": title, "status": "saved"})
        return {"status": "created"}

    if action == "update":
        ref.update({"status": status})
        return {"status": "updated"}

    if action == "list":
        return {
            "applications": [d.to_dict() for d in db.collection("applications").stream()]
        }

    return {"error": "invalid action"}

# ---------------- HEALTH ---------------- #

@app.get("/")
def root():
    return {"status": "MCP Server Running"}

# ---------------- CRITICAL FIX ---------------- #

mcp.mount()