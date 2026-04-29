from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse
from google.cloud import firestore
import json
import os

app = FastAPI()

# ---------------- FIRESTORE (ADC SAFE) ---------------- #

db = firestore.Client(
    project=os.getenv("GOOGLE_CLOUD_PROJECT")
)

# ---------------- MOCK DATA ---------------- #

JOBS = [
    {"id": "1", "company": "Google", "title": "Software Intern", "location": "NYC"},
    {"id": "2", "company": "Amazon", "title": "SDE Intern", "location": "Seattle"},
    {"id": "3", "company": "Meta", "title": "ML Intern", "location": "NYC"},
]

# ---------------- MCP TOOLS ---------------- #

def fetch_jobs(params):
    role = (params.get("role") or "").lower()
    location = (params.get("location") or "").lower()

    return {
        "jobs": [
            j for j in JOBS
            if role in j["title"].lower()
            and location in j["location"].lower()
        ]
    }


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
        ref.update({"status": params.get("status", "updated")})
        return {"status": "updated"}

    if action == "list":
        return {
            "applications": [d.to_dict() for d in db.collection("applications").stream()]
        }

    return {"error": "invalid action"}

# ---------------- TOOL REGISTRY (MCP STANDARD) ---------------- #

TOOLS = {
    "fetch_jobs": {
        "description": "Fetch job listings filtered by role and location",
        "input_schema": {
            "role": "string",
            "location": "string"
        }
    },
    "sync_pipeline": {
        "description": "Create/update/list job applications in Firestore",
        "input_schema": {
            "action": "string",
            "job_id": "string",
            "company": "string",
            "title": "string",
            "status": "string"
        }
    }
}

# ---------------- MCP: TOOL DISCOVERY ---------------- #

@app.get("/tools")
def tools():
    return {"tools": TOOLS}

# ---------------- MCP: TOOL EXECUTION ---------------- #

@app.post("/invoke")
async def invoke(request: Request):
    body = await request.json()

    tool = body.get("name")
    params = body.get("arguments", {})

    if tool == "fetch_jobs":
        return fetch_jobs(params)

    if tool == "sync_pipeline":
        return sync_pipeline(params)

    return {"error": "unknown tool"}

# ---------------- MCP: SSE STREAM (CRITICAL FOR AGENTS) ---------------- #

@app.get("/sse")
async def sse():
    async def event_generator():
        # simple heartbeat stream for MCP clients
        while True:
            yield {
                "event": "message",
                "data": json.dumps({"status": "connected"})
            }

    return EventSourceResponse(event_generator())

# ---------------- HEALTH ---------------- #

@app.get("/")
def root():
    return {"status": "MCP Server Running"}