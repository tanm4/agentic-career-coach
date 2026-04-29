import os
import uvicorn
from fastapi import FastAPI
from google.cloud import firestore

from mcp.server.fastapi import MCPServer

app = FastAPI()
db = firestore.Client()

# ---------------- DATA ---------------- #

JOBS = [
    {"id": "1", "company": "Google", "title": "Software Intern", "location": "NYC"},
    {"id": "2", "company": "Amazon", "title": "SDE Intern", "location": "Seattle"},
    {"id": "3", "company": "Meta", "title": "ML Intern", "location": "NYC"},
]

# ---------------- MCP ---------------- #

mcp = MCPServer(app)

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

# IMPORTANT: mount MCP BEFORE anything else
mcp.mount(app)

# ---------------- HEALTH ---------------- #

@app.get("/")
def root():
    return {"status": "MCP Server Running"}

# ---------------- CRITICAL CLOUD RUN FIX ---------------- #

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))

    # IMPORTANT: no import string, direct app reference
    uvicorn.run(app, host="0.0.0.0", port=port)