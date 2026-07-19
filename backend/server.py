from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, UploadFile, File, Depends
from fastapi.responses import FileResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
import logging
import uuid
import bcrypt
import jwt
import secrets
import shutil
import zipfile
import io
import re
import yfinance as yf
import pandas as pd
from bs4 import BeautifulSoup
import requests
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from emergentintegrations.llm.chat import LlmChat, UserMessage
from routes.linkedin import router as linkedin_router
from routes.directory import router as directory_router
from routes.account_checker import router as checker_router
from routes.hearclear_leads import router as hearclear_leads_router
from routes.linkedin_search import router as li_search_router

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', '')
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get('DB_NAME', 'agent_hub')]

# JWT Configuration
JWT_ALGORITHM = "HS256"

def get_jwt_secret() -> str:
    return os.environ.get("JWT_SECRET", "fallback-secret-change-me")

# Create the main app
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ensure upload directories exist
UPLOAD_DIR = ROOT_DIR / "uploads"
ORIGINAL_DIR = UPLOAD_DIR / "original"
EDITED_DIR = UPLOAD_DIR / "edited"
ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)
EDITED_DIR.mkdir(parents=True, exist_ok=True)

# ============== Password Hashing ==============
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

# ============== JWT Token Management ==============
def create_access_token(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id, 
        "email": email, 
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60), 
        "type": "access"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id, 
        "exp": datetime.now(timezone.utc) + timedelta(days=7), 
        "type": "refresh"
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)

# ============== Auth Helper ==============
async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user = await db.users.find_one({"_id": ObjectId(payload["sub"])})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        user["_id"] = str(user["_id"])
        user.pop("password_hash", None)
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# ============== Models ==============
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str

class InvoiceResponse(BaseModel):
    id: str
    original_filename: str
    upload_date: str
    status: str
    original_path: Optional[str] = None
    edited_path: Optional[str] = None


# ============== Scheduler Status ==============
@api_router.get("/schedulers/status")
async def get_scheduler_status():
    """Check status of all background schedulers."""
    now_utc = datetime.now(timezone.utc)
    ist_now = now_utc + timedelta(hours=5.5)

    # Last farm
    last_farm = await db.farm_schedule_log.find_one({}, {"_id": 0}, sort=[("date", -1)])
    # Last credits scan
    last_credits = await db.credits_schedule_log.find_one({}, {"_id": 0}, sort=[("date", -1)])
    # Last LinkedIn post
    last_post = await db.linkedin_posts.find_one({"auto_generated": True}, {"_id": 0, "published_at": 1, "company": 1}, sort=[("published_at", -1)])
    # LinkedIn account schedule
    li_account = await db.linkedin_accounts.find_one({"schedule_enabled": True}, {"_id": 0, "name": 1, "last_auto_post_at": 1, "schedule_interval_hours": 1})

    return {
        "current_time_utc": now_utc.isoformat(),
        "current_time_ist": ist_now.strftime("%Y-%m-%d %H:%M IST"),
        "farm_scheduler": {
            "schedule": "Daily at 3:00 PM IST",
            "last_run": last_farm,
        },
        "credits_scanner": {
            "schedule": "Daily at 6:00 AM IST",
            "last_run": last_credits,
        },
        "linkedin_auto_poster": {
            "schedule": f"Every {li_account.get('schedule_interval_hours', '?')}h" if li_account else "disabled",
            "account": li_account.get("name") if li_account else None,
            "last_post_at": li_account.get("last_auto_post_at") if li_account else None,
            "last_published": {
                "at": last_post.get("published_at") if last_post else None,
                "company": last_post.get("company") if last_post else None,
            }
        }
    }

# ============== Auth Endpoints ==============
@api_router.post("/auth/login")
async def login(request: LoginRequest, response: Response):
    email = request.email.lower()
    user = await db.users.find_one({"email": email})
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    user_id = str(user["_id"])
    access_token = create_access_token(user_id, email)
    refresh_token = create_refresh_token(user_id)
    
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=True, samesite="none", max_age=3600, path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=True, samesite="none", max_age=604800, path="/")
    
    return {
        "id": user_id,
        "email": user["email"],
        "name": user["name"],
        "role": user.get("role", "user")
    }

@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    return {"message": "Logged out successfully"}

@api_router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    return {
        "id": user["_id"],
        "email": user["email"],
        "name": user["name"],
        "role": user.get("role", "user")
    }

# ============== Agent Auth (Simple Password) ==============
AGENT_PASSWORD = os.environ.get("AGENT_PASSWORD", "Agent@2024!")

class AgentLoginRequest(BaseModel):
    agent: str
    password: str

@api_router.post("/auth/agent-login")
async def agent_login(request: AgentLoginRequest):
    if request.password == AGENT_PASSWORD:
        return {"success": True, "agent": request.agent}
    raise HTTPException(status_code=401, detail="Invalid password")



# ============== PDF Processing ==============
def process_invoice_pdf(input_path: str, output_path: str) -> bool:
    """
    Process invoice PDF:
    1. Keep only the first page
    2. Fix "Page 1 of 2" footer to "Page 1 of 1"
    """
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()

        if len(reader.pages) == 0:
            return False

        first_page = reader.pages[0]
        page_width = float(first_page.mediabox.width)
        page_height = float(first_page.mediabox.height)

        # Create overlay to fix page number
        overlay_buf = io.BytesIO()
        c = canvas.Canvas(overlay_buf, pagesize=(page_width, page_height))
        # White rectangle over the "Page 1 of 2" area (bottom-right footer)
        # Typical invoice footer is at y=20-40, right side
        c.setFillColorRGB(1, 1, 1)  # white
        c.rect(page_width - 200, 0, 200, 45, fill=1, stroke=0)
        # Write corrected page number
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.setFont("Helvetica", 8)
        c.drawRightString(page_width - 30, 20, "Page 1 of 1")
        c.save()

        overlay_buf.seek(0)
        overlay_reader = PdfReader(overlay_buf)
        overlay_page = overlay_reader.pages[0]

        first_page.merge_page(overlay_page)
        writer.add_page(first_page)

        with open(output_path, "wb") as f:
            writer.write(f)

        return True
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        return False

# ============== Invoice Agent Endpoints ==============
@api_router.post("/invoices/reprocess-all")
async def reprocess_all_invoices(user: dict = Depends(get_current_user)):
    """Reprocess all invoices to fix any corruption issues"""
    invoices = await db.invoices.find({"user_id": user["_id"]}).to_list(1000)
    
    reprocessed = 0
    for invoice in invoices:
        if invoice.get("original_path") and os.path.exists(invoice["original_path"]):
            edited_path = invoice.get("edited_path") or str(EDITED_DIR / f"{invoice['id']}_edited.pdf")
            success = process_invoice_pdf(invoice["original_path"], edited_path)
            if success:
                reprocessed += 1
                await db.invoices.update_one(
                    {"id": invoice["id"]},
                    {"$set": {"edited_path": edited_path, "status": "processed"}}
                )
    
    return {"message": f"Reprocessed {reprocessed} invoices"}

@api_router.post("/invoices/upload")
async def upload_invoices(
    files: List[UploadFile] = File(...),
    user: dict = Depends(get_current_user)
):
    """Upload and process invoice PDFs"""
    results = []
    
    for file in files:
        if not file.filename.lower().endswith('.pdf'):
            results.append({
                "filename": file.filename,
                "status": "error",
                "message": "Only PDF files are allowed"
            })
            continue
        
        try:
            # Generate unique ID
            invoice_id = str(uuid.uuid4())
            
            # Save original file
            original_filename = f"{invoice_id}_original.pdf"
            original_path = ORIGINAL_DIR / original_filename
            
            with open(original_path, "wb") as f:
                content = await file.read()
                f.write(content)
            
            # Process the PDF
            edited_filename = f"{invoice_id}_edited.pdf"
            edited_path = EDITED_DIR / edited_filename
            
            success = process_invoice_pdf(str(original_path), str(edited_path))
            
            # Store in database
            invoice_doc = {
                "id": invoice_id,
                "original_filename": file.filename,
                "original_path": str(original_path),
                "edited_path": str(edited_path) if success else None,
                "user_id": user["_id"],
                "upload_date": datetime.now(timezone.utc).isoformat(),
                "status": "processed" if success else "failed"
            }
            
            await db.invoices.insert_one(invoice_doc)
            
            results.append({
                "id": invoice_id,
                "filename": file.filename,
                "status": "processed" if success else "failed",
                "message": "Invoice processed successfully" if success else "Failed to process invoice"
            })
            
        except Exception as e:
            logger.error(f"Error uploading invoice: {e}")
            results.append({
                "filename": file.filename,
                "status": "error",
                "message": str(e)
            })
    
    return {"results": results}

@api_router.get("/invoices")
async def get_invoices(user: dict = Depends(get_current_user)):
    """Get all invoices for the current user"""
    invoices = await db.invoices.find(
        {"user_id": user["_id"]},
        {"_id": 0}
    ).sort("upload_date", -1).to_list(1000)
    
    return {"invoices": invoices}

@api_router.get("/invoices/{invoice_id}/original")
async def download_original(invoice_id: str, user: dict = Depends(get_current_user)):
    """Download original invoice PDF"""
    invoice = await db.invoices.find_one({"id": invoice_id, "user_id": user["_id"]})
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if not invoice.get("original_path") or not os.path.exists(invoice["original_path"]):
        raise HTTPException(status_code=404, detail="Original file not found")
    
    return FileResponse(
        invoice["original_path"],
        media_type="application/pdf",
        filename=f"original_{invoice['original_filename']}"
    )

@api_router.get("/invoices/{invoice_id}/edited")
async def download_edited(invoice_id: str, user: dict = Depends(get_current_user)):
    """Download edited invoice PDF"""
    invoice = await db.invoices.find_one({"id": invoice_id, "user_id": user["_id"]})
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    if not invoice.get("edited_path") or not os.path.exists(invoice["edited_path"]):
        raise HTTPException(status_code=404, detail="Edited file not found")
    
    return FileResponse(
        invoice["edited_path"],
        media_type="application/pdf",
        filename=f"edited_{invoice['original_filename']}"
    )

@api_router.get("/invoices/download-all")
async def download_all_edited(user: dict = Depends(get_current_user), filter: str = "all"):
    """Download edited invoices as a ZIP file with date filter"""
    invoices = await db.invoices.find(
        {"user_id": user["_id"], "status": "processed"}
    ).to_list(1000)
    
    # Apply date filter
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    filtered_invoices = []
    for inv in invoices:
        inv_date = datetime.fromisoformat(inv["upload_date"].replace("Z", "+00:00"))
        if filter == "today":
            if inv_date >= today_start:
                filtered_invoices.append(inv)
        elif filter == "week":
            week_ago = today_start - timedelta(days=7)
            if inv_date >= week_ago:
                filtered_invoices.append(inv)
        elif filter == "month":
            month_ago = today_start - timedelta(days=30)
            if inv_date >= month_ago:
                filtered_invoices.append(inv)
        else:  # "all"
            filtered_invoices.append(inv)
    
    if not filtered_invoices:
        raise HTTPException(status_code=404, detail="No processed invoices found for this filter")
    
    # Create ZIP file
    filter_label = f"_{filter}" if filter != "all" else ""
    zip_filename = f"invoices{filter_label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = UPLOAD_DIR / zip_filename
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for invoice in filtered_invoices:
            if invoice.get("edited_path") and os.path.exists(invoice["edited_path"]):
                arcname = invoice['original_filename']
                zipf.write(invoice["edited_path"], arcname)
    
    return FileResponse(
        str(zip_path),
        media_type="application/zip",
        filename=zip_filename
    )

@api_router.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str, user: dict = Depends(get_current_user)):
    """Delete an invoice"""
    invoice = await db.invoices.find_one({"id": invoice_id, "user_id": user["_id"]})
    
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Delete files
    if invoice.get("original_path") and os.path.exists(invoice["original_path"]):
        os.remove(invoice["original_path"])
    if invoice.get("edited_path") and os.path.exists(invoice["edited_path"]):
        os.remove(invoice["edited_path"])
    
    # Delete from database
    await db.invoices.delete_one({"id": invoice_id})
    
    return {"message": "Invoice deleted successfully"}

# ============== Refund Agent Endpoints ==============
class RefundRequest(BaseModel):
    transaction_details: str

@api_router.post("/refund/generate")
async def generate_refund_request(request: RefundRequest, user: dict = Depends(get_current_user)):
    """Generate a human-like refund request based on transaction details"""
    try:
        llm_key = os.environ.get("EMERGENT_LLM_KEY")
        if not llm_key:
            raise HTTPException(status_code=500, detail="LLM key not configured")
        
        chat = LlmChat(
            api_key=llm_key,
            session_id=f"refund-{user['_id']}-{uuid.uuid4()}",
            system_message="""You write DETAILED refund requests for Google Play that get APPROVED by human reviewers.

STRATEGY: Since auto-approval failed, we need to convince the human reviewer. Write a compelling case.

FORMAT (follow exactly):
1. Start with the problem (1 sentence)
2. Explain what happened step by step (2-3 sentences)  
3. Mention you tried troubleshooting (1 sentence)
4. Express how this affected you (1 sentence)
5. Politely but firmly request refund (1 sentence)

TONE:
- Sound like a genuine frustrated customer
- Be specific with dates, amounts, order IDs
- Show you made effort to resolve it yourself
- Express disappointment, not anger
- Be respectful but firm
- Use natural language, not corporate speak

INCLUDE:
- Order ID (if provided)
- Exact amount paid
- Date of purchase
- What was supposed to happen vs what actually happened
- What you tried to fix it (restarted app, waited X days, etc.)
- How it affected your experience

EXAMPLE:
"I purchased the 500 Diamond Pack (Order: GPA.3385-1234-5678) on March 28th for ₹799 but the diamonds never appeared in my account. I've restarted the app multiple times, cleared cache, and even reinstalled - still nothing. It's been 3 days now and I've contacted the game support but they said the purchase shows as failed on their end even though my money was deducted. I was really looking forward to using these for an in-game event that's now over. I'd really appreciate a refund since I paid but received nothing in return."

DO NOT:
- Use bullet points
- Sound like AI or use phrases like "I hope this email finds you"
- Be rude or threatening
- Make it too formal or too casual"""
        ).with_model("openai", "gpt-4o")
        
        user_message = UserMessage(
            text=f"""Transaction details:
{request.transaction_details}

Write a detailed, compelling refund request (5-7 sentences) that will convince a human reviewer to approve the refund. Include all relevant details, show you tried to resolve it yourself, and express genuine frustration without being rude."""
        )
        
        response = await chat.send_message(user_message)
        
        # Save to history
        await db.refund_history.insert_one({
            "user_id": user["_id"],
            "transaction_details": request.transaction_details,
            "refund_request": response,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        return {"refund_request": response}
        
    except Exception as e:
        logger.error(f"Error generating refund request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/refund/history")
async def get_refund_history(user: dict = Depends(get_current_user)):
    """Get refund request history for the current user"""
    history = await db.refund_history.find(
        {"user_id": user["_id"]},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    
    return {"history": history}

# ============== Stock Market Agent Endpoints ==============

# NSE stocks under ₹100 with typically high volume (penny stocks, small/mid caps)
NSE_STOCKS_UNDER_100 = [
    # High volume penny/small cap stocks
    "YESBANK", "IDEA", "SUZLON", "JPASSOCIAT", "RPOWER", "IDFCFIRSTB", 
    "ZOMATO", "PAYTM", "IRFC", "PNB", "BANKBARODA", "UNIONBANK", "CANBK",
    "INDIANB", "CENTRALBK", "UCOBANK", "BANKINDIA", "MAHABANK", "IOB",
    "NHPC", "SJVN", "IREDA", "RECLTD", "PFC", "HUDCO",
    "SAIL", "NMDC", "NATIONALUM", "HINDCOPPER", "MOIL",
    "GMRINFRA", "IRB", "JPPOWER", "RTNPOWER", "NESCO",
    "TRIDENT", "WELSPUNIND", "RAYMOND", "ARVIND", "NIITLTD",
    "TATAPOWER", "ADANIPOWER", "TORNTPOWER", "CESC", "TATAELXSI",
    "GAIL", "ONGC", "OIL", "MRPL", "CHENNPETRO", "IOCL", "BPCL", "HPCL",
    "BHEL", "BEML", "BEL", "HAL", "COCHINSHIP", "GRSE", "MAZDA",
    "VODAFONE", "TTML", "HFCL", "STLTECH", "NELCO",
    "IBULHSGFIN", "IIFL", "MUTHOOTFIN", "MANAPPURAM", "CHOLAFIN",
    "DELTACORP", "NAZARA", "TANLA", "ROUTE", "RATEGAIN",
    "HAPPSTMNDS", "KPITTECH", "PERSISTENT", "COFORGE", "LTTS",
    "FSL", "NETWORK18", "TV18BRDCST", "DISHTV", "ZEEL", "SUNTV",
    "TATACHEM", "DEEPAKNI", "ATUL", "NAVINFLUOR", "CLEAN",
    "POLYCAB", "HAVELLS", "AMBER", "DIXON", "VOLTAS",
    "EQUITAS", "UJJIVANSFB", "SURYODAY", "ESAFSFB", "FINOPB",
    "JINDALSAW", "JINDWORLD", "WELCORP", "RATNAMANI", "ASTRAL"
]

# Combine with original for broader coverage
NSE_ALL_STOCKS = list(set(NSE_STOCKS_UNDER_100 + [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "HINDUNILVR", "SBIN", 
    "BHARTIARTL", "ITC", "KOTAKBANK", "LT", "AXISBANK", "BAJFINANCE", "ASIANPAINT",
    "MARUTI", "TITAN", "SUNPHARMA", "ULTRACEMCO", "NESTLEIND", "WIPRO", "HCLTECH",
    "POWERGRID", "NTPC", "ONGC", "TATAMOTORS", "ADANIENT", "ADANIPORTS", "COALINDIA",
    "JSWSTEEL", "TATASTEEL", "HINDALCO", "GRASIM", "TECHM", "INDUSINDBK", "BAJAJFINSV"
]))

def get_stock_data(symbol: str, period: str = "3mo"):
    """Fetch stock data from Yahoo Finance"""
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        hist = ticker.history(period=period)
        info = ticker.info
        return hist, info
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return None, None

def get_stock_news(symbol: str):
    """Fetch news for a stock from Google News"""
    try:
        url = f"https://news.google.com/rss/search?q={symbol}+NSE+stock&hl=en-IN&gl=IN&ceid=IN:en"
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'xml')
        items = soup.find_all('item')[:5]  # Get top 5 news
        
        news = []
        for item in items:
            news.append({
                "title": item.title.text if item.title else "",
                "link": item.link.text if item.link else "",
                "date": item.pubDate.text if item.pubDate else ""
            })
        return news
    except Exception as e:
        logger.error(f"Error fetching news for {symbol}: {e}")
        return []


# Endpoint to serve sample infographics
@api_router.get("/samples/infographic/{company}")
async def get_sample_infographic(company: str):
    """Serve sample infographic images"""
    file_map = {
        "hearclear": "hearclear_infographic.png",
        "fundle": "fundle_infographic.png",
        "tagnpay": "tagnpay_infographic.png"
    }
    
    filename = file_map.get(company.lower())
    if not filename:
        raise HTTPException(status_code=404, detail="Company not found")
    
    file_path = UPLOAD_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Infographic not found")
    
    return FileResponse(str(file_path), media_type="image/png")

@api_router.get("/stocks/scanner")
async def scan_stocks(user: dict = Depends(get_current_user), max_price: float = 100.0):
    """Scan for top volume NSE stocks under ₹100 - sorted by today's trading volume"""
    results = []
    
    # Format volume in lakhs/crores for display
    def format_volume(vol):
        if vol >= 10000000:  # 1 crore
            return f"{vol/10000000:.2f} Cr"
        elif vol >= 100000:  # 1 lakh
            return f"{vol/100000:.2f} L"
        else:
            return f"{vol:,}"
    
    for symbol in NSE_ALL_STOCKS:  # Scan all stocks
        try:
            hist, info = get_stock_data(symbol, period="3mo")
            if hist is None or hist.empty:
                continue
            
            # Get today's/latest volume and price
            today_volume = int(hist['Volume'].iloc[-1]) if not hist.empty else 0
            current_price = float(hist['Close'].iloc[-1]) if not hist.empty else 0
            
            # Skip if price > max_price (default ₹100)
            if current_price > max_price:
                continue
            
            # 7-day average volume for comparison
            avg_volume_7d = int(hist['Volume'].tail(7).mean()) if len(hist) >= 7 else 0
            
            # 52-week high
            week_52_high = float(hist['High'].max()) if not hist.empty else 0
            price_vs_52w = (current_price / week_52_high * 100) if week_52_high > 0 else 0
            
            # Check criteria: price < 60% of 52-week high
            meets_criteria = bool(price_vs_52w < 60)
            
            # High volume day: today's volume > 7-day average
            high_volume_day = bool(today_volume > avg_volume_7d * 1.2) if avg_volume_7d > 0 else False
            
            results.append({
                "symbol": symbol,
                "name": info.get("longName", symbol) if info else symbol,
                "current_price": round(current_price, 2),
                "week_52_high": round(week_52_high, 2),
                "price_vs_52w_pct": round(price_vs_52w, 1),
                "today_volume": today_volume,
                "today_volume_formatted": format_volume(today_volume),
                "avg_volume_7d": avg_volume_7d,
                "avg_volume_7d_formatted": format_volume(avg_volume_7d),
                "high_volume_day": high_volume_day,
                "meets_criteria": meets_criteria,
                "sector": info.get("sector", "N/A") if info else "N/A"
            })
        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            continue
    
    # Sort by today's volume (highest first) - TOP VOLUME MOVERS
    results.sort(key=lambda x: x["today_volume"], reverse=True)
    
    # Return top 50
    results = results[:50]
    
    return {
        "stocks": results,
        "scan_time": datetime.now(timezone.utc).isoformat(),
        "criteria": {
            "description": f"Top 50 NSE stocks under ₹{max_price} by volume",
            "max_price": max_price,
            "price_below_52w_pct": 60
        }
    }

@api_router.get("/stocks/{symbol}/details")
async def get_stock_details(symbol: str, user: dict = Depends(get_current_user)):
    """Get detailed info for a specific stock"""
    hist, info = get_stock_data(symbol.upper(), period="1y")
    
    if hist is None or hist.empty:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    # Get news
    news = get_stock_news(symbol.upper())
    
    # Calculate metrics
    current_price = float(hist['Close'].iloc[-1])
    week_52_high = float(hist['High'].max())
    week_52_low = float(hist['Low'].min())
    
    # Price history for chart
    price_history = []
    for date, row in hist.tail(30).iterrows():
        price_history.append({
            "date": date.strftime("%Y-%m-%d"),
            "price": round(float(row['Close']), 2),
            "volume": int(row['Volume'])
        })
    
    return {
        "symbol": symbol.upper(),
        "name": info.get("longName", symbol) if info else symbol,
        "current_price": round(current_price, 2),
        "week_52_high": round(week_52_high, 2),
        "week_52_low": round(week_52_low, 2),
        "price_vs_52w_pct": round(current_price / week_52_high * 100, 1),
        "sector": info.get("sector", "N/A") if info else "N/A",
        "industry": info.get("industry", "N/A") if info else "N/A",
        "market_cap": info.get("marketCap", 0) if info else 0,
        "pe_ratio": float(info.get("trailingPE", 0)) if info and info.get("trailingPE") else 0,
        "price_history": price_history,
        "news": news
    }

class PortfolioEntry(BaseModel):
    symbol: str
    buy_price: float
    quantity: int
    target_pct: float = 30.0  # Default 30% profit target

@api_router.post("/stocks/portfolio/add")
async def add_to_portfolio(entry: PortfolioEntry, user: dict = Depends(get_current_user)):
    """Add a stock to portfolio for tracking"""
    portfolio_entry = {
        "id": str(uuid.uuid4()),
        "user_id": user["_id"],
        "symbol": entry.symbol.upper(),
        "buy_price": entry.buy_price,
        "quantity": entry.quantity,
        "target_pct": entry.target_pct,
        "target_price": round(entry.buy_price * (1 + entry.target_pct / 100), 2),
        "status": "holding",
        "bought_at": datetime.now(timezone.utc).isoformat(),
        "sold_at": None,
        "sell_price": None,
        "profit_loss": None
    }
    
    await db.portfolio.insert_one(portfolio_entry)
    portfolio_entry.pop("_id", None)
    
    return portfolio_entry

@api_router.get("/stocks/portfolio")
async def get_portfolio(user: dict = Depends(get_current_user)):
    """Get user's portfolio with current prices and alerts"""
    portfolio = await db.portfolio.find(
        {"user_id": user["_id"]},
        {"_id": 0}
    ).sort("bought_at", -1).to_list(100)
    
    # Update with current prices and check alerts
    alerts = []
    for item in portfolio:
        if item["status"] == "holding":
            try:
                hist, _ = get_stock_data(item["symbol"], period="1d")
                if hist is not None and not hist.empty:
                    current_price = hist['Close'].iloc[-1]
                    item["current_price"] = round(current_price, 2)
                    item["current_value"] = round(current_price * item["quantity"], 2)
                    item["invested_value"] = round(item["buy_price"] * item["quantity"], 2)
                    item["profit_loss_pct"] = round((current_price - item["buy_price"]) / item["buy_price"] * 100, 2)
                    
                    # Check if target hit
                    if current_price >= item["target_price"]:
                        alerts.append({
                            "type": "sell",
                            "symbol": item["symbol"],
                            "message": f"🎯 SELL ALERT: {item['symbol']} hit target! Current: ₹{current_price:.2f}, Target: ₹{item['target_price']:.2f}, Profit: {item['profit_loss_pct']:.1f}%",
                            "current_price": current_price,
                            "target_price": item["target_price"],
                            "profit_pct": item["profit_loss_pct"]
                        })
            except Exception as e:
                logger.error(f"Error updating {item['symbol']}: {e}")
    
    return {
        "portfolio": portfolio,
        "alerts": alerts,
        "total_invested": sum(p.get("invested_value", 0) for p in portfolio if p["status"] == "holding"),
        "total_current": sum(p.get("current_value", 0) for p in portfolio if p["status"] == "holding")
    }

@api_router.post("/stocks/portfolio/{entry_id}/sell")
async def sell_from_portfolio(entry_id: str, sell_price: float, user: dict = Depends(get_current_user)):
    """Mark a position as sold"""
    entry = await db.portfolio.find_one({"id": entry_id, "user_id": user["_id"]})
    if not entry:
        raise HTTPException(status_code=404, detail="Portfolio entry not found")
    
    profit_loss = (sell_price - entry["buy_price"]) * entry["quantity"]
    profit_loss_pct = (sell_price - entry["buy_price"]) / entry["buy_price"] * 100
    
    await db.portfolio.update_one(
        {"id": entry_id},
        {"$set": {
            "status": "sold",
            "sold_at": datetime.now(timezone.utc).isoformat(),
            "sell_price": sell_price,
            "profit_loss": round(profit_loss, 2),
            "profit_loss_pct": round(profit_loss_pct, 2)
        }}
    )
    
    return {"message": "Position sold", "profit_loss": profit_loss, "profit_loss_pct": profit_loss_pct}

@api_router.delete("/stocks/portfolio/{entry_id}")
async def delete_portfolio_entry(entry_id: str, user: dict = Depends(get_current_user)):
    """Delete a portfolio entry"""
    result = await db.portfolio.delete_one({"id": entry_id, "user_id": user["_id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"message": "Entry deleted"}

# ============== Agents Management ==============
@api_router.get("/agents")
async def get_agents(user: dict = Depends(get_current_user)):
    """Get all available agents"""
    return {
        "agents": [
            {
                "id": "invoicing",
                "name": "Invoicing Agent",
                "description": "Upload, process, and manage Google invoices",
                "icon": "receipt",
                "status": "active"
            },
            {
                "id": "refund",
                "name": "Refund Agent",
                "description": "Generate refund requests for Google Play transactions",
                "icon": "refresh",
                "status": "active"
            },
            {
                "id": "stocks",
                "name": "Stock Investor",
                "description": "Track high-volume undervalued stocks with buy/sell alerts",
                "icon": "trending-up",
                "status": "active"
            },
            {
                "id": "linkedin",
                "name": "LinkedIn Agent",
                "description": "Auto-generate and publish LinkedIn posts for your companies",
                "icon": "linkedin",
                "status": "active"
            }
        ]
    }

# Health check endpoint
@api_router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Agent Builder API"}

# Root endpoint
@api_router.get("/")
async def root():
    return {"message": "Agent Builder API", "status": "running"}

# Include the router in the main app
app.include_router(api_router)
app.include_router(linkedin_router)
app.include_router(directory_router)
app.include_router(checker_router)
app.include_router(hearclear_leads_router)
app.include_router(li_search_router)

# CORS Configuration
frontend_url = os.environ.get('FRONTEND_URL', '')
backend_url = os.environ.get('REACT_APP_BACKEND_URL', '')
cors_origins = [
    "http://localhost:3000",
    "https://www.linkedin.com",
]
if frontend_url:
    cors_origins.append(frontend_url)
if backend_url:
    cors_origins.append(backend_url)
# Add production domain
cors_origins.append("https://vnagents.agenticindia.ai")

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============== Startup Events ==============
@app.on_event("startup")
async def startup_event():
    """Seed admin user and create indexes"""
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.invoices.create_index("user_id")
    await db.invoices.create_index("id", unique=True)
    
    # Seed admin user
    admin_email = os.environ.get("ADMIN_EMAIL", "vineetnarangofc@gmail.com")
    admin_password = os.environ.get("ADMIN_PASSWORD", "InvoiceAgent@2024!")
    
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        hashed = hash_password(admin_password)
        await db.users.insert_one({
            "email": admin_email,
            "password_hash": hashed,
            "name": "Vineet",
            "role": "admin",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        logger.info(f"Admin user created: {admin_email}")
    elif not verify_password(admin_password, existing["password_hash"]):
        await db.users.update_one(
            {"email": admin_email},
            {"$set": {"password_hash": hash_password(admin_password)}}
        )
        logger.info(f"Admin password updated: {admin_email}")
    
    # Write credentials to test file
    os.makedirs("/app/memory", exist_ok=True)
    with open("/app/memory/test_credentials.md", "w") as f:
        f.write("# Test Credentials\n\n")
        f.write(f"## Admin User\n")
        f.write(f"- Email: {admin_email}\n")
        f.write(f"- Password: {admin_password}\n")
        f.write(f"- Role: admin\n\n")
        f.write("## Auth Endpoints\n")
        f.write("- POST /api/auth/login\n")
        f.write("- POST /api/auth/logout\n")
        f.write("- GET /api/auth/me\n")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()


# ============== Scheduled Posts Worker ==============
import asyncio as _asyncio

async def _scheduled_posts_worker():
    """Background task that checks for and publishes scheduled posts."""
    await _asyncio.sleep(10)  # Wait for startup
    while True:
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            # Find posts that are due
            due_posts = await db.scheduled_posts.find({
                "status": "scheduled",
                "scheduled_at": {"$lte": now.isoformat()}
            }).to_list(10)

            for post in due_posts:
                try:
                    import httpx
                    from routes.linkedin import get_valid_token, LINKEDIN_POSTS_URL, LINKEDIN_API_VERSION, INFOGRAPHIC_DIR
                    access_token, person_urn = await get_valid_token(post["account_id"])

                    headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "X-Restli-Protocol-Version": "2.0.0",
                        "LinkedIn-Version": LINKEDIN_API_VERSION
                    }

                    image_urn = None
                    if post.get("image_path"):
                        image_file = Path(post["image_path"])
                        if image_file.exists():
                            init_payload = {"initializeUploadRequest": {"owner": person_urn}}
                            async with httpx.AsyncClient() as http_client:
                                init_resp = await http_client.post(
                                    "https://api.linkedin.com/rest/images?action=initializeUpload",
                                    json=init_payload, headers=headers
                                )
                            if init_resp.status_code in [200, 201]:
                                init_data = init_resp.json()
                                upload_url = init_data["value"]["uploadUrl"]
                                image_urn = init_data["value"]["image"]
                                with open(image_file, "rb") as f:
                                    image_bytes = f.read()
                                async with httpx.AsyncClient() as http_client:
                                    await http_client.put(upload_url, content=image_bytes, headers={
                                        "Authorization": f"Bearer {access_token}",
                                        "Content-Type": "application/octet-stream",
                                        "LinkedIn-Version": LINKEDIN_API_VERSION
                                    }, timeout=60.0)

                    payload = {
                        "author": person_urn,
                        "commentary": post["content"],
                        "visibility": "PUBLIC",
                        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
                        "lifecycleState": "PUBLISHED",
                        "isReshareDisabledByAuthor": False
                    }
                    if image_urn:
                        payload["content"] = {"media": {"id": image_urn}}

                    async with httpx.AsyncClient() as http_client:
                        response = await http_client.post(LINKEDIN_POSTS_URL, json=payload, headers=headers)

                    post_id = response.headers.get("x-restli-id", "")
                    if response.status_code in [200, 201]:
                        await db.scheduled_posts.update_one(
                            {"_id": post["_id"]},
                            {"$set": {"status": "published", "post_id": post_id, "published_at": now.isoformat()}}
                        )
                        logger.info(f"Scheduled post published: {post_id}")
                    else:
                        await db.scheduled_posts.update_one(
                            {"_id": post["_id"]},
                            {"$set": {"status": "failed", "error": response.text[:500]}}
                        )
                        logger.error(f"Scheduled post failed: {response.text[:200]}")

                except Exception as e:
                    logger.error(f"Scheduled post error: {e}")
                    await db.scheduled_posts.update_one(
                        {"_id": post["_id"]},
                        {"$set": {"status": "failed", "error": str(e)[:500]}}
                    )

        except Exception as e:
            logger.error(f"Scheduler worker error: {e}")

        await _asyncio.sleep(60)  # Check every minute


async def _auto_post_generator():
    """Background task that auto-generates and publishes LinkedIn posts on schedule."""
    await _asyncio.sleep(30)  # Wait for startup
    while True:
        try:
            accounts = await db.linkedin_accounts.find({"schedule_enabled": True}).to_list(20)
            now = datetime.now(timezone.utc)

            for account in accounts:
                interval = account.get("schedule_interval_hours", 6)
                last_post_at = account.get("last_auto_post_at")

                # Check if enough time has passed since last auto-post
                if last_post_at:
                    try:
                        last_dt = datetime.fromisoformat(last_post_at.replace("Z", "+00:00")) if isinstance(last_post_at, str) else last_post_at
                        hours_since = (now - last_dt).total_seconds() / 3600
                        if hours_since < interval:
                            continue
                    except Exception:
                        pass

                # Pick company from rotation
                rotation = account.get("companies_rotation", [account.get("selected_company", "fundle")])
                last_company = account.get("last_auto_company")
                if last_company and last_company in rotation:
                    idx = (rotation.index(last_company) + 1) % len(rotation)
                else:
                    idx = 0
                company = rotation[idx] if rotation else "fundle"

                logger.info(f"Auto-generating LinkedIn post for {account['name']} ({company})")

                try:
                    from routes.linkedin import COMPANY_CONTEXTS, get_valid_token, LINKEDIN_POSTS_URL, LINKEDIN_API_VERSION
                    ctx = COMPANY_CONTEXTS.get(company)
                    if not ctx:
                        continue

                    llm_key = os.environ.get("EMERGENT_LLM_KEY")
                    if not llm_key:
                        continue

                    # Pick a topic from the rotation to ensure diversity
                    import random as _rnd
                    FUNDLE_TOPIC_PILLARS = [
                        "Deep drill-down analytics: how real-time sales reporting and BI dashboards are transforming how mall operators make decisions. Talk about ADSR (Automated Daily Sales Reporting), footfall-to-conversion ratios, tenant performance benchmarking.",
                        "Customer segmentation and cohorting: how first-party data enables malls and brands to build micro-cohorts based on spend patterns, visit frequency, category affinity. Share real segmentation strategies that drive 3-5x better campaign ROI.",
                        "Campaign management across SMS, WhatsApp, Meta, RCS with intelligent fallback mechanisms. Explain omnichannel orchestration — how the right message reaches the right customer on the right channel, and what happens when one channel fails.",
                        "Loyalty point distribution, earning rules, and conversion mechanics. Break down how modern loyalty goes beyond earn-and-burn — dynamic multipliers, tier-based rewards, brand-funded coalition points, instant redemption at POS.",
                        "AI-powered personalization in retail loyalty — how machine learning models predict what a shopper wants before they know it. How Fundle.ai uses GPT-driven personalization to deliver hyper-relevant offers. Don't name competitors, focus on the AI differentiation.",
                        "Mall media monetisation and retail media networks: how physical retail spaces are becoming media channels. Digital screens, geo-targeted notifications, brand-sponsored experiences — the new revenue layer for malls.",
                        "First-party data ownership vs walled gardens: why malls and retailers must own their customer data instead of depending on Google/Meta. The strategic advantage of cross-ecosystem intelligence across malls, brands, and consumers.",
                        "The D2C-meets-offline revolution: how FundleXperiences brings digital engagement (games, rewards, bill-based activations) into physical retail. Consumer engagement that doesn't require an app download.",
                        "Mall-wide e-commerce with loyalty-integrated checkout: bridging online and offline retail. How a unified commerce platform changes the economics of mall retail.",
                        "Unit economics of retail loyalty: CAC vs LTV, repeat purchase rates, basket size uplift from loyalty members vs non-members. Data-backed insights on why loyalty infrastructure pays for itself.",
                    ]

                    # Track used topics to avoid repetition
                    recent_posts = await db.linkedin_posts.find(
                        {"company": company, "auto_generated": True},
                        {"topic_pillar": 1}
                    ).sort("published_at", -1).limit(5).to_list(5)
                    recent_topics = [p.get("topic_pillar", -1) for p in recent_posts]

                    # Pick a topic not used in last 5 posts
                    available = [i for i in range(len(FUNDLE_TOPIC_PILLARS)) if i not in recent_topics]
                    if not available:
                        available = list(range(len(FUNDLE_TOPIC_PILLARS)))
                    topic_idx = _rnd.choice(available)
                    topic = FUNDLE_TOPIC_PILLARS[topic_idx]

                    chat = LlmChat(
                        api_key=llm_key,
                        session_id=f"auto-linkedin-{company}-{uuid.uuid4()}",
                        system_message=f"""You are Abhinav Khanna, Chief Business Officer at Fundle.ai — a Retail Intelligence Platform powering malls, brands, and consumers through unified data, AI insights, and monetisation rails.

You write LinkedIn posts as a seasoned retail-tech leader with deep domain expertise. You've worked at Paytm and understand India's retail ecosystem intimately.

Company: {ctx['name']}
Tagline: {ctx['tagline']}  
Products: {', '.join(ctx['products'])}
Value Props: {', '.join(ctx['value_props'])}
Target Audience: {ctx['target_audience']}

WRITING STYLE:
- First person, founder voice — confident, insightful, never salesy
- Open with a provocative stat, counterintuitive insight, or bold claim
- Short paragraphs (1-3 lines max) for mobile readability
- Weave in real data points and industry benchmarks
- Show deep domain knowledge — you've seen this from the inside
- End with a thought-provoking question that invites comments
- 2-3 emojis max (subtle, not decorative)
- 3-5 SEO-friendly hashtags at the end
- 150-300 words — punchy, not verbose
- NEVER sound like AI. Sound like a real person sharing hard-won insights.
- NEVER use phrases like "In today's rapidly evolving" or "Did you know"
- Don't name competitors. Focus on the problem and the Fundle approach."""
                    ).with_model("openai", "gpt-4o")

                    user_msg = UserMessage(
                        text=f"""Write a LinkedIn post on this specific topic:

{topic}

Make it keyword-rich and SEO-friendly. Include specific numbers/data where possible (industry benchmarks, percentages, ROI figures).
Use these hashtags where appropriate: {ctx['hashtags']}
Write ONLY the post content. No meta commentary."""
                    )
                    content = await chat.send_message(user_msg)

                    # Generate Fundle infographic using Nano Banana with logo reference
                    import httpx
                    import base64 as _b64
                    image_path = None
                    try:
                        infographic_chat = LlmChat(
                            api_key=llm_key,
                            session_id=f"auto-infographic-{company}-{uuid.uuid4()}",
                            system_message="""You are a world-class brand designer at a top agency creating vertical infographics for Fundle.ai's LinkedIn. 

BRAND IDENTITY — FUNDLE.AI:
- Logo: The word "fundle" in rounded sans-serif. Letters "f","d","l","e" are light gray. The "u" contains a colorful curved path (red section with white fork icon, yellow section with dashed road lines, teal section). The "n" has a purple shopping bag icon. Colors: red/pink, yellow, purple, teal on gray.
- Tagline: "First-Party Retail Data Intelligence"
- Brand Colors: Deep navy blue (#1a2744), white, accent teal (#2dd4bf), warm amber/gold (#f59e0b), and the logo's signature red-yellow-purple-teal palette.

INFOGRAPHIC RULES (MANDATORY):
1. The Fundle.ai logo text "fundle" must appear prominently at the TOP of every infographic — large, clear, unmissable. Reproduce it as the word "fundle" in the brand style with the colorful "u" and "n" elements.
2. The tagline "First-Party Retail Data Intelligence" must appear directly below the logo.
3. Vertical format: 768x1376 pixels (LinkedIn-optimized).
4. Use the brand color palette consistently — navy background sections, white text, teal/amber accents.
5. Professional, data-driven, modern design. Think McKinsey meets Stripe — authoritative yet visually engaging.
6. Include real data points, percentages, stats. No placeholder or fake data.
7. Clean typography hierarchy: bold headlines, clear section breaks, scannable layout.
8. Include subtle icons or data visualizations (not clip art).
9. Bottom footer: "www.fundle.ai" and the logo again, smaller."""
                        )
                        infographic_chat.with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])

                        # Include the actual logo as reference image
                        logo_path = Path(__file__).parent / "uploads" / "fundle_logo_1.png"
                        logo_images = []
                        if logo_path.exists():
                            with open(logo_path, "rb") as f:
                                logo_b64 = _b64.b64encode(f.read()).decode()
                            logo_images = [{"data": logo_b64, "mime_type": "image/png"}]

                        infographic_prompt = f"""Create a striking vertical infographic (768x1376 pixels) for Fundle.ai.

CRITICAL: Place the Fundle.ai logo prominently at the TOP. The logo is the word "fundle" with colorful graphic elements in the "u" (red fork, yellow path, teal curve) and "n" (purple shopping bag). I've attached the actual logo — reproduce it faithfully at the top of the infographic.

Below the logo, add tagline: "First-Party Retail Data Intelligence"

TOPIC — based on this LinkedIn post:
{content[:600]}

DESIGN SPECIFICATIONS:
- 768x1376 vertical format
- Navy blue (#1a2744) primary background
- White text for headings, light gray for body
- Teal (#2dd4bf) and amber (#f59e0b) for accents, highlights, data callouts
- 3-5 key statistics or data points with large bold numbers
- Clean section layout with visual hierarchy
- Icons or mini-charts for each data point
- Footer: "www.fundle.ai" with smaller logo"""

                        msg = UserMessage(text=infographic_prompt)
                        if logo_images:
                            from emergentintegrations.llm.chat import FileContent
                            logo_file = FileContent(content_type="image/png", file_content_base64=logo_b64)
                            msg = UserMessage(text=infographic_prompt, file_contents=[logo_file])

                        text_resp, images = await infographic_chat.send_message_multimodal_response(msg)

                        if images and len(images) > 0:
                            from routes.linkedin import INFOGRAPHIC_DIR
                            image_data = _b64.b64decode(images[0]['data'])
                            filename = f"fundle_auto_{uuid.uuid4().hex[:8]}.png"
                            filepath = INFOGRAPHIC_DIR / filename
                            with open(filepath, "wb") as f:
                                f.write(image_data)
                            image_path = str(filepath)
                            logger.info(f"Auto-infographic generated: {filename} ({len(image_data)} bytes)")
                    except Exception as img_err:
                        logger.error(f"Auto-infographic generation error: {img_err}")

                    # Publish with image
                    from routes.linkedin import get_valid_token, LINKEDIN_POSTS_URL, LINKEDIN_API_VERSION
                    access_token, person_urn = await get_valid_token(account["account_id"])
                    headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                        "X-Restli-Protocol-Version": "2.0.0",
                        "LinkedIn-Version": LINKEDIN_API_VERSION
                    }

                    # Upload image if generated
                    image_urn = None
                    if image_path:
                        try:
                            init_payload = {"initializeUploadRequest": {"owner": person_urn}}
                            async with httpx.AsyncClient() as http_client:
                                init_resp = await http_client.post(
                                    "https://api.linkedin.com/rest/images?action=initializeUpload",
                                    json=init_payload, headers=headers
                                )
                            if init_resp.status_code in [200, 201]:
                                init_data = init_resp.json()
                                upload_url = init_data["value"]["uploadUrl"]
                                image_urn = init_data["value"]["image"]
                                with open(image_path, "rb") as f:
                                    image_bytes = f.read()
                                async with httpx.AsyncClient() as http_client:
                                    await http_client.put(upload_url, content=image_bytes, headers={
                                        "Authorization": f"Bearer {access_token}",
                                        "Content-Type": "application/octet-stream",
                                        "LinkedIn-Version": LINKEDIN_API_VERSION
                                    }, timeout=60.0)
                                logger.info(f"Auto-infographic uploaded to LinkedIn: {image_urn}")
                        except Exception as upload_err:
                            logger.error(f"Image upload error: {upload_err}")

                    payload = {
                        "author": person_urn,
                        "commentary": content,
                        "visibility": "PUBLIC",
                        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
                        "lifecycleState": "PUBLISHED",
                        "isReshareDisabledByAuthor": False
                    }
                    if image_urn:
                        payload["content"] = {"media": {"id": image_urn}}

                    async with httpx.AsyncClient() as http_client:
                        response = await http_client.post(LINKEDIN_POSTS_URL, json=payload, headers=headers)

                    if response.status_code in [200, 201]:
                        post_id = response.headers.get("x-restli-id", "")
                        await db.linkedin_posts.insert_one({
                            "post_id": post_id,
                            "account_id": account["account_id"],
                            "company": company,
                            "content": content,
                            "published_at": now.isoformat(),
                            "auto_generated": True,
                            "topic_pillar": topic_idx,
                            "has_image": image_urn is not None
                        })
                        await db.linkedin_accounts.update_one(
                            {"account_id": account["account_id"]},
                            {"$set": {
                                "last_auto_post_at": now.isoformat(),
                                "last_auto_company": company,
                                "last_sync_status": "auto_post_published",
                                "last_sync_at": now.isoformat()
                            }}
                        )
                        logger.info(f"Auto-post published for {account['name']} ({company}): {post_id}")
                    else:
                        logger.error(f"Auto-post failed for {account['name']}: {response.status_code} {response.text[:200]}")

                except Exception as e:
                    logger.error(f"Auto-post generation error for {account['name']}: {e}")

        except Exception as e:
            logger.error(f"Auto-post generator error: {e}")

        await _asyncio.sleep(300)  # Check every 5 minutes


@app.on_event("startup")
async def start_scheduler():
    # Ensure Playwright browsers are installed (non-blocking)
    try:
        import subprocess
        pw_path = os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/pw-browsers')
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = pw_path
        if not os.path.exists(pw_path) or not os.listdir(pw_path):
            logger.info("Installing Playwright browsers in background...")
            # Run in background thread to not block startup
            import threading
            def _install_pw():
                try:
                    subprocess.run(["python", "-m", "playwright", "install", "--with-deps", "chromium"],
                                   check=False, timeout=300, capture_output=True)
                    logger.info("Playwright browsers installed")
                except Exception as e:
                    logger.warning(f"Playwright install failed: {e}")
            threading.Thread(target=_install_pw, daemon=True).start()
        else:
            logger.info(f"Playwright browsers found at {pw_path}")
    except Exception as e:
        logger.warning(f"Playwright browser install check: {e}")

    # Ensure upload directories exist
    for d in ["uploads", "uploads/infographics"]:
        os.makedirs(ROOT_DIR / d, exist_ok=True)

    _asyncio.create_task(_scheduled_posts_worker())
    _asyncio.create_task(_auto_post_generator())
    _asyncio.create_task(_daily_farm_scheduler())
    _asyncio.create_task(_auto_credits_scanner())


async def _daily_farm_scheduler():
    """Run chip farming daily at 3 PM IST (9:30 AM UTC)."""
    await _asyncio.sleep(60)  # Wait for startup
    IST_OFFSET_HOURS = 5.5  # IST = UTC + 5:30
    TARGET_HOUR_IST = 15    # 3 PM IST
    TARGET_MINUTE_IST = 0

    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            # Convert to IST
            ist_now = now_utc + timedelta(hours=IST_OFFSET_HOURS)
            ist_hour = ist_now.hour
            ist_minute = ist_now.minute

            # Check if it's within the target window (3:00 PM - 3:05 PM IST)
            if ist_hour == TARGET_HOUR_IST and ist_minute < 5:
                # Check if we already farmed today
                today_str = ist_now.strftime("%Y-%m-%d")
                last_farm = await db.farm_schedule_log.find_one({"date": today_str})

                if not last_farm:
                    logger.info(f"Daily Farm Scheduler: Starting farm at {ist_now.strftime('%H:%M')} IST")
                    await db.farm_schedule_log.insert_one({
                        "date": today_str,
                        "started_at": now_utc.isoformat(),
                        "status": "started"
                    })

                    # Trigger farm via the same mechanism as the API endpoint
                    from routes.account_checker import run_farm_worker
                    job_id = str(uuid.uuid4())
                    run_farm_worker(job_id)
                    logger.info(f"Daily Farm Scheduler: Farm job {job_id} started")

                    await db.farm_schedule_log.update_one(
                        {"date": today_str},
                        {"$set": {"job_id": job_id, "status": "running"}}
                    )

        except Exception as e:
            logger.error(f"Daily Farm Scheduler error: {e}")

        await _asyncio.sleep(120)  # Check every 2 minutes


async def _auto_credits_scanner():
    """Auto-run credits scan for accounts missing credits, once daily at 6 AM IST."""
    await _asyncio.sleep(120)  # Wait for startup
    IST_OFFSET_HOURS = 5.5
    TARGET_HOUR_IST = 6  # 6 AM IST

    while True:
        try:
            now_utc = datetime.now(timezone.utc)
            ist_now = now_utc + timedelta(hours=IST_OFFSET_HOURS)

            if ist_now.hour == TARGET_HOUR_IST and ist_now.minute < 5:
                today_str = ist_now.strftime("%Y-%m-%d")
                last_scan = await db.credits_schedule_log.find_one({"date": today_str})

                if not last_scan:
                    # Count accounts needing credits
                    pending = await db.login_results.count_documents({
                        "status": "success",
                        "$or": [
                            {"credits": {"$exists": False}},
                            {"credits": None},
                            {"credits": "LOGIN_OK_CREDITS_UNKNOWN"}
                        ]
                    })

                    if pending > 0:
                        logger.info(f"Auto Credits Scanner: {pending} accounts need credits scan")
                        await db.credits_schedule_log.insert_one({
                            "date": today_str,
                            "started_at": now_utc.isoformat(),
                            "pending": pending
                        })

                        from routes.account_checker import run_credits_worker
                        job_id = str(uuid.uuid4())
                        run_credits_worker(job_id)
                        logger.info(f"Auto Credits Scanner: Job {job_id} started for {pending} accounts")

        except Exception as e:
            logger.error(f"Auto Credits Scanner error: {e}")

        await _asyncio.sleep(120)  # Check every 2 minutes
