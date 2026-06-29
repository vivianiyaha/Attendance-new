import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
from datetime import datetime, time
import os

# ─── PAGE CONFIG ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="HR Analytics System",
    page_icon="👥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── THEME ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Global */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Main background */
.main .block-container {
    background-color: #ffffff;
    padding-top: 1.5rem;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background-color: #111111 !important;
}
section[data-testid="stSidebar"] * {
    color: #f0f0f0 !important;
}
section[data-testid="stSidebar"] .stRadio label {
    color: #f0f0f0 !important;
    font-size: 0.95rem;
}
section[data-testid="stSidebar"] hr {
    border-color: #333 !important;
}

/* Orange accent for buttons */
.stButton > button {
    background-color: #ff6b00;
    color: white;
    border: none;
    border-radius: 6px;
}
.stButton > button:hover {
    background-color: #e05a00;
}

/* KPI Cards */
.kpi-card {
    background: #fff;
    border: 1px solid #f0f0f0;
    border-left: 4px solid #ff6b00;
    border-radius: 8px;
    padding: 1.2rem 1.4rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}
.kpi-card .kpi-value {
    font-size: 2rem;
    font-weight: 700;
    color: #ff6b00;
    line-height: 1.1;
}
.kpi-card .kpi-label {
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #888;
    margin-top: 0.25rem;
}

/* Section headers */
.section-header {
    font-size: 1.1rem;
    font-weight: 600;
    color: #111;
    border-bottom: 2px solid #ff6b00;
    padding-bottom: 0.3rem;
    margin: 1.5rem 0 0.75rem;
}

/* Alert / info boxes */
.info-box {
    background: #fff8f3;
    border: 1px solid #ffd6b3;
    border-radius: 6px;
    padding: 0.75rem 1rem;
    color: #8a3300;
    font-size: 0.9rem;
}

/* Page title */
.page-title {
    font-size: 1.6rem;
    font-weight: 700;
    color: #111;
    margin-bottom: 0.25rem;
}
.page-subtitle {
    color: #666;
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
}
</style>
""", unsafe_allow_html=True)

# ─── DIRECTORIES & FILES ────────────────────────────────────────────────────
BASE_DIR = Path(".")
DAILY_DIR = BASE_DIR / "daily-attendance"
LEAVE_DIR = BASE_DIR / "leave-management"
EMP_CSV   = BASE_DIR / "employee.csv"

DAILY_DIR.mkdir(exist_ok=True)
LEAVE_DIR.mkdir(exist_ok=True)

# ─── HELPERS ────────────────────────────────────────────────────────────────

def kpi(label, value, col):
    col.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-value">{value}</div>
        <div class="kpi-label">{label}</div>
    </div>""", unsafe_allow_html=True)

def section(title):
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)

def load_employees():
    if EMP_CSV.exists():
        df = pd.read_csv(EMP_CSV)
        df.columns = df.columns.str.strip()
        name_col = next((c for c in df.columns if c.lower() == "name"), None)
        if name_col:
            df = df.rename(columns={name_col: "Name"})
            df["Name"] = df["Name"].str.strip()
            df = df.drop_duplicates(subset="Name")
            return df
    return pd.DataFrame(columns=["Name"])

def normalize_attendance(df):
    """Normalize column names to Name / Time_in / Time_out / Date."""
    df.columns = df.columns.str.strip()
    rename_map = {}
    for col in df.columns:
        low = col.lower().replace(" ", "_")
        if "name" in low:
            rename_map[col] = "Name"
        elif "time_in" in low or low == "time_in":
            rename_map[col] = "Time_in"
        elif "time_out" in low or low == "time_out":
            rename_map[col] = "Time_out"
        elif "date" in low:
            rename_map[col] = "Date"
    df = df.rename(columns=rename_map)

    # Also handle "Time in" / "Time out" (space variants)
    for col in list(df.columns):
        low = col.lower()
        if low == "time in":
            df = df.rename(columns={col: "Time_in"})
        elif low == "time out":
            df = df.rename(columns={col: "Time_out"})

    if "Name" in df.columns:
        df["Name"] = df["Name"].astype(str).str.strip()
        df = df[df["Name"].str.lower() != "nan"]

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    if "Time_in" in df.columns:
        df["Time_in_dt"] = pd.to_datetime(df["Time_in"], errors="coerce")

    if "Time_out" in df.columns:
        df["Time_out_dt"] = pd.to_datetime(df["Time_out"], errors="coerce")

    return df

def get_approved_leaves():
    """Return set of (name_lower, date) tuples on approved leave."""
    approved = set()
    for f in LEAVE_DIR.glob("*.csv"):
        try:
            df = pd.read_csv(f)
            df.columns = df.columns.str.strip()
            name_col   = next((c for c in df.columns if "name" in c.lower()), None)
            date_col   = next((c for c in df.columns if "date" in c.lower()), None)
            status_col = next((c for c in df.columns if "status" in c.lower()), None)
            if not name_col or not date_col:
                continue
            for _, row in df.iterrows():
                status = str(row.get(status_col, "approved")).strip().lower() if status_col else "approved"
                if status == "approved":
                    name = str(row[name_col]).strip().lower()
                    date = pd.to_datetime(row[date_col], errors="coerce")
                    if pd.notna(date):
                        approved.add((name, date.date()))
        except Exception:
            pass
    return approved

def is_rainy_day(filename: str) -> bool:
    return "rainy day" in filename.lower()

# ─── SIDEBAR ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 👥 HR System")
    st.markdown("---")
    page = st.radio(
        "Navigation",
        ["Dashboard", "Attendance Reports", "Leave Management", "HR Analytics"],
        label_visibility="collapsed"
    )
    st.markdown("---")
    st.markdown(
        "<small style='color:#555'>Cardstel Solutions Limited</small>",
        unsafe_allow_html=True
    )

# ════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════════════════════
if page == "Dashboard":
    st.markdown('<div class="page-title">Dashboard</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Overview of employee and attendance data</div>', unsafe_allow_html=True)

    emp_df       = load_employees()
    att_files    = list(DAILY_DIR.glob("*.csv"))
    leave_files  = list(LEAVE_DIR.glob("*.csv"))

    c1, c2, c3 = st.columns(3)
    kpi("Total Employees",      len(emp_df),       c1)
    kpi("Total Attendance Files", len(att_files),  c2)
    kpi("Total Leave Files",    len(leave_files),  c3)

    section("Employee Master List")
    if emp_df.empty:
        st.markdown('<div class="info-box">No employee data found. Add <b>employee.csv</b> to the root folder.</div>', unsafe_allow_html=True)
    else:
        display = emp_df.copy().reset_index(drop=True)
        display.index += 1
        display.index.name = "S/N"
        st.dataframe(display, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# ATTENDANCE REPORTS
# ════════════════════════════════════════════════════════════════════════════
elif page == "Attendance Reports":
    st.markdown('<div class="page-title">Attendance Reports</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Analyse daily attendance records</div>', unsafe_allow_html=True)

    att_files = sorted(DAILY_DIR.glob("*.csv"), key=lambda f: f.name)
    if not att_files:
        st.markdown('<div class="info-box">No attendance files found in <b>daily-attendance/</b> folder.</div>', unsafe_allow_html=True)
        st.stop()

    selected_file = st.selectbox("Select Attendance File", [f.name for f in att_files])
    chosen = DAILY_DIR / selected_file

    try:
        raw = pd.read_csv(chosen)
    except Exception as e:
        st.error(f"Could not read file: {e}")
        st.stop()

    df = normalize_attendance(raw)

    missing = [c for c in ["Name", "Time_in", "Date"] if c not in df.columns]
    if missing:
        st.error(f"Missing required columns: {missing}. Found: {list(raw.columns)}")
        st.stop()

    emp_df       = load_employees()
    all_employees = set(emp_df["Name"].str.lower().tolist()) if not emp_df.empty else set()
    approved      = get_approved_leaves()

    # Derive date from file data
    att_date = df["Date"].dropna().iloc[0].date() if "Date" in df.columns and not df["Date"].dropna().empty else None

    # Classify shifts
    cutoff_shift = pd.Timestamp("1900-01-01 13:00:00")
    cutoff_late  = pd.Timestamp("1900-01-01 08:30:00")
    cutoff_ot    = pd.Timestamp("1900-01-01 19:00:00")

    def to_time_only(ts):
        if pd.isna(ts):
            return pd.NaT
        return pd.Timestamp(f"1900-01-01 {ts.strftime('%H:%M:%S')}")

    df["_timein_norm"]  = df["Time_in_dt"].apply(to_time_only) if "Time_in_dt" in df.columns else pd.NaT
    df["_timeout_norm"] = df["Time_out_dt"].apply(to_time_only) if "Time_out_dt" in df.columns else pd.NaT

    df["Shift"] = df["_timein_norm"].apply(
        lambda t: "Day Shift" if pd.notna(t) and t < cutoff_shift else ("Afternoon/Night" if pd.notna(t) else "Unknown")
    )

    day_shift   = df[df["Shift"] == "Day Shift"].copy()
    aft_shift   = df[df["Shift"] == "Afternoon/Night"].copy()

    late_df     = day_shift[day_shift["_timein_norm"] > cutoff_late].copy()
    ot_df       = day_shift[day_shift["_timeout_norm"] > cutoff_ot].copy()

    present_names = set(df["Name"].str.lower().dropna())

    def on_leave(name_lower):
        if att_date:
            return (name_lower, att_date) in approved
        return False

    absent_list = [
        name for name in emp_df["Name"].tolist()
        if name.lower() not in present_names and not on_leave(name.lower())
    ] if not emp_df.empty else []
    absent_df = pd.DataFrame({"Name": absent_list})

    # ── Summary cards
    c1, c2, c3, c4 = st.columns(4)
    kpi("Late",              len(late_df),    c1)
    kpi("Absent",            len(absent_df),  c2)
    kpi("Overtime",          len(ot_df),      c3)
    kpi("Afternoon/Night Shift", len(aft_shift), c4)

    # ── Tables
    display_cols = [c for c in ["Name", "Time_in", "Time_out", "Date", "Shift"] if c in df.columns]

    section("Attendance List")
    st.dataframe(df[display_cols].reset_index(drop=True), use_container_width=True)

    section("Late Staff (Day Shift — after 08:30)")
    if late_df.empty:
        st.info("No late staff recorded.")
    else:
        st.dataframe(late_df[display_cols].reset_index(drop=True), use_container_width=True)

    section("Afternoon / Night Shift Staff")
    if aft_shift.empty:
        st.info("No afternoon/night shift staff.")
    else:
        st.dataframe(aft_shift[display_cols].reset_index(drop=True), use_container_width=True)

    section("Absentees")
    if absent_df.empty:
        st.success("No absentees recorded.")
    else:
        st.dataframe(absent_df.reset_index(drop=True), use_container_width=True)

    section("Overtime Staff (Day Shift — Time Out after 19:00)")
    if ot_df.empty:
        st.info("No overtime staff recorded.")
    else:
        st.dataframe(ot_df[display_cols].reset_index(drop=True), use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# LEAVE MANAGEMENT
# ════════════════════════════════════════════════════════════════════════════
elif page == "Leave Management":
    st.markdown('<div class="page-title">Leave Management</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">View leave records and approval status</div>', unsafe_allow_html=True)

    leave_files = sorted(LEAVE_DIR.glob("*.csv"), key=lambda f: f.name)
    if not leave_files:
        st.markdown('<div class="info-box">No leave files found in <b>leave-management/</b> folder.</div>', unsafe_allow_html=True)
        st.stop()

    selected = st.selectbox("Select Leave File", [f.name for f in leave_files])
    chosen   = LEAVE_DIR / selected

    try:
        ldf = pd.read_csv(chosen)
        ldf.columns = ldf.columns.str.strip()
        section(f"Leave Records — {selected}")
        st.dataframe(ldf.reset_index(drop=True), use_container_width=True)
    except Exception as e:
        st.error(f"Could not read file: {e}")

# ════════════════════════════════════════════════════════════════════════════
# HR ANALYTICS — Saturday Absentee Monitoring
# ════════════════════════════════════════════════════════════════════════════
elif page == "HR Analytics":
    st.markdown('<div class="page-title">HR Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="page-subtitle">Saturday absentee monitoring dashboard</div>', unsafe_allow_html=True)

    emp_df      = load_employees()
    approved    = get_approved_leaves()
    all_emp     = emp_df["Name"].str.strip().tolist() if not emp_df.empty else []
    all_emp_lower = {n.lower(): n for n in all_emp}

    # ── Load valid (non-rainy-day) attendance files
    valid_files = [f for f in DAILY_DIR.glob("*.csv") if not is_rainy_day(f.name)]
    rainy_count = len(list(DAILY_DIR.glob("*.csv"))) - len(valid_files)

    if not valid_files:
        st.markdown('<div class="info-box">No valid attendance files found (rainy-day files excluded).</div>', unsafe_allow_html=True)
        st.stop()

    if rainy_count:
        st.markdown(
            f'<div class="info-box">ℹ️ {rainy_count} rainy-day file(s) excluded from analytics.</div>',
            unsafe_allow_html=True
        )

    # Per-employee Saturday tracking: {emp_name: {date: "present"/"absent"/"leave"}}
    saturday_records = {n: {} for n in all_emp}

    for f in valid_files:
        try:
            raw = pd.read_csv(f)
        except Exception:
            continue

        df = normalize_attendance(raw)
        if "Date" not in df.columns or df["Date"].dropna().empty:
            continue

        att_date = df["Date"].dropna().iloc[0].date()

        # Only Saturdays
        if pd.Timestamp(att_date).day_name() != "Saturday":
            continue

        present_lower = set(df["Name"].str.lower().dropna().str.strip())

        for emp_name in all_emp:
            emp_lower = emp_name.lower()
            if emp_lower in present_lower:
                saturday_records[emp_name][att_date] = "present"
            elif (emp_lower, att_date) in approved:
                saturday_records[emp_name][att_date] = "leave"
            else:
                saturday_records[emp_name][att_date] = "absent"

    # Collect all Saturday dates
    all_saturdays = set()
    for rec in saturday_records.values():
        all_saturdays.update(rec.keys())
    all_saturdays = sorted(all_saturdays)

    if not all_saturdays:
        st.markdown('<div class="info-box">No Saturday attendance data found in valid files.</div>', unsafe_allow_html=True)
        st.stop()

    # Build summary df
    rows = []
    for emp_name in all_emp:
        rec = saturday_records.get(emp_name, {})
        sat_count   = len(all_saturdays)
        sat_present = sum(1 for d in all_saturdays if rec.get(d) == "present")
        sat_leave   = sum(1 for d in all_saturdays if rec.get(d) == "leave")
        sat_absent  = sum(1 for d in all_saturdays if rec.get(d) == "absent")
        rate        = round((sat_present / sat_count) * 100, 1) if sat_count > 0 else 0.0
        rows.append({
            "Name":            emp_name,
            "Saturday_Count":  sat_count,
            "Saturday_Present": sat_present,
            "Saturday_Leave":  sat_leave,
            "Saturday_Absent": sat_absent,
            "Attendance_Rate": rate,
        })

    summary = pd.DataFrame(rows)

    total_employees  = len(summary)
    total_saturdays  = len(all_saturdays)
    total_absences   = int(summary["Saturday_Absent"].sum())
    frequent_absent  = int((summary["Saturday_Absent"] >= 3).sum())

    # ── KPI Row
    c1, c2, c3, c4 = st.columns(4)
    kpi("Employees Tracked",             total_employees,  c1)
    kpi("Total Saturdays Analysed",      total_saturdays,  c2)
    kpi("Total Saturday Absences",       total_absences,   c3)
    kpi("Employees With 3+ Absences",    frequent_absent,  c4)

    # ── Saturday Attendance Ranking
    section("Saturday Attendance Ranking")
    ranking = summary.sort_values(
        by=["Attendance_Rate", "Saturday_Absent"],
        ascending=[False, True]
    ).reset_index(drop=True)
    ranking.index += 1
    ranking.index.name = "Rank"

    display_cols = ["Name", "Saturday_Count", "Saturday_Present", "Saturday_Absent", "Attendance_Rate"]
    st.dataframe(
        ranking[display_cols].rename(columns={"Attendance_Rate": "Attendance_Rate (%)"}),
        use_container_width=True
    )

    # ── Frequent Saturday Absentees
    section("Frequent Saturday Absentees  (3 or more absences)")
    frequent = summary[summary["Saturday_Absent"] >= 3].sort_values("Saturday_Absent", ascending=False).reset_index(drop=True)
    if frequent.empty:
        st.success("No employees with 3 or more Saturday absences.")
    else:
        frequent.index += 1
        st.dataframe(
            frequent[["Name", "Saturday_Absent", "Attendance_Rate"]].rename(
                columns={"Attendance_Rate": "Attendance_Rate (%)"}
            ),
            use_container_width=True
        )

    # ── Charts
    section("Saturday Attendance Rate by Employee")
    chart_rate = summary.sort_values("Attendance_Rate", ascending=True)
    fig1 = px.bar(
        chart_rate,
        x="Attendance_Rate",
        y="Name",
        orientation="h",
        labels={"Attendance_Rate": "Attendance Rate (%)", "Name": "Employee"},
        color="Attendance_Rate",
        color_continuous_scale=[[0, "#ff6b00"], [0.5, "#ffaa55"], [1, "#22c55e"]],
        text="Attendance_Rate",
    )
    fig1.update_traces(texttemplate="%{text}%", textposition="outside")
    fig1.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        coloraxis_showscale=False,
        height=max(300, len(summary) * 32),
        margin=dict(l=0, r=20, t=10, b=10),
        xaxis=dict(range=[0, 110]),
    )
    st.plotly_chart(fig1, use_container_width=True)

    section("Saturday Absence Count — Employees with 3+ Absences")
    if frequent.empty:
        st.info("No employees with 3 or more Saturday absences to display.")
    else:
        fig2 = px.bar(
            frequent.sort_values("Saturday_Absent", ascending=False),
            x="Name",
            y="Saturday_Absent",
            labels={"Saturday_Absent": "Saturdays Absent", "Name": "Employee"},
            color="Saturday_Absent",
            color_continuous_scale=[[0, "#ffaa55"], [1, "#cc2200"]],
            text="Saturday_Absent",
        )
        fig2.update_traces(textposition="outside")
        fig2.update_layout(
            plot_bgcolor="white",
            paper_bgcolor="white",
            coloraxis_showscale=False,
            height=400,
            margin=dict(l=0, r=20, t=10, b=80),
        )
        st.plotly_chart(fig2, use_container_width=True)
