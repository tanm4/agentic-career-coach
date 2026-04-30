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

# ---------------- LOCATION HELPERS ---------------- #

def normalize(text: str):
    return (text or "").lower().strip()


US_CITY_ALIASES = {
    "nyc": "new york",
    "new york": "new york",
    "new york city": "new york",
    "sf": "san francisco",
    "san francisco": "san francisco",
    "la": "los angeles",
    "los angeles": "los angeles",
    "seattle": "seattle",
    "austin": "austin",
    "chicago": "chicago",
}


def match_location(job_location: str, user_location: str):
    if not user_location:
        return True

    job_loc = normalize(job_location)
    user_loc = normalize(user_location)

    user_loc = US_CITY_ALIASES.get(user_loc, user_loc)

    # broad matches from API
    if "worldwide" in job_loc or "anywhere" in job_loc:
        return True

    if "usa" in job_loc and "usa" in user_loc:
        return True

    return user_loc in job_loc or job_loc in user_loc


# ---------------- REAL-TIME JOB TOOL ---------------- #

def fetch_jobs(role="", location=""):
    try:
        res = requests.get(
            "https://remotive.com/api/remote-jobs",
            timeout=8
        )
        data = res.json()

        jobs = data.get("jobs", [])

        role = normalize(role)
        location = normalize(location)

        results = []

        for job in jobs:
            title = normalize(job.get("title", ""))
            job_location = job.get("candidate_required_location", "")

            role_ok = role in title if role else True
            location_ok = match_location(job_location, location)

            if role_ok and location_ok:
                results.append({
                    "title": job.get("title"),
                    "company": job.get("company_name"),
                    "location": job_location,
                    "url": job.get("url")
                })

        return {
            "count": len(results),
            "filters": {
                "role": role or "any",
                "location": location or "any"
            },
            "jobs": results[:10],
            "updated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return {
            "error": "job_fetch_failed",
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


# ---------------- TOOLS ---------------- #

TOOLS = {
    "fetch_jobs": fetch_jobs,
    "sync_pipeline": sync_pipeline
}


# ---------------- MCP ENDPOINT ---------------- #

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
                        "version": "3.0.0"
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
                        "content": [
                            {"type": "text", "text": "Unknown tool"}
                        ],
                        "isError": True
                    }
                }

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

        # ---------------- FALLBACK ---------------- #
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": "Method not found"
            }
        }

    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32000,
                "message": str(e)
            }
        }


# ---------------- HEALTH CHECK ---------------- #
@app.get("/")
def root():
    return {
        "status": "MCP RUNNING",
        "version": "3.0.0",
        "mode": "REAL-TIME JOB SEARCH ENABLED"
    }