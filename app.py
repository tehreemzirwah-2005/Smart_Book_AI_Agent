import os
import json
import sqlite3
from datetime import datetime, timedelta
import streamlit as st
from openai import OpenAI

# ==========================================
# 1. DATABASE & INITIALIZATION
# ==========================================
DB_NAME = "smartbook.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Business & Physician Tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            physician_name TEXT,
            slot_time TEXT,
            status TEXT DEFAULT 'AVAILABLE', -- AVAILABLE, HELD, CONFIRMED, CANCELLED
            date TEXT
        )
    ''')
    
    # Appointments Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            client_phone TEXT,
            physician_name TEXT,
            slot_time TEXT,
            status TEXT DEFAULT 'CONFIRMED',
            date TEXT
        )
    ''')
    
    # Waiting List Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS waiting_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            client_phone TEXT,
            preferred_date TEXT,
            status TEXT DEFAULT 'PENDING'
        )
    ''')
    
    # AI Activity Log
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            action TEXT,
            details TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# ==========================================
# 2. DETERMINISTIC BACKEND ENGINE & TOOLS
# ==========================================

def get_db_connection():
    return sqlite3.connect(DB_NAME)

def log_ai_action(action, details):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO ai_logs (timestamp, action, details) VALUES (?, ?, ?)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), action, details)
    )
    conn.commit()
    conn.close()

# --- BACKEND FUNCTIONS CALLED BY AI OR UI ---

def db_get_available_slots(date_str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT slot_time FROM availability WHERE date = ? AND status = 'AVAILABLE'",
        (date_str,)
    )
    slots = [row[0] for row in cursor.fetchall()]
    conn.close()
    return slots

def db_book_appointment(client_name, client_phone, physician_name, slot_time, date_str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Deterministic Lock Check
    cursor.execute(
        "SELECT status FROM availability WHERE date = ? AND slot_time = ? AND physician_name = ?",
        (date_str, slot_time, physician_name)
    )
    row = cursor.fetchone()
    
    if not row or row[0] != 'AVAILABLE':
        conn.close()
        return {"success": False, "message": "Slot is no longer available."}
    
    # Update availability slot to CONFIRMED
    cursor.execute(
        "UPDATE availability SET status = 'CONFIRMED' WHERE date = ? AND slot_time = ? AND physician_name = ?",
        (date_str, slot_time, physician_name)
    )
    
    # Create Appointment Record
    cursor.execute(
        "INSERT INTO appointments (client_name, client_phone, physician_name, slot_time, status, date) VALUES (?, ?, ?, ?, 'CONFIRMED', ?)",
        (client_name, client_phone, physician_name, slot_time, date_str)
    )
    
    conn.commit()
    conn.close()
    
    log_ai_action("BOOK_APPOINTMENT", f"Booked {slot_time} for {client_name}")
    return {"success": True, "message": f"Appointment confirmed for {slot_time} with {physician_name}."}

def db_cancel_appointment(client_phone, date_str):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id, slot_time, physician_name FROM appointments WHERE client_phone = ? AND date = ? AND status = 'CONFIRMED'",
        (client_phone, date_str)
    )
    appt = cursor.fetchone()
    
    if not appt:
        conn.close()
        return {"success": False, "message": "No active appointment found for this phone number."}
    
    appt_id, slot_time, physician_name = appt
    
    # Cancel appointment
    cursor.execute("UPDATE appointments SET status = 'CANCELLED' WHERE id = ?", (appt_id,))
    
    # Release Slot back to AVAILABLE
    cursor.execute(
        "UPDATE availability SET status = 'AVAILABLE' WHERE date = ? AND slot_time = ? AND physician_name = ?",
        (date_str, slot_time, physician_name)
    )
    
    conn.commit()
    conn.close()
    
    log_ai_action("CANCEL_APPOINTMENT", f"Cancelled appt for {client_phone}. Released slot {slot_time}.")
    return {"success": True, "released_slot": slot_time, "message": "Appointment cancelled successfully."}

def db_add_to_waitlist(client_name, client_phone, date_str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO waiting_list (client_name, client_phone, preferred_date) VALUES (?, ?, ?)",
        (client_name, client_phone, date_str)
    )
    conn.commit()
    conn.close()
    log_ai_action("WAITLIST_ADDED", f"Added {client_name} ({client_phone}) to waitlist for {date_str}")
    return {"success": True, "message": "Added to waiting list successfully."}

# ==========================================
# 3. OPENAI TOOL-CALLING AI RECEPTIONIST
# ==========================================

tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "get_available_slots",
            "description": "Fetch available appointment slots for a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_str": {"type": "string", "description": "YYYY-MM-DD format"}
                },
                "required": ["date_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment slot after deterministic availability verification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_name": {"type": "string"},
                    "client_phone": {"type": "string"},
                    "physician_name": {"type": "string"},
                    "slot_time": {"type": "string"},
                    "date_str": {"type": "string"}
                },
                "required": ["client_name", "client_phone", "physician_name", "slot_time", "date_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an appointment and automatically release the slot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_phone": {"type": "string"},
                    "date_str": {"type": "string"}
                },
                "required": ["client_phone", "date_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "add_to_waitlist",
            "description": "Add client to waitlist if no slots are available.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_name": {"type": "string"},
                    "client_phone": {"type": "string"},
                    "date_str": {"type": "string"}
                },
                "required": ["client_name", "client_phone", "date_str"]
            }
        }
    }
]

def run_ai_receptionist(user_prompt, conversation_history):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "⚠️ OpenAI API Key is missing. Please set OPENAI_API_KEY environment variable."
    
    client = OpenAI(api_key=api_key)
    
    system_instruction = f"""
    You are SmartBook AI, a virtual receptionist for ABC Medical Clinic (Dr. Ahmed).
    Today's Date: {datetime.now().strftime('%Y-%m-%d')}.
    
    STRICT RULES:
    1. NEVER invent slots. Always call `get_available_slots` to check real database state first.
    2. MEDICAL SAFETY: Never give medical advice, diagnosis, or prescription. If user asks medical questions, escalate to clinic staff.
    3. Keep responses friendly, short, and professional.
    """
    
    messages = [{"role": "system", "content": system_instruction}] + conversation_history + [{"role": "user", "content": user_prompt}]
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools_schema,
        tool_choice="auto"
    )
    
    msg = response.choices[0].message
    
    # Handle Tool Execution Loop
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            
            tool_result = {}
            if func_name == "get_available_slots":
                slots = db_get_available_slots(args.get("date_str"))
                tool_result = {"available_slots": slots}
            elif func_name == "book_appointment":
                tool_result = db_book_appointment(
                    args.get("client_name"), args.get("client_phone"),
                    args.get("physician_name"), args.get("slot_time"), args.get("date_str")
                )
            elif func_name == "cancel_appointment":
                tool_result = db_cancel_appointment(args.get("client_phone"), args.get("date_str"))
            elif func_name == "add_to_waitlist":
                tool_result = db_add_to_waitlist(args.get("client_name"), args.get("client_phone"), args.get("date_str"))
            
            messages.append(msg)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(tool_result)
            })
        
        # Second call to LLM to summarize response in natural language
        second_response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )
        return second_response.choices[0].message.content
        
    return msg.content

# ==========================================
# 4. STREAMLIT FRONTEND DASHBOARD
# ==========================================

st.set_page_config(page_title="SmartBook Agent", layout="wide", page_icon="📅")

st.title("🤖 SmartBook Agent - AI Appointment Receptionist")
st.caption("AI-Operated Appointment Management Infrastructure")

# Sidebar - Persona Switcher
app_mode = st.sidebar.radio("Select View / User Type:", ["Physician Morning Setup", "Client AI Receptionist", "Admin SaaS Dashboard"])

today_str = datetime.now().strftime("%Y-%m-%d")

# ------------------------------------------
# A. PHYSICIAN DASHBOARD
# ------------------------------------------
if app_mode == "Physician Morning Setup":
    st.header("👨‍⚕️ Physician Morning Availability")
    st.subheader(f"Dr. Ahmed — {today_str}")
    
    slots_list = [
        "09:00 AM", "09:30 AM", "10:00 AM", "10:30 AM",
        "11:00 AM", "11:30 AM", "03:00 PM", "03:30 PM", "04:00 PM"
    ]
    
    st.write("Select available slots for today and publish:")
    selected_slots = st.multiselect("Today's Available Hours", slots_list, default=slots_list[:5])
    
    if st.button("Publish Today's Availability", type="primary"):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Reset current day's available slots
        cursor.execute("DELETE FROM availability WHERE date = ? AND status = 'AVAILABLE'", (today_str,))
        
        for slot in selected_slots:
            cursor.execute(
                "INSERT INTO availability (physician_name, slot_time, status, date) VALUES (?, ?, 'AVAILABLE', ?)",
                ("Dr. Ahmed", slot, today_str)
            )
        conn.commit()
        conn.close()
        
        st.success(f"🟢 Published {len(selected_slots)} slots! SmartBook AI is now managing your schedule.")
        log_ai_action("PHYSICIAN_PUBLISH", f"Published {len(selected_slots)} slots for Dr. Ahmed.")

# ------------------------------------------
# B. CLIENT AI CHATBOT INTERFACE
# ------------------------------------------
elif app_mode == "Client AI Receptionist":
    st.header("💬 WhatsApp / AI Receptionist Assistant")
    st.info("Test AI tool-calling for booking, cancellation, and availability checks.")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Hi, can I book an appointment with Dr. Ahmed today?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("AI is verifying database state..."):
                # Pass previous history for context
                conv_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[:-1]]
                response_text = run_ai_receptionist(prompt, conv_history)
                st.markdown(response_text)
                
        st.session_state.messages.append({"role": "assistant", "content": response_text})

# ------------------------------------------
# C. ADMIN SAAS DASHBOARD
# ------------------------------------------
elif app_mode == "Admin SaaS Dashboard":
    st.header("📈 Business Admin & Analytics Dashboard")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Analytics Metrics
    cursor.execute("SELECT COUNT(*) FROM appointments WHERE date = ? AND status = 'CONFIRMED'", (today_str,))
    confirmed_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM availability WHERE date = ? AND status = 'AVAILABLE'", (today_str,))
    available_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM appointments WHERE date = ? AND status = 'CANCELLED'", (today_str,))
    cancelled_count = cursor.fetchone()[0]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Confirmed Appointments", confirmed_count)
    col2.metric("Available Slots", available_count)
    col3.metric("Cancellations", cancelled_count)
    col4.metric("Est. Revenue Saved", f"${confirmed_count * 100}")
    
    st.divider()
    
    # Live Schedule Board
    st.subheader("📅 Today's Live Schedule Engine")
    cursor.execute("SELECT slot_time, status, physician_name FROM availability WHERE date = ?", (today_str,))
    slots_data = cursor.fetchall()
    
    if slots_data:
        st.table([{"Time Slot": s[0], "Status": s[1], "Physician": s[2]} for s in slots_data])
    else:
        st.warning("No availability published for today yet.")

    # Real-time AI Action Logs
    st.subheader("🤖 AI Real-Time Activity Log")
    cursor.execute("SELECT timestamp, action, details FROM ai_logs ORDER BY id DESC LIMIT 10")
    logs = cursor.fetchall()
    
    if logs:
        st.table([{"Timestamp": l[0], "Action": l[1], "Details": l[2]} for l in logs])
        
    conn.close()
