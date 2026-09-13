import os
import streamlit as st
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# ==========================================
# 1. PAGE SETUP & STYLING
# ==========================================
st.set_page_config(page_title="SmartBook AI Agent", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    .stApp { background: linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%); }
    .main-title {
        background: -webkit-linear-gradient(45deg, #4F46E5, #9333EA, #EC4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem; font-weight: 900; text-align: center; margin-bottom: 5px;
    }
    .sub-title { text-align: center; color: #64748B; font-size: 1rem; margin-bottom: 25px; }
    .metric-card {
        background: white; border-radius: 12px; padding: 15px; text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #E2E8F0;
    }
    .metric-value { font-size: 1.8rem; font-weight: 800; color: #0F172A; }
    .metric-label { color: #64748B; font-size: 0.8rem; font-weight: 600; text-transform: uppercase; }
    .slot-card {
        background: white; border-radius: 10px; padding: 12px; margin-bottom: 10px;
        border-left: 5px solid #CBD5E1; box-shadow: 0 2px 5px rgba(0,0,0,0.03);
    }
    </style>
""", unsafe_allow_html=True)

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))

st.markdown('<p class="main-title">SmartBook AI System ⚡</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Real-time Slot Booking, Dynamic Dashboard & AI WhatsApp Support</p>', unsafe_allow_html=True)

# ==========================================
# 2. DYNAMIC SESSION STATE (NO DUMMY DATA)
# ==========================================
if "slots" not in st.session_state:
    # Stores slot objects: {"id": 1, "time": "10:00 AM", "service": "Consultation", "status": "Available", "client": "", "phone": ""}
    st.session_state.slots = []

if "business_kb" not in st.session_state:
    st.session_state.business_kb = "Operating Hours: 9 AM - 5 PM. Policy: Cancel at least 2 hours before your slot."

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ==========================================
# 3. NAVIGATION (SEPARATE PANELS)
# ==========================================
admin_tab, client_tab = st.tabs([
    "👨‍💼 Consultant / Admin Dashboard", 
    "📱 Client WhatsApp & Slot Booking"
])

# ------------------------------------------
# PANEL 1: ADMIN & CONSULTANT DASHBOARD
# ------------------------------------------
with admin_tab:
    st.subheader("🛠️ Admin Controls & Live Metrics")
    
    # Real-Time Metrics Calculation
    total_slots = len(st.session_state.slots)
    available_slots = sum(1 for s in st.session_state.slots if s['status'] == "Available")
    pending_slots = sum(1 for s in st.session_state.slots if s['status'] == "Pending Confirmation")
    confirmed_slots = sum(1 for s in st.session_state.slots if s['status'] == "Confirmed")
    
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{total_slots}</div><div class="metric-label">Total Slots</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#10B981;">{available_slots}</div><div class="metric-label">Free Slots</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#F59E0B;">{pending_slots}</div><div class="metric-label">Pending Approval</div></div>', unsafe_allow_html=True)
    with m4:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#6366F1;">{confirmed_slots}</div><div class="metric-label">Confirmed Bookings</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    
    col_add, col_list = st.columns([1, 2])
    
    # Form to add new manual slots
    with col_add:
        st.markdown("### ➕ Create New Free Slot")
        with st.form("add_slot_form", clear_on_submit=True):
            slot_time = st.text_input("Slot Time (e.g., 11:00 AM):")
            slot_service = st.text_input("Service Name (e.g., General Audit):")
            submit_slot = st.form_submit_button("Publish Free Slot")
            
            if submit_slot and slot_time and slot_service:
                new_id = len(st.session_state.slots) + 1
                st.session_state.slots.append({
                    "id": new_id,
                    "time": slot_time,
                    "service": slot_service,
                    "status": "Available",
                    "client": "",
                    "phone": ""
                })
                st.success(f"Slot {slot_time} added successfully!")
                st.rerun()

        st.markdown("### 🧠 Business Knowledge Base")
        kb_input = st.text_area("Update Business Rules (for AI Agent):", value=st.session_state.business_kb, height=120)
        if st.button("Save Knowledge Base"):
            st.session_state.business_kb = kb_input
            st.success("Rules updated!")

    # Live schedule management for Admin
    with col_list:
        st.markdown("### 📋 Schedule & Booking Approvals")
        if not st.session_state.slots:
            st.info("No slots available. Add slots using the form on the left.")
        else:
            for s in st.session_state.slots:
                border_color = "#10B981" if s['status'] == "Available" else ("#F59E0B" if s['status'] == "Pending Confirmation" else "#4F46E5")
                st.markdown(f"""
                <div class="slot-card" style="border-left-color: {border_color};">
                    <strong>⏰ {s['time']}</strong> | Service: <b>{s['service']}</b><br/>
                    Status: <b>{s['status']}</b> | Client: {s['client'] if s['client'] else 'None'} ({s['phone']})
                </div>
                """, unsafe_allow_html=True)
                
                # Action Buttons for Pending Requests
                if s['status'] == "Pending Confirmation":
                    c_acc, c_rej = st.columns(2)
                    with c_acc:
                        if st.button(f"✅ Confirm #{s['id']}", key=f"conf_{s['id']}"):
                            s['status'] = "Confirmed"
                            st.rerun()
                    with c_rej:
                        if st.button(f"❌ Reject #{s['id']}", key=f"rej_{s['id']}"):
                            s['status'] = "Available"
                            s['client'] = ""
                            s['phone'] = ""
                            st.rerun()

# ------------------------------------------
# PANEL 2: CLIENT PORTAL & WHATSAPP SIMULATOR
# ------------------------------------------
with client_tab:
    c_book, c_chat = st.columns([1, 1])
    
    # Available Slots View for Client
    with c_book:
        st.markdown("### 📅 Available Slots (Client View)")
        available_list = [s for s in st.session_state.slots if s['status'] == "Available"]
        
        if not available_list:
            st.warning("No free slots currently available. Please check back later or ask AI!")
        else:
            for s in available_list:
                with st.expander(f"🟢 {s['time']} - {s['service']}"):
                    with st.form(f"book_form_{s['id']}"):
                        c_name = st.text_input("Your Name:")
                        c_phone = st.text_input("Your Phone Number:")
                        btn_submit = st.form_submit_button("Request Slot Booking")
                        
                        if btn_submit and c_name and c_phone:
                            s['status'] = "Pending Confirmation"
                            s['client'] = c_name
                            s['phone'] = c_phone
                            st.success("Booking request sent! Awaiting consultant confirmation.")
                            st.rerun()

    # WhatsApp AI Simulator
    with c_chat:
        st.markdown("### 💬 WhatsApp Support AI")
        st.caption("Ask AI about free slots, policy rules, or manage your bookings.")

        for msg in st.session_state.chat_history:
            role = "user" if isinstance(msg, HumanMessage) else "assistant"
            with st.chat_message(role):
                st.markdown(msg.content)

        user_msg = st.chat_input("Type e.g., 'What slots are free today?'...")

        if user_msg:
            with st.chat_message("user"):
                st.markdown(user_msg)
            st.session_state.chat_history.append(HumanMessage(content=user_msg))

            if not GROQ_API_KEY:
                st.error("🔑 GROQ_API_KEY Missing in Streamlit Secrets!")
            else:
                with st.chat_message("assistant"):
                    with st.spinner("AI Agent is checking live calendar..."):
                        try:
                            llm = ChatGroq(
                                groq_api_key=GROQ_API_KEY,
                                model_name="openai/gpt-oss-120b",
                                temperature=0.3
                            )
                            
                            system_prompt = f"""
                            You are SmartBook WhatsApp Assistant.
                            
                            DYNAMIC BUSINESS KNOWLEDGE BASE:
                            {st.session_state.business_kb}
                            
                            LIVE REAL-TIME SLOTS DATA:
                            {st.session_state.slots}
                            
                            INSTRUCTIONS:
                            1. Strictly read live slots data above.
                            2. Answer client questions about free/available slots accurately based on real data.
                            3. Keep responses natural, concise (WhatsApp style), and helpful.
                            """
                            
                            formatted = [SystemMessage(content=system_prompt)] + st.session_state.chat_history
                            response = llm.invoke(formatted)
                            
                            st.markdown(response.content)
                            st.session_state.chat_history.append(AIMessage(content=response.content))
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
