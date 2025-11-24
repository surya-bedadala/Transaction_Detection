import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime, date
from PIL import Image
import pytesseract
import re
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from io import BytesIO

# ---------- CONFIG ----------
DATA_DIR = Path("data")
LOG_FILE = DATA_DIR / "payments_log.xlsx"

# Colab lo Tesseract path set cheyyalsina avasaram ledu.
# Local Windows lo install chesaka path kavali ante:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# ---------- STORAGE HELPERS ----------

def init_storage():
    DATA_DIR.mkdir(exist_ok=True)
    if not LOG_FILE.exists():
        df = pd.DataFrame(columns=[
            "record_id",
            "upload_time",
            "file_name",
            "txn_date",
            "txn_time",
            "amount",
            "is_date_match",
            "extracted_text"
        ])
        df.to_excel(LOG_FILE, index=False)


def load_log():
    if LOG_FILE.exists():
        return pd.read_excel(LOG_FILE)
    else:
        return pd.DataFrame(columns=[
            "record_id",
            "upload_time",
            "file_name",
            "txn_date",
            "txn_time",
            "amount",
            "is_date_match",
            "extracted_text"
        ])


def clean_excel_string(v):
    """Excel ki save cheyyadaniki mundu illegal chars remove chesthundi."""
    if isinstance(v, str):
        return ILLEGAL_CHARACTERS_RE.sub("", v)
    return v


def save_log(df: pd.DataFrame):
    # String columns clean cheyyadam
    for col in ["file_name", "extracted_text"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_excel_string)
    df.to_excel(LOG_FILE, index=False)


# ---------- OCR HELPERS ----------

def extract_text_from_image(image: Image.Image) -> str:
    # OCR improve kosam grayscale
    img_gray = image.convert("L")
    text = pytesseract.image_to_string(img_gray)
    return text


def extract_date(text: str):
    """
    Text lo date patterns kanukoni Python date ga marchadaniki try chesthundi.
    Support: 11/11/2025, 11-11-2025, 11 Nov 2025, 11 November 2025
    """
    patterns = [
        (r"\b\d{2}/\d{2}/\d{4}\b", ["%d/%m/%Y", "%m/%d/%Y"]),
        (r"\b\d{2}-\d{2}-\d{4}\b", ["%d-%m-%Y", "%m-%d-%Y"]),
        (r"\b\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\b", ["%d %b %Y"]),
        (r"\b\d{1,2}\s+[A-Za-z]{4,9}\s+\d{4}\b", ["%d %B %Y"]),
    ]

    for pattern, formats in patterns:
        m = re.search(pattern, text)
        if m:
            date_str = m.group().strip()
            for fmt in formats:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.date()
                except ValueError:
                    continue
    return None


def extract_time(text: str):
    """
    Text lo time pattern kanukuntundi: 10:35, 10:35 AM, 2:05 pm
    """
    m = re.search(r"\b\d{1,2}:\d{2}\s?(AM|PM|am|pm)?\b", text)
    if not m:
        return None

    time_str = m.group().strip()
    for fmt in ["%I:%M %p", "%H:%M"]:
        try:
            t = datetime.strptime(time_str, fmt).time()
            return t
        except ValueError:
            continue
    return None


def extract_amount(text: str):
    """
    Amount detect cheyyali: ₹ 1,234.50 / Rs 1,234 / INR 1234
    """
    m = re.search(r"₹\s*([\d,]+\.?\d*)", text)
    if m:
        num_str = m.group(1).replace(",", "")
        try:
            return float(num_str)
        except ValueError:
            return None

    m2 = re.search(r"(?:Rs\.?|INR)\s*([\d,]+\.?\d*)", text, re.IGNORECASE)
    if m2:
        num_str = m2.group(1).replace(",", "")
        try:
            return float(num_str)
        except ValueError:
            return None

    return None


def extract_info_from_image(image: Image.Image):
    text = extract_text_from_image(image)
    txn_date = extract_date(text)
    txn_time = extract_time(text)
    amount = extract_amount(text)

    return {
        "extracted_text": text,
        "txn_date": txn_date,
        "txn_time": txn_time,
        "amount": amount,
    }


# ---------- STREAMLIT APP ----------

def main():
    st.set_page_config(page_title="Payment Screenshot Checker", layout="wide")

    init_storage()
    log_df = load_log()

    st.title("📷 Payment Screenshot Checker")
    st.write("Payment screenshots upload chesi, **date eroju date ki match ayinda leda** check cheyyadaniki tool.")

    # Sidebar - Expected date
    st.sidebar.header("Settings")
    expected_date = st.sidebar.date_input("Expected payment date", value=date.today())
    st.sidebar.write("Ee date tho screenshot lo unna date compare chestham.")

    st.markdown("### 1️⃣ Upload Payment Screenshots")
    uploaded_files = st.file_uploader(
        "Multiple screenshots select chesi upload cheyyi (PNG/JPG).",
        type=["png", "jpg", "jpeg"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        st.info(f"{len(uploaded_files)} file(s) upload chesavu. 'Process Screenshots' click chey👇")

        if st.button("Process Screenshots"):
            new_records = []
            for i, file in enumerate(uploaded_files, start=1):
                try:
                    image = Image.open(file)
                except Exception as e:
                    st.error(f"{file.name} open cheyyaledu: {e}")
                    continue

                info = extract_info_from_image(image)

                is_match = False
                if isinstance(info["txn_date"], date):
                    is_match = (info["txn_date"] == expected_date)

                record = {
                    "record_id": f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}",
                    "upload_time": datetime.now(),
                    "file_name": file.name,
                    "txn_date": info["txn_date"],
                    "txn_time": info["txn_time"],
                    "amount": info["amount"],
                    "is_date_match": is_match,
                    "extracted_text": info["extracted_text"],
                }
                new_records.append(record)

            if new_records:
                new_df = pd.DataFrame(new_records)
                log_df = pd.concat([log_df, new_df], ignore_index=True)
                save_log(log_df)
                st.success(f"{len(new_records)} screenshot(s) process ayyayi & Excel log lo save ayyayi.")

    st.markdown("### 2️⃣ Processed Payments & Daily Report")

    log_df = load_log()
    if log_df.empty:
        st.info("Inka records levu. Mundu screenshots process cheyyi.")
    else:
        # txn_date column ni date type ga marchadam (filter easy ga undadaniki)
        if "txn_date" in log_df.columns:
            log_df["txn_date"] = pd.to_datetime(log_df["txn_date"], errors="coerce").dt.date

        filter_date = st.date_input("Filter by transaction date", value=date.today(), key="filter_date")
        filtered = log_df[log_df["txn_date"] == filter_date]

        st.write(f"**Date:** {filter_date} ki {len(filtered)} transaction(s) unnayi.")

        if not filtered.empty:
            total_amount = filtered["amount"].fillna(0).sum()
            total_count = len(filtered)
            matched_count = filtered["is_date_match"].sum()
            unmatched_count = total_count - matched_count

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Transactions", total_count)
            col2.metric("Total Amount", f"₹ {total_amount:,.2f}")
            col3.metric("Date Matched", int(matched_count))
            col4.metric("Date NOT Matched", int(unmatched_count))

            display_cols = [
                "record_id",
                "file_name",
                "txn_date",
                "txn_time",
                "amount",
                "is_date_match",
            ]
            st.dataframe(filtered[display_cols], use_container_width=True)

            # Excel download (memory lo create chestham)
            out_file_name = f"payments_{filter_date}.xlsx"
            excel_buffer = BytesIO()
            filtered.to_excel(excel_buffer, index=False)
            excel_buffer.seek(0)

            st.download_button(
                label="⬇️ Download this day's transactions as Excel",
                data=excel_buffer.getvalue(),
                file_name=out_file_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.warning("Ee date ki transactions levu.")


if __name__ == "__main__":
    main()
