import os
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

# ---------------- ADZUNA CONFIG ---------------- #
ADZUNA_APP_ID = "723844d0"
ADZUNA_APP_KEY = "c06ef9a282048c61a5acf06a754c30a2"

# ---------------- NORMALIZATION ---------------- #

def normalize(text: str):
    return (text or "").lower().strip()


# ---------------- GEO JOB SEARCH (REAL) ---------------- #

def fetch_jobs(role="", location="new york"):
    """
    Real geo-based job search using Adzuna API
    """

    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        return {
            "error": "Missing ADZUNA_APP_ID or ADZUNA_APP_KEY"
        }

    role = role or "software engineer"
    location = location or "new york"

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

        res = requests.get(url, timeout=10)
        data = res.json()

        results = []

        for job in data.get("results", []):
            results.append({
                "title": job.get("title"),
                "company": job.get("company", {}).get("display_name"),
                "location": job.get("location", {}).get("display_name"),
                "salary_min": job.get("salary_min"),
                "salary_max": job.get("salary_max"),
                "url": job.get("redirect_url")
            })

        return {
            "query": {
                "role": role,
                "location": location
            },
            "count": len(results),
            "jobs": results,
            "updated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        return {
            "error": "adzuna_fetch_failed",
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

        # ---------------- INITIALIZE ---------------- #
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "career-mcp",
                        "version": "5.0.0"
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
                            "description": "Find real location-based jobs using Adzuna API",
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
                        "content": [{
                            "type": "text",
                            "text": "Unknown tool"
                        }],
                        "isError": True
                    }
                }

            result = TOOLS[name](**args)

            # ---------------- AGENT-STUDIO SAFE OUTPUT ---------------- #
            if name == "fetch_jobs":
                jobs = result.get("jobs", [])

                if not jobs:
                    text = f"""
No exact matches found for:
Role: {result.get('query', {}).get('role')}
Location: {result.get('query', {}).get('location')}

Try broadening your search (e.g., "software", "engineer", or nearby cities).
"""
                else:
                    text = f"""
Found {len(jobs)} real jobs via Adzuna:

""" + "\n".join(
    f"- {j['title']} at {j['company']} ({j['location']})"
    for j in jobs[:10]
)

                response_text = text

            else:
                response_text = json.dumps(result, indent=2)

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": response_text
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


# ---------------- HEALTH ---------------- #
@app.get("/")
def root():
    return {
        "status": "MCP RUNNING",
        "version": "5.0.0",
        "data_source": "Adzuna (real geo jobs)"
    }