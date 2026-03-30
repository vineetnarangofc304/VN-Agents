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
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field, ConfigDict, EmailStr
from typing import List, Optional
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

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

# ============== PDF Processing ==============
def process_invoice_pdf(input_path: str, output_path: str) -> bool:
    """
    Process invoice PDF:
    1. Keep only the first page
    2. Change "Page 1 of 2" to "Page 1 of 1"
    """
    try:
        reader = PdfReader(input_path)
        writer = PdfWriter()
        
        if len(reader.pages) == 0:
            return False
        
        # Get the first page
        first_page = reader.pages[0]
        writer.add_page(first_page)
        
        # Write to a temporary file first
        temp_output = output_path + ".temp"
        with open(temp_output, "wb") as f:
            writer.write(f)
        
        # Now we need to modify the text "Page 1 of 2" to "Page 1 of 1"
        # Read the temp file and do text replacement using reportlab overlay
        reader2 = PdfReader(temp_output)
        writer2 = PdfWriter()
        
        page = reader2.pages[0]
        
        # Extract text to check for page numbering
        text = page.extract_text() or ""
        
        # Create an overlay to cover and replace page numbering
        if "Page 1 of 2" in text or "page 1 of 2" in text.lower():
            # Create overlay PDF with white rectangle and new text
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            
            # Get page dimensions
            media_box = page.mediabox
            page_width = float(media_box.width)
            page_height = float(media_box.height)
            
            # Draw white rectangle at bottom to cover old page number
            # Typically page numbers are at the bottom center or bottom right
            can.setFillColorRGB(1, 1, 1)  # White
            can.rect(0, 0, page_width, 30, fill=1, stroke=0)
            
            # Add new page number
            can.setFillColorRGB(0, 0, 0)  # Black
            can.setFont("Helvetica", 10)
            can.drawCentredString(page_width / 2, 15, "Page 1 of 1")
            
            can.save()
            packet.seek(0)
            
            overlay_reader = PdfReader(packet)
            overlay_page = overlay_reader.pages[0]
            
            # Merge overlay with original page
            page.merge_page(overlay_page)
        
        writer2.add_page(page)
        
        with open(output_path, "wb") as f:
            writer2.write(f)
        
        # Clean up temp file
        os.remove(temp_output)
        
        return True
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        return False

# ============== Invoice Agent Endpoints ==============
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
async def download_all_edited(user: dict = Depends(get_current_user)):
    """Download all edited invoices as a ZIP file"""
    invoices = await db.invoices.find(
        {"user_id": user["_id"], "status": "processed"}
    ).to_list(1000)
    
    if not invoices:
        raise HTTPException(status_code=404, detail="No processed invoices found")
    
    # Create ZIP file
    zip_filename = f"invoices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = UPLOAD_DIR / zip_filename
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for invoice in invoices:
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

# ============== Agents Management ==============
@api_router.get("/agents")
async def get_agents(user: dict = Depends(get_current_user)):
    """Get all available agents"""
    # For now, return hardcoded agents - can be made dynamic later
    return {
        "agents": [
            {
                "id": "invoicing",
                "name": "Invoicing Agent",
                "description": "Upload, process, and manage Google invoices",
                "icon": "receipt",
                "status": "active"
            }
        ]
    }

# Root endpoint
@api_router.get("/")
async def root():
    return {"message": "Agent Builder API", "status": "running"}

# Include the router in the main app
app.include_router(api_router)

# CORS Configuration - must be specific origins for credentials to work
frontend_url = os.environ.get('FRONTEND_URL', 'https://agent-builder-133.preview.emergentagent.com')
cors_origins = [
    frontend_url,
    "https://agent-builder-133.preview.emergentagent.com",
    "http://localhost:3000"
]

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
