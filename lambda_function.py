import os
import json
import httpx
import base64

JENKINS_URL   = os.environ["JENKINS_URL"]
JENKINS_USER  = os.environ["JENKINS_USER"]
JENKINS_TOKEN = os.environ["JENKINS_TOKEN"]

def auth():
    creds = base64.b64encode(f"{JENKINS_USER}:{JENKINS_TOKEN}".encode()).decode()
    return {"Authorization": f"Basic {creds}"}

def jenkins_get(path):
    r = httpx.get(f"{JENKINS_URL}{path}", headers=auth(), timeout=10)
    r.raise_for_status()
    return r.json()

def jenkins_text(path):
    r = httpx.get(f"{JENKINS_URL}{path}", headers=auth(), timeout=10)
    r.raise_for_status()
    return r.text

def jenkins_post(path):
    r = httpx.post(f"{JENKINS_URL}{path}", headers=auth(), timeout=10)
    r.raise_for_status()
    return r.text

TOOLS = [
    {"name": "list_jobs", "description": "List all Jenkins jobs and their status. Supports nested folders up to 3 levels deep.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "trigger_build", "description": "Trigger a Jenkins job. Requires: job_name", "inputSchema": {"type": "object", "properties": {"job_name": {"type": "string"}}, "required": ["job_name"]}},
    {"name": "abort_build", "description": "Abort a running build. Requires: job_name, build_number", "inputSchema": {"type": "object", "properties": {"job_name": {"type": "string"}, "build_number": {"type": "string"}}, "required": ["job_name", "build_number"]}},
    {"name": "get_build_status", "description": "Get result of a specific build. Requires: job_name, build_number", "inputSchema": {"type": "object", "properties": {"job_name": {"type": "string"}, "build_number": {"type": "string"}}, "required": ["job_name", "build_number"]}},
    {"name": "get_pipeline_stages", "description": "Get stage-by-stage breakdown of a pipeline build. Requires: job_name, build_number", "inputSchema": {"type": "object", "properties": {"job_name": {"type": "string"}, "build_number": {"type": "string"}}, "required": ["job_name", "build_number"]}},
    {"name": "get_console_output", "description": "Get full console log of a build. Requires: job_name, build_number", "inputSchema": {"type": "object", "properties": {"job_name": {"type": "string"}, "build_number": {"type": "string"}}, "required": ["job_name", "build_number"]}},
    {"name": "get_last_build", "description": "Get last build status for a job. Requires: job_name", "inputSchema": {"type": "object", "properties": {"job_name": {"type": "string"}}, "required": ["job_name"]}},
    {"name": "get_artifacts", "description": "List artifacts produced by a build. Requires: job_name, build_number", "inputSchema": {"type": "object", "properties": {"job_name": {"type": "string"}, "build_number": {"type": "string"}}, "required": ["job_name", "build_number"]}},
    {"name": "get_job_config", "description": "Get raw XML config of a job. Requires: job_name", "inputSchema": {"type": "object", "properties": {"job_name": {"type": "string"}}, "required": ["job_name"]}},
    {"name": "list_nodes", "description": "List all Jenkins build agents and their online/offline status.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_build_queue", "description": "Get all builds currently waiting in the queue.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "list_plugins", "description": "List all installed Jenkins plugins and their versions.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_system_info", "description": "Get Jenkins version and system information.", "inputSchema": {"type": "object", "properties": {}}},
]

def call_tool(name, args):
    if name == "list_jobs":
        return jenkins_get("/api/json?tree=jobs[name,color,url,jobs[name,color,url,jobs[name,color,url]]]")
    elif name == "trigger_build":
        return jenkins_post(f"/job/{args['job_name']}/build")
    elif name == "abort_build":
        return jenkins_post(f"/job/{args['job_name']}/{args['build_number']}/stop")
    elif name == "get_build_status":
        return jenkins_get(f"/job/{args['job_name']}/{args['build_number']}/api/json")
    elif name == "get_pipeline_stages":
        return jenkins_get(f"/job/{args['job_name']}/{args['build_number']}/wfapi/describe")
    elif name == "get_console_output":
        return jenkins_text(f"/job/{args['job_name']}/{args['build_number']}/consoleText")
    elif name == "get_last_build":
        return jenkins_get(f"/job/{args['job_name']}/lastBuild/api/json")
    elif name == "get_artifacts":
        return jenkins_get(f"/job/{args['job_name']}/{args['build_number']}/api/json?tree=artifacts[*]")
    elif name == "get_job_config":
        return jenkins_text(f"/job/{args['job_name']}/config.xml")
    elif name == "list_nodes":
        return jenkins_get("/computer/api/json?tree=computer[displayName,offline,numExecutors]")
    elif name == "get_build_queue":
        return jenkins_get("/queue/api/json")
    elif name == "list_plugins":
        return jenkins_get("/pluginManager/api/json?tree=plugins[shortName,version,active]")
    elif name == "get_system_info":
        return jenkins_get("/api/json?tree=nodeDescription,numExecutors,version")
    else:
        raise ValueError(f"Unknown tool: {name}")

def handle_jsonrpc(request):
    method = request.get("method")
    req_id = request.get("id")
    params = request.get("params", {})

    if method == "initialize":
        return {"jsonrpc": "2.0", "id": req_id, "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "jenkins-mcp", "version": "1.0.0"}
        }}
    elif method == "notifications/initialized":
        return None
    elif method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    elif method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        try:
            result = call_tool(name, args)
            content = json.dumps(result) if not isinstance(result, str) else result
            return {"jsonrpc": "2.0", "id": req_id, "result": {
                "content": [{"type": "text", "text": content}]
            }}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": req_id, "result": {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                "isError": True
            }}
    elif method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    else:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}

def handler(event, context):
    method = event.get("requestContext", {}).get("http", {}).get("method", "GET")

    if method == "GET":
        return {"statusCode": 405, "body": "Method not allowed"}

    if method == "POST":
        body = json.loads(event.get("body", "{}"))
        response = handle_jsonrpc(body)
        if response is None:
            return {"statusCode": 202, "body": ""}
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps(response)
        }

    return {"statusCode": 404, "body": "Not found"}
