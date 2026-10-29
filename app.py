import os
import re
import time
from dotenv import load_dotenv
from google import genai
import streamlit as st

# ---------- Environment & Configuration ----------
# Load local .env file (this will do nothing in the cloud, which is fine)
load_dotenv()

st.set_page_config(page_title="Duka Cash Flow Check", page_icon="📊", layout="centered")
st.title("📊 Duka Cash Flow Health Check")
st.caption("Paste M-Pesa SMS below. Get a simple monthly summary + 3 actionable tips.")

# Check for API key in Streamlit secrets first, then environment variables
api_key = st.secrets.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY")

if not api_key:
    st.error("⚠️ `GEMINI_API_KEY` not found. Please add it to your `.env` file locally, or Streamlit Secrets on the cloud.")
    st.stop()

# Initialize Gemini Client
client = genai.Client(api_key=api_key.strip())
MODEL_NAME = "gemini-3.8-flash" 

# ---------- M-Pesa SMS Parser ----------
PATTERNS = {
    "received": re.compile(
        r"([A-Z0-9]{10})\s+Confirmed\.\s*You have received Ksh([\d,]+\.?\d*) from (.+?) "
        r"(?:0\d{9}|\d{11}) on (\d{1,2}/\d{1,2}/\d{2,4}) at (\d{1,2}:\d{2}\s*[AP]M)",
        re.IGNORECASE,
    ),
    "sent": re.compile(
        r"([A-Z0-9]{10})\s+Confirmed\.\s*Ksh([\d,]+\.?\d*) sent to (.+?) "
        r"(?:0\d{9}|\d{11}) on (\d{1,2}/\d{1,2}/\d{2,4}) at (\d{1,2}:\d{2}\s*[AP]M)",
        re.IGNORECASE,
    ),
    "paybill": re.compile(
        r"([A-Z0-9]{10})\s+Confirmed\.\s*Ksh([\d,]+\.?\d*) paid to (.+?)\.?\s*"
        r"(?:Account|Business)\s*(.+?)\s*on (\d{1,2}/\d{1,2}/\d{2,4})",
        re.IGNORECASE,
    ),
    "buygoods": re.compile(
        r"([A-Z0-9]{10})\s+Confirmed\.\s*Ksh([\d,]+\.?\d*) paid to (.+?)\.?\s*"
        r"Till number\s*(\d+)\s*on (\d{1,2}/\d{1,2}/\d{2,4})",
        re.IGNORECASE,
    ),
}

def parse_sms(text: str) -> list[dict]:
    """Parse SMS lines into structured transaction objects."""
    txs = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        for kind, pat in PATTERNS.items():
            m = pat.search(line)
            if m:
                amount = float(m.group(2).replace(",", ""))
                txs.append({
                    "kind": kind,
                    "amount": amount,
                    "raw": line,
                    "direction": "in" if kind == "received" else "out",
                })
                break
    return txs

# ---------- Sample SMS (Demo) ----------
SAMPLE = """QAB1XYZ2CD Confirmed. You have received Ksh2,500.00 from MAMA NJERI 0712345678 on 5/6/26 at 9:15 AM
QAB1XYZ3EF Confirmed. Ksh450.00 sent to JANE WANJIKU 0723456789 on 5/6/26 at 10:20 AM
QAB1XYZ4GH Confirmed. Ksh1,200.00 paid to KPLC. Account 12345678 on 6/6/26
QAB1XYZ5IJ Confirmed. Ksh3,000.00 paid to NAIVAS SUPERMARKET. Till number 123456 on 7/6/26
QAB1XYZ6KL Confirmed. You have received Ksh1,800.00 from PETER OTIENO 0734567890 on 8/6/26 at 4:30 PM"""

# ---------- UI Inputs ----------
sms_text = st.text_area(
    "Paste your M-Pesa SMS messages (one per line)",
    value=st.session_state.get("sms", ""),
    height=180,
    placeholder="Example: QAB1XYZ2CD Confirmed. You have received Ksh2,500.00 from ...",
)

col1, col2 = st.columns([1, 1])
if col1.button("Load sample SMS"):
    st.session_state["sms"] = SAMPLE
    st.rerun()

st.subheader("Manual expenses (this month)")
c1, c2 = st.columns(2)
with c1:
    rent = st.number_input("Rent", min_value=0, value=8000, step=500)
    stock = st.number_input("Stock / inventory", min_value=0, value=15000, step=500)
    wages = st.number_input("Wages", min_value=0, value=6000, step=500)
with c2:
    transport = st.number_input("Transport", min_value=0, value=1500, step=100)
    other = st.number_input("Other", min_value=0, value=1000, step=100)

# ---------- Analysis & Processing ----------
if st.button("Analyze Cash Flow", type="primary"):
    active_sms = sms_text.strip()
    if not active_sms:
        st.warning("Please paste at least one M-Pesa SMS message.")
        st.stop()

    txs = parse_sms(active_sms)
    if not txs:
        st.warning("No recognizable M-Pesa transactions found. Check format.")
        st.stop()

    money_in = sum(t["amount"] for t in txs if t["direction"] == "in")
    money_out = sum(t["amount"] for t in txs if t["direction"] == "out")
    total_expenses = rent + stock + wages + transport + other
    net = money_in - money_out - total_expenses

    # Metric Cards
    m1, m2, m3 = st.columns(3)
    m1.metric("Money In (M-Pesa)", f"KES {money_in:,.0f}")
    m2.metric("Total Out", f"KES {money_out + total_expenses:,.0f}")
    m3.metric("Net Cash Flow", f"KES {net:,.0f}", delta=f"{net:,.0f}")

    # Expense breakdown table
    st.subheader("Expense breakdown")
    expense_data = {
        "Category": ["Rent", "Stock", "Wages", "Transport", "Other", "M-Pesa Outflow"],
        "Amount (KES)": [rent, stock, wages, transport, other, money_out],
    }
    st.table(expense_data)

    # ---------- Gemini Call ----------
    st.subheader("💡 3 Actionable Recommendations")

    prompt = f"""You are a friendly financial advisor for a small duka (shop) owner in Nairobi.
You speak in simple English, mixed with a little Swahili where natural. No accounting jargon.

Here is this month's data (KES):
- Money received via M-Pesa: {money_in:,.0f}
- Money sent/paid via M-Pesa: {money_out:,.0f}
- Rent: {rent:,.0f}
- Stock: {stock:,.0f}
- Wages: {wages:,.0f}
- Transport: {transport:,.0f}
- Other expenses: {other:,.0f}
- Net cash flow: {net:,.0f}
- Number of parsed M-Pesa transactions: {len(txs)}

Give EXACTLY 3 short, practical recommendations the owner can act on this month.
Each recommendation must be one sentence, starting with a verb.
Do not use bullet points. Number them 1, 2, 3.
If net cash flow is negative, the first recommendation must directly address it.
Keep the total response under 80 words."""

    with st.spinner("Analyzing with Gemini 3.8 Flash..."):
        max_retries = 3
        response_text = None

        for attempt in range(max_retries):
            try:
                # Standard generation call (no custom unsupported parameters)
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=prompt,
                )
                response_text = response.text
                break
            except Exception as e:
                err_msg = str(e)
                if ("503" in err_msg or "UNAVAILABLE" in err_msg or "429" in err_msg) and attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    time.sleep(wait_time)
                    continue
                else:
                    st.error(f"Gemini service unavailable: {e}")
                    st.info("The model is currently experiencing temporary high demand. Please try clicking Analyze again in a few moments.")
                    break

        if response_text:
            st.success("Recommendations Generated")
            st.markdown(response_text)