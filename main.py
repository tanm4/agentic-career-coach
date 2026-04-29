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
        ref.update({"status": status})
        return {"status": "updated"}

    if action == "list":
        return {
            "applications": [d.to_dict() for d in db.collection("applications").stream()]
        }

    return {"error": "invalid action"}


TOOLS = {
    "fetch_jobs": fetch_jobs,
    "sync_pipeline": sync_pipeline
}

# ---------------- MCP: TOOL DISCOVERY ---------------- #

@app.get("/tools")
def tools():
    return {
        "tools": [
            {
                "name": name,
                "description": func.__doc__ or "No description",
                "input_schema": {}
            }
            for name, func in TOOLS.items()
        ]
    }

# ---------------- MCP: JSON-RPC CORE ---------------- #

@app.post("/mcp")
async def mcp(request: Request):
    body = await request.json()

    method = body.get("method")
    params = body.get("params", {})
    tool_name = body.get("params", {}).get("name")
    args = body.get("params", {}).get("arguments", {})

    # ---- TOOL CALL ---- #
    if method == "tools/call":
        if tool_name in TOOLS:
            result = TOOLS[tool_name](**args)
            return {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "result": result
            }

        return JSONResponse(
            status_code=400,
            content={"error": "Unknown tool"}
        )

    # ---- LIST TOOLS ---- #
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {
                "tools": [
                    {"name": k} for k in TOOLS.keys()
                ]
            }
        }

    return JSONResponse(
        status_code=400,
        content={"error": "Unknown method"}
    )

# ---------------- SSE (REQUIRED FOR REAL MCP CLIENTS) ---------------- #

@app.get("/sse")
async def sse():
    async def event_stream():
        yield f"data: {json.dumps({'status': 'connected'})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

# ---------------- HEALTH ---------------- #

@app.get("/")
def root():
    return {"status": "FULL MCP SERVER RUNNING"}