from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastmcp import FastMCP

import httpx
import database as db


# ============================================================
# CONFIGURATION
# ============================================================

API_BASE_URL = "http://127.0.0.1:9998"


# ============================================================
# DATABASE
# ============================================================

db.init_db()


# ============================================================
# MCP SERVER
# ============================================================

mcp = FastMCP("TimeTrack")


# ============================================================
# FASTAPI APP
# ============================================================

# MCP HTTP application
mcp_app = mcp.http_app(path="/")

app = FastAPI(
    title="TimeTrack",
    description="TimeTrack REST API + MCP server",
    lifespan=mcp_app.lifespan,
)


# ============================================================
# DATA MODEL
# ============================================================

class NewEntry(BaseModel):
    employee_name: str
    project: str
    entry_date: str
    hours: float
    description: str = ""


# ============================================================
# REST API
# ============================================================

@app.get("/api/entries")
def api_list_entries():
    return db.list_all_entries()


@app.post("/api/entries")
def api_log_entry(entry: NewEntry):
    return db.log_time(
        entry.employee_name,
        entry.project,
        entry.entry_date,
        entry.hours,
        entry.description,
    )


@app.get("/api/projects")
def api_list_projects():
    return db.list_projects()


@app.get("/api/projects/{project}/summary")
def api_project_summary(project: str):
    return db.get_project_summary(project)


@app.get("/api/timesheet/{employee_name}")
def api_get_timesheet(
    employee_name: str,
    start_date: str | None = None,
    end_date: str | None = None,
):
    return db.get_timesheet(
        employee_name,
        start_date,
        end_date,
    )


# ============================================================
# MCP TOOLS
# ============================================================

@mcp.tool
def log_time(
    employee_name: str,
    project: str,
    entry_date: str,
    hours: float,
    description: str = "",
) -> dict:
    """
    Log time using the TimeTrack REST API.
    """

    response = httpx.post(
        f"{API_BASE_URL}/api/entries",
        json={
            "employee_name": employee_name,
            "project": project,
            "entry_date": entry_date,
            "hours": hours,
            "description": description,
        },
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()


@mcp.tool
def get_timesheet(
    employee_name: str,
    start_date: str = "",
    end_date: str = "",
) -> list[dict]:
    """
    Get an employee's timesheet using the REST API.
    """

    params = {}

    if start_date:
        params["start_date"] = start_date

    if end_date:
        params["end_date"] = end_date

    response = httpx.get(
        f"{API_BASE_URL}/api/timesheet/{employee_name}",
        params=params,
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()


@mcp.tool
def get_project_summary(project: str) -> dict:
    """
    Get a project's time summary using the REST API.
    """

    response = httpx.get(
        f"{API_BASE_URL}/api/projects/{project}/summary",
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()


@mcp.tool
def list_projects() -> list[str]:
    """
    List projects using the REST API.
    """

    response = httpx.get(
        f"{API_BASE_URL}/api/projects",
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# MCP RESOURCE
# ============================================================

@mcp.resource("timesheet://projects")
def known_projects() -> list[str]:
    """
    List known projects using the REST API.
    """

    response = httpx.get(
        f"{API_BASE_URL}/api/projects",
        timeout=10.0,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# MCP PROMPT
# ============================================================

@mcp.prompt
def generate_weekly_report(
    employee_name: str,
    week_start: str,
) -> str:
    """
    Guide the AI to create a weekly hours report.
    """

    return f"""Build a weekly report for {employee_name}, starting {week_start}.

1. Call get_timesheet with:
   employee_name='{employee_name}'
   start_date='{week_start}'

2. Group the results by project.

3. Present it as:

{employee_name} -- Week of {week_start}

[Project]: [total hours for that project]h

Total: [sum of all hours]h

If no entries are found for that week,
say so plainly instead of inventing data.
"""


# ============================================================
# WEBSITE
# ============================================================

@app.get("/")
def serve_index():
    return FileResponse("static/index.html")


app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static",
)


# ============================================================
# MCP HTTP ENDPOINT
# ============================================================

app.mount(
    "/mcp",
    mcp_app,
)