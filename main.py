import os
import json
import requests
from fastapi import FastAPI, Request
from datetime import datetime
from google.cloud import firestore

app = FastAPI()

# ---------------- FIRESTORE ---------------- #
try:
    db = firestore.Client()
except Exception:
    db = None


# ---------------- ADZUNA CONFIG ---------------- #
ADZUNA_APP_ID = "723844d0"
ADZUNA_APP_KEY = "c06ef9a282048c61a5acf06a754c30a2"


# ---------------- HELPERS ---------------- #

def safe_id(url: str):
    return (url or "").replace("/", "_")


def to_text(data: dict) -> str:
    """Agent Studio SAFE serialization"""
    try:
        return json.dumps(data, indent=2)
    except Exception:
        return json.dumps({"error": "serialization_failed"})


# ---------------- REAL JOB SEARCH ---------------- #

def fetch_jobs(role="", location=""):
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        return {"error": "Missing Adzuna credentials"}


    try:
        url = (
            f"https://api.adzuna.com/v1/api/jobs/us/search/1"
            f"?app_id={ADZUNA_APP_ID}"
            f"&app_key={ADZUNA_APP_KEY}"
            f"&what={role}"
            f"&where={location}"
            f"&results_per_page=10"
            f"&content-type=application/json"
        )

        res = requests.get(url, timeout=8)
        res.raise_for_status()
        data = res.json()

        jobs = []

        for job in data.get("results", []):
            job_url = job.get("redirect_url")

            jobs.append({
                "job_id": safe_id(job_url),
                "title": job.get("title"),
                "company": job.get("company", {}).get("display_name"),
                "location": job.get("location", {}).get("display_name"),
                "url": job_url
            })

        return {
            "query": {
                "role": role,
                "location": location
            },
            "count": len(jobs),
            "jobs": jobs,
            "updated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return {
            "error": "adzuna_failed",
            "details": str(e)
        }


# ---------------- PIPELINE ---------------- #

def sync_pipeline(action="", job_id="", company="", title="", status=""):
    if db is None:
        return {"error": "Firestore not available"}

    if action != "list" and not job_id:
        return {"error": "job_id required"}

    ref = db.collection("applications").document(safe_id(job_id))

    try:
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
            ref.update({
                "status": status,
                "updated_at": datetime.utcnow().isoformat()
            })
            return {"status": "updated"}

        if action == "list":
            docs = db.collection("applications").stream()
            return {
                "applications": [d.to_dict() for d in docs]
            }

        return {"error": "invalid_action"}

    except Exception as e:
        return {
            "error": "sync_pipeline_failed",
            "details": str(e)
        }


# ---------------- TOOLS ---------------- #

TOOLS = {
    "fetch_jobs": fetch_jobs,
    "sync_pipeline": sync_pipeline
}


# ---------------- MCP ENDPOINT ---------------- #

@app.post("/mcp")
async def mcp(request: Request):
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
                    "version": "8.0.0"
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
                        "description": "Get real geo-based jobs via Adzuna",
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
                                "action": {
                                    "type": "string",
                                    "enum": ["create", "update", "list"]
                                },
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
                    "content": [
                        {
                            "type": "text",
                            "text": "Unknown tool"
                        }
                    ],
                    "isError": True
                }
            }

        result = TOOLS[name](**args)

        # ---------------- SAFE OUTPUT (CRITICAL FIX) ---------------- #
        if name == "fetch_jobs":
            text = to_text({
                "query": result.get("query"),
                "count": result.get("count"),
                "jobs": result.get("jobs", [])[:10],
                "note": "Each job includes a clickable 'url' field"
            })
        else:
            text = to_text(result)

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": text
                    }
                ],
                "isError": False
            }
        }

    # ---------------- FALLBACK ---------------- #
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {
            "code": -32601,
            "message": "Method not found"
        }
    }


# ---------------- HEALTH ---------------- #
@app.get("/")
def root():
    return {
        "status": "MCP RUNNING",
        "version": "8.0.0",
        "fixes": [
            "no json content type",
            "agent studio safe",
            "adzuna geo jobs",
            "stable links",
            "no internal errors"
        ]
    }