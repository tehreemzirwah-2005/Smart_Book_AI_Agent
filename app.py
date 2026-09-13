import os
import streamlit as st
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# ==========================================
# 1. PAGE SETUP & GRADIENT STYLING
# ==========================================
st.set_page_config(page_title="SmartBook AI Agent", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(135deg, #F8FAFC 0%, #EFF6FF 100%);
    }
    .main-title {
        background: -webkit-linear-gradient(45deg, #4F46E5, #9333EA, #EC4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.8rem;
        font-weight: 900;
        text-align: center;
        margin-bottom: 5px;
    }
    .sub-title {
        text-align: center; color: #64748B; font-size: 1.1rem; margin-bottom: 30px;
    }
    .stButton>button {
        background: linear-gradient(90deg, #4F46E5 0%, #7C3AED 100%);
        color: white; font-weight: 700; border-radius: 10px; padding: 0.65rem 1.2rem;
        border: none; width: 100%; box-shadow: 0 4px 14px 0 rgba(79, 70, 229, 0.39);
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px 0 rgba(79, 70, 229, 0.5);
        color: white;
    }
    .metric-card {
        background: white; border-radius: 16px; padding: 20px; text-align: center;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05); border: 1px solid #E2E8F0;
    }
    .metric-value { font-size: 2.2rem; font-weight: 800; color: #0F172A; }
    .metric-label { color: #64748B; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
    .chat-box {
        background: white; border-radius: 12px; padding: 15px; border: 1px solid #E2E8F0; margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# Fetching Groq API Key
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("GROQ_API_KEY"))

st.markdown('<p class="main-title">SmartBook AI Agent ⚡</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Automate Appointments, Eliminate No-Shows & Recover Lost Revenue</p>', unsafe_allow_html=True)

# ==========================================
# 2. SESSION STATE DATA SETUP
# ==========================================
if "appointments" not in st.session_state:
    st.session_state.appointments = [
        {"id": 1, "client": "Sarah Khan", "time": "10:00 AM", "service": "Hair Styling", "status": "Confirmed", "phone": "+923001234567"},
        {"id": 2, "client": "Ali Raza", "time": "11:30 AM", "service": "Consultation", "status": "Pending Confirmation", "phone": "+923007654321"},
        {"id": 3, "client": "Usman Malik", "time": "02:00 PM", "service": "Dental Checkup", "status": "Cancelled", "phone": "+923009998877"},
        {"id": 4, "client": "Zainab Ahmed", "time": "04:30 PM", "service": "Facial Spa", "status": "Confirmed", "phone": "+923004445566"},
    ]

if "business_kb" not in st.session_state:
    st.session_state.business_kb = """
    Business Name: Luxe Glow Studio & Clinic
    Operating Hours: Monday to Saturday (9:00 AM - 8:00 PM)
    Cancellation Policy: 2 hours advance notice required for full refund or free rescheduling.
    Late Policy: 15 minutes late arrival results in automatic slot release to waiting list.
    Pricing: Hair styling = $30, Dental Consultation = $50, Spa Treatment = $60.
    """

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ==========================================
# 3. NAVIGATION TABS
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Revenue & Live Dashboard", 
    "🧠 RAG Business Brain", 
    "📅 Calendar Management", 
    "💬 WhatsApp AI Simulator"
])

# ------------------------------------------
# TAB 1: LIVE DASHBOARD
# ------------------------------------------
with tab1:
    st.markdown("### 📈 Real-Time Business Performance")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown('<div class="metric-card"><div class="metric-value">4</div><div class="metric-label">Total Appointments</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="metric-card"><div class="metric-value" style="color:#10B981;">75%</div><div class="metric-label">AI Response Rate</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="metric-card"><div class="metric-value" style="color:#EF4444;">1</div><div class="metric-label">Slot Recovered</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown('<div class="metric-card"><div class="metric-value" style="color:#6366F1;">$180</div><div class="metric-label">Revenue Saved Today</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 📋 Today's Live Schedule")
    
    for appt in st.session_state.appointments:
        status_color = "#10B981" if appt['status'] == "Confirmed" else ("#F59E0B" if appt['status'] == "Pending Confirmation" else "#EF4444")
        st.markdown(f"""
            <div class="chat-box" style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <strong>👤 {appt['client']}</strong> ({appt['service']})<br/>
                    <small>⏰ Time: {appt['time']} | 📱 {appt['phone']}</small>
                </div>
                <div>
                    <span style="background:{status_color}; color:white; padding:4px 12px; border-radius:20px; font-size:0.85rem; font-weight:bold;">{appt['status']}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

# ------------------------------------------
# TAB 2: RAG KNOWLEDGE BASE
# ------------------------------------------
with tab2:
    st.markdown("### 🧠 Train AI Agent Knowledge Base (RAG)")
    st.info("💡 Write your business policies below. Groq AI will strictly follow these rules during customer chats.")
    
    updated_kb = st.text_area("Custom Business Knowledge Base:", value=st.session_state.business_kb, height=200)
    
    if st.button("💾 Save Knowledge Base"):
        st.session_state.business_kb = updated_kb
        st.success("✅ AI Knowledge Base updated and saved!")

# ------------------------------------------
# TAB 3: CALENDAR MANAGEMENT
# ------------------------------------------
with tab3:
    st.markdown("### 📅 Quick Slot Booking (Staff View)")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        new_client = st.text_input("Client Name:")
    with c2:
        new_time = st.selectbox("Slot Time:", ["09:00 AM", "10:30 AM", "01:00 PM", "03:00 PM", "05:00 PM"])
    with c3:
        new_service = st.text_input("Service Name:", value="General Consultation")

    if st.button("➕ Manual Slot Book"):
        if new_client:
            st.session_state.appointments.append({
                "id": len(st.session_state.appointments) + 1,
                "client": new_client,
                "time": new_time,
                "service": new_service,
                "status": "Confirmed",
                "phone": "+923000000000"
            })
            st.success(f"Slot booked for {new_client} at {new_time}!")
            st.rerun()

# ------------------------------------------
# TAB 4: WHATSAPP SIMULATOR (GROQ ENGINE)
# ------------------------------------------
with tab4:
    st.markdown("### 💬 WhatsApp AI Agent Simulator")
    st.caption("Test how your AI agent talks with clients on WhatsApp 24 hours before their appointment.")

    # Display History
    for msg in st.session_state.chat_history:
        role = "user" if isinstance(msg, HumanMessage) else "assistant"
        with st.chat_message(role):
            st.markdown(msg.content)

    # User Input
    user_msg = st.chat_input("Type customer reply (e.g., 'I want to cancel my 11:30 AM appointment')...")

    if user_msg:
        with st.chat_message("user"):
            st.markdown(user_msg)
        st.session_state.chat_history.append(HumanMessage(content=user_msg))

        if not GROQ_API_KEY:
            st.error("🔑 GROQ_API_KEY nahi mili! Streamlit Secrets mein 'GROQ_API_KEY' add karein.")
        else:
            with st.chat_message("assistant"):
                with st.spinner("SmartBook Groq AI Agent is typing..."):
                    try:
                        # Exact Verified Groq Active Model Setup
                        llm = ChatGroq(
                            groq_api_key=GROQ_API_KEY,
                            model_name="openai/gpt-oss-120b",
                            temperature=0.3
                        )
                        
                        system_prompt = f"""
                        You are SmartBook AI, a professional WhatsApp appointment assistant for small businesses.
                        
                        BUSINESS KNOWLEDGE BASE:
                        {st.session_state.business_kb}
                        
                        CURRENT APPOINTMENTS:
                        {st.session_state.appointments}
                        
                        RULES:
                        1. Be polite, concise, and natural (WhatsApp style).
                        2. If client wants to cancel/reschedule, handle it according to the business knowledge base.
                        3. Maximum 2-3 short sentences per response.
                        """
                        
                        formatted = [SystemMessage(content=system_prompt)] + st.session_state.chat_history
                        response = llm.invoke(formatted)
                        
                        st.markdown(response.content)
                        st.session_state.chat_history.append(AIMessage(content=response.content))
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
