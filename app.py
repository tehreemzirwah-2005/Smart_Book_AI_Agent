
import os
import json
import sqlite3
from datetime import datetime
import streamlit as st
from openai import OpenAI

# 1. DATABASE SETUP
DB_NAME = "smartbook.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            physician_name TEXT, slot_time TEXT, status TEXT DEFAULT 'AVAILABLE', date TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT, client_phone TEXT, physician_name TEXT, slot_time TEXT, status TEXT DEFAULT 'CONFIRMED', date TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS waiting_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT, client_phone TEXT, preferred_date TEXT, status TEXT DEFAULT 'PENDING'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ai_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT, action TEXT, details TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    return sqlite3.connect(DB_NAME)

def log_ai_action(action, details):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO ai_logs (timestamp, action, details) VALUES (?, ?, ?)",
                   (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), action, details))
    conn.commit()
    conn.close()

# 2. BACKEND FUNCTIONS
def db_get_available_slots(date_str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT slot_time FROM availability WHERE date = ? AND status = 'AVAILABLE'", (date_str,))
    slots = [row[0] for row in cursor.fetchall()]
    conn.close()
    return slots

def db_book_appointment(client_name, client_phone, physician_name, slot_time, date_str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM availability WHERE date = ? AND slot_time = ? AND physician_name = ?", (date_str, slot_time, physician_name))
    row = cursor.fetchone()
    if not row or row[0] != 'AVAILABLE':
        conn.close()
        return {"success": False, "message": "Slot is no longer available."}
    cursor.execute("UPDATE availability SET status = 'CONFIRMED' WHERE date = ? AND slot_time = ? AND physician_name = ?", (date_str, slot_time, physician_name))
    cursor.execute("INSERT INTO appointments (client_name, client_phone, physician_name, slot_time, status, date) VALUES (?, ?, ?, ?, 'CONFIRMED', ?)",
                   (client_name, client_phone, physician_name, slot_time, date_str))
    conn.commit()
    conn.close()
    log_ai_action("BOOK_APPOINTMENT", f"Booked {slot_time} for {client_name}")
    return {"success": True, "message": f"Appointment confirmed for {slot_time} with {physician_name}."}

def db_cancel_appointment(client_phone, date_str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, slot_time, physician_name FROM appointments WHERE client_phone = ? AND date = ? AND status = 'CONFIRMED'", (client_phone, date_str))
    appt = cursor.fetchone()
    if not appt:
        conn.close()
        return {"success": False, "message": "No active appointment found."}
    appt_id, slot_time, physician_name = appt
    cursor.execute("UPDATE appointments SET status = 'CANCELLED' WHERE id = ?", (appt_id,))
    cursor.execute("UPDATE availability SET status = 'AVAILABLE' WHERE date = ? AND slot_time = ? AND physician_name = ?", (date_str, slot_time, physician_name))
    conn.commit()
    conn.close()
    log_ai_action("CANCEL_APPOINTMENT", f"Cancelled appt for {client_phone}.")
    return {"success": True, "message": "Appointment cancelled successfully."}

# 3. AI RECEPTIONIST ENGINE
tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "get_available_slots",
            "description": "Fetch available slots for a given date.",
            "parameters": {"type": "object", "properties": {"date_str": {"type": "string"}}, "required": ["date_str"]}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "client_name": {"type": "string"}, "client_phone": {"type": "string"},
                    "physician_name": {"type": "string"}, "slot_time": {"type": "string"}, "date_str": {"type": "string"}
                },
                "required": ["client_name", "client_phone", "physician_name", "slot_time", "date_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an appointment.",
            "parameters": {
                "type": "object",
                "properties": {"client_phone": {"type": "string"}, "date_str": {"type": "string"}},
                "required": ["client_phone", "date_str"]
            }
        }
    }
]

def run_ai_receptionist(user_prompt, conversation_history, api_key):
    if not api_key:
        return "⚠️ Please enter your OpenAI API Key in the sidebar!"
    
    client = OpenAI(api_key=api_key)
    system_instruction = f"You are SmartBook AI for ABC Medical Clinic. Today's Date: {datetime.now().strftime('%Y-%m-%d')}."
    messages = [{"role": "system", "content": system_instruction}] + conversation_history + [{"role": "user", "content": user_prompt}]
    
    response = client.chat.completions.create(model="gpt-4o", messages=messages, tools=tools_schema, tool_choice="auto")
    msg = response.choices[0].message
    
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            tool_result = {}
            if func_name == "get_available_slots":
                tool_result = {"available_slots": db_get_available_slots(args.get("date_str"))}
            elif func_name == "book_appointment":
                tool_result = db_book_appointment(args.get("client_name"), args.get("client_phone"), args.get("physician_name"), args.get("slot_time"), args.get("date_str"))
            elif func_name == "cancel_appointment":
                tool_result = db_cancel_appointment(args.get("client_phone"), args.get("date_str"))
            
            messages.append(msg)
            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": json.dumps(tool_result)})
        
        second_response = client.chat.completions.create(model="gpt-4o", messages=messages)
        return second_response.choices[0].message.content
        
    return msg.content

# 4. STREAMLIT UI
st.set_page_config(page_title="SmartBook Agent", layout="wide", page_icon="📅")
st.title("🤖 SmartBook Agent - AI Receptionist")

openai_key = st.sidebar.text_input("Enter OpenAI API Key:", type="password")
app_mode = st.sidebar.radio("Select View:", ["Physician Morning Setup", "Client AI Receptionist", "Admin SaaS Dashboard"])
today_str = datetime.now().strftime("%Y-%m-%d")

if app_mode == "Physician Morning Setup":
    st.header("👨‍⚕️ Physician Availability")
    slots_list = ["09:00 AM", "09:30 AM", "10:00 AM", "10:30 AM", "11:00 AM", "03:00 PM"]
    selected_slots = st.multiselect("Select today's available slots:", slots_list, default=slots_list[:4])
    if st.button("Publish Availability", type="primary"):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM availability WHERE date = ? AND status = 'AVAILABLE'", (today_str,))
        for slot in selected_slots:
            cursor.execute("INSERT INTO availability (physician_name, slot_time, status, date) VALUES (?, ?, 'AVAILABLE', ?)", ("Dr. Ahmed", slot, today_str))
        conn.commit()
        conn.close()
        st.success("🟢 Published successfully!")

elif app_mode == "Client AI Receptionist":
    st.header("💬 AI Receptionist Chat")
    if "messages" not in st.session_state:
        st.session_state.messages = []
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    if prompt := st.chat_input("Hi, I want to book an appointment with Dr. Ahmed today."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            conv_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[:-1]]
            res = run_ai_receptionist(prompt, conv_history, openai_key)
            st.markdown(res)
        st.session_state.messages.append({"role": "assistant", "content": res})

elif app_mode == "Admin SaaS Dashboard":
    st.header("📈 Admin Dashboard")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT slot_time, status, physician_name FROM availability WHERE date = ?", (today_str,))
    slots_data = cursor.fetchall()
    st.subheader("Today's Schedule")
    if slots_data:
        st.table([{"Time Slot": s[0], "Status": s[1], "Physician": s[2]} for s in slots_data])
    conn.close()
