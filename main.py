import json
from fastapi import FastAPI, Request
from google.cloud import firestore

app = FastAPI()

# ---------------- SAFE FIRESTORE INIT ---------------- #
try:
    db = firestore.Client()
except Exception:
    db = None  # prevents Cloud Run crash

# ---------------- MOCK DATA ---------------- #
JOBS = [
    {"id": "1", "company": "Google", "title": "Software Intern", "location": "NYC"},
    {"id": "2", "company": "Amazon", "title": "SDE Intern", "location": "Seattle"},
    {"id": "3", "company": "Meta", "title": "ML Intern", "location": "NYC"},
]

# ---------------- TOOLS ---------------- #

def fetch_jobs(role="", location=""):
    role = role.lower()
    location = location.lower()

    results = [
        j for j in JOBS
        if role in j["title"].lower()
        and location in j["location"].lower()
    ]

    return {"jobs": results}


def sync_pipeline(action="", job_id="", company="", title="", status=""):
    if db is None:
        return {"error": "Firestore not initialized"}

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
                        "version": "1.0.0"
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

        # ---------------- TOOL CALL ---------------- #
        if method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})

            if tool_name not in TOOLS:
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

            try:
                result = TOOLS[tool_name](**args)

                # 🔥 SAFE OUTPUT (NO DOUBLE JSON ENCODING)
                pretty_text = json.dumps(result, indent=2)

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": pretty_text
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
                            {"type": "text", "text": f"Tool error: {str(e)}"}
                        ],
                        "isError": True
                    }
                }

        # ---------------- UNKNOWN METHOD ---------------- #
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
    return {"status": "MCP SERVER OK"}