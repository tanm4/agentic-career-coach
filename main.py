from fastapi import FastAPI
from google.cloud import firestore
from mcp.server.fastapi import MCPServer

app = FastAPI()
mcp = MCPServer(app)

db = firestore.Client()

# ---------------- DATA ---------------- #

JOBS = [
    {"id": "1", "company": "Google", "title": "Software Intern", "location": "NYC", "url": "https://careers.google.com"},
    {"id": "2", "company": "Amazon", "title": "SDE Intern", "location": "Seattle", "url": "https://amazon.jobs"},
    {"id": "3", "company": "Meta", "title": "ML Intern", "location": "NYC", "url": "https://metacareers.com"},
]

# ---------------- CORE LOGIC ---------------- #

def fetch_jobs(role: str = "", location: str = ""):
    role = role.lower()
    location = location.lower()

    return {
        "jobs": [
            job for job in JOBS
            if role in job["title"].lower()
            and location in job["location"].lower()
        ]
    }


def sync_pipeline(action: str, job_id: str = "", company: str = "", title: str = "", status: str = ""):
    ref = db.collection("applications").document(job_id)

    if action == "create":
        ref.set({
            "job_id": job_id,
            "company": company,
            "title": title,
            "status": "saved"
        })
        return {"status": "created"}

    if action == "update":
        ref.update({"status": status or "updated"})
        return {"status": "updated"}

    if action == "list":
        return {
            "applications": [doc.to_dict() for doc in db.collection("applications").stream()]
        }

    return {"error": "invalid action"}

# ---------------- MCP TOOLS ---------------- #

@mcp.tool()
def fetch_jobs_tool(role: str = "", location: str = ""):
    return fetch_jobs(role, location)


@mcp.tool()
def sync_pipeline_tool(action: str, job_id: str = "", company: str = "", title: str = "", status: str = ""):
    return sync_pipeline(action, job_id, company, title, status)

# IMPORTANT: enables /sse + MCP protocol
mcp.mount(app)

# ---------------- HEALTH ---------------- #

@app.get("/")
def root():
    return {"status": "MCP Server Running"}