import os
import re
import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/banking", tags=["banking-agent"])

mongo_url = os.environ.get("MONGO_URL", "")
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ.get("DB_NAME", "agent_hub")]

# Create indices for fast queries
async def _ensure_indices():
    await db.banking_transactions.create_index([("stmt_id", 1), ("date", -1)])
    await db.banking_transactions.create_index([("stmt_id", 1), ("category", 1)])
    await db.banking_transactions.create_index([("stmt_id", 1), ("merchant", 1)])
    await db.banking_transactions.create_index([("stmt_id", 1), ("txn_type", 1)])
    await db.banking_statements.create_index("stmt_id", unique=True)

import asyncio
try:
    asyncio.get_event_loop().create_task(_ensure_indices())
except RuntimeError:
    pass


# Merchant → Category mapping
MERCHANT_CATEGORIES = {
    "zepto": "Food & Groceries", "blinkit": "Food & Groceries", "zomato": "Food & Groceries",
    "swiggy": "Food & Groceries", "bigbasket": "Food & Groceries", "dunzo": "Food & Groceries",
    "samosa": "Food & Dining", "kamat": "Food & Dining", "pinnacle f": "Food & Dining",
    "mcd": "Food & Dining", "domino": "Food & Dining", "pizza": "Food & Dining",
    "starbucks": "Food & Dining", "opera": "Food & Dining", "restaurant": "Food & Dining",
    "cafe": "Food & Dining", "kitchen": "Food & Dining", "bakery": "Food & Dining",
    "haldiram": "Food & Dining", "food": "Food & Dining",
    "razer": "Gaming", "google play": "Gaming", "googleplay": "Gaming",
    "google asia": "Gaming", "google india digital": "Gaming", "steam": "Gaming",
    "amazon": "Shopping", "flipkart": "Shopping", "myntra": "Shopping", "ajio": "Shopping",
    "meesho": "Shopping", "nykaa": "Shopping",
    "uber": "Transport", "ola": "Transport", "rapido": "Transport",
    "irctc": "Transport", "makemytrip": "Transport", "cleartrip": "Transport",
    "indigo": "Transport", "goibibo": "Transport", "metro": "Transport",
    "electricity": "Bills & Utilities", "bescom": "Bills & Utilities", "tata power": "Bills & Utilities",
    "bses": "Bills & Utilities", "broadband": "Bills & Utilities", "airtel": "Bills & Utilities",
    "jio": "Bills & Utilities", "vodafone": "Bills & Utilities", "gas": "Bills & Utilities",
    "water": "Bills & Utilities", "dth": "Bills & Utilities",
    "netflix": "Subscriptions", "spotify": "Subscriptions", "hotstar": "Subscriptions",
    "prime": "Subscriptions", "youtube": "Subscriptions", "apple": "Subscriptions",
    "pharma": "Health", "medic": "Health", "hospital": "Health", "apollo": "Health",
    "practo": "Health", "1mg": "Health", "netmeds": "Health",
    "insurance": "Insurance & Finance", "lic": "Insurance & Finance",
    "mutual fund": "Insurance & Finance", "sip": "Insurance & Finance",
    "razorpay": "Subscriptions & Services", "earlysalar": "Loan EMI",
    "school": "Education", "college": "Education", "university": "Education",
    "udemy": "Education",
    "petroleum": "Fuel", "petrol": "Fuel", "iocl": "Fuel", "bpcl": "Fuel",
    "probe": "Services",
    "american express": "Credit Card Payment", "amex": "Credit Card Payment",
}


def _categorize_merchant(particulars: str) -> tuple:
    """Extract merchant name and category from particulars."""
    p = particulars.lower().replace("\n", " ")

    # ATM
    if "atm" in p:
        atm_m = re.search(r"atm[- ]*(?:cash|cwdr?)?[/ ]*(.{0,30})", p)
        name = atm_m.group(1).strip().title()[:30] if atm_m else ""
        return f"ATM - {name}" if name else "ATM Cash", "Cash Withdrawal"

    # IMPS
    if p.startswith("imps/") or "/imps/" in p:
        m = re.search(r"imps/[^/]+/(.+?)(?:/|$)", p)
        return (m.group(1).strip().title()[:40] if m else "IMPS Transfer"), "Bank Transfer"

    # RTGS
    if "rtgs/" in p or p.startswith("rtgs"):
        m = re.search(r"rtgs/[^/]+/(.+?)(?:/|$)", p)
        return (m.group(1).strip().title()[:40] if m else "RTGS Transfer"), "Bank Transfer"

    # MOB/TPFT
    mob = re.search(r"mob/tpft/(.+?)(?:/|$)", p)
    if mob:
        return mob.group(1).strip().title(), "Person Transfer"

    # NEFT
    neft = re.search(r"neft/[^/]+/(.+?)(?:/|$)", p)
    if neft:
        merchant = neft.group(1).strip().title()[:40]
        for key, cat in MERCHANT_CATEGORIES.items():
            if key in merchant.lower():
                return merchant, cat
        return merchant, "Bank Transfer"

    # Interest
    if "int.pd:" in p or p.startswith("sb:"):
        return "Bank Interest", "Interest Income"

    # Refund / reversal
    if "refund" in p or "pur-rev" in p:
        m = re.search(r"(?:refund|pur-rev)\s*/[^/]*/(.+?)$", p)
        name = m.group(1).strip().title()[:30] if m else ("Google Play" if "google" in p else "Refund")
        return name, "Refund"

    # ACH / NACH
    ach = re.search(r"(?:ach-dr|nach)-?(.+?)[-/]", p)
    if ach:
        merchant = ach.group(1).strip().title()[:40]
        if "earlysalar" in p:
            return merchant, "Loan EMI"
        if "insurance" in p or "lic" in p:
            return merchant, "Insurance & Finance"
        return merchant, "Subscriptions & Services"

    # SI (Standing Instruction)
    if p.startswith("si-") or "/si/" in p:
        m = re.search(r"si[-/](.+?)(?:/|$)", p)
        return (m.group(1).strip().title()[:40] if m else "Standing Instruction"), "Subscriptions & Services"

    # AMEX / Credit card payments
    if "american express" in p or "amex" in p:
        return "American Express", "Credit Card Payment"

    # --- UPI patterns ---
    merchant = ""
    category = "Uncategorized"

    upi_p2m = re.search(r"upi/p2m/\d+/(.+?)(?:/|$)", p)
    if upi_p2m:
        merchant = upi_p2m.group(1).strip()

    upi_p2a = re.search(r"upi/p2a/\d+/(.+?)(?:/|$)", p)
    if upi_p2a:
        name = upi_p2a.group(1).strip()
        if re.match(r"\d{10,}", name):
            return "Self Transfer", "Self Transfer"
        merchant = name.title()
        category = "Person Transfer"

    # POS
    if not merchant:
        pos = re.search(r"pos/(.+?)/", p)
        if pos:
            merchant = pos.group(1).strip().title()
            category = "POS/Card"

    # ECOM PUR
    if not merchant:
        ecom = re.search(r"pur/(.+?)/", p)
        if ecom:
            merchant = ecom.group(1).strip().title()

    # Fallback
    if not merchant:
        parts = particulars.replace("\n", " ").split("/")
        for part in parts:
            c = part.strip()
            if c and len(c) > 2 and not c.isdigit():
                merchant = c[:50]
                break
        if not merchant:
            merchant = particulars.replace("\n", " ")[:50]

    # Category lookup
    m_lower = merchant.lower()
    for key, cat in MERCHANT_CATEGORIES.items():
        if key in m_lower:
            category = cat
            break
    if category in ("Uncategorized", "POS/Card"):
        for key, cat in MERCHANT_CATEGORIES.items():
            if key in p:
                category = cat
                break

    return merchant, category


TRANSACTION_TYPE_MAP = {
    "UPI/P2M": "UPI Merchant",
    "UPI/P2A": "UPI Transfer",
    "NEFT": "NEFT Transfer",
    "IMPS": "IMPS Transfer",
    "RTGS": "RTGS Transfer",
    "MOB/TPFT": "Mobile Transfer",
    "ECOM": "E-commerce",
    "POS": "POS/Card",
    "ATM": "ATM Withdrawal",
    "ACH-DR": "Auto Debit",
    "ACH-CR": "Auto Credit",
    "NACH": "Auto Debit",
    "SB:": "Interest",
    "VISA MERCH Refund": "Refund",
    "PUR-REV": "Purchase Reversal",
    "SALARY": "Salary",
    "FD ": "Fixed Deposit",
    "SI-": "Standing Instruction",
}


def _detect_txn_type(particulars: str) -> str:
    p = particulars.upper().replace("\n", " ")
    for prefix, txn_type in TRANSACTION_TYPE_MAP.items():
        if prefix.upper() in p:
            return txn_type
    return "Other"


def _parse_amount(val: str) -> float:
    if not val or not val.strip():
        return 0.0
    try:
        return float(val.strip().replace(",", ""))
    except ValueError:
        return 0.0


async def _parse_statement(file_bytes: bytes, password: str = "") -> dict:
    """Parse a bank statement PDF into structured transactions."""
    import pdfplumber

    transactions = []
    bank_name = ""
    account_number = ""
    account_holder = ""
    statement_period = ""
    opening_balance = 0.0

    try:
        pdf_stream = io.BytesIO(file_bytes)
        with pdfplumber.open(pdf_stream, password=password or None) as pdf:
            first_text = pdf.pages[0].extract_text() or ""
            lines = first_text.split("\n")
            if lines:
                account_holder = lines[0].strip()
            for line in lines:
                if "IFSC" in line:
                    if "UTIB" in line:
                        bank_name = "Axis Bank"
                    elif "ICIC" in line:
                        bank_name = "ICICI Bank"
                    elif "HDFC" in line:
                        bank_name = "HDFC Bank"
                    elif "SBIN" in line:
                        bank_name = "SBI"
                if "Account No" in line or "Statement of Account" in line:
                    acc = re.search(r"(\d{12,18})", line)
                    if acc:
                        account_number = acc.group(1)
                if "period" in line.lower():
                    pm = re.search(r"From\s*:\s*(\d{2}-\d{2}-\d{4})\s*To\s*:\s*(\d{2}-\d{2}-\d{4})", line)
                    if pm:
                        statement_period = f"{pm.group(1)} to {pm.group(2)}"

            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if not row or len(row) < 6:
                            continue
                        date_str = (row[0] or "").strip()
                        particulars = (row[2] or "").strip().replace("\n", " ")
                        debit_str = (row[3] or "").strip()
                        credit_str = (row[4] or "").strip()
                        balance_str = (row[5] or "").strip()

                        if "OPENING BALANCE" in particulars:
                            opening_balance = _parse_amount(balance_str)
                            continue
                        if date_str == "Tran Date":
                            continue
                        if not re.match(r"\d{2}-\d{2}-\d{4}", date_str):
                            continue

                        debit = _parse_amount(debit_str)
                        credit = _parse_amount(credit_str)
                        balance = _parse_amount(balance_str)

                        try:
                            txn_date = datetime.strptime(date_str, "%d-%m-%Y")
                        except ValueError:
                            continue

                        merchant, category = _categorize_merchant(particulars)
                        txn_type = _detect_txn_type(particulars)

                        transactions.append({
                            "date": txn_date.strftime("%Y-%m-%d"),
                            "particulars": particulars,
                            "debit": debit,
                            "credit": credit,
                            "balance": balance,
                            "merchant": merchant,
                            "category": category,
                            "txn_type": txn_type,
                            "is_debit": debit > 0,
                        })

    except Exception as e:
        logger.error(f"PDF parse error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {str(e)}")

    return {
        "bank_name": bank_name,
        "account_holder": account_holder,
        "account_number": account_number,
        "statement_period": statement_period,
        "opening_balance": opening_balance,
        "transactions": transactions,
        "total_transactions": len(transactions),
    }


@router.post("/upload")
async def upload_statement(file: UploadFile = File(...), password: str = Form("")):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_bytes = await file.read()
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    result = await _parse_statement(file_bytes, password)
    transactions = result["transactions"]

    stmt_id = str(uuid.uuid4())
    meta = {
        "stmt_id": stmt_id,
        "bank_name": result["bank_name"],
        "account_holder": result["account_holder"],
        "account_number": result["account_number"],
        "statement_period": result["statement_period"],
        "opening_balance": result["opening_balance"],
        "total_transactions": len(transactions),
        "uploaded_at": datetime.now(timezone.utc),
        "filename": file.filename,
    }
    await db.banking_statements.insert_one(meta)

    if transactions:
        docs = [{**txn, "stmt_id": stmt_id} for txn in transactions]
        await db.banking_transactions.insert_many(docs)

    return {
        "success": True,
        "stmt_id": stmt_id,
        "bank_name": result["bank_name"],
        "account_holder": result["account_holder"],
        "statement_period": result["statement_period"],
        "total_transactions": len(transactions),
        "opening_balance": result["opening_balance"],
    }


@router.get("/statements")
async def get_statements():
    cursor = db.banking_statements.find().sort("uploaded_at", -1)
    stmts = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("uploaded_at"), datetime):
            doc["uploaded_at"] = doc["uploaded_at"].isoformat()
        stmts.append(doc)
    return {"statements": stmts}


@router.get("/dashboard/{stmt_id}")
async def get_dashboard(stmt_id: str):
    meta = await db.banking_statements.find_one({"stmt_id": stmt_id})
    if not meta:
        raise HTTPException(status_code=404, detail="Statement not found")

    txns = []
    async for doc in db.banking_transactions.find({"stmt_id": stmt_id}):
        doc["_id"] = str(doc["_id"])
        txns.append(doc)

    if not txns:
        raise HTTPException(status_code=404, detail="No transactions found")

    total_debit = sum(t["debit"] for t in txns)
    total_credit = sum(t["credit"] for t in txns)
    closing_balance = txns[-1]["balance"] if txns else 0

    monthly = {}
    for t in txns:
        mk = t["date"][:7]
        if mk not in monthly:
            monthly[mk] = {"month": mk, "debit": 0, "credit": 0, "count": 0}
        monthly[mk]["debit"] += t["debit"]
        monthly[mk]["credit"] += t["credit"]
        monthly[mk]["count"] += 1

    categories = {}
    for t in txns:
        c = t["category"]
        if c not in categories:
            categories[c] = {"category": c, "debit": 0, "credit": 0, "count": 0}
        categories[c]["debit"] += t["debit"]
        categories[c]["credit"] += t["credit"]
        categories[c]["count"] += 1

    merchants = {}
    for t in txns:
        m = t["merchant"]
        if m not in merchants:
            merchants[m] = {"merchant": m, "category": t["category"], "debit": 0, "credit": 0, "count": 0}
        merchants[m]["debit"] += t["debit"]
        merchants[m]["credit"] += t["credit"]
        merchants[m]["count"] += 1

    daily_balance = {}
    for t in txns:
        daily_balance[t["date"]] = t["balance"]

    txn_types = {}
    for t in txns:
        tt = t["txn_type"]
        if tt not in txn_types:
            txn_types[tt] = {"type": tt, "debit": 0, "credit": 0, "count": 0}
        txn_types[tt]["debit"] += t["debit"]
        txn_types[tt]["credit"] += t["credit"]
        txn_types[tt]["count"] += 1

    return {
        "summary": {
            "bank_name": meta.get("bank_name", ""),
            "account_holder": meta.get("account_holder", ""),
            "account_number": meta.get("account_number", ""),
            "statement_period": meta.get("statement_period", ""),
            "opening_balance": meta.get("opening_balance", 0),
            "closing_balance": closing_balance,
            "total_debit": round(total_debit, 2),
            "total_credit": round(total_credit, 2),
            "net_flow": round(total_credit - total_debit, 2),
            "total_transactions": len(txns),
        },
        "monthly": sorted(monthly.values(), key=lambda x: x["month"]),
        "categories": sorted(categories.values(), key=lambda x: x["debit"], reverse=True),
        "merchants": sorted(merchants.values(), key=lambda x: x["debit"], reverse=True)[:50],
        "balance_trend": [{"date": d, "balance": b} for d, b in sorted(daily_balance.items())],
        "txn_types": sorted(txn_types.values(), key=lambda x: x["debit"], reverse=True),
    }


@router.get("/transactions/{stmt_id}")
async def get_transactions(
    stmt_id: str,
    category: Optional[str] = None,
    merchant: Optional[str] = None,
    txn_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    debit_only: Optional[bool] = None,
    credit_only: Optional[bool] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    sort: str = "date",
    sort_dir: int = -1,
):
    query = {"stmt_id": stmt_id}
    if category:
        query["category"] = category
    if merchant:
        query["merchant"] = {"$regex": merchant, "$options": "i"}
    if txn_type:
        query["txn_type"] = txn_type
    if date_from:
        query.setdefault("date", {})["$gte"] = date_from
    if date_to:
        query.setdefault("date", {})["$lte"] = date_to
    if debit_only:
        query["is_debit"] = True
    if credit_only:
        query["is_debit"] = False
    if search:
        query["$or"] = [
            {"particulars": {"$regex": search, "$options": "i"}},
            {"merchant": {"$regex": search, "$options": "i"}},
        ]

    total = await db.banking_transactions.count_documents(query)
    cursor = db.banking_transactions.find(query).sort(sort, sort_dir).skip(skip).limit(limit)
    txns = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        txns.append(doc)

    return {"transactions": txns, "total": total}


@router.delete("/statements/{stmt_id}")
async def delete_statement(stmt_id: str):
    await db.banking_statements.delete_one({"stmt_id": stmt_id})
    result = await db.banking_transactions.delete_many({"stmt_id": stmt_id})
    return {"success": True, "deleted_transactions": result.deleted_count}
