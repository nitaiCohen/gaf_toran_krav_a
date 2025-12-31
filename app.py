import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, timedelta
import urllib.parse

# --- קבצים ---
SCHEDULE_FILE = 'schedule.csv'
MESSAGES_FILE = 'messages.csv'
USERS_FILE = 'users.json'
ADMIN_LOG_FILE = 'admin_log.csv'

# --- הגדרות כלליות ---
st.set_page_config(page_title="רישום כיתת מעלה", layout="wide")
st.markdown(
    """
    <div style='
        background: linear-gradient(90deg, #1f3c88, #4062bb);
        padding: 24px;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 30px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    '>
        <h1 style='margin-bottom: 10px;'>📘מערכת רישום כיתת מעלה גף קרב א</h1>
        <p style='font-size: 18px; margin: 0;'>ניהול תורים, מפקדים והודעות — במקום אחד מסודר</p>
    </div>
    """,
    unsafe_allow_html=True
)

# --- טעינת משתמשים ---
def load_users():
    if not os.path.exists(USERS_FILE):
        default_users = {
            "admin1": {"password": "1234", "role": "admin"}
        }
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_users, f, ensure_ascii=False, indent=2)

    with open(USERS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

users = load_users()

# --- התחברות ---
def login():
    with st.sidebar.expander("🔐 התחברות מנהלים"):
        username = st.text_input("שם משתמש")
        password = st.text_input("סיסמה", type="password")
        if st.button("התחבר"):
            if username in users and users[username]["password"] == password:
                st.session_state.username = username
                st.session_state.role = users[username]["role"]
                st.success("התחברת בהצלחה!")
                st.rerun()
            else:
                st.error("שם משתמש או סיסמה שגויים")

if "role" not in st.session_state:
    st.session_state.role = "guest"
if "username" not in st.session_state:
    st.session_state.username = "אורח"

if st.session_state.role != "admin":
    login()

# --- יצירת קבצים אם לא קיימים ---
if not os.path.exists(SCHEDULE_FILE):
    pd.DataFrame(columns=["מספר קורס", "שם מפקד", "טלפון", "תאריך", "משעה", "עד שעה"]).to_csv(SCHEDULE_FILE, index=False)

if not os.path.exists(MESSAGES_FILE):
    pd.DataFrame(columns=["תאריך", "הודעה"]).to_csv(MESSAGES_FILE, index=False)

if not os.path.exists(ADMIN_LOG_FILE):
    pd.DataFrame(columns=["תאריך", "מנהל", "פעולה", "פרטים"]).to_csv(ADMIN_LOG_FILE, index=False)

# --- ניקוי פעולות מנהלים ישנות (24 שעות) ---
def clean_old_admin_logs():
    df = pd.read_csv(ADMIN_LOG_FILE)
    if df.empty:
        return
    df["תאריך"] = pd.to_datetime(df["תאריך"], format="%Y-%m-%d %H:%M", errors="coerce")
    cutoff = datetime.now() - timedelta(hours=24)
    df = df[df["תאריך"] > cutoff]
    df.to_csv(ADMIN_LOG_FILE, index=False)

clean_old_admin_logs()

# --- רישום פעולות מנהלים ---
def log_admin_action(admin, action, details):
    df = pd.read_csv(ADMIN_LOG_FILE)
    new = pd.DataFrame([[datetime.now().strftime("%Y-%m-%d %H:%M"), admin, action, details]], columns=df.columns)
    df = pd.concat([df, new], ignore_index=True)
    df.to_csv(ADMIN_LOG_FILE, index=False)

# --- הודעה כללית ---
def show_message():
    df = pd.read_csv(MESSAGES_FILE)
    if not df.empty:
        msg = str(df.iloc[-1]["הודעה"])
        st.info("📢 " + msg)

show_message()

# --- טופס רישום ---
st.subheader("📌 רישום לקורס")

with st.form("booking_form"):
    course_id = st.text_input("מספר קורס")
    commander = st.text_input("שם מפקד")
    phone = st.text_input("טלפון")

    today = datetime.today().date()

    if st.session_state.role == "admin":
        date = st.date_input("בחר תאריך", value=today)
    else:
        max_date = today + timedelta(days=7)
        date = st.date_input(
            "בחר תאריך (7 ימים קדימה בלבד)",
            value=today,
            min_value=today,
            max_value=max_date
        )

    # רשימת שעות
    times = [f"{h:02d}:{m:02d}" for h in range(6, 22) for m in [0, 30]]

    df = pd.read_csv(SCHEDULE_FILE)
    if df.empty:
        df = pd.DataFrame(
            columns=["מספר קורס", "שם מפקד", "טלפון", "תאריך", "משעה", "עד שעה"]
        )

    # תאריך בפורמט פנימי (ISO)
    selected_date_iso = date.strftime("%Y-%m-%d")

    # שעות תפוסות בתאריך הזה
    taken = df[df["תאריך"] == selected_date_iso]

    unavailable = []
    for _, row in taken.iterrows():
        if row["משעה"] in times and row["עד שעה"] in times:
            s = times.index(row["משעה"])
            e = times.index(row["עד שעה"])
            unavailable.extend(times[s:e])

    available = [t for t in times if t not in unavailable]

    if not available:
        st.warning("אין שעות פנויות בתאריך זה.")
        submitted = st.form_submit_button("שלח")
    else:
        start = st.selectbox("שעת התחלה", available)
        end_options = [t for t in available if times.index(t) > times.index(start)]
        end = st.selectbox("שעת סיום", end_options)

        submitted = st.form_submit_button("שלח")

        if submitted:
            if not course_id or not commander or not phone:
                st.error("יש למלא את כל השדות.")
            else:
                # שמירה בפורמט פנימי
                new_row = pd.DataFrame(
                    [[course_id, commander, phone, selected_date_iso, start, end]],
                    columns=df.columns
                )
                df = pd.concat([df, new_row], ignore_index=True)
                df.to_csv(SCHEDULE_FILE, index=False)

                if st.session_state.role == "admin":
                    log_admin_action(
                        st.session_state.username,
                        "רישום קורס",
                        f"{selected_date_iso} {start}-{end}"
                    )

                st.success("התור נרשם בהצלחה!")

                # --- שליחת WhatsApp (עם תיקון מספר טלפון) ---

                # ניקוי מספר
                clean_phone = phone.replace(" ", "").replace("-", "").replace("+", "")

                # אם מתחיל ב-0 → להמיר ל-972
                if clean_phone.startswith("0"):
                    clean_phone = "972" + clean_phone[1:]

                # אם מתחיל ב-972 → להשאיר
                elif clean_phone.startswith("972"):
                    pass

                # אחרת → מספר לא תקין
                else:
                    st.error("מספר הטלפון שהוזן אינו תקין. יש להזין מספר כמו 0534444494.")
                    st.stop()

                # יצירת הודעה
                date_he = date.strftime("%d-%m-%Y")
                msg = (
                    f"התור שלך לכיתת מעלה נקבע בהצלחה:\n"
                    f"תאריך: {date_he}\n"
                    f"שעות: {start}–{end}\n"
                    f"מספר קורס: {course_id}"
                )

                encoded = urllib.parse.quote(msg)

                # קישור WhatsApp עם מספר יעד
                whatsapp_url = f"https://wa.me/{clean_phone}?text={encoded}"

                # כפתור WhatsApp
                st.markdown(
                    f"<a href='{whatsapp_url}' target='_blank' "
                    f"style='text-decoration:none;'>"
                    f"<button style='background-color:#25D366;color:white;"
                    f"padding:10px 20px;border:none;border-radius:5px;"
                    f"font-size:16px;cursor:pointer;'>📲 שלח אישור ב־WhatsApp</button>"
                    f"</a>",
                    unsafe_allow_html=True
                )

# --- לוח זמנים עם דפדוף בין ימים ---
st.subheader("📋 לוח זמנים")

df = pd.read_csv(SCHEDULE_FILE)

if df.empty:
    st.write("אין רישומים עדיין.")
else:
    if "view_date" not in st.session_state:
        st.session_state.view_date = datetime.today().date()

    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("⬅️ יום קודם"):
            st.session_state.view_date -= timedelta(days=1)

    with col3:
        if st.button("➡️ יום הבא"):
            st.session_state.view_date += timedelta(days=1)

    st.markdown(
        "### 📅 תאריך מוצג: " +
        st.session_state.view_date.strftime("%d-%m-%Y")
    )

    show_date_iso = st.session_state.view_date.strftime("%Y-%m-%d")
    filtered = df[df["תאריך"] == show_date_iso]

    if filtered.empty:
        st.write("אין רישומים בתאריך זה.")
    else:
        filtered = filtered.copy()
        filtered["תאריך"] = pd.to_datetime(
            filtered["תאריך"],
            format="%Y-%m-%d",
            errors="coerce"
        ).dt.strftime("%d-%m-%Y")

        # אינדקס מסודר
        filtered = filtered.sort_values(by="משעה")
        filtered = filtered.reset_index(drop=True)
        filtered.index = filtered.index + 1

        st.dataframe(filtered)

# --- חיפוש מתקדם (למנהלים בלבד) ---
if st.session_state.role == "admin":
    st.subheader("🔎 חיפוש מתקדם")

    with st.expander("פתח חיפוש"):
        search_course = st.text_input("חפש לפי מספר קורס")
        search_name = st.text_input("חפש לפי שם מפקד")
        search_date = st.date_input("חפש לפי תאריך", value=None)

        if st.button("בצע חיפוש"):
            results = df.copy()

            if search_course.strip() != "":
                results = results[results["מספר קורס"].astype(str).str.contains(search_course)]

            if search_name.strip() != "":
                results = results[results["שם מפקד"].str.contains(search_name)]

            if search_date:
                iso = search_date.strftime("%Y-%m-%d")
                results = results[results["תאריך"] == iso]

            if results.empty:
                st.warning("לא נמצאו תוצאות.")
            else:
                results = results.copy()
                results["תאריך"] = pd.to_datetime(
                    results["תאריך"],
                    format="%Y-%m-%d",
                    errors="coerce"
                ).dt.strftime("%d-%m-%Y")

                # אינדקס מסודר
                results = results.sort_values(by=["תאריך", "משעה"])
                results = results.reset_index(drop=True)
                results.index = results.index + 1

                st.dataframe(results)

# --- פעולות מנהל ---
if st.session_state.role == "admin":
    st.subheader("🛠️ ניהול")

    df = pd.read_csv(SCHEDULE_FILE)

    # מחיקת רישום
    if not df.empty:
        with st.expander("🗑️ מחיקת רישום"):
            def format_label(r):
                try:
                    d = datetime.strptime(r["תאריך"], "%Y-%m-%d").strftime("%d-%m-%Y")
                except:
                    d = r["תאריך"]
                return f"{d} {r['משעה']}-{r['עד שעה']} | {r['מספר קורס']}"

            labels = df.apply(format_label, axis=1)
            choice = st.selectbox("בחר רישום", labels)

            if st.button("מחק רישום"):
                idx = df[labels == choice].index
                df = df.drop(idx)
                df.to_csv(SCHEDULE_FILE, index=False)
                log_admin_action(st.session_state.username, "מחיקת רישום", choice)
                st.success("נמחק.")
                st.rerun()

    # מחיקת כל הטבלה
    with st.expander("🧹 מחיקת כל הרישומים"):
        if st.button("מחק הכול"):
            df = df[0:0]
            df.to_csv(SCHEDULE_FILE, index=False)
            log_admin_action(st.session_state.username, "מחיקת כל הטבלה", "נמחק הכול")
            st.success("כל הרישומים נמחקו.")
            st.rerun()
        # מחיקת תורים לפי תאריך
    with st.expander("🗑️ מחיקת תורים לפי תאריך"):
        delete_date = st.date_input("בחר תאריך למחיקה", key="delete_date")
        if st.button("מחק את כל התורים בתאריך זה"):
            iso = delete_date.strftime("%Y-%m-%d")
            before = len(df)
            df = df[df["תאריך"] != iso]
            after = len(df)
            df.to_csv(SCHEDULE_FILE, index=False)

            log_admin_action(
                st.session_state.username,
                "מחיקת תורים לפי תאריך",
                f"{delete_date.strftime('%d-%m-%Y')} — נמחקו {before - after} תורים"
            )

            st.success(f"נמחקו {before - after} תורים בתאריך זה.")
            st.rerun()

    # פרסום הודעה
    with st.expander("📣 פרסום הודעה"):
        msg = st.text_area("כתוב הודעה")
        if st.button("פרסם הודעה"):
            dfm = pd.read_csv(MESSAGES_FILE)
            new = pd.DataFrame([[datetime.now().strftime("%Y-%m-%d %H:%M"), msg]], columns=dfm.columns)
            dfm = pd.concat([dfm, new], ignore_index=True)
            dfm.to_csv(MESSAGES_FILE, index=False)
            log_admin_action(st.session_state.username, "פרסום הודעה", msg)
            st.success("פורסם.")
            st.rerun()

    # מחיקת הודעה אחרונה
    with st.expander("🗑️ מחיקת הודעה אחרונה"):
        dfm = pd.read_csv(MESSAGES_FILE)
        if dfm.empty:
            st.write("אין הודעות למחיקה.")
        else:
            last_msg = str(dfm.iloc[-1]["הודעה"])
            st.info("ההודעה האחרונה:\n" + last_msg)

            if st.button("מחק הודעה אחרונה"):
                dfm = dfm.iloc[:-1]
                dfm.to_csv(MESSAGES_FILE, index=False)
                log_admin_action(st.session_state.username, "מחיקת הודעה", last_msg)
                st.success("ההודעה נמחקה.")
                st.rerun()

    # יומן פעולות מנהלים
    with st.expander("📜 יומן פעולות מנהלים"):
        log = pd.read_csv(ADMIN_LOG_FILE)
        if not log.empty:
            log = log.sort_values(by="תאריך", ascending=False)
            log = log.reset_index(drop=True)
            log.index = log.index + 1
            st.dataframe(log)
        else:
            st.write("אין פעולות מנהלים עדיין.")

# --- קרדיט ---
st.markdown("---")
st.markdown(
    """
    <div style='text-align:center; direction:rtl; font-size:14px;'>
        פותח על ידי <strong>ניתאי כהן</strong> | 053-4444494<br>
        מערכת רישום כיתת מעלה — גרסה מתקדמת
    </div>
    """,
    unsafe_allow_html=True
)

