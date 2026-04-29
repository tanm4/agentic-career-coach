from fastapi import FastAPI, Request
from google.cloud import firestore

app = FastAPI()

db = firestore.Client()

# ---------------- DATA ---------------- #

JOBS = [
    {"id": "1", "company": "Google", "title": "Software Intern", "location": "NYC", "url": "https://careers.google.com"},
    {"id": "2", "company": "Amazon", "title": "SDE Intern", "location": "Seattle", "url": "https://amazon.jobs"},
    {"id": "3", "company": "Meta", "title": "ML Intern", "location": "NYC", "url": "https://metacareers.com"},
]

# ---------------- CORE LOGIC ---------------- #

def fetch_jobs(params):
    role = (params.get("role") or "").lower()
    location = (params.get("location") or "").lower()

    return {
        "jobs": [
            job for job in JOBS
            if role in job["title"].lower()
            and location in job["location"].lower()
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
            "applications": [doc.to_dict() for doc in db.collection("applications").stream()]
        }

    return {"error": "invalid action"}

# ---------------- MCP: TOOL DISCOVERY ---------------- #

@app.get("/tools")
def tools():
    return {
        "tools": [
            {
                "name": "fetch_jobs",
                "description": "Fetch job listings filtered by role and location",
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

# ---------------- MCP: TOOL EXECUTION (STANDARDIZED) ---------------- #

@app.post("/invoke")
async def invoke(request: Request):
    body = await request.json()

    tool_name = body.get("name") or body.get("tool")
    params = body.get("arguments") or body.get("params") or {}

    if tool_name == "fetch_jobs":
        return fetch_jobs(params)

    if tool_name == "sync_pipeline":
        return sync_pipeline(params)

    return {
        "error": f"Unknown tool: {tool_name}"
    }

# ---------------- HEALTH ---------------- #

@app.get("/")
def root():
    return {"status": "MCP Server Running"}