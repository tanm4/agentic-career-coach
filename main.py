import json
import requests
from fastapi import FastAPI, Request
from datetime import datetime
from google.cloud import firestore

app = FastAPI()

# ---------------- FIRESTORE SAFE INIT ---------------- #
try:
    db = firestore.Client()
except Exception:
    db = None

# ---------------- REAL-TIME JOB FETCH ---------------- #

def fetch_jobs(role="", location=""):
    """
    Fetch REAL jobs from Remotive API (live data)
    """
    try:
        url = "https://remotive.com/api/remote-jobs"
        res = requests.get(url, timeout=5)
        data = res.json()

        jobs = data.get("jobs", [])

        # filter live data
        filtered = []
        for j in jobs:
            title = j.get("title", "").lower()

            if role.lower() in title:
                filtered.append({
                    "title": j.get("title"),
                    "company": j.get("company_name"),
                    "location": j.get("candidate_required_location"),
                    "url": j.get("url")
                })

        return {
            "count": len(filtered),
            "jobs": filtered[:10],
            "updated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return {
            "error": "job fetch failed",
            "details": str(e)
        }

# ---------------- APPLICATION TRACKING ---------------- #

def sync_pipeline(action="", job_id="", company="", title="", status=""):
    if db is None:
        return {"error": "Firestore not available"}

    ref = db.collection("applications").document(job_id)

    if action == "create":
        ref.set({
            "job_id": job_id,
            "company": company,
            "title": title,
            "status": "saved",
            "created_at": datetime.utcnow().isoformat()
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

# ---------------- TOOLS REGISTRY ---------------- #

TOOLS = {
    "fetch_jobs": fetch_jobs,
    "sync_pipeline": sync_pipeline
}

# ---------------- MCP SERVER ---------------- #

@app.post("/mcp")
async def mcp(request: Request):
    try:
        body = await request.json()
        method = body.get("method")
        req_id = body.get("id")
        params = body.get("params", {})

        # ---------------- INIT ---------------- #
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "career-mcp",
                        "version": "2.0.0"
                    }
                }
            }

        # ---------------- TOOLS LIST ---------------- #
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": [
                        {
                            "name": "fetch_jobs",
                            "description": "Get real-time remote jobs",
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
                            "description": "Track job applications",
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

        # ---------------- TOOL CALL ---------------- #
        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments", {})

            if name not in TOOLS:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": "Unknown tool"}],
                        "isError": True
                    }
                }

            try:
                result = TOOLS[name](**args)

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(result, indent=2)
                            }
                        ],
                        "isError": False
                    }
                }

            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": str(e)}
                        ],
                        "isError": True
                    }
                }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": "Method not found"}
        }

    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32000, "message": str(e)}
        }

# ---------------- HEALTH ---------------- #
@app.get("/")
def root():
    return {
        "status": "MCP RUNNING",
        "mode": "REAL-TIME JOB API"
    }