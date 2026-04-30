Multi-Agent Internship Search Assistant (GCP)
Overview
This project implements a multi-agent internship search assistant using Google Cloud Platform (GCP). The system demonstrates how autonomous agents coordinate using Agent-to-Agent (A2A) communication and interact with backend tools via the Model Context Protocol (MCP).
Unlike traditional REST-based systems, this architecture enables dynamic task delegation, shared context, and stateful workflows across distributed services.
The assistant helps users:
•	Search for real internship/job opportunities
•	Track application progress
•	Maintain a centralized internship pipeline
Architecture
The system follows a Supervisor–Specialist architecture with three layers:
1. Agent Orchestration (Vertex AI Agent Builder)
•	Supervisor Agent (Lead Orchestrator)
o	User-facing (chat/API)
o	Interprets high-level goals
o	Delegates tasks to the Career Specialist via A2A communication
o	Aggregates results into final responses
•	Career Specialist Agent (Worker)
o	Not user-facing
o	Executes tasks using MCP tools
o	Handles job search and pipeline management
2. MCP Data Layer (Cloud Run)
A Python-based MCP server built with FastAPI and deployed on Cloud Run.
Key Features
•	Implements MCP over JSON-RPC
•	Supports tool discovery (tools/list)
•	Handles tool execution (tools/call)
•	Safe JSON serialization for agent compatibility
•	Designed for streaming compatibility (SSE-ready)

3. Persistence Layer (Cloud Firestore)
Cloud Firestore is used to store and manage the internship pipeline.
Collection: applications
Fields:
•	job_id
•	company
•	title
•	status (saved, applied, interviewing)
•	created_at
•	updated_at

Agent Interaction Flow
1.	User sends request to Supervisor Agent
2.	Supervisor interprets intent (e.g., "Find software internships in California")
3.	Supervisor delegates task to Career Specialist (A2A)
4.	Career Specialist calls MCP tools:
o	fetch_jobs → retrieve job listings
o	sync_pipeline → update or query Firestore
5.	Specialist returns structured results
6.	Supervisor formats and returns final response to user

MCP Tools
1. fetch_jobs
Fetches real job listings using the Adzuna API.
Parameters:
•	role (string)
•	location (string)
Features:
•	Returns up to 10 job results
•	Includes:
o	job_id
o	title
o	company
o	location
o	URL (clickable job link)

2. sync_pipeline
Manages internship application tracking using Firestore.
Supported Actions:
•	create → Save a job to pipeline
•	update → Update application status
•	list → Retrieve all tracked applications

MCP Endpoint
POST /mcp
Implements MCP protocol methods:
•	initialize
•	tools/list
•	tools/call
Example Tool Call
{
  "method": "tools/call",
  "params": {
    "name": "fetch_jobs",
    "arguments": {
      "role": "software engineer",
      "location": "California"
    }
  }
}

Tech Stack
•	Google Cloud Platform (GCP)
•	Vertex AI Agent Builder
•	Cloud Run
•	Cloud Firestore
•	FastAPI
•	Python 3.11
•	Model Context Protocol (MCP)
•	Server-Sent Events (SSE)
•	Adzuna Job Search API

Project Structure
.
├── main.py              # MCP server (FastAPI)
├── requirements.txt    # Python dependencies
├── Dockerfile          # Container configuration

Deployment
1. Build and Deploy to Cloud Run
gcloud builds submit --tag gcr.io/v-ai-city-events-finder/mcp-server
gcloud run deploy mcp-server \
  --image gcr.io/v-ai-city-events-finder/mcp-server \
  --platform managed \
  --allow-unauthenticated

2. Firestore Setup
•	Enable Firestore in GCP
•	Use Native Mode
•	Ensure proper IAM permissions

3. Environment Configuration
•	Set Adzuna credentials in main.py:
o	ADZUNA_APP_ID
o	ADZUNA_APP_KEY

Health Check
GET /
Returns:
{
  "status": "MCP RUNNING",
  "version": "8.0.0"
}

Key Design Decisions
Why Supervisor–Specialist?
•	Separates decision-making from execution
•	Enables scalable multi-agent workflows
Why MCP instead of REST?
•	Standardized tool interface for agents
•	Supports structured reasoning and tool chaining
Why Firestore?
•	Serverless, scalable state management
•	Native integration with GCP services

Future Improvements
•	Integrate additional job APIs (LinkedIn, Indeed)
•	Add recommendation system based on user preferences
•	Implement deadline reminders and notifications
•	Improve ranking and filtering of job results

Authors
Manuel Tan and Robert Storey


