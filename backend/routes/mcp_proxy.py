"""
MCP Proxy — Forwards /api/mcp/* requests to the local supergateway (port 5050).
This allows ChatGPT to connect to the LinkedIn MCP server via the preview URL.
"""
import os
import logging
import asyncio
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse
import httpx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mcp", tags=["mcp"])

MCP_GATEWAY_URL = "http://localhost:5050"


@router.get("/sse")
async def mcp_sse_proxy(request: Request):
    """Proxy SSE connection to the supergateway, rewriting message URLs."""
    # Build the public base URL for message endpoint
    # Try to use the forwarded host from the request (Kubernetes ingress sets this)
    forwarded_host = request.headers.get("x-forwarded-host", "")
    scheme = request.headers.get("x-forwarded-proto", "https")
    if forwarded_host:
        public_base = f"{scheme}://{forwarded_host}/api/mcp"
    else:
        host = request.headers.get("host", "localhost:8001")
        public_base = f"{scheme}://{host}/api/mcp"

    async def event_stream():
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream("GET", f"{MCP_GATEWAY_URL}/sse") as resp:
                    async for line in resp.aiter_lines():
                        # Rewrite the message endpoint URL to point to our proxy
                        if line.startswith("data: /message?"):
                            session_part = line.split("/message?", 1)[1]
                            line = f"data: {public_base}/message?{session_part}"
                        yield f"{line}\n"
            except httpx.ConnectError:
                yield "data: {\"error\": \"MCP server not running\"}\n\n"
            except Exception as e:
                logger.error(f"MCP SSE proxy error: {e}")
                yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/message")
async def mcp_message_proxy(request: Request):
    """Proxy POST messages to the supergateway."""
    body = await request.body()
    # Forward query params (sessionId)
    query_string = str(request.url.query) if request.url.query else ""
    target_url = f"{MCP_GATEWAY_URL}/message"
    if query_string:
        target_url += f"?{query_string}"

    headers = {"Content-Type": request.headers.get("Content-Type", "application/json")}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(target_url, content=body, headers=headers)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type=resp.headers.get("Content-Type", "application/json"),
        )
    except httpx.ConnectError:
        return Response(
            content='{"error": "MCP server not running. Start it first."}',
            status_code=503,
            media_type="application/json",
        )
    except Exception as e:
        logger.error(f"MCP message proxy error: {e}")
        return Response(
            content=f'{{"error": "{str(e)}"}}',
            status_code=500,
            media_type="application/json",
        )


@router.get("/status")
async def mcp_status():
    """Check if the MCP server process is running."""
    import subprocess
    result = subprocess.run(["pgrep", "-f", "supergateway.*5050"], capture_output=True, text=True)
    running = result.returncode == 0
    return {
        "running": running,
        "gateway_url": MCP_GATEWAY_URL,
        "chatgpt_endpoint": "https://qikberry-whatsapp.preview.emergentagent.com/api/mcp/sse",
    }


@router.post("/start")
async def start_mcp_server():
    """Start the LinkedIn MCP server with supergateway. Pulls token from DB."""
    import subprocess
    import pymongo

    # Check if already running
    import subprocess as _sp
    result = _sp.run(["pgrep", "-f", "supergateway.*5050"], capture_output=True)
    if result.returncode == 0:
        return {"success": True, "detail": "MCP server already running"}

    # Get LinkedIn token from DB
    try:
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")
        mc = pymongo.MongoClient(mongo_url)
        db = mc[db_name]
        acc = db.linkedin_accounts.find_one({"name": "Abhinav Khanna"})
        token = acc.get("access_token", "") if acc else ""
        mc.close()
    except Exception as e:
        logger.error(f"Failed to get LinkedIn token from DB: {e}")
        token = ""

    if not token:
        return {"success": False, "detail": "No LinkedIn access token found. Re-authenticate via CRM Settings > LinkedIn OAuth first."}

    # Write .env for MCP server
    env_content = f"""MCP_SERVER_NAME=linkedin-mcpserver
MCP_SERVER_VERSION=1.0.0
MCP_SERVER_PORT=5050
LINKEDIN_CLIENT_ID=86sfk0agzbez8k
LINKEDIN_CLIENT_SECRET=WPL_AP1.zNsWRgELZ3xgojGi.Q76evQ==
LINKEDIN_ACCESS_TOKEN={token}
"""
    with open("/app/linkedin-mcp/.env", "w") as f:
        f.write(env_content)

    # Kill existing
    subprocess.run(["pkill", "-f", "supergateway.*5050"], capture_output=True)
    await asyncio.sleep(1)

    # Start supergateway in background
    try:
        proc = subprocess.Popen(
            ["supergateway",
             "--stdio", "npx tsx --env-file=.env src/main.ts",
             "--port", "5050",
             "--baseUrl", "http://localhost:5050",
             "--ssePath", "/sse",
             "--messagePath", "/message"],
            cwd="/app/linkedin-mcp",
            stdout=open("/tmp/mcp-gateway.log", "a"),
            stderr=subprocess.STDOUT,
        )
        await asyncio.sleep(4)
        if proc.poll() is not None:
            with open("/tmp/mcp-gateway.log") as f:
                logs = f.read()[-500:]
            return {"success": False, "detail": f"MCP server exited. Last logs: {logs}"}
        return {"success": True, "detail": f"MCP server started (PID: {proc.pid})", "pid": proc.pid,
                "sse_endpoint": "https://qikberry-whatsapp.preview.emergentagent.com/api/mcp/sse"}
    except Exception as e:
        return {"success": False, "detail": str(e)}
