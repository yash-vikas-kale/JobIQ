from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from passlib.context import CryptContext
from pymongo import MongoClient
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import List
import os, json, re, random, string, datetime, google.generativeai as genai

# ⚙️ CONFIGURATION
load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_FROM = os.getenv("MAIL_FROM")
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "JobIQ CARE")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OTP_EXPIRE_SECONDS = int(os.getenv("OTP_EXPIRE_SECONDS", 300))

# 🚀 FASTAPI SETUP
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
app.mount("/static", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

@app.get("/")
def serve_login_page():
    path = os.path.join(FRONTEND_DIR, "login.html")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="login.html not found")
    return FileResponse(path)

# 🧠 GEMINI SETUP
genai.configure(api_key=GEMINI_API_KEY)
MODEL_NAME = "models/gemini-2.5-flash"

# 📦 DATABASE
try:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    print("✅ MongoDB Connected!")
except Exception as e:
    print("❌ MongoDB connection error:", e)

# 🔐 PASSWORD HASHING
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 📧 EMAIL CONFIG
conf = ConnectionConfig(
    MAIL_USERNAME=MAIL_USERNAME,
    MAIL_PASSWORD=MAIL_PASSWORD,
    MAIL_FROM=MAIL_FROM,
    MAIL_FROM_NAME=MAIL_FROM_NAME,
    MAIL_PORT=587,
    MAIL_SERVER="smtp.gmail.com",
    MAIL_STARTTLS=True,
    MAIL_SSL_TLS=False,
    USE_CREDENTIALS=True,
)

# 🧱 MODELS
class SignupRequest(BaseModel):
    name: str
    email: str
    password: str

class VerifyOTPRequest(BaseModel):
    email: str
    otp: str

class LoginRequest(BaseModel):
    email: str
    password: str

class QuestionRequest(BaseModel):
    cvData: dict

class ResultRequest(BaseModel):
    cvData: dict
    answers: list

# 🔢 HELPER FUNCTIONS
def generate_otp(length=6):
    return "".join(random.choices(string.digits, k=length))

# 📨 SIGNUP → SEND OTP
@app.post("/signup")
async def signup(user: SignupRequest):
    if db.users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="User already exists")

    otp = generate_otp()
    expiry = datetime.datetime.utcnow() + datetime.timedelta(seconds=OTP_EXPIRE_SECONDS)
    db.otps.update_one(
        {"email": user.email},
        {"$set": {
            "otp": otp,
            "expires_at": expiry,
            "name": user.name,
            "password": pwd_context.hash(user.password[:72])
        }},
        upsert=True
    )

    # ✉️ HTML Email Template
    html_body = f"""
    <div style="font-family: 'Poppins', sans-serif; background-color: #f6f8fa; padding: 20px;">
      <div style="max-width: 500px; background: white; margin: auto; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); padding: 25px;">
        <div style="text-align: center; border-bottom: 2px solid #468189; padding-bottom: 10px; margin-bottom: 20px;">
          <h2 style="color:#468189; margin:0;">JobIQ <span style='color:#2d5c5f;'>CARE</span></h2>
        </div>
        <p style="font-size:1rem; color:#333;">Hi <strong>{user.name}</strong>,</p>
        <p style="font-size:1rem; color:#333;">
          Your one-time verification code is:
        </p>
        <div style="background:#e8f6f5; color:#468189; text-align:center; font-size:1.8rem; font-weight:700; letter-spacing:3px; padding:15px; border-radius:10px; margin:15px 0;">
          {otp}
        </div>
        <p style="color:#555; font-size:0.95rem;">This code will expire in <strong>5 minutes</strong>.</p>
        <p style="color:#777; font-size:0.9rem;">Please do not share this code with anyone.</p>
        <hr style="border:none; border-top:1px solid #eee; margin:20px 0;">
        <p style="font-size:0.9rem; text-align:center; color:#777;">
          Thank you for joining <strong>JobIQ CARE</strong> — AI for your career success.<br>
          🌐 <a href="https://jobiqcare.ai" style="color:#468189; text-decoration:none;">jobiqcare.ai</a>
        </p>
      </div>
    </div>
    """

    message = MessageSchema(
        subject="Your JobIQ CARE Verification Code",
        recipients=[user.email],
        body=html_body,
        subtype="html",
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(message)
        return {"message": "Beautiful OTP email sent successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send OTP email: {str(e)}")


# ✅ VERIFY OTP + SEND WELCOME EMAIL
@app.post("/verify_otp")
async def verify_otp(data: VerifyOTPRequest):
    record = db.otps.find_one({"email": data.email})
    if not record:
        raise HTTPException(status_code=400, detail="No OTP found for this email")
    if record["otp"] != data.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if record["expires_at"] < datetime.datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired")

    # ✅ Save user
    db.users.insert_one({
        "name": record.get("name", ""),
        "email": data.email,
        "password": record.get("password", ""),
        "is_verified": True,
        "created_at": datetime.datetime.utcnow()
    })

    # ✅ Delete OTP record
    db.otps.delete_one({"email": data.email})

    # ✉️ Send Welcome Email
    name = record.get("name", "User")
    html_welcome = f"""
    <div style="font-family: 'Poppins', sans-serif; background-color:#f6f8fa; padding:20px;">
      <div style="max-width:550px; margin:auto; background:white; border-radius:12px; box-shadow:0 4px 15px rgba(0,0,0,0.1); padding:25px;">
        <div style="text-align:center; border-bottom:2px solid #468189; padding-bottom:10px; margin-bottom:20px;">
          <h2 style="color:#468189; margin:0;">Welcome to <span style='color:#2d5c5f;'>JobIQ CARE</span> 🎉</h2>
        </div>
        <p style="font-size:1rem; color:#333;">Hi <strong>{name}</strong>,</p>
        <p style="font-size:1rem; color:#333;">
          Congratulations! Your JobIQ CARE account has been successfully created and verified.
        </p>
        <p style="font-size:0.95rem; color:#555;">
          You’re now ready to explore personalized career recommendations powered by AI.
        </p>
        <div style="text-align:center; margin:25px 0;">
          <a href="#" style="background:#468189; color:white; padding:12px 25px; border-radius:8px; text-decoration:none; font-weight:600;">Start Exploring</a>
        </div>
        <hr style="border:none; border-top:1px solid #eee; margin:20px 0;">
        <p style="font-size:0.9rem; text-align:center; color:#777;">
          🚀 <strong>JobIQ CARE</strong> – AI for your career success.<br>
          🌐 <a href="#" style="color:#468189; text-decoration:none;">jobiqcare.ai</a>
        </p>
      </div>
    </div>
    """

    welcome_message = MessageSchema(
        subject="🎉 Welcome to JobIQ CARE!",
        recipients=[data.email],
        body=html_welcome,
        subtype="html"
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(welcome_message)
    except Exception as e:
        print("⚠️ Failed to send welcome email:", e)

    return {"message": "Account verified successfully and welcome email sent!"}


# 🔐 LOGIN
@app.post("/login")
async def login(data: LoginRequest):
    user = db.users.find_one({"email": data.email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not pwd_context.verify(data.password[:72], user["password"]):
        raise HTTPException(status_code=401, detail="Incorrect password")
    return {"message": "Login successful!", "email": data.email}

# 📄 ANALYZE CV (Gemini)
@app.post("/analyze_cv")
async def analyze_cv(request: Request):
    data = await request.json()
    text = data.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="No CV text provided")

    try:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"""
        You are a professional career assistant AI. Analyze the following CV text
        and return ONLY valid JSON (no explanations, no markdown).

        Return this structure:
        {{
          "name": "Candidate's name",
          "email": "Candidate's email",
          "total_experience_years": number,
          "top_skills": ["skill1", "skill2", "skill3", ...],
          "summary": "A short summary about the candidate"
        }}

        CV TEXT:
        {text}
        """

        response = model.generate_content(prompt)
        content = response.text.strip()

        match = re.search(r"\{.*\}", content, re.DOTALL)
        parsed = json.loads(match.group(0)) if match else {"error": "Invalid JSON", "raw": content}
        return parsed

    except Exception as e:
        print("❌ Gemini Error (CV Analysis):", e)
        raise HTTPException(status_code=500, detail=f"Gemini error: {e}")

# ❓ GENERATE QUESTIONS (Gemini)
@app.post("/generate_questions")
async def generate_questions(req: QuestionRequest):
    try:
        cv = req.cvData
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"""
        You are an intelligent career interviewer.
        Based on this candidate’s CV, generate 6 relevant and diverse interview questions.
        Make them thoughtful and personalized.

        CV DATA:
        {json.dumps(cv, indent=2)}

        Respond ONLY in JSON:
        {{
          "questions": [
            "Question 1",
            "Question 2",
            "Question 3",
            "Question 4",
            "Question 5",
            "Question 6"
          ]
        }}
        """

        response = model.generate_content(prompt)
        content = response.text.strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        parsed = json.loads(match.group(0)) if match else {"error": "Invalid JSON", "raw": content}
        return parsed

    except Exception as e:
        print("❌ Gemini Error (Question Generation):", e)
        raise HTTPException(status_code=500, detail=f"Gemini error: {e}")

# 💼 GENERATE JOB RECOMMENDATIONS (Gemini)
@app.post("/generate_result")
async def generate_result(req: ResultRequest):
    try:
        model = genai.GenerativeModel(MODEL_NAME)
        prompt = f"""
        You are an expert career advisor AI.
        Based on the following candidate CV data and their interview answers,
        recommend the top 4 most suitable jobs in JSON format only.

        Candidate CV:
        {json.dumps(req.cvData, indent=2)}

        Interview Answers:
        {json.dumps(req.answers, indent=2)}

        Return ONLY valid JSON like this:
        {{
          "recommendations": [
            {{
              "title": "Job Title",
              "company": "Company Name",
              "match_score": number (0-100),
              "reason": "Why this job fits them",
              "skills_to_learn": ["Skill1", "Skill2"],
              "salary": "Salary range in INR (e.g. 10–15 LPA)"
            }}
          ]
        }}
        """

        response = model.generate_content(prompt)
        content = response.text.strip()
        match = re.search(r"\{.*\}", content, re.DOTALL)
        parsed = json.loads(match.group(0)) if match else {"error": "Invalid JSON", "raw": content}
        return parsed

    except Exception as e:
        print("❌ Gemini Error (Result Generation):", e)
        raise HTTPException(status_code=500, detail=f"Gemini error: {e}")

#FORGET PASSWORD 
class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str

@app.post("/forgot_password")
async def forgot_password(req: ForgotPasswordRequest):
    user = db.users.find_one({"email": req.email})
    if not user:
        raise HTTPException(status_code=404, detail="No user found with this email")

    otp = generate_otp()
    expiry = datetime.datetime.utcnow() + datetime.timedelta(seconds=OTP_EXPIRE_SECONDS)
    db.otps.update_one(
        {"email": req.email},
        {"$set": {"otp": otp, "expires_at": expiry, "type": "reset"}},
        upsert=True
    )

    html_body = f"""
    <div style="font-family: 'Poppins', sans-serif; background-color: #f6f8fa; padding: 20px;">
      <div style="max-width: 500px; background: white; margin: auto; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); padding: 25px;">
        <div style="text-align: center; border-bottom: 2px solid #468189; padding-bottom: 10px; margin-bottom: 20px;">
          <h2 style="color:#468189; margin:0;">JobIQ <span style='color:#2d5c5f;'>CARE</span></h2>
        </div>
        <p>We received a password reset request for your JobIQ CARE account.</p>
        <p>Your OTP is:</p>
        <div style="background:#e8f6f5; color:#468189; text-align:center; font-size:1.8rem; font-weight:700; letter-spacing:3px; padding:15px; border-radius:10px; margin:15px 0;">
          {otp}
        </div>
        <p>This code will expire in <strong>5 minutes</strong>.</p>
      </div>
    </div>
    """

    message = MessageSchema(
        subject="JobIQ CARE Password Reset Code",
        recipients=[req.email],
        body=html_body,
        subtype="html"
    )

    try:
        fm = FastMail(conf)
        await fm.send_message(message)
        return {"message": "Password reset OTP sent successfully!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send reset OTP: {str(e)}")


@app.post("/reset_password")
async def reset_password(req: ResetPasswordRequest):
    record = db.otps.find_one({"email": req.email, "type": "reset"})
    if not record:
        raise HTTPException(status_code=400, detail="No OTP found for reset")
    if record["otp"] != req.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    if record["expires_at"] < datetime.datetime.utcnow():
        raise HTTPException(status_code=400, detail="OTP expired")

    hashed_pw = pwd_context.hash(req.new_password[:72])
    db.users.update_one({"email": req.email}, {"$set": {"password": hashed_pw}})
    db.otps.delete_one({"email": req.email})
    return {"message": "Password reset successful!"}

# SERVER START
print("🚀 JobIQ backend running")
