import os
import re
from flask import Flask, request, jsonify, session, redirect, render_template, url_for
from flask_cors import CORS
from datetime import datetime
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from googletrans import Translator
from difflib import get_close_matches ,  SequenceMatcher
from deep_translator import GoogleTranslator

app = Flask(__name__)
CORS(app)  # ✅ Allow frontend to call Flask API
     app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-me") = "supersecretkey"  # required for login sessions
translator = Translator()

def fuzzy_match(user_msg, keywords, cutoff=0.6):
    matches = get_close_matches(user_msg, keywords, n=1, cutoff=cutoff)
    return bool(matches)

# ---------------- Helper Functions ----------------
def is_tamil(text):
    """Check if text contains Tamil characters"""
    return any("\u0B80" <= ch <= "\u0BFF" for ch in text)

def calculate_deadline(date_str):
    """
    Calculate the number of days left until the given date.
    date_str format: '24 October 2025'
    """
    try:
        exam_date = datetime.strptime(date_str, "%d %B %Y")
        today = datetime.today()
        days_left = (exam_date - today).days
        if days_left > 0:
            return f"🗓 Days left: {days_left} day{'s' if days_left > 1 else ''}"
        elif days_left == 0:
            return "🗓 The exam is today!"
        else:
            return "⚠ The exam date has passed."
    except ValueError:
        return "⚠ Invalid date format. Use DD Month YYYY (e.g., 24 October 2025)."

def translate_reply_deep(reply, user_msg):
    """Translate reply to Tamil using deep-translator."""
    if any("\u0B80" <= ch <= "\u0BFF" for ch in user_msg):
        try:
            clean_text = re.sub(r'<[^>]+>', '', reply)
            return GoogleTranslator(source='auto', target='ta').translate(clean_text)
        except Exception as e:
            print("Translation error:", e)
            return reply
    return reply


# ---------------- FAQ Data ----------------
courses = {
    "engineering": {
        "eee": {"1st year": "₹50,000", "2nd year": "₹45,000", "3rd year": "₹45,000", "4th year": "₹45,000"},
        "ece": {"1st year": "₹55,000", "2nd year": "₹50,000", "3rd year": "₹50,000", "4th year": "₹50,000"},
        "cse": {"1st year": "₹60,000", "2nd year": "₹55,000", "3rd year": "₹55,000", "4th year": "₹55,000"},
        "civil": {"1st year": "₹48,000", "2nd year": "₹45,000", "3rd year": "₹45,000", "4th year": "₹45,000"},
        "mechanical": {"1st year": "₹52,000", "2nd year": "₹48,000", "3rd year": "₹48,000", "4th year": "₹48,000"}
    },
    "arts": {
        "bcom": {"1st year": "₹20,000", "2nd year": "₹18,000", "3rd year": "₹18,000"},
        "bba": {"1st year": "₹22,000", "2nd year": "₹20,000", "3rd year": "₹20,000"},
        "bsc tamil": {"1st year": "₹15,000", "2nd year": "₹15,000", "3rd year": "₹15,000"},
        "bsc english": {"1st year": "₹15,000", "2nd year": "₹15,000", "3rd year": "₹15,000"},
        "ba history": {"1st year": "₹18,000", "2nd year": "₹17,000", "3rd year": "₹17,000"}
    },
    "science": {
        "bsc cs": {"1st year": "₹25,000", "2nd year": "₹22,000", "3rd year": "₹22,000"},
        "bsc ca": {"1st year": "₹27,000", "2nd year": "₹24,000", "3rd year": "₹24,000"},
        "bsc physics": {"1st year": "₹23,000", "2nd year": "₹21,000", "3rd year": "₹21,000"},
        "bsc chemistry": {"1st year": "₹23,000", "2nd year": "₹21,000", "3rd year": "₹21,000"},
        "bsc maths": {"1st year": "₹20,000", "2nd year": "₹19,000", "3rd year": "₹19,000"}
    },
    "medical": {
        "mbbs": {"1st year": "₹3,50,000", "2nd year": "₹3,25,000", "3rd year": "₹3,25,000", "4th year": "₹3,25,000"},
        "bds": {"1st year": "₹2,00,000", "2nd year": "₹1,80,000", "3rd year": "₹1,80,000", "4th year": "₹1,80,000"},
        "bpharm": {"1st year": "₹1,50,000", "2nd year": "₹1,25,000", "3rd year": "₹1,25,000", "4th year": "₹1,25,000"},
        "bsc nursing": {"1st year": "₹90,000", "2nd year": "₹80,000", "3rd year": "₹80,000", "4th year": "₹80,000"}
    },
    "law": {
        "llb": {"1st year": "₹70,000", "2nd year": "₹65,000", "3rd year": "₹65,000"},
        "ba llb": {"1st year": "₹85,000", "2nd year": "₹80,000", "3rd year": "₹80,000", "4th year": "₹80,000", "5th year": "₹80,000"},
        "bba llb": {"1st year": "₹90,000", "2nd year": "₹85,000", "3rd year": "₹85,000", "4th year": "₹85,000", "5th year": "₹85,000"}
    },
    "architecture": {
        "barch": {"1st year": "₹1,25,000", "2nd year": "₹1,10,000", "3rd year": "₹1,10,000", "4th year": "₹1,10,000", "5th year": "₹1,10,000"},
        "m.arch": {"1st year": "₹1,50,000", "2nd year": "₹1,25,000"}
    }
}
# Main chat handling function
def handle_user_message(user_msg):
    user_msg_lower = user_msg.lower().strip()
    reply = None 
    # Check if user is asking about fees
    if re.search(r"\b(fee|fees|amount|rupees|cost)\b", user_msg_lower):
        found_course = None
        for course in courses:
            if course in user_msg_lower:
                found_course = course
                break

        if found_course:
            fee_info = courses.get(found_course)
            if fee_info:
                reply = f"💰 Fees for {found_course.upper()}:\n"
                for year, amount in fee_info.items():
                    reply += f"{year}: {amount}\n"
            else:
                reply = "❌ Sorry, no fee information found for that course."
        else:
            reply = "❌ Sorry, I didn’t understand. Please specify a correct course. Example: 'fees for CSE' or 'fees for MBBS'."


# ----------------- Intents Keywords -----------------
intents = {
    "dress_code": [
        "dress code", "uniform rules", "college attire", "what to wear", "clothing regulations",
        "உடை விதிகள்", "யூனிபாம் விதிகள்", "கல்லூரி உடை", "என்ன அணிய வேண்டும்", "அணிவது எப்படி"
    ],
    "college_timing": [
        "college timing", "class hours", "schedule", "lecture timings",
        "கல்லூரி நேரம்", "மாணவர் நேரம்", "வகுப்பு நேரம்", "பாடநெறி நேரம்"
    ],
    "admission_eligibility": [
        "eligibility criteria", "minimum marks required", "who can apply", "admission eligibility",
        "விண்ணப்பதாரர்கள் யார்", "குறைந்த மதிப்பெண்கள்", "தகுதி நிபந்தனைகள்", "செல்லும் நிபந்தனை"
    ],
    "admission_process": [
        "how to apply", "documents required", "application procedure", "admission process",
        "விண்ணப்பிப்பது எப்படி", "தேவையான ஆவணங்கள்", "விண்ணப்ப செயல்முறை", "சேர்க்கை செயல்முறை"
    ],
    "fees": [
        "fees", "fee", "tuition", "course fee", "கட்டணம்", "படிப்பின் கட்டணம்", "பாடநெறி கட்டணம்"
    ],
    "hostel": [
        "hostel", "boys hostel", "girls hostel", "accommodation", "dormitory",
        "ஹோஸ்டல்", "ஆண் ஹோஸ்டல்", "பெண் ஹோஸ்டல்", "வசதி"
    ],
    "courses": [

        "courses", "arts", "science", "engineering", "medical", "law", "mba",
        "பாடநெறிகள்", "கலை", "அறிவு விஞ்ஞானம்", "பொறியியல்", "மருத்துவம்", "நீதியியல்", "மேலாண்மை"
    ]
}


college_timings = {
    "mca": {
        "1st year": "⏰ MCA 1st Year: Mon-Fri 10:00 AM - 5:00 PM, Lunch 1:00 PM - 2:00 PM; Sat 10:00 AM - 2:00 PM; Sun Holiday",
        "2nd year": "⏰ MCA 2nd Year: Mon-Fri 10:00 AM - 5:00 PM, Lunch 1:00 PM - 2:00 PM; Sat 10:00 AM - 2:00 PM; Sun Holiday",
    },
    "btech": {
        "1st year": "⏰ B.Tech 1st Year: Mon-Fri 9:00 AM - 4:00 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:00 AM - 1:00 PM; Sun Holiday",
        "2nd year": "⏰ B.Tech 2nd Year: Mon-Fri 9:30 AM - 4:30 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:30 AM - 1:30 PM; Sun Holiday",
        "3rd year": "⏰ B.Tech 3rd Year: Mon-Fri 9:30 AM - 4:30 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:30 AM - 1:30 PM; Sun Holiday",
        "4th year": "⏰ B.Tech 4th Year: Mon-Fri 9:30 AM - 4:30 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:30 AM - 1:30 PM; Sun Holiday"
    },
    "mba": {
        "1st year": "⏰ MBA 1st Year: Mon-Fri 9:30 AM - 4:30 PM, Lunch 1:00 PM - 2:00 PM; Sat 10:00 AM - 2:00 PM; Sun Holiday",
        "2nd year": "⏰ MBA 2nd Year: Mon-Fri 9:30 AM - 4:30 PM, Lunch 1:00 PM - 2:00 PM; Sat 10:00 AM - 2:00 PM; Sun Holiday",
    },
    "law": {
        "1st year": "⏰ Law 1st Year: Mon-Fri 9:00 AM - 4:00 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:00 AM - 1:00 PM; Sun Holiday",
        "2nd year": "⏰ Law 2nd Year: Mon-Fri 9:00 AM - 4:00 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:00 AM - 1:00 PM; Sun Holiday",
        "3rd year": "⏰ Law 3rd Year: Mon-Fri 9:00 AM - 4:00 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:00 AM - 1:00 PM; Sun Holiday",
        "4th year": "⏰ Law 4th Year: Mon-Fri 9:00 AM - 4:00 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:00 AM - 1:00 PM; Sun Holiday",
        "5th year": "⏰ Law 5th Year: Mon-Fri 9:00 AM - 4:00 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:00 AM - 1:00 PM; Sun Holiday",
    },
    "arts": {
        "bcom": "⏰ B.Com: Mon-Fri 9:30 AM - 4:30 PM, Lunch 1:00 PM - 2:00 PM; Sat 9:30 AM - 1:30 PM; Sun Holiday",
        "bba": "⏰ BBA: Mon-Fri 9:30 AM - 4:30 PM, Lunch 1:00 PM - 2:00 PM; Sat 9:30 AM - 1:30 PM; Sun Holiday",
        "bsc tamil": "⏰ B.Sc Tamil: Mon-Fri 9:30 AM - 4:30 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:30 AM - 1:30 PM; Sun Holiday",
        "bsc english": "⏰ B.Sc English: Mon-Fri 9:30 AM - 4:30 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:30 AM - 1:30 PM; Sun Holiday",
        "ba history": "⏰ BA History: Mon-Fri 9:30 AM - 4:30 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:30 AM - 1:30 PM; Sun Holiday",
    },
    "science": {
        "bsc cs": "⏰ B.Sc CS: Mon-Fri 9:30 AM - 4:30 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:30 AM - 1:30 PM; Sun Holiday",
        "bsc ca": "⏰ B.Sc CA: Mon-Fri 9:30 AM - 4:30 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:30 AM - 1:30 PM; Sun Holiday",
        "bsc physics": "⏰ B.Sc Physics: Mon-Fri 9:30 AM - 4:30 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:30 AM - 1:30 PM; Sun Holiday",
        "bsc chemistry": "⏰ B.Sc Chemistry: Mon-Fri 9:30 AM - 4:30 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:30 AM - 1:30 PM; Sun Holiday",
        "bsc maths": "⏰ B.Sc Maths: Mon-Fri 9:30 AM - 4:30 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:30 AM - 1:30 PM; Sun Holiday",
    },
    "medical": {
        "mbbs": "⏰ MBBS: Mon-Fri 8:00 AM - 3:30 PM, Lunch 12:30 PM - 1:30 PM; Sat 8:00 AM - 1:00 PM; Sun Holiday",
        "bds": "⏰ BDS: Mon-Fri 8:00 AM - 3:30 PM, Lunch 12:30 PM - 1:30 PM; Sat 8:00 AM - 1:00 PM; Sun Holiday",
        "bpharm": "⏰ B.Pharm: Mon-Fri 9:00 AM - 4:00 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:00 AM - 1:00 PM; Sun Holiday",
        "bsc nursing": "⏰ B.Sc Nursing: Mon-Fri 9:00 AM - 4:00 PM, Lunch 12:30 PM - 1:30 PM; Sat 9:00 AM - 1:00 PM; Sun Holiday",
    }
}


dress_code = """👔 College Dress Code:
• Boys: Formal shirt and pants, shoes
• Girls: Salwar kameez / formal tops and chudi / saree, shoes
• ID card must be worn at all times
• Casual wear allowed only on Festivals and special events
• Contact the Student Affairs Office for more details
"""
# ----------------- Predict Intent Function -----------------
def predict_intent(user_input, intents):
    user_input_lower = user_input.lower()

    # 1️⃣ Exact match first
    for intent_name, keywords in intents.items():
        for kw in keywords:
            if kw.lower() in user_input_lower:
                return intent_name

    # 2️⃣ Fuzzy match if no exact match
    best_intent = None
    best_match_score = 0
    for intent_name, keywords in intents.items():
        match = get_close_matches(user_input_lower, keywords, n=1, cutoff=0.6)
        if match:
            ratio = SequenceMatcher(None, user_input_lower, match[0]).ratio()
            if ratio > best_match_score:
                best_match_score = ratio
                best_intent = intent_name
    return best_intent

responses = {
    "dress_code": "👔 College Dress Code: Boys - formal shirt/pants; Girls - salwar/saree; ID card mandatory.",
    "fees": "💰 Fees depend on course and year.",
    "hostel": "🏠 Separate hostels for boys and girls; AC & Non-AC available."
}


def get_response(user_input, user_id="default"):
    # Step 1: Predict intent
    intent = predict_intent(user_input, intents)

    # Step 2: Handle timing intent
    if intent == "college_timing":
        # ← Replace old user_state logic with this line
        return get_college_timing(user_input)

    # Step 3: Other known responses
    elif intent and intent in responses:
        return responses[intent]

    # Step 4: Fallback
    else:
        return "Sorry, I didn't understand that. Could you please try again?"


# Hostel Data
boys_hostels = [
    {"name": "Paari Hostel (AC)", "rooms": 50, "members_per_room": 2, "ac": True, "hostel_fees": 10000, "mess_fees": 20000},
    {"name": "Kkkk Hostel (AC)", "rooms": 40, "members_per_room": 2, "ac": True, "hostel_fees": 10000, "mess_fees": 20000},
    {"name": "aaaa Hostel (Non-AC)", "rooms": 60, "members_per_room": 3, "ac": False, "hostel_fees": 8000, "mess_fees": 20000},
    {"name": "Adhiyaman Hostel (Non-AC)", "rooms": 55, "members_per_room": 3, "ac": False, "hostel_fees": 8000, "mess_fees": 20000},
    {"name": "Marutham Hostel (Non-AC)", "rooms": 45, "members_per_room": 4, "ac": False, "hostel_fees": 8000, "mess_fees": 20000}
]

girls_hostels = [
    {"name": "Yamuna Hostel (AC)", "rooms": 40, "members_per_room": 2, "ac": True, "hostel_fees": 10000, "mess_fees": 20000},
    {"name": "Kalpana Hostel (AC)", "rooms": 35, "members_per_room": 2, "ac": True, "hostel_fees": 10000, "mess_fees": 20000},
    {"name": "Sneha Hostel (Non-AC)", "rooms": 50, "members_per_room": 3, "ac": False, "hostel_fees": 8000, "mess_fees": 20000},
    {"name": "Priya Hostel (Non-AC)", "rooms": 55, "members_per_room": 3, "ac": False, "hostel_fees": 8000, "mess_fees": 20000},
    {"name": "cccc Hostel (Non-AC)", "rooms": 45, "members_per_room": 4, "ac": False, "hostel_fees": 8000, "mess_fees": 20000}
]

# Admission dates
admission_start_date = datetime(2025, 5, 1)
admission_deadline = datetime(2025, 6, 15)
# ===== Campus Life Data =====
campus_life = {
    "clubs": {
        "details": (
            "SRM Institude Of Technology hosts a diverse range of student clubs and professional chapters "
            "promoting holistic development and extracurricular engagement.<br><br>"
            "📌 Active Clubs:<br>"
            "• Rotaract Club – Social service and community projects.<br>"
            "• Fashion Club – Fashion shows and creative styling.<br>"
            "• Literature Club – Creative writing, debates, and poetry.<br>"
            "• Social Club – Social awareness campaigns and events.<br>"
            "• Self Defense Club – Martial arts and safety workshops.<br>"
            "• GeeksforGeeks SRMIST – Coding and programming workshops.<br>"
            "• CENTINEL – Cybersecurity training with domains like SoftwareGeeks, CyberSquad, and WebGen.<br><br>"
            "💡 <b style='color:red;'>How to Join:</b> Visit the Student Affairs Office or the respective club stall during the Club Signup Week."
        )
    },
    "cultural": {
        "details": (
            "🎭 SRM Institude Of Technology hosts vibrant cultural events and annual fests that bring together students from all campuses.<br><br>"
            "📌 Major Cultural Events:<br>"
            "• Milan – Annual cultural extravaganza with music, dance, and theatre.<br>"
            "• Rubaroo – Freshers cultural night.<br>"
            "• Talent Hunt – Platform for students to showcase creative talents.<br>"
            "• Department Fests – Each department hosts its own cultural & technical events.<br><br>"
            "💡 <b style='color:red;'>How to Participate:</b> Register online through the cultural committee or contact your department cultural coordinator."
        )
    },
    "sports": {
        "details": (
            "🏅 SRM Institude Of Technology (AIT)offers excellent sports facilities and actively promotes athletic activities.<br><br>"
            "📌 Available Sports:<br>"
            "• Cricket – Coach: Mr. Rajesh Kumar<br>"
            "• Football – Coach: Mr. Suresh Reddy<br>"
            "• Basketball – Coach: Ms. Priya Sharma<br>"
            "• Badminton – Coach: Mr. Arvind Singh<br>"
            "• Athletics & Track – Coach: Mr. Manoj Nair<br><br>"
            "💡 Facilities: Indoor stadium, outdoor tracks, gymnasiums, swimming pool, tennis courts.<br>"
            "💡 <b style='color:red;'>How to Join:</b> Contact the Sports Department Office or the respective coach."
        )
    }
}
BROCHURE_URL = "https://college.edu/brochure.pdf"

def days_left_to_apply():
    deadline = datetime(2025, 8, 31)
    today = datetime.now()
    remaining = (deadline - today).days
    if remaining >= 0:
        return f"Application deadline: {deadline.strftime('%d %B %Y')}<br>{remaining} days left to apply."
    else:
        return " The appication deadline has passed."
    


# ---------------- Chat Endpoint ----------------
from datetime import datetime 
@app.route("/chat", methods=["POST"])
def chat():
    user_msg = request.json.get("message", "")
    if not isinstance(user_msg, str) or user_msg.strip() == "":
        return jsonify({"reply": "⚠️ Please type a message."})
    user_msg = user_msg.strip()
    user_msg_lower = user_msg.lower()  
    # ----------------- COURSE FEES LOGIC -----------------
    reply = None

    for dept, dept_courses in courses.items():
        for course_name, fee_info in dept_courses.items():
            if course_name.lower() in user_msg_lower:
                reply = f"💰 Fees for {course_name.upper()}:\n"
                for year, amount in fee_info.items():
                    reply += f"{year}: {amount}\n"
                break  # breaks inner loop
        if reply:
            break  # breaks outer loop if reply is found

    # ===== FUZZY MATCH CHECKS =====
    if not reply and fuzzy_match(user_msg_lower, intents.get("admission_eligibility", [])):
        reply = (
            "📌 Admission Eligibility:\n"
            "• Must have passed 12th with minimum 50% marks (varies by course).\n"
            "• Some courses may require entrance exams.\n"
            "• For detailed eligibility, visit the Admissions Office or website."
        )

    if not reply and fuzzy_match(user_msg_lower, intents.get("admission_process", [])):
        reply = (
            "📝 Admission Process:\n"
            "1. Fill online application form.\n"
            "2. Submit required documents.\n"
            "3. Appear for entrance exam (if applicable).\n"
            "4. Confirm admission after fee payment."
        )
  


# Dress Code Queries
    if not reply:
        try:
            if fuzzy_match(user_msg_lower, intents.get("dress_code", [])):
                reply = (
                    "👔 College Dress Code:\n"
                    "• Boys: Formal shirt and pants, shoes\n"
                    "• Girls: Salwar kameez / formal tops and chudi / saree, shoes\n"
                    "• ID card must be worn at all times\n"
                    "• Casual wear allowed only on Festivals and special events\n"
                    "• Contact the Student Affairs Office for more details"
                )
        except Exception as e:
            reply = f"⚠️ Server error occurred: {str(e)}"

    # 1️⃣ COLLEGE INFORMATION - English & Tamil
    if not reply and any(phrase in user_msg_lower for phrase in [
        # English keywords
        "about college", "college details", "tell me about college",
        "about our college", "information about college", "college information",
        # Tamil keywords
        "கல்லூரி பற்றிய", "கல்லூரி விவரங்கள்"
    ]):
        # If Tamil keyword detected
        if any(phrase in user_msg_lower for phrase in ["கல்லூரி பற்றிய", "கல்லூரி விவரங்கள்"]):
            reply = (
            "<div style='text-align:center; font-size:22px; font-weight:bold;'>"
            "🏫 SRM தொழில்நுட்ப நிறுவனம்"
            "</div><br>"
            "SRM தொழில்நுட்ப நிறுவனம் கல்வி சிறப்புமிக்க, நவீன வசதிகள் மற்றும் மாணவர் நட்பு சூழலுக்காக புகழ்பெற்றது.<br><br>"

            "<b>👤 தலைமைச் செயலாளர்:</b> திரு. நள்ளத்தம்பி<br>"
            "<b>🎓 தலைவர்:</b> டாக்டர் R. கிருஷ்ணமூர்த்தி<br>"
            "<b>🏆 தேசிய ரேங்க்:</b> 15<br>"
            "<b>🏆 மாநில ரேங்க்:</b> 2<br>"
            "<b>👩‍🏫 பேராசிரியர்கள்:</b> 250+ அர்ப்பணிப்புடன் கூடிய ப்ரொஃபெசர்கள்<br>"
            "<b>🎓 பி.எச்.டி. ஹோல்டர்கள்:</b> 80+ highly qualified faculty<br><br>"

            "<b>💼 பிளேஸ்மென்ட்:</b> மாணவர்களை சிறந்த நிறுவனங்களில் வெற்றிகரமாக பிளேஸ் செய்துள்ளோம்.<br><br>"

            "<b>📚 வசதிகள்:</b><br>• நவீன வகுப்பறைகள் மற்றும் ஸ்மார்ட் போர்டுகள்<br>"
            "• நூலகம் - ஆயிரக்கணக்கான புத்தகங்கள்<br>"
            "• உயர் தொழில்நுட்ப கணினி லேப்கள் மற்றும் வேகமான இன்டர்நெட்<br>"
            "• அமைதியான மற்றும் பசுமை நிறைந்த வளாகம்<br><br>"

            "<b>🏠 ஹாஸ்டல் வசதிகள்:</b><br>"
            "• பையன்கள் மற்றும் பெண் மாணவர்களுக்கு தனித்தனியான ஹாஸ்டல்கள்<br>"
            "• 24/7 பாதுகாப்பு மற்றும் CCTV கண்காணிப்பு<br>"
            "• சத்துணவு மற்றும் சுத்தமான உணவுக்கூடங்கள்<br>"
            "• ஓய்வுக்கூடங்கள் மற்றும் படிப்பு அறைகள்<br><br>"

            "<b>🏅 விளையாட்டு மற்றும் செயல்பாடுகள்:</b><br>"
            "• கிரிக்கெட், கால்பந்து, பேஸ்கெட்ட்பால், பேட்மிண்டன் மற்றும் தடகளம்<br>"
            "• வருடாந்திர விளையாட்டு விழா மற்றும் இன்டர்கல்லூரி போட்டிகள்<br>"
            "• பயிற்சியாளர்கள் மற்றும் உடற்பயிற்சி திட்டங்கள்<br><br>"

            "<b>💡 நமது குறிக்கோள்:</b> 'அறிவை உருவாக்கி எதிர்காலத்தை கட்டமைப்போம்.'<br><br>"
            "<b>கல்லூரியின் நோக்கம்:</b><br>"
            "அறிவை உருவாக்கி உலக தரமான கல்வியை வழங்கும் கல்வி மற்றும் ஆராய்ச்சி சூழலை உருவாக்குவதே நோக்கம்.<br>"
            "<b>கால்கட்டுக் குறிக்கோள்:</b><br>"
            "சுதந்திரம், சுயம்செய்தல், படைப்பு மற்றும் புதுமையை ஊக்குவிக்கும் சூழலை உருவாக்குதல்."
            )
        else:
        # English reply
            reply = (
            "<div style='text-align:center; font-size:22px; font-weight:bold;'>"
            "🏫 SRM Institute of Technology"
            "</div><br>"
            "SRM Institute of Technology is one of the most prestigious institutions, renowned for its academic excellence, modern facilities, and student-friendly environment.<br><br>"

            "<b>👤 CEO:</b> Mr. Nallathambi<br>"
            "<b>🎓 Principal:</b> Dr. R. Krishnamoorthy<br>"
            "<b>🏆 National Rank:</b> 15th<br>"
            "<b>🏆 State Rank:</b> 2nd<br>"
            "<b>👩‍🏫 Faculty Members:</b> 250+ dedicated professors<br>"
            "<b>🎓 Ph.D. Holders:</b> 80+ highly qualified faculty members<br><br>"

            "<b>💼 Placements:</b> We have successfully placed thousands of students in top multinational companies with attractive salary packages.<br><br>"

            "<b>📚 Facilities:</b><br>• Spacious and modern classrooms with smart boards<br>"
            "• Well-stocked library with thousands of academic and reference books<br>"
            "• High-tech computer labs with fast internet<br>"
            "• Peaceful and green campus for a positive learning environment<br><br>"

            "<b>🏠 Hostel Facilities:</b><br>"
            "• Separate hostels for boys and girls<br>"
            "• 24/7 security and CCTV surveillance<br>"
            "• Nutritious food and clean dining halls<br>"
            "• Recreation rooms and study lounges<br><br>"

            "<b>🏅 Sports & Activities:</b><br>"
            "• Cricket, Football, Basketball, Badminton, and Athletics<br>"
            "• Annual Sports Meet and Inter-College Competitions<br>"
            "• Dedicated sports coaches and fitness programs<br><br>"

            "<b>💡 Our Motto:</b> 'Innovating Minds, Building Futures.'<br><br>"
            "<b>Vision of AIT:</b><br>"
            "To emerge as a World-Class University in creating and disseminating knowledge, "
            "and providing students a unique learning experience in science, technology, medicine, management and other areas of scholarship.<br>"
            "<b>Mission of AIT:</b><br>"
            "MOVE UP through international alliances and collaborative initiatives to achieve global excellence.<br>"
            "ACCOMPLISH a process to advance knowledge in a rigorous academic and research environment.<br>"
            "ATTRACT and BUILD people in a rewarding and inspiring environment by fostering freedom, empowerment, creativity, and innovation."
            )

# 2️⃣ COURSES LIST - English & Tamil
    if not reply and any(phrase in user_msg_lower for phrase in ["courses","arts", "பாடநெறிகள்"]):
        if any(phrase in user_msg_lower for phrase in ["பாடநெறிகள்"]):
            reply = (
            "📚 <b>நாம் வழங்கும் பாடநெறிகள்:</b><br><br>"
            "<b>பொறியியல்:</b> EEE, ECE, CSE, Civil, Mechanical<br>"
            "<b>கலை:</b> B.Com, BBA, B.Sc Tamil, B.Sc English, BA History<br>"
            "<b>அறிவு விஞ்ஞானம்:</b> B.Sc CS, B.Sc CA, B.Sc Physics, B.Sc Chemistry, B.Sc Maths<br>"
            "<b>மருத்துவம்:</b> MBBS, BDS, B.Pharm, B.Sc Nursing<br>"
            "<b>நீதியியல்:</b> LLB, BA LLB, BBA LLB<br>"
            "<b>கலைக்கலைப்பொருளமைப்பு:</b> B.Arch, M.Arch"
            )
        else:
            reply = (
            "📚 <b>Our Courses:</b><br><br>"
            "<b>Engineering:</b> EEE, ECE, CSE, Civil, Mechanical<br>"
            "<b>Arts:</b> B.Com, BBA, B.Sc Tamil, B.Sc English, BA History<br>"
            "<b>Science:</b> B.Sc CS, B.Sc CA, B.Sc Physics, B.Sc Chemistry, B.Sc Maths<br>"
            "<b>Medical:</b> MBBS, BDS, B.Pharm, B.Sc Nursing<br>"
            "<b>Law:</b> LLB, BA LLB, BBA LLB<br>"
            "<b>Architecture:</b> B.Arch, M.Arch"
            )
    # 3️⃣ FEES STRUCTURE
    # Convert user input to lowercase and remove extra spaces
    def get_course_name(user_msg):
        user_msg = user_msg.lower()
        for dept, dept_courses in courses.items():
            for course_name in dept_courses.keys():
                if course_name in user_msg:
                    return course_name
        return None



    #for 4️⃣ HOSTEL DETAILS
    # Hostel details
    # 4️⃣ HOSTEL DETAILS
    if not reply and any(word in user_msg_lower for word in ["hostel", "boys", "girls", "ஆண்கள்", "பெண்கள்", "ஹோஸ்டல்"]):
        details = ""
        try:
            if "boys" in user_msg_lower or "ஆண்கள்" in user_msg_lower:
                details = "<b>🏠 Boys Hostels:</b><br>"
                for h in boys_hostels:
                    details += f"{h['name']} - {'AC' if h['ac'] else 'Non-AC'}<br>Rooms: {h['rooms']}, Members/Room: {h['members_per_room']}<br>Hostel Fees: ₹{h['hostel_fees']}, Mess Fees: ₹{h['mess_fees']}<br><br>"
                reply = details

            elif "girls" in user_msg_lower or "பெண்கள்" in user_msg_lower:
                details = "<b>🏠 Girls Hostels:</b><br>"
                for h in girls_hostels:
                    details += f"{h['name']} - {'AC' if h['ac'] else 'Non-AC'}<br>Rooms: {h['rooms']}, Members/Room: {h['members_per_room']}<br>Hostel Fees: ₹{h['hostel_fees']}, Mess Fees: ₹{h['mess_fees']}<br><br>"
                reply = details

            else:
                reply = (
                "<b>🏠 Hostel Details:</b><br>"
                "Separate hostels for boys and girls with AC & Non-AC rooms.<br>"
                "24/7 Security, WiFi, Study Room, Gym & Medical Facilities available.<br>"
                "Use 'boys hostel' or 'girls hostel' to get more details."
                )
        except Exception as e:
            reply = f"⚠️ Error fetching hostel data: {str(e)}"



    # 📌 PLACEMENT DETAILS
    if not reply and any(word in user_msg_lower for word in ["placements", "placement details", "placement info","பதவி"]):
        reply =(
                "<b>💼 Placement Information - SRM Institute of Technology</b><br><br>"
                "🌟 <i>We provide one of the best placement opportunities for our students, "
                "connecting them with top recruiters across India and abroad.</i><br><br>"
                
                "<b>🏆 Top Companies Visiting:</b><br>"
                "• TCS - ₹12 LPA<br>"
                "• Infosys - ₹10 LPA<br>"
                "• Wipro - ₹9 LPA<br>"
                "• HCL - ₹8 LPA<br>"
                "• Cognizant - ₹8.5 LPA<br><br>"

                "<b>📜 Eligibility for Placement:</b><br>"
                "• You must score more than 75% in semester exams to apply.<br>"
                "• Placement fees will be collected in your final year.<br>"
                "• The fee will be informed in the final year and will be under ₹1,50,000.<br><br>"

                "<b> Placement Related Trainings:</b><br>"
                "We will provide placement trainings during your final year.<br>"
                "Like Aptitude,Programming,Communication<br><br>"

                "<b>Placement Fee:</b> Paid separately in the final year.<br><br>"
                "<b>Note:</b> Fee amount will be announced during the final year.<br>"
        )

    # 📌 PREVIOUS YEAR PLACEMENT STATUS
    if not reply and any(word in user_msg_lower for word in ["previous year placement", "past placements", "placement stats","முன்னாள் பதவிகள்"]):
        
        reply = (
                "<b>📊 Previous Year Placement Statistics</b><br><br>"
                
                "<u>2024</u><br>"
                "• Overall: 95% placed<br>"
                "• Engineering: IT - 300, Non-IT - 150<br>"
                "• Arts: IT - 80, Non-IT - 70<br>"
                "• Science: IT - 90, Non-IT - 60<br><br>"

                "<u>2023</u><br>"
                "• Overall: 92% placed<br>"
                "• Engineering: IT - 280, Non-IT - 140<br>"
                "• Arts: IT - 75, Non-IT - 65<br>"
                "• Science: IT - 85, Non-IT - 55<br><br>"

                "<u>2022</u><br>"
                "• Overall: 90% placed<br>"
                "• Engineering: IT - 260, Non-IT - 130<br>"
                "• Arts: IT - 70, Non-IT - 60<br>"
                "• Science: IT - 80, Non-IT - 50<br>"
        )

    # 4️⃣ College timing (Add your code here)
    elif "college timing" in user_msg_lower or "timing" in user_msg_lower:
        reply = ""
        for course, years in college_timings.items():
            if course in user_msg_lower:
                if isinstance(years, dict):
                    for year, timing in years.items():
                        reply += f"{timing}\n"
                else:
                    reply = years
                break
        if not reply:
            reply = "⏰ College Timings:\n"
            for course, years in college_timings.items():
                if isinstance(years, dict):
                    for year, timing in years.items():
                        reply += f"{timing}\n"
                else:
                    reply += f"{years}\n"

    # 4️⃣ ADMISSION DATE
    if not reply and any(word in user_msg_lower for word in ["admission date", "start of admission", "when will admission start", "சென்னை"]):
        days_left = (admission_start_date - datetime.now()).days
        reply = (
                f"📅 Admission at <b>SRM Institute of Technology</b> starts on "
                f"<b>{admission_start_date.strftime('%d-%m-%Y')}</b>.<br>"
                f"⏳ Only <b>{days_left}</b> days left!<br>"
                f"🔥 Hurry up! Secure your seat and start your journey towards excellence."
            )

    # 5️⃣ ADMISSION DEADLINE
    if not reply and any(word in user_msg_lower for word in ["admission deadline", "last date for admission", "end of admission","முடிவும்"]):
        days_left = (admission_deadline - datetime.now()).days
        if days_left < 0:
            reply = "⚠ Admission deadline has passed."
        else:
            reply = f"📅 Admission ends on {admission_deadline.strftime('%d-%m-%Y')}<br>⏳ Only {days_left} days left!"

    # ===== Campus Life Queries =====
    if any(word in user_msg_lower for word in ["club", "clubs", "student club", "society", "கிளப்புகள்"]):
        reply= f"<b>🏛 Clubs at AIT:</b><br><br>{campus_life['clubs']['details']}"
    
    elif any(word in user_msg_lower for word in ["cultural", "fest", "annual day", "milan", "rubaroo","கலை நிகழ்ச்சி"]):
        reply= f"<b>🎭 Cultural & Annual Fests at AIT:</b><br><br>{campus_life['cultural']['details']}"
    elif any(word in user_msg_lower for word in ["sports", "games", "athletics", "coach", "football", "cricket", "basketball","விளையாட்டு"]):
        reply= f"<b>🏅 Sports at AIT:</b><br><br>{campus_life['sports']['details']}"
    # Contact details
    if any(word in user_msg_lower for word in ["contact", "phone", "email", "reach you", "call you", "college contact","தொடர்பு"]):
        reply=(
                "<b>📞 Contact Details:</b><br>"
                "Phone: <a href='tel:+911234567890'>+91 12345 67890</a><br>"
                "Email: <a href='mailto:info@srmcollege.edu'>info@srmcollege.edu</a>"
                "<b>If you have any queries, you can visit our Admissions Office between 9:00 AM and 5:00 PM, Monday to Saturday.</b>"
        )
            # ENTRANCE EXAM INFORMATION
    elif (
        "entrance exam" in user_msg_lower
        or "exam date" in user_msg_lower
        or "is there any entrance" in user_msg_lower
        or "entrance test" in user_msg_lower
    ):
       # Department-specific entrance details
       if "engineering" in user_msg_lower or "cse" in user_msg_lower or "ece" in user_msg_lower or "eee" in user_msg_lower:
        exam_info = "🛠️ For Engineering (B.E/B.Tech), admission is based on JEE / TNEA counselling depending on your state."
       elif "medical" in user_msg_lower or "mbbs" in user_msg_lower or "bds" in user_msg_lower or "bpharm" in user_msg_lower or "nursing" in user_msg_lower:
        exam_info = "🩺 For Medical courses (MBBS, BDS, B.Pharm, Nursing), admission is through NEET (National Eligibility cum Entrance Test)."
       elif "mba" in user_msg_lower or "management" in user_msg_lower:
        exam_info = "📊 For MBA, admission is based on an entrance exam conducted by SRM / or valid scores from CAT, MAT, XAT, or TANCET."
       elif "law" in user_msg_lower or "llb" in user_msg_lower:
        exam_info = "⚖️ For Law courses (LLB, BA LLB, BBA LLB), admission is usually through CLAT (Common Law Admission Test)."
       elif "architecture" in user_msg_lower or "barch" in user_msg_lower or "m.arch" in user_msg_lower:
        exam_info = "🏛 For Architecture (B.Arch, M.Arch), admission is based on NATA (National Aptitude Test in Architecture)."
       elif "arts" in user_msg_lower or "science" in user_msg_lower:
        exam_info = "📚 For Arts & Science courses (B.Com, BBA, B.Sc, BA, etc.), admission is usually merit-based (marks in 12th standard)."
       else:
        exam_info = "📝 Entrance exam requirements vary by course. Please specify your department (Engineering, Medical, Law, Architecture, Arts, or Science)."
        reply= (
                "<b>📝 Entrance Exam Details – SRM College</b><br><br>"
                "<b>🎓 Courses Requiring Entrance Exams:</b><br>"
                "• B.Tech – 10 September 2025 (Offline, 2 hours)<br>"
                "• MBA – 15 September 2025 (Online, 1.5 hours)<br>"
                "• B.Sc Nursing – 18 September 2025 (Offline, 2 hours)<br><br>"
                "<b>📌 Courses Without Entrance Exam:</b><br>"
                "• All Arts & Science degree programs – Direct admission based on 12th grade marks<br><br>"
                "<b>⚠ Note:</b> Admit cards will be available online 7 days before the exam.<br>"
                "<b>📍 Exam Centres:</b> We will inform you about your exam centre and timing 2 days before the exam date.<br><br>"
                f"<b>🔎 Department-specific Info:</b><br>{exam_info}"
            )
 # Direct department-only queries
    elif any(word in user_msg_lower for word in ["medical", "mbbs", "bds", "bpharm", "nursing", "மருத்துவம்"]):
        reply = "🩺 For Medical courses, admission is through NEET (National Eligibility cum Entrance Test)."
    elif fuzzy_match(user_msg_lower, ["engineering", "cse", "eee", "ece"]):
        reply = "🛠️ For Engineering (B.E/B.Tech), admission is based on JEE / TNEA counselling."
    elif any(word in user_msg_lower for word in ["mba", "management"]):
        reply = (
            "📊 For MBA admission:<br>"
            "• Entrance exam conducted by SRM<br>"
            "• OR valid scores from CAT, MAT, XAT, or TANCET"
        )
    elif any(word in user_msg_lower for word in ["law", "llb"]):
        reply = "⚖️ For Law courses, admission is usually through CLAT."
    elif any(word in user_msg_lower for word in ["architecture", "barch", "m.arch"]):
        reply = "🏛 For Architecture, admission is based on NATA."
    elif any(word in user_msg_lower for word in ["arts", "science", "bcom", "bsc"]):
        reply = "📚 For Arts & Science courses, admission is usually merit-based (12th marks)."
        # If nothing matched
    

    # ----------------- AI DEFAULT RESPONSE -----------------
    if not reply:
        reply = get_response(user_msg)  # Use AI response if no course fees match
    # Fallback if AI also fails
        if not reply:
            reply = (
                "மன்னிக்கவும், எனக்கு அது புரியவில்லை. மீண்டும் முயற்சிக்க முடியுமா?"
                if is_tamil(user_msg)
                else "Sorry, I didn't understand that. Could you please try again?"
            )

# Translate if Tamil detected
    reply = translate_reply_deep(reply, user_msg)
    return jsonify({"reply": reply})



# ---------------- Database Setup ----------------
def init_db():
    with sqlite3.connect("users.db") as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                          username TEXT UNIQUE,
                          password TEXT)''')
        conn.commit()
init_db()

# ---------- home page ----------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chatbot")
def chatbot_page():
    return render_template("chatbot.html")
@app.route("/exit")
def exit_page():
    return redirect(url_for('home'))

# ---------- Run ----------
if __name__ == "__main__":
    app.run(debug=True)
