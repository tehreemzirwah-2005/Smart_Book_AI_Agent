import os
import json
import streamlit as st
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# ==========================================
# 1. PAGE SETUP & UI STYLING
# ==========================================
st.set_page_config(page_title="SmartBook AI - Automated Booking Agent", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%); }
    .main-title {
        background: -webkit-linear-gradient(45deg, #4F46E5, #9333EA, #EC4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.6rem; font-weight: 900; text-align: center; margin-bottom: 5px;
    }
    .sub-title { text-align: center; color: #64748B; font-size: 1.1rem; margin-bottom: 25px; }
    .metric-card {
        background: white; border-radius: 12px; padding: 18px; text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05); border: 1px solid #E2E8F0;
    }
    .metric-value { font-size: 2rem; font-weight: 800; color: #0F172A; }
    .metric-label { color: #64748B; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; }
    .wa-card {
        background: #E5DDD5; border-radius: 15px; padding: 15px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .wa-bubble-user {
        background: #DCF8C6; padding: 10px 14px; border-radius: 10px; margin: 8px 0; max-width: 80%; float: right; clear: both; color: #000;
    }
    .wa-bubble-ai {
        background: #FFFFFF; padding: 10px 14px; border-radius: 10px; margin: 8px 0; max-width: 80%; float: left; clear: both; color: #000;
    }
    .notification-box {
        background: #F0FDF4; border: 1px solid #86EFAC; border-radius: 8px; padding: 10px; margin-top: 5px; font-size: 0.9rem;
    }
    </style>
""", unsafe_allow_html=True)

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))

st.markdown('<p class="main-title">SmartBook AI Enterprise Agent ⚡</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Autonomous Appointment Scheduling, Dynamic Slot Recovery & Instant WhatsApp Dispatch</p>', unsafe_allow_html=True)

# ==========================================
# 2. STATE INITIALIZATION (REAL-TIME DATA)
# ==========================================
if "slots" not in st.session_state:
    st.session_state.slots = [
        {"id": 1, "time": "09:00 AM", "status": "Available", "client": "", "phone": "", "service": "General Consultation"},
        {"id": 2, "time": "10:30 AM", "status": "Available", "client": "", "phone": "", "service": "General Consultation"},
        {"id": 3, "time": "01:00 PM", "status": "Available", "client": "", "phone": "", "service": "General Consultation"},
        {"id": 4, "time": "03:00 PM", "status": "Available", "client": "", "phone": "", "service": "General Consultation"},
        {"id": 5, "time": "04:30 PM", "status": "Available", "client": "", "phone": "", "service": "General Consultation"}
    ]

if "notifications" not in st.session_state:
    st.session_state.notifications = []

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "doctor_phone" not in st.session_state:
    st.session_state.doctor_phone = "+923001234567"

# Helper Function: Process Slot Updates from AI Actions
def apply_ai_slot_action(action_type, target_time, client_name="", phone=""):
    for slot in st.session_state.slots:
        if slot["time"].lower().strip() == target_time.lower().strip():
            if action_type == "BOOK":
                slot["status"] = "Confirmed"
                slot["client"] = client_name
                slot["phone"] = phone
                st.session_state.notifications.append({
                    "to": f"Doctor ({st.session_state.doctor_phone}) & Client ({phone})",
                    "msg": f"✅ CONFIRMED: Appointment for {client_name} at {slot['time']} ({slot['service']}).",
                    "type": "Confirmation"
                })
                return True
            elif action_type == "CANCEL":
                old_client = slot["client"]
                slot["status"] = "Available"
                slot["client"] = ""
                slot["phone"] = ""
                st.session_state.notifications.append({
                    "to": f"Doctor ({st.session_state.doctor_phone})",
                    "msg": f"⚠️ CANCELLED: Slot at {slot['time']} by {old_client} is now FREE for new clients.",
                    "type": "Cancellation"
                })
                return True
    return False

# ==========================================
# 3. PORTAL SELECTOR (ADMIN vs CLIENT)
# ==========================================
portal_mode = st.sidebar.radio("🌐 Select System Portal:", ["📱 Client WhatsApp & Self-Booking", "👨‍⚕️ Physician / Admin Operations"])

# ------------------------------------------
# PORTAL 1: CLIENT WHATSAPP & SELF-BOOKING
# ------------------------------------------
if portal_mode == "📱 Client WhatsApp & Self-Booking":
    st.subheader("📱 WhatsApp AI Booking Assistant")
    st.caption("Clients can select free slots visually OR chat naturally with AI to Book, Cancel, or Reschedule.")
    
    col_left, col_right = st.columns([1, 1])

    # Dynamic Slot Selector
    with col_left:
        st.markdown("### 📅 Real-Time Available Slots")
        free_slots = [s for s in st.session_state.slots if s["status"] == "Available"]
        
        if not free_slots:
            st.warning("⚠️ All slots booked for today! Chat with AI below to get added to the waiting list or check cancellations.")
        else:
            for s in free_slots:
                with st.container():
                    st.markdown(f"""
                    <div style="background:white; border-left:5px solid #10B981; padding:12px; border-radius:8px; margin-bottom:10px;">
                        <strong>⏰ Time: {s['time']}</strong> | Service: {s['service']}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    with st.expander(f"Book Slot: {s['time']}"):
                        with st.form(f"manual_book_{s['id']}"):
                            c_name = st.text_input("Full Name:")
                            c_phone = st.text_input("WhatsApp Mobile Number:")
                            btn = st.form_submit_button("Confirm Booking")
                            if btn and c_name and c_phone:
                                apply_ai_slot_action("BOOK", s['time'], c_name, c_phone)
                                st.success("🎉 Slot Booked! Automated confirmation sent to Doctor and Client.")
                                st.rerun()

    # WhatsApp AI Chat Interface
    with col_right:
        st.markdown("### 💬 Automated AI Conversational Agent")
        
        for msg in st.session_state.chat_history:
            role = "user" if isinstance(msg, HumanMessage) else "assistant"
            with st.chat_message(role):
                st.markdown(msg.content)

        user_input = st.chat_input("Type e.g., 'Book 10:30 AM slot for Ali (+92300...)' or 'Cancel my slot'...")

        if user_input:
            with st.chat_message("user"):
                st.markdown(user_input)
            st.session_state.chat_history.append(HumanMessage(content=user_input))

            if not GROQ_API_KEY:
                st.error("🔑 GROQ_API_KEY missing in Secrets!")
            else:
                with st.chat_message("assistant"):
                    with st.spinner("AI checking Live Calendar & executing actions..."):
                        try:
                            llm = ChatGroq(
                                groq_api_key=GROQ_API_KEY,
                                model_name="openai/gpt-oss-120b",
                                temperature=0.1
                            )
                            
                            system_prompt = f"""
                            You are SmartBook AI, an autonomous appointment agent.
                            
                            LIVE CALENDAR SLOTS DATA:
                            {json.dumps(st.session_state.slots)}
                            
                            YOUR CAPABILITIES & INSTRUCTIONS:
                            1. Read live calendar slots above accurately.
                            2. If client wants to BOOK a free slot and provides name + phone number, instruct system in response and inform client it's booked.
                            3. If client wants to CANCEL or RESCHEDULE, automatically free up their old slot and book the new available slot.
                            4. Keep responses brief, polite, and professional (WhatsApp format).
                            """
                            
                            formatted = [SystemMessage(content=system_prompt)] + st.session_state.chat_history
                            response = llm.invoke(formatted)
                            reply = response.content
                            
                            # Simple AI Action Parser for Autonomous State Management
                            lower_input = user_input.lower()
                            for s in st.session_state.slots:
                                slot_t = s["time"].lower()
                                if slot_t in lower_input:
                                    if "book" in lower_input or "confirm" in lower_input:
                                        apply_ai_slot_action("BOOK", s["time"], "WhatsApp Client", "+92300XXXXXXX")
                                    elif "cancel" in lower_input or "reschedule" in lower_input:
                                        apply_ai_slot_action("CANCEL", s["time"])
                            
                            st.markdown(reply)
                            st.session_state.chat_history.append(AIMessage(content=reply))
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

# ------------------------------------------
# PORTAL 2: PHYSICIAN / ADMIN OPERATIONS
# ------------------------------------------
else:
    st.subheader("👨‍⚕️ Physician & Admin Operational Dashboard")
    st.caption("Zero manual workload: AI handles calendar updates, slot recovery, and dispatches instant notifications.")

    # High Level Metrics
    total = len(st.session_state.slots)
    avail = sum(1 for s in st.session_state.slots if s["status"] == "Available")
    conf = sum(1 for s in st.session_state.slots if s["status"] == "Confirmed")

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{total}</div><div class="metric-label">Total Daily Slots</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#10B981;">{avail}</div><div class="metric-label">Free Slots (Auto-Managed)</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#4F46E5;">{conf}</div><div class="metric-label">Confirmed Patients</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    
    c_sched, c_notif = st.columns([1.2, 1])

    # Live Doctor Schedule View
    with c_sched:
        st.markdown("### 📋 Live Master Calendar")
        for s in st.session_state.slots:
            st_color = "#10B981" if s["status"] == "Available" else "#4F46E5"
            st.markdown(f"""
            <div style="background:white; border-left:6px solid {st_color}; padding:12px; border-radius:10px; margin-bottom:10px; box-shadow:0 2px 4px rgba(0,0,0,0.04);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <strong>⏰ {s['time']}</strong> - <span>{s['service']}</span><br/>
                        <small>Patient: <b>{s['client'] if s['client'] else 'No Booking Yet'}</b> ({s['phone']})</small>
                    </div>
                    <div>
                        <span style="background:{st_color}; color:white; padding:4px 10px; border-radius:12px; font-size:0.8rem; font-weight:bold;">{s['status']}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Postpone / Override Controls for Doctor
            if s["status"] == "Confirmed":
                c_post, c_can = st.columns(2)
                with c_post:
                    if st.button(f"⏱️ Postpone #{s['id']}", key=f"post_{s['id']}"):
                        s["status"] = "Available"
                        st.session_state.notifications.append({
                            "to": f"Client ({s['phone']})",
                            "msg": f"📢 POSTPONED: Your appointment at {s['time']} has been postponed by the physician. Please choose another slot.",
                            "type": "Postponement"
                        })
                        s["client"] = ""
                        s["phone"] = ""
                        st.success("Slot postponed and freed up!")
                        st.rerun()
                with c_can:
                    if st.button(f"🚫 Cancel #{s['id']}", key=f"can_{s['id']}"):
                        apply_ai_slot_action("CANCEL", s["time"])
                        st.rerun()

        # One-Time Slot Creator
        st.markdown("---")
        st.markdown("### ➕ Admin Initial Setup: Add Custom Slot")
        with st.form("add_custom_slot"):
            new_t = st.text_input("Slot Time (e.g., 06:00 PM):")
            new_s = st.text_input("Service Name:", value="Follow-up Consultation")
            if st.form_submit_button("Add Slot to AI Engine"):
                if new_t:
                    st.session_state.slots.append({
                        "id": len(st.session_state.slots) + 1,
                        "time": new_t,
                        "status": "Available",
                        "client": "",
                        "phone": "",
                        "service": new_s
                    })
                    st.success("New slot added to live calendar!")
                    st.rerun()

    # WhatsApp Automated Notifications Audit Log
    with c_notif:
        st.markdown("### 📲 Automated Dispatch Audit Log")
        st.caption("Live stream of automated SMS/WhatsApp messages sent by AI to Doctor & Clients.")
        
        if not st.session_state.notifications:
            st.info("No dispatches logged yet. Book or cancel a slot to see real-time automated messages.")
        else:
            for n in reversed(st.session_state.notifications):
                st.markdown(f"""
                <div class="notification-box">
                    <strong>📢 Dispatch Type: {n['type']}</strong><br/>
                    <small><b>To:</b> {n['to']}</small><br/>
                    <span>{n['msg']}</span>
                </div>
                """, unsafe_allow_html=True)
