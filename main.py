import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from google.cloud import firestore

app = FastAPI()
db = firestore.Client()

# ---------------- DATA ---------------- #

JOBS = [
    {"id": "1", "company": "Google", "title": "Software Intern", "location": "NYC"},
    {"id": "2", "company": "Amazon", "title": "SDE Intern", "location": "Seattle"},
    {"id": "3", "company": "Meta", "title": "ML Intern", "location": "NYC"},
]

# ---------------- TOOLS ---------------- #

def fetch_jobs(role="", location=""):
    role = role.lower()
    location = location.lower()

    return {
        "jobs": [
            j for j in JOBS
            if role in j["title"].lower()
            and location in j["location"].lower()
        ]
    }

def sync_pipeline(action, job_id="", company="", title="", status=""):
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
        ref.update({"status": status})
        return {"status": "updated"}

    if action == "list":
        return {
            "applications": [
                d.to_dict() for d in db.collection("applications").stream()
            ]
        }

    return {"error": "invalid action"}

TOOLS = {
    "fetch_jobs": fetch_jobs,
    "sync_pipeline": sync_pipeline
}

# ---------------- MCP ---------------- #

@app.post("/mcp")
async def mcp(request: Request):
    body = await request.json()

    method = body.get("method")
    req_id = body.get("id")
    params = body.get("params", {})

    # ---------------- initialize ---------------- #
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "career-coach-mcp",
                    "version": "1.0.0"
                }
            }
        }

    # ---------------- list tools ---------------- #
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "fetch_jobs",
                        "description": "Find internships/jobs",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "role": {"type": "string"},
                                "location": {"type": "string"}
                            }
                        }
                    },
                    {
                        "name": "sync_pipeline",
                        "description": "Track applications",
                        "inputSchema": {
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
        }

    # ---------------- call tool ---------------- #
    if method == "tools/call":
        tool = params.get("name")
        args = params.get("arguments", {})

        if tool in TOOLS:
            result = TOOLS[tool](**args)

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result)
                        }
                    ]
                }
            }

    return JSONResponse(
        status_code=400,
        content={"error": "Unknown MCP method"}
    )

# ---------------- SSE ---------------- #

@app.get("/sse")
async def sse():
    async def stream():
        while True:
            yield "data: connected\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")

# ---------------- ROOT ---------------- #

@app.get("/")
def root():
    return {"status": "MCP READY"}