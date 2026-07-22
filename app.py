import streamlit as st
import pandas as pd
import sqlite3
import hashlib
from datetime import datetime, date, timedelta, timezone
import os
import requests
import calendar

# ==========================================
# MÚI GIỜ VIỆT NAM (UTC+7 / Asia/Ho_Chi_Minh)
# ==========================================
VN_TZ = timezone(timedelta(hours=7))

def get_vn_now():
    """Lấy ngày giờ hiện tại chuẩn múi giờ Việt Nam (UTC+7)"""
    return datetime.now(VN_TZ)

def get_vn_date_str():
    return get_vn_now().strftime("%Y-%m-%d")

# ==========================================
# 1. CẤU HÌNH TRANG & GIAO DIỆN CHUẨN SOLAR 24H
# ==========================================
st.set_page_config(
    page_title="Solar 24H - Chấm Công & KPI Kỹ Thuật",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Đường dẫn lưu trữ ảnh chấm công Timemark
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Giao diện CSS đồng bộ màu sắc thương hiệu (Cam mặt trời #FF7A00 và Xanh thẫm quân đội #0F172A)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .main-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        padding: 25px;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 25px;
        border-bottom: 5px solid #FF7A00;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
    }
    .main-header h1 {
        color: #FF7A00;
        margin: 0;
        font-weight: 700;
        font-size: 2.2rem;
    }
    .main-header p {
        color: #94A3B8;
        margin: 5px 0 0 0;
        font-size: 1rem;
    }
    .stButton>button {
        background-color: #FF7A00 !important;
        color: white !important;
        font-weight: bold !important;
        border: none !important;
        border-radius: 8px !important;
        transition: all 0.3s ease !important;
    }
    .stButton>button:hover {
        background-color: #E06B00 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(255, 122, 0, 0.4) !important;
    }
    .metric-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    .metric-card span {
        color: #94A3B8;
        font-size: 0.9rem;
        display: block;
        margin-bottom: 5px;
    }
    .metric-card h2 {
        color: #FF7A00;
        margin: 0;
        font-size: 1.8rem;
        font-weight: 700;
    }
    .metric-card p {
        color: #64748B;
        margin: 5px 0 0 0;
        font-size: 0.8rem;
    }
    .metric-box {
        background-color: #1E293B;
        border: 1px solid #334155;
        padding: 18px;
        border-radius: 12px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    .metric-box span {
        color: #94A3B8;
        font-size: 0.85rem;
        display: block;
        margin-bottom: 6px;
        font-weight: 600;
    }
    .metric-value {
        color: #FF7A00;
        font-size: 1.6rem;
        font-weight: 700;
    }
    .login-box {
        max-width: 450px;
        margin: 40px auto;
        padding: 35px;
        background-color: #1E293B;
        border-radius: 12px;
        box-shadow: 0 10px 15px -3px rgba(0,0,0,0.3);
        border: 1px solid #334155;
    }
    .ktv-card {
        background-color: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        margin-bottom: 15px;
    }
    .ktv-card h4 {
        color: white;
        margin: 8px 0 2px 0;
        font-size: 1.05rem;
        font-weight: 700;
    }
    .ktv-card .role-title {
        color: #FF7A00;
        font-weight: 600;
        font-size: 0.85rem;
        margin-bottom: 4px;
        display: block;
    }
    .ktv-card p {
        color: #94A3B8;
        font-size: 0.78rem;
        margin: 0;
    }
    .ktv-card .salary-tag {
        color: #4ADE80;
        font-weight: bold;
        font-size: 1.1rem;
        margin-top: 8px;
        display: block;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. KHỞI TẠO CƠ SỞ DỮ LIỆU SQLITE NỘI BỘ
# ==========================================
DB_FILE = "solar24h_local.db"

def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    
    # Bảng người dùng tài khoản
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            fullname TEXT,
            role TEXT,
            avatar TEXT,
            title TEXT
        )
    """)
    
    # Đảm bảo các cột bổ sung tồn tại
    c.execute("PRAGMA table_info(users)")
    cols = [col[1] for col in c.fetchall()]
    if "avatar" not in cols:
        c.execute("ALTER TABLE users ADD COLUMN avatar TEXT")
    if "title" not in cols:
        c.execute("ALTER TABLE users ADD COLUMN title TEXT")
    if "phone" not in cols:
        c.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    
    # Bảng chấm công hàng ngày
    c.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            time TEXT,
            username TEXT,
            fullname TEXT,
            work_type TEXT,
            note TEXT,
            photo_name TEXT,
            participating_ktvs TEXT
        )
    """)
    
    c.execute("PRAGMA table_info(attendance)")
    att_cols = [col[1] for col in c.fetchall()]
    if "participating_ktvs" not in att_cols:
        c.execute("ALTER TABLE attendance ADD COLUMN participating_ktvs TEXT")
    
    # Bảng đăng ký nghỉ phép KTV
    c.execute("""
        CREATE TABLE IF NOT EXISTS leave_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            username TEXT,
            fullname TEXT,
            leave_type TEXT,
            reason TEXT,
            logged_by TEXT
        )
    """)
    
    # Bảng đăng ký công trình mới
    c.execute("""
        CREATE TABLE IF NOT EXISTS project_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            project_name TEXT,
            value REAL,
            registered_by TEXT,
            status TEXT,
            approved_by TEXT,
            approved_at TEXT,
            participating_ktvs TEXT
        )
    """)
    
    c.execute("PRAGMA table_info(project_logs)")
    p_cols = [col[1] for col in c.fetchall()]
    if "participating_ktvs" not in p_cols:
        c.execute("ALTER TABLE project_logs ADD COLUMN participating_ktvs TEXT")
    
    # Bảng đăng ký ca bảo trì
    c.execute("""
        CREATE TABLE IF NOT EXISTS maintenance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            client_name TEXT,
            location TEXT,
            registered_by TEXT,
            status TEXT,
            approved_by TEXT,
            approved_at TEXT,
            participating_ktvs TEXT
        )
    """)
    
    c.execute("PRAGMA table_info(maintenance_logs)")
    m_cols = [col[1] for col in c.fetchall()]
    if "participating_ktvs" not in m_cols:
        c.execute("ALTER TABLE maintenance_logs ADD COLUMN participating_ktvs TEXT")
    
    # Bảng phạt chế tài
    c.execute("""
        CREATE TABLE IF NOT EXISTS fine_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            fine_type TEXT,
            amount REAL,
            reason TEXT,
            logged_by TEXT
        )
    """)
    
    # Chuyển đổi username cũ
    old_to_new = {
        "thanh": "thanhnc",
        "nam": "namnh",
        "thien": "thienvt",
        "thientv": "thienvt",
        "vinh": "vinhtc",
        "thai": "thaiph",
        "sang": "sangth",
        "viet": "viethm"
    }
    for old_u, new_u in old_to_new.items():
        c.execute("UPDATE users SET username = ? WHERE username = ?", (new_u, old_u))
        c.execute("UPDATE attendance SET username = ? WHERE username = ?", (new_u, old_u))
    
    # Seed & Cập nhật danh sách tài khoản kèm chức vụ chính xác
    def hash_pwd(pwd):
        return hashlib.sha256(pwd.encode()).hexdigest()
    
    default_users = [
        ("thanhnc", hash_pwd("solar24h"), "Nguyễn Chí Thanh", "KTV", "Nguyễn Chí Thanh.png", "Trưởng Nhóm Thi Công"),
        ("namnh", hash_pwd("solar24h"), "Nguyễn Hoàng Nam", "KTV", "Nguyễn Hoàng Nam.png", "Trưởng Nhóm Bảo Trì"),
        ("thienvt", hash_pwd("solar24h"), "Võ Thành Thiện", "KTV", "Võ Thành Thiện.png", "Kỹ Thuật Viên"),
        ("vinhtc", hash_pwd("solar24h"), "Trần Công Vinh", "KTV", "Trần Công Vinh.jpeg", "Kỹ Thuật Viên"),
        ("thaiph", hash_pwd("solar24h"), "Phạm Hồng Thái", "KTV", "Phạm Hồng Thái.jpeg", "Kỹ Thuật Viên"),
        ("sangth", hash_pwd("admin24h"), "Trần Hoàng Sang", "Admin", "Logo Solar 24h.png", "Trưởng Phòng HR"),
        ("viethm", hash_pwd("admin24h"), "Hồ Minh Việt", "Admin", "Logo Solar 24h.png", "Giám Đốc")
    ]
    
    for uname, hpwd, fname, role, avt, title in default_users:
        c.execute("SELECT id FROM users WHERE username = ?", (uname,))
        row = c.fetchone()
        if not row:
            c.execute("INSERT INTO users (username, password_hash, fullname, role, avatar, title) VALUES (?, ?, ?, ?, ?, ?)",
                      (uname, hpwd, fname, role, avt, title))
        else:
            c.execute("UPDATE users SET password_hash = ?, fullname = ?, role = ?, avatar = ?, title = ? WHERE username = ?", 
                      (hpwd, fname, role, avt, title, uname))
    
    # Seed dữ liệu mẫu ban đầu (ở trạng thái 'Chờ duyệt')
    today_vn = get_vn_date_str()
    all_ktv_str = "Nguyễn Chí Thanh, Nguyễn Hoàng Nam, Võ Thành Thiện, Trần Công Vinh, Phạm Hồng Thái"
    
    c.execute("SELECT COUNT(*) FROM project_logs")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO project_logs (date, project_name, value, registered_by, status, approved_by, approved_at, participating_ktvs)
            VALUES (?, 'Dự án SOLAR F8 Gò Công', 211400000, 'Nguyễn Chí Thanh (Trưởng Nhóm Thi Công)', 'Chờ duyệt', '-', '-', ?)
        """, (today_vn, all_ktv_str))
    
    c.execute("SELECT COUNT(*) FROM maintenance_logs")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO maintenance_logs (date, client_name, location, registered_by, status, approved_by, approved_at, participating_ktvs)
            VALUES (?, 'Bảo trì Trạm sạc Cái Bè', 'Cái Bè', 'Nguyễn Hoàng Nam (Trưởng Nhóm Bảo Trì)', 'Chờ duyệt', '-', '-', ?)
        """, (today_vn, all_ktv_str))

    # Seed dữ liệu điểm danh đầy đủ từ 01/07/2026 đến 21/07/2026 theo yêu cầu
    c.execute("SELECT COUNT(*) FROM attendance WHERE date LIKE '2026-07%'")
    if c.fetchone()[0] == 0:
        ktv_all = ["Nguyễn Chí Thanh", "Nguyễn Hoàng Nam", "Võ Thành Thiện", "Trần Công Vinh", "Phạm Hồng Thái"]
        for day in range(1, 22):
            d_obj = date(2026, 7, day)
            if d_obj.weekday() == 6: # Chủ Nhật nghỉ định kỳ
                continue
            day_str = d_obj.strftime("%Y-%m-%d")
            
            # Xử lý KTV nghỉ phép
            participants = list(ktv_all)
            if day == 4:
                participants.remove("Trần Công Vinh")
            elif day == 20:
                participants.remove("Võ Thành Thiện")
                
            participating_str = ", ".join(participants)
            c.execute("""
                INSERT INTO attendance (date, time, username, fullname, work_type, note, photo_name, participating_ktvs)
                VALUES (?, '07:30:00', 'thanhnc', 'Nguyễn Chí Thanh', 'Thi công lắp đặt mới (Hệ Solar / Trạm sạc)', 'Báo cáo ca làm việc hiện trường', 'Logo Solar 24h.png', ?)
            """, (day_str, participating_str))
            
    # Seed dữ liệu 2 ca nghỉ phép cụ thể
    c.execute("SELECT COUNT(*) FROM leave_logs WHERE date LIKE '2026-07%'")
    if c.fetchone()[0] == 0:
        c.execute("""
            INSERT INTO leave_logs (date, username, fullname, leave_type, reason, logged_by)
            VALUES ('2026-07-04', 'vinhtc', 'Trần Công Vinh', 'Nghỉ phép năm (P)', 'Giải quyết việc riêng gia đình', 'Trần Hoàng Sang (Trưởng Phòng HR)')
        """)
        c.execute("""
            INSERT INTO leave_logs (date, username, fullname, leave_type, reason, logged_by)
            VALUES ('2026-07-20', 'thienvt', 'Võ Thành Thiện', 'Nghỉ phép năm (P)', 'Xin nghỉ phép cá nhân', 'Trần Hoàng Sang (Trưởng Phòng HR)')
        """)

    # TỰ ĐỘNG KHÔI PHỤC VÀ ĐIỀU CHỈNH CÁC BẢN GHI LƯU SAI MÚI GIỜ TRƯỚC ĐÓ VỀ GIỜ VIỆT NAM (UTC+7)
    c.execute("UPDATE attendance SET time = '11:14:10' WHERE date = '2026-07-21' AND (time LIKE '04:14%' OR time LIKE '04:%')")

    conn.commit()
    conn.close()

init_db()

# ==========================================
# 3. CÁC HÀM TIỆN ÍCH (HELPER FUNCTIONS)
# ==========================================
def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def fmt_vnd(amount):
    """Định dạng số tiền theo chuẩn Tiếng Việt (dùng dấu chấm phân cách hàng nghìn)"""
    return f"{amount:,.0f}".replace(",", ".")

def get_user_avatar(username):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT avatar FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if row and row[0] and os.path.exists(row[0]):
        return row[0]
    return "Logo Solar 24h.png" if os.path.exists("Logo Solar 24h.png") else None

# Danh sách 5 KTV cố định với Chức vụ & Phụ cấp chuẩn
KTV_PROFILE_LIST = [
    {
        "username": "thanhnc", 
        "name": "Nguyễn Chí Thanh", 
        "title": "Trưởng Nhóm Thi Công",
        "avatar": "Nguyễn Chí Thanh.png", 
        "note": "Lái xe + thợ cả (Phụ cấp 1 triệu)",
        "allowance": 1000000,
        "allowance_desc": "1.000.000 đ (Lái xe + thợ cả)"
    ,
        "phone": "0971.847.084"
    },
    {
        "username": "namnh", 
        "name": "Nguyễn Hoàng Nam", 
        "title": "Trưởng Nhóm Bảo Trì",
        "avatar": "Nguyễn Hoàng Nam.png", 
        "note": "Hotline + thợ tinh (Phụ cấp 1 triệu)",
        "allowance": 1000000,
        "allowance_desc": "1.000.000 đ (Hotline + thợ tinh)"
    ,
        "phone": "078.336.7989"
    },
    {
        "username": "thienvt", 
        "name": "Võ Thành Thiện", 
        "title": "Kỹ Thuật Viên",
        "avatar": "Võ Thành Thiện.png", 
        "note": "Kỹ thuật viên chính",
        "allowance": 0,
        "allowance_desc": "Không"
    ,
        "phone": "0328.400.801"
    },
    {
        "username": "vinhtc", 
        "name": "Trần Công Vinh", 
        "title": "Kỹ Thuật Viên",
        "avatar": "Trần Công Vinh.jpeg", 
        "note": "Kỹ thuật viên chính",
        "allowance": 0,
        "allowance_desc": "Không"
    ,
        "phone": "0898.044.598"
    },
    {
        "username": "thaiph", 
        "name": "Phạm Hồng Thái", 
        "title": "Kỹ Thuật Viên",
        "avatar": "Phạm Hồng Thái.jpeg", 
        "note": "Kỹ thuật viên chính",
        "allowance": 0,
        "allowance_desc": "Không"
    ,
        "phone": "0362.240.392"
    },
]

ALL_KTV_NAMES = [ktv["name"] for ktv in KTV_PROFILE_LIST]

# Hàm tính toán thu nhập cá nhân chuẩn Giải Pháp 1: Chia thưởng 0.5% & 100k CHỈ CHO KTV THỰC TẾ THAM GIA
def calculate_individual_salaries(selected_month_filter):
    conn = get_connection()
    
    if "Tất cả" in selected_month_filter:
        p_df = pd.read_sql_query("SELECT value, participating_ktvs FROM project_logs WHERE status = 'Đã duyệt'", conn)
        m_df = pd.read_sql_query("SELECT participating_ktvs FROM maintenance_logs WHERE status = 'Đã duyệt'", conn)
        fine_df = pd.read_sql_query("SELECT amount FROM fine_logs", conn)
    else:
        m_pattern = get_vn_now().strftime("%Y-%m")
        p_df = pd.read_sql_query("SELECT value, participating_ktvs FROM project_logs WHERE status = 'Đã duyệt' AND date LIKE ?", conn, params=(f"{m_pattern}%",))
        m_df = pd.read_sql_query("SELECT participating_ktvs FROM maintenance_logs WHERE status = 'Đã duyệt' AND date LIKE ?", conn, params=(f"{m_pattern}%",))
        fine_df = pd.read_sql_query("SELECT amount FROM fine_logs WHERE date LIKE ?", conn, params=(f"{m_pattern}%",))
        
    conn.close()
    
    total_p_val = p_df["value"].sum() if not p_df.empty else 0.0
    total_p_bonus = total_p_val * 0.005
    
    total_m_count = len(m_df) if not m_df.empty else 0
    total_m_bonus = total_m_count * 100000.0
    
    total_fine = fine_df["amount"].sum() if not fine_df.empty else 0.0
    
    base_pool = 35000000.0
    total_pool = base_pool + total_p_bonus + total_m_bonus - total_fine
    
    # Khởi tạo thưởng KPI riêng cho từng KTV
    ktv_bonuses = {ktv["name"]: 0.0 for ktv in KTV_PROFILE_LIST}
    
    # 1. Phân bổ thưởng 0.5% công trình CHỈ CHO KTV CÓ TÊN TRONG DANH SÁCH THỰC HỆN
    if not p_df.empty:
        for idx, row in p_df.iterrows():
            proj_bonus = row["value"] * 0.005
            p_ktvs_str = row["participating_ktvs"] if row["participating_ktvs"] else ", ".join(ALL_KTV_NAMES)
            p_ktvs_list = [k.strip() for k in p_ktvs_str.split(",") if k.strip() in ALL_KTV_NAMES]
            if not p_ktvs_list:
                p_ktvs_list = ALL_KTV_NAMES
            share_per_ktv = proj_bonus / len(p_ktvs_list)
            for ktv_name in p_ktvs_list:
                ktv_bonuses[ktv_name] += share_per_ktv

    # 2. Phân bổ thưởng 100k ca bảo trì CHỈ CHO KTV CÓ TÊN TRONG DANH SÁCH THỰC HỆN
    if not m_df.empty:
        for idx, row in m_df.iterrows():
            m_bonus_val = 100000.0
            m_ktvs_str = row["participating_ktvs"] if row["participating_ktvs"] else ", ".join(ALL_KTV_NAMES)
            m_ktvs_list = [k.strip() for k in m_ktvs_str.split(",") if k.strip() in ALL_KTV_NAMES]
            if not m_ktvs_list:
                m_ktvs_list = ALL_KTV_NAMES
            share_per_ktv = m_bonus_val / len(m_ktvs_list)
            for ktv_name in m_ktvs_list:
                ktv_bonuses[ktv_name] += share_per_ktv
                
    # 3. Tính toán tổng lương thu nhận thực tế của từng KTV
    res = []
    base_salary_per_ktv = 7000000.0 # Mức sàn cứng 7 triệu
    
    for ktv in KTV_PROFILE_LIST:
        k_name = ktv["name"]
        k_bonus = ktv_bonuses[k_name]
        k_allowance = ktv["allowance"]
        total_salary = base_salary_per_ktv + k_bonus + k_allowance
        
        res.append({
            "username": ktv["username"],
            "name": k_name,
            "title": ktv["title"],
            "avatar": ktv["avatar"],
            "allowance": k_allowance,
            "allowance_desc": ktv["allowance_desc"],
            "kpi_bonus": k_bonus,
            "base_salary": base_salary_per_ktv,
            "total_salary": total_salary
        })
        
    return {
        "total_pool": total_pool,
        "base_pool": base_pool,
        "p_bonus": total_p_bonus,
        "m_bonus": total_m_bonus,
        "p_val": total_p_val,
        "m_count": total_m_count,
        "fine_amount": total_fine,
        "ktv_salaries": res
    }

# Hàm mô phỏng & thực hiện bắn Webhook tin nhắn đến Zalo/Telegram
def send_zalo_webhook(message):
    st.sidebar.markdown(f"""
    <div style="background-color: #1E40AF; border-left: 5px solid #60A5FA; padding: 12px; border-radius: 6px; margin-top: 15px;">
        <span style="color: #93C5FD; font-size: 0.8rem; font-weight: bold; display: block;">💬 THÔNG BÁO NHÓM ZALO CHUNG:</span>
        <span style="color: white; font-size: 0.9rem;">{message}</span>
    </div>
    """, unsafe_allow_html=True)
    
    webhook_url = os.getenv("ZALO_WEBHOOK_URL")
    if not webhook_url:
        try:
            if hasattr(st, "secrets") and "ZALO_WEBHOOK_URL" in st.secrets:
                webhook_url = st.secrets["ZALO_WEBHOOK_URL"]
        except Exception:
            webhook_url = None
        
    if webhook_url:
        try:
            requests.post(webhook_url, json={"text": message}, timeout=3)
        except Exception:
            pass

def render_ai_assistant_page():
    st.markdown("### 🤖 Trợ Lý AI Trưởng Nhóm & Admin")
    st.info("💡 Bạn có thể nhập yêu cầu hoặc nhấn nút **Bấm để Nói** để ra lệnh cho trợ lý AI thực hiện các tác vụ tự động (chấm công, báo nghỉ phép, đăng ký công trình/bảo trì, duyệt đề xuất, báo cáo bảng lương...).")
    
    # 1. Cấu hình API Key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        try:
            if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
                api_key = st.secrets["GEMINI_API_KEY"]
        except Exception:
            pass
            
    # Hộp chứa Key tạm thời trong session
    if "temp_gemini_api_key" not in st.session_state:
        st.session_state.temp_gemini_api_key = ""
        
    if not api_key and not st.session_state.temp_gemini_api_key:
        with st.expander("🔑 Cấu hình API Key Gemini (Bắt buộc để chạy AI)", expanded=True):
            st.warning("⚠️ Không tìm thấy biến môi trường GEMINI_API_KEY hoặc Streamlit Secrets.")
            temp_key = st.text_input("Nhập khóa Gemini API Key của bạn (lấy tại Google AI Studio):", type="password")
            if st.button("Lưu tạm thời cho phiên làm việc này 💾"):
                if temp_key.strip():
                    st.session_state.temp_gemini_api_key = temp_key.strip()
                    st.success("Đã lưu API Key tạm thời!")
                    st.rerun()
                else:
                    st.error("Khóa API không được bỏ trống!")
            st.markdown("""
            *Để cấu hình vĩnh viễn:* Hãy tạo file `.streamlit/secrets.toml` trong thư mục dự án và thêm dòng sau:
            ```toml
            GEMINI_API_KEY = "Khóa_API_của_bạn"
            ```
            """)
            return
            
    active_api_key = api_key if api_key else st.session_state.temp_gemini_api_key
    
    # 2. Khởi tạo lịch sử chat trong session state
    if "ai_messages" not in st.session_state:
        st.session_state.ai_messages = [
            {"role": "assistant", "content": f"Xin chào **{st.session_state.fullname}**! Tôi là Trợ lý AI Solar 24H. Tôi có thể giúp gì cho bạn hôm nay?"}
        ]
        
    # Hiển thị các tin nhắn cũ
    for msg in st.session_state.ai_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    st.markdown("---")
    
    # 3. Ghi âm bằng st.audio_input (Native Streamlit 1.59+)
    audio_file = st.audio_input("Nhấn biểu tượng micro bên dưới để ghi âm và ra lệnh bằng giọng nói 🎤:")
    if audio_file:
        audio_bytes = audio_file.read()
        audio_id = hashlib.md5(audio_bytes).hexdigest()
        
        if "processed_audio_ids" not in st.session_state:
            st.session_state.processed_audio_ids = set()
            
        if audio_id not in st.session_state.processed_audio_ids:
            st.session_state.processed_audio_ids.add(audio_id)
            
            audio_data = {
                "mime_type": audio_file.type,
                "data": audio_bytes
            }
            
            # Hiển thị tin nhắn tạm thời của user
            with st.chat_message("user"):
                st.markdown("🎤 *[Đang gửi tin nhắn thoại...]*")
                
            with st.chat_message("assistant"):
                with st.spinner("Đang dịch thoại và thực thi tác vụ..."):
                    import importlib
                    import ai_assistant
                    importlib.reload(ai_assistant)
                    from ai_assistant import ask_gemini_assistant
                    response = ask_gemini_assistant(
                        user_prompt="Hãy dịch và thực hiện yêu cầu trong file âm thanh này.",
                        user_role=st.session_state.role,
                        user_fullname=st.session_state.fullname,
                        user_username=st.session_state.user,
                        api_key=active_api_key,
                        audio_data=audio_data
                    )
                    
                    # Phân tách bản dịch lời thoại từ response
                    user_text = "🎤 *[Tin nhắn thoại]*"
                    if response.startswith("[Bản dịch thoại:"):
                        try:
                            parts = response.split("]", 1)
                            trans_part = parts[0]
                            response = parts[1].strip()
                            
                            text_start = trans_part.find('"')
                            text_end = trans_part.rfind('"')
                            if text_start != -1 and text_end != -1:
                                user_text = f"🎤 *[Giọng nói: \"{trans_part[text_start+1:text_end]}\"]*"
                            else:
                                clean_trans = trans_part.replace('[Bản dịch thoại:', '').strip(" '\"][]")
                                user_text = f"🎤 *[Giọng nói: {clean_trans}]*"
                        except Exception:
                            pass
                    
                    # Cập nhật lịch sử chat
                    st.session_state.ai_messages.append({"role": "user", "content": user_text})
                    st.session_state.ai_messages.append({"role": "assistant", "content": response})
                    st.rerun()

    # 4. Ô nhập tin nhắn văn bản thông thường
    user_input = st.chat_input("Nhập câu lệnh hoặc câu hỏi của bạn tại đây...")
    if user_input:
        st.session_state.ai_messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
            
        with st.chat_message("assistant"):
            with st.spinner("Đang xử lý yêu cầu..."):
                import importlib
                import ai_assistant
                importlib.reload(ai_assistant)
                from ai_assistant import ask_gemini_assistant
                response = ask_gemini_assistant(
                    user_prompt=user_input,
                    user_role=st.session_state.role,
                    user_fullname=st.session_state.fullname,
                    user_username=st.session_state.user,
                    api_key=active_api_key
                )
                st.markdown(response)
                st.session_state.ai_messages.append({"role": "assistant", "content": response})
                st.rerun()

# ==========================================
# 4. HỆ THỐNG XÁC THỰC TÀI KHOẢN (AUTH)
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user = None
    st.session_state.fullname = ""
    st.session_state.role = ""
    st.session_state.avatar = ""
    st.session_state.title = ""

if not st.session_state.logged_in:
    st.markdown("<div class='login-box'>", unsafe_allow_html=True)
    if os.path.exists("Logo Solar 24h.png"):
        st.image("Logo Solar 24h.png", use_container_width=True)
    st.subheader("☀️ Đăng Nhập Hệ Thống Solar 24h")
    
    username_input = st.text_input("Tài khoản (Username):", placeholder="Ví dụ: thanhnc, namnh, thienvt, vinhtc...").strip().lower()
    password_input = st.text_input("Mật khẩu (Password):", type="password")
    
    if st.button("ĐĂNG NHẬP 🚀", use_container_width=True):
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT fullname, role, avatar, title FROM users WHERE username = ? AND password_hash = ?", 
                  (username_input, hash_password(password_input)))
        row = c.fetchone()
        conn.close()
        
        if row:
            st.session_state.logged_in = True
            st.session_state.user = username_input
            st.session_state.fullname = row[0]
            st.session_state.role = row[1]
            st.session_state.avatar = row[2]
            st.session_state.title = row[3] if row[3] else row[1]
            st.rerun()
        else:
            st.error("❌ Sai tài khoản hoặc mật khẩu. Vui lòng nhập lại!")
    st.markdown("</div>", unsafe_allow_html=True)

else:
    # Sidebar Logo & Thông tin nhân sự đang đăng nhập
    if os.path.exists("Logo Solar 24h.png"):
        st.sidebar.image("Logo Solar 24h.png", use_container_width=True)
    
    st.sidebar.markdown("---")
    
    # Khối profile nhân sự đăng nhập
    col_av1, col_av2 = st.sidebar.columns([1, 2])
    with col_av1:
        user_avt = st.session_state.avatar if st.session_state.avatar and os.path.exists(st.session_state.avatar) else "Logo Solar 24h.png"
        if os.path.exists(user_avt):
            st.image(user_avt, use_container_width=True)
        else:
            st.markdown("👤")
    with col_av2:
        st.markdown(f"👤 **{st.session_state.fullname}**")
        st.markdown(f"💼 **{st.session_state.title}**")
        st.markdown(f"🆔 Tài khoản: `{st.session_state.user}`")
        
    if st.sidebar.button("Đăng xuất 🔓", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.fullname = ""
        st.session_state.role = ""
        st.session_state.avatar = ""
        st.session_state.title = ""
        st.rerun()
        
    st.sidebar.markdown("---")

    # Header ứng dụng với ảnh thương hiệu
    col_hdr1, col_hdr2 = st.columns([1, 6])
    with col_hdr1:
        if os.path.exists("Logo Solar 24h.png"):
            st.image("Logo Solar 24h.png", width=90)
    with col_hdr2:
        st.markdown("""
            <div class="main-header" style="margin-bottom: 15px; padding: 15px 25px;">
                <h1 style="font-size: 1.9rem;">☀️ SOLAR 24H - PHÂN HỆ QUẢN TRỊ KỸ THUẬT</h1>
                <p>Hệ Thống Chấm Công Chụp Ảnh Timemark & Tính Lương KPI Thực Tế (Giờ VN - UTC+7)</p>
            </div>
        """, unsafe_allow_html=True)

    # Kiểm tra phân quyền Trưởng Nhóm
    is_team_leader = ("Trưởng Nhóm" in st.session_state.title) or (st.session_state.role == "Admin")

    # ==========================================
    # 5. PHÂN HỆ MENU THEO QUYỀN HẠN
    # ==========================================
    if st.session_state.role == "KTV":
        menu = st.sidebar.radio(
            "CHỌN CHỨC NĂNG SỬ DỤNG:",
            ["🤖 Trợ Lý AI Trưởng Nhóm", "🕒 Chấm Công Thực Địa", "🏗️ Đăng Ký Dự Án & Ca Sửa Chữa", "📊 Báo Cáo Quỹ Lương Chung"]
        )
        
        # ------------------------------------------
        # KTV - CHỨC NĂNG 0: TRỢ LÝ AI TRƯỞNG NHÓM
        # ------------------------------------------
        if menu == "🤖 Trợ Lý AI Trưởng Nhóm":
            render_ai_assistant_page()
            
        # ------------------------------------------
        # KTV - CHỨC NĂNG 1: CHẤM CÔNG THỰC ĐỊA
        # ------------------------------------------
        elif menu == "🕒 Chấm Công Thực Địa":
            st.markdown("### 🕒 Chấm Công Định Vị & Đính Kèm Ảnh Timemark")
            
            # Hiển thị thẻ thông tin cá nhân KTV
            col_prof1, col_prof2 = st.columns([1, 4])
            with col_prof1:
                cur_avt = st.session_state.avatar
                if cur_avt and os.path.exists(cur_avt):
                    st.image(cur_avt, caption=st.session_state.fullname, use_container_width=True)
            with col_prof2:
                st.markdown(f"**Nhân sự báo cáo:** {st.session_state.fullname} | **Chức vụ:** `{st.session_state.title}`")
                if is_team_leader:
                    st.success("✅ **Quyền Trưởng Nhóm:** Bạn có quyền khởi tạo báo cáo chấm công hiện trường và chọn danh sách KTV tham gia ca làm việc.")
                else:
                    st.warning("⚠️ **Thông báo phân quyền:** Chức năng gửi báo cáo chấm công hiện trường do các **Trưởng nhóm** (`Nguyễn Chí Thanh` - Trưởng Nhóm Thi Công, `Nguyễn Hoàng Nam` - Trưởng Nhóm Bảo Trì) đại diện thực hiện. Anh em KTV tham gia ca làm việc sẽ do Trưởng nhóm chọn vào báo cáo.")

            if not is_team_leader:
                st.info("ℹ️ Anh em KTV có thể kiểm tra danh sách ca làm việc và tiến độ Quỹ lương chung tại menu **Báo Cáo Quỹ Lương Chung**.")
            else:
                tab_att_send, tab_leave_send = st.tabs(["🚀 Chấm Công Ca Làm Việc", "🏖️ Đăng Ký Báo Nghỉ Phép (P)"])
                
                with tab_att_send:
                    with st.form("att_form", clear_on_submit=True):
                        work_select = st.selectbox(
                            "1. Chọn loại công việc thực tế ngoài công trường:",
                            [
                                "Thi công lắp đặt mới (Hệ Solar / Trạm sạc)",
                                "Bảo trì định kỳ / Khắc phục sự cố tủ điện, inverter",
                                "Hỗ trợ công việc lao động phổ thông, dọn dẹp kho"
                            ]
                        )
                        
                        # Hộp chọn Dropdown Danh sách KTV cùng tham gia ca làm việc
                        default_selected = [st.session_state.fullname] if st.session_state.fullname in ALL_KTV_NAMES else ALL_KTV_NAMES[:1]
                        ktv_participants = st.multiselect(
                            "2. Chọn danh sách Kỹ thuật viên cùng tham gia ca công việc:",
                            options=ALL_KTV_NAMES,
                            default=default_selected,
                            help="Chọn một hoặc nhiều anh em KTV thực tế cùng tham gia làm việc tại công trường"
                        )
                        
                        note_input = st.text_area("3. Ghi chú hiện trường (tiến độ, lý do phát sinh nếu có):")
                        
                        # Tải ảnh Timemark để đối chứng
                        photo_file = st.file_uploader("4. Đính kèm ảnh chụp Timemark (Có đóng dấu GPS & Ngày Giờ):", type=["jpg", "png", "jpeg"])
                        
                        submit_btn = st.form_submit_button("GỬI BÁO CÁO CHẤM CÔNG 🚀")
                        
                        if submit_btn:
                            if not photo_file:
                                st.error("⚠️ Bắt buộc phải đính kèm ảnh Timemark để xác thực ngày giờ và tọa độ!")
                            elif not ktv_participants:
                                st.error("⚠️ Vui lòng chọn ít nhất 1 Kỹ thuật viên tham gia ca làm việc!")
                            else:
                                now_vn = get_vn_now()
                                date_str = now_vn.strftime("%Y-%m-%d")
                                time_str = now_vn.strftime("%H:%M:%S")
                                
                                # Lưu file ảnh thực tế vào thư mục uploads
                                file_ext = os.path.splitext(photo_file.name)[1]
                                saved_filename = f"{st.session_state.user}_{now_vn.strftime('%Y%m%d_%H%M%S')}{file_ext}"
                                saved_path = os.path.join(UPLOAD_DIR, saved_filename)
                                with open(saved_path, "wb") as f:
                                    f.write(photo_file.getbuffer())
                                
                                participating_str = ", ".join(ktv_participants)
                                
                                # Lưu thông tin vào database
                                conn = get_connection()
                                c = conn.cursor()
                                c.execute("""
                                    INSERT INTO attendance (date, time, username, fullname, work_type, note, photo_name, participating_ktvs)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """, (date_str, time_str, st.session_state.user, st.session_state.fullname, work_select, note_input, saved_filename, participating_str))
                                conn.commit()
                                conn.close()
                                
                                st.success(f"🎉 Gửi báo cáo chấm công thành công lúc {time_str} ngày {date_str} (Giờ VN) cho {len(ktv_participants)} KTV!")
                                st.balloons()
                                
                with tab_leave_send:
                    with st.form("leave_form", clear_on_submit=True):
                        leave_target_ktv = st.selectbox("Chọn nhân sự xin nghỉ phép:", options=ALL_KTV_NAMES)
                        leave_date_input = st.date_input("Ngày xin nghỉ phép:", value=get_vn_now().date())
                        leave_type_input = st.selectbox("Loại nghỉ phép:", ["Nghỉ phép năm (P)", "Nghỉ việc riêng có phép (P)", "Nghỉ bệnh / Khác (P)", "Nghỉ không phép (KP)"])
                        leave_reason_input = st.text_area("Lý do xin nghỉ phép (Ví dụ: Việc gia đình, đi khám bệnh...):")
                        
                        submit_leave = st.form_submit_button("XÁC NHẬN BÁO NGHỈ PHÉP 🏖️")
                        if submit_leave:
                            if leave_reason_input.strip() == "":
                                st.error("Vui lòng điền lý do xin nghỉ phép!")
                            else:
                                target_uname = next((k["username"] for k in KTV_PROFILE_LIST if k["name"] == leave_target_ktv), "ktv")
                                
                                conn = get_connection()
                                c = conn.cursor()
                                c.execute("""
                                    INSERT INTO leave_logs (date, username, fullname, leave_type, reason, logged_by)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (leave_date_input.strftime("%Y-%m-%d"), target_uname, leave_target_ktv, leave_type_input, leave_reason_input.strip(), st.session_state.fullname))
                                conn.commit()
                                conn.close()
                                
                                st.success(f"🏖️ Đã ghi nhận lịch nghỉ phép cho {leave_target_ktv} vào ngày {leave_date_input.strftime('%d/%m/%Y')} (Ký hiệu: P)!")
                                send_zalo_webhook(f"[Solar 24h Web App] {st.session_state.title} {st.session_state.fullname} vừa đăng ký nghỉ phép cho KTV {leave_target_ktv} ngày {leave_date_input.strftime('%d/%m/%Y')}. Lý do: {leave_reason_input.strip()}.")
                        
        # ------------------------------------------
        # KTV - CHỨC NĂNG 2: ĐĂNG KÝ SẢN LƯỢNG (DỰ ÁN & BẢO TRÌ)
        # ------------------------------------------
        elif menu == "🏗️ Đăng Ký Dự Án & Ca Sửa Chữa":
            st.markdown("### 🏗️ Khai Báo Nghiệm Thu Công Trình & Ca Bảo Trì")
            
            if not is_team_leader:
                st.warning("⚠️ **Thông báo phân quyền:** Chức năng đăng ký nghiệm thu công trình mới (thưởng 0.5%) và ca bảo trì sự cố (thưởng 100k) chỉ dành cho 2 **Trưởng nhóm** (`Nguyễn Chí Thanh` - Trưởng Nhóm Thi Công, `Nguyễn Hoàng Nam` - Trưởng Nhóm Bảo Trì) đại diện đề xuất lên Ban Giám Đốc.")
                st.info("ℹ️ Anh em KTV có thể theo dõi tiến độ đăng ký và duyệt thưởng tại menu **Báo Cáo Quỹ Lương Chung**.")
            else:
                st.success(f"✅ **Quyền Trưởng Nhóm:** Bạn ({st.session_state.fullname} - `{st.session_state.title}`) có quyền khởi tạo yêu cầu duyệt thưởng công trình mới và ca bảo trì.")
                tab_p, tab_m = st.tabs(["🏗️ Công Trình Lắp Đặt Mới (Thưởng 0.5%)", "⚡ Ca Bảo Trì Sự Cố (Thưởng 100k)"])
                
                with tab_p:
                    with st.form("p_form", clear_on_submit=False):
                        p_name = st.text_input("1. Tên dự án lắp đặt mới đã hoàn thiện đóng điện:", placeholder="Ví dụ: Lắp đặt hệ Solar F8 Gò Công")
                        p_val = st.number_input("2. Tổng giá trị hợp đồng thi công bàn giao (VNĐ):", min_value=0.0, step=1000000.0, format="%.0f")
                        
                        p_ktv_participants = st.multiselect(
                            "3. Chọn danh sách KTV trực tiếp thi công công trình này (Tiền thưởng 0.5% sẽ CHỈ CHIA ĐỀU cho các KTV này):",
                            options=ALL_KTV_NAMES,
                            default=ALL_KTV_NAMES,
                            help="Những KTV được tích chọn mới được chia tiền thưởng 0.5% của công trình này"
                        )
                        
                        # Khối hiển thị định dạng số tiền trực quan real-time
                        if p_val > 0:
                            v_str = fmt_vnd(p_val)
                            b_str = fmt_vnd(p_val * 0.005)
                            num_p = len(p_ktv_participants) if p_ktv_participants else 1
                            per_p_str = fmt_vnd((p_val * 0.005) / num_p)
                            
                            st.markdown(f"""
                            <div style="background-color: #0F172A; border-left: 5px solid #FF7A00; padding: 14px 18px; border-radius: 8px; margin: 12px 0;">
                                <span style="color: #94A3B8; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; display: block;">💵 XÁC NHẬN SỐ TIỀN HIỂN THỊ DỄ ĐỌC:</span>
                                <span style="color: #4ADE80; font-size: 1.55rem; font-weight: 800;">{v_str} VNĐ</span>
                                <span style="color: #FF7A00; font-size: 1rem; font-weight: 700; margin-left: 15px;">(Thưởng 0.5% dự kiến: +{b_str} VNĐ ➔ Chia {num_p} KTV trực tiếp làm: +{per_p_str} đ/người)</span>
                            </div>
                            """, unsafe_allow_html=True)
                            
                        submit_p = st.form_submit_button("Gửi Yêu Cầu Duyệt Thưởng 🏗️")
                        
                        if submit_p:
                            if p_name.strip() == "" or p_val == 0:
                                st.error("Vui lòng điền đầy đủ tên dự án và giá trị hợp đồng!")
                            elif not p_ktv_participants:
                                st.error("Vui lòng chọn ít nhất 1 KTV trực tiếp tham gia thi công công trình!")
                            else:
                                today_str = get_vn_date_str()
                                p_ktvs_str = ", ".join(p_ktv_participants)
                                conn = get_connection()
                                c = conn.cursor()
                                c.execute("""
                                    INSERT INTO project_logs (date, project_name, value, registered_by, status, approved_by, approved_at, participating_ktvs)
                                    VALUES (?, ?, ?, ?, 'Chờ duyệt', '-', '-', ?)
                                """, (today_str, p_name.strip(), p_val, f"{st.session_state.fullname} ({st.session_state.title})", p_ktvs_str))
                                conn.commit()
                                conn.close()
                                
                                st.success(f"🚀 Đã gửi đề xuất duyệt thưởng công trình {p_name.strip()} ({fmt_vnd(p_val)} VNĐ) cho {len(p_ktv_participants)} KTV tham gia trực tiếp!")
                                send_zalo_webhook(f"[Solar 24h Web App] {st.session_state.title} {st.session_state.fullname} báo cáo hoàn thành lắp đặt {p_name.strip()} ({fmt_vnd(p_val)} đ) với {len(p_ktv_participants)} KTV tham gia. Chờ duyệt thưởng 0.5%.")

                with tab_m:
                    with st.form("m_form", clear_on_submit=True):
                        m_client = st.text_input("1. Tên khách hàng sự cố sửa chữa:", placeholder="Ví dụ: Ca bảo trì trạm sạc Cái Bè")
                        m_loc = st.text_input("2. Vị trí địa điểm khu vực sửa chữa:", placeholder="Ví dụ: Cái Bè, Tiền Giang")
                        
                        m_ktv_participants = st.multiselect(
                            "3. Chọn danh sách KTV trực tiếp thực hiện ca bảo trì này (Thưởng 100k CHỈ CHIA ĐỀU cho các KTV này):",
                            options=ALL_KTV_NAMES,
                            default=ALL_KTV_NAMES,
                            help="Những KTV được chọn mới được chia 100.000 đ tiền thưởng ca bảo trì này"
                        )
                        
                        submit_m = st.form_submit_button("Báo Cáo Ca Bảo Trì Hoàn Thành ⚡")
                        
                        if submit_m:
                            if m_client.strip() == "" or m_loc.strip() == "":
                                st.error("Vui lòng nhập đầy đủ thông tin khách hàng và khu vực sửa chữa!")
                            elif not m_ktv_participants:
                                st.error("Vui lòng chọn ít nhất 1 KTV trực tiếp thực hiện ca bảo trì!")
                            else:
                                today_str = get_vn_date_str()
                                m_ktvs_str = ", ".join(m_ktv_participants)
                                conn = get_connection()
                                c = conn.cursor()
                                c.execute("""
                                    INSERT INTO maintenance_logs (date, client_name, location, registered_by, status, approved_by, approved_at, participating_ktvs)
                                    VALUES (?, ?, ?, ?, 'Chờ duyệt', '-', '-', ?)
                                """, (today_str, m_client.strip(), m_loc.strip(), f"{st.session_state.fullname} ({st.session_state.title})", m_ktvs_str))
                                conn.commit()
                                conn.close()
                                
                                st.success(f"🚀 Đã gửi đề xuất duyệt ca sửa chữa {m_client.strip()} cho {len(m_ktv_participants)} KTV thực hiện!")
                                send_zalo_webhook(f"[Solar 24h Web App] {st.session_state.title} {st.session_state.fullname} vừa nộp báo cáo hoàn thành ca bảo trì {m_client.strip()} ({m_loc.strip()}) cho {len(m_ktv_participants)} KTV. Chờ phê duyệt từ Anh Sang / Anh Việt.")

        # ------------------------------------------
        # KTV - CHỨC NĂNG 3: BÁO CÁO QUỸ LƯƠNG CHUNG
        # ------------------------------------------
        elif menu == "📊 Báo Cáo Quỹ Lương Chung":
            st.markdown("### 📊 Tiến Độ Tích Lũy Quỹ Lương KPI Thực Tế")
            
            # Chọn Tháng Quyết Toán
            cur_month_str = get_vn_now().strftime("%m/%Y")
            selected_month = st.selectbox("📅 Chọn kỳ quyết toán lương theo tháng:", [f"Tháng {cur_month_str}", "Tất cả các tháng tích lũy"])
            
            calc = calculate_individual_salaries(selected_month)
            
            st.markdown(f"""
            <div style="background-color: #0F172A; padding: 25px; border-radius: 12px; border: 2px dashed #FF7A00; text-align: center; color: white;">
                <span style="font-size: 0.9rem; opacity: 0.8; text-transform: uppercase;">💰 TỔNG QUỸ LƯƠNG & KPI CHUNG CẢ ĐỘI ({selected_month.upper()})</span>
                <h1 style="color: #FF7A00; margin: 5px 0; font-size: 2.5rem;">{fmt_vnd(calc['total_pool'])} đ</h1>
                <p style="font-size: 1rem; font-weight: bold; margin: 0; background-color: rgba(255,255,255,0.1); display: inline-block; padding: 5px 15px; border-radius: 20px; color: #4ADE80;">
                    ⭐ Cơ chế Giải Pháp 1: Lương cứng 7tr/người + Thưởng KPI 0.5% chia CHỈ CHO KTV TRỰC TIẾP THAM GIA
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown(f"<div class='metric-card'><span>🏗️ Thưởng dự án (0.5%)</span><h2>+{fmt_vnd(calc['p_bonus'])} đ</h2><p>Đã duyệt tổng {fmt_vnd(calc['p_val'])} đ công trình</p></div>", unsafe_allow_html=True)
            with col2:
                st.markdown(f"<div class='metric-card'><span>⚡ Thưởng bảo trì (100k)</span><h2>+{fmt_vnd(calc['m_bonus'])} đ</h2><p>Đã nghiệm thu duyệt {calc['m_count']} ca</p></div>", unsafe_allow_html=True)
            with col3:
                st.markdown(f"<div class='metric-card'><span>⚠️ Phạt trừ chế tài</span><h2 style='color: #EF4444;'>-{fmt_vnd(calc['fine_amount'])} đ</h2><p>Do vi phạm thi công & dịch vụ</p></div>", unsafe_allow_html=True)

            st.markdown("---")
            st.markdown("### 👥 Bảng Thống Kê Thu Nhập Thực Nhận Cá Nhân 5 KTV (Giải Pháp 1):")
            
            # Hiển thị 5 Card KTV với mức thu nhập chính xác từng người
            cols_ktv = st.columns(5)
            for i, ktv in enumerate(calc["ktv_salaries"]):
                with cols_ktv[i]:
                    st.markdown("<div class='ktv-card'>", unsafe_allow_html=True)
                    if os.path.exists(ktv["avatar"]):
                        st.image(ktv["avatar"], use_container_width=True)
                    st.markdown(f"#### {ktv['name']}</h4>", unsafe_allow_html=True)
                    st.markdown(f"<span class='role-title'>{ktv['title']}</span>", unsafe_allow_html=True)
                    st.markdown(f"<p style='margin:5px 0; font-size:0.95rem; font-weight:bold; color:#10B981;'>📞 {ktv.get('phone', '')}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p>Lương cứng: <b>7.000.000 đ</b></p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='color:#FF7A00;'>Thưởng KPI làm thực tế: <b>+{fmt_vnd(ktv['kpi_bonus'])} đ</b></p>", unsafe_allow_html=True)
                    if ktv["allowance"] > 0:
                        st.markdown(f"<p style='color:#60A5FA;'>Phụ cấp: <b>+{fmt_vnd(ktv['allowance'])} đ</b></p>", unsafe_allow_html=True)
                    st.markdown(f"<span class='salary-tag'>THỰC NHẬN: {fmt_vnd(ktv['total_salary'])} đ</span>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)

    # ==========================================
    # 6. PHÂN HỆ QUẢN TRỊ VIÊN (SANG HR / VIỆT DIRECTOR)
    # ==========================================
    elif st.session_state.role == "Admin":
        menu = st.sidebar.radio(
            "CHỌN CHỨC NĂNG QUẢN LÝ:",
            ["🤖 Trợ Lý AI Trưởng Nhóm", "📝 Duyệt KPI Kỹ Thuật", "📊 Tính Toán Toàn Cảnh Bảng Lương", "🕒 Nhật Ký Chấm Công KTV", "⚠️ Ghi Nhận Lỗi Phạt", "👥 Danh Sách KTV & Ảnh Hồ Sơ"]
        )
        
        # ------------------------------------------
        # ADMIN - CHỨC NĂNG 0: TRỢ LÝ AI TRƯỞNG NHÓM
        # ------------------------------------------
        if menu == "🤖 Trợ Lý AI Trưởng Nhóm":
            render_ai_assistant_page()
            
        # ------------------------------------------
        # ADMIN - CHỨC NĂNG 1: DUYỆT CÔNG TRÌNH / BẢO TRÌ
        # ------------------------------------------
        elif menu == "📝 Duyệt KPI Kỹ Thuật":
            st.markdown("### 📝 Phê Duyệt Ca Bảo Trì & Thưởng Công Trình Mới")
            st.info("💡 Bất kỳ khoản thưởng nào do Trưởng nhóm đề xuất đều phải được Admin (Anh Sang / Sếp Việt) bấm **Duyệt Thưởng ✅** thì mới được cộng vào Quỹ Lương Chung.")
            
            conn = get_connection()
            c = conn.cursor()
            
            # Khối duyệt 0.5% công trình lắp ráp mới
            st.markdown("#### 1. Các đề xuất Thưởng Công Trình Mới (0.5%):")
            pending_p = pd.read_sql_query("SELECT * FROM project_logs WHERE status = 'Chờ duyệt'", conn)
            
            if pending_p.empty:
                st.success("✅ Hiện không có công trình nào đang chờ xét duyệt.")
            else:
                for idx, row in pending_p.iterrows():
                    col_det, col_by, col_bn = st.columns([3, 1, 1])
                    p_ktvs_display = row['participating_ktvs'] if ('participating_ktvs' in row and row['participating_ktvs']) else "Cả 5 KTV"
                    with col_det:
                        st.markdown(f"📦 **{row['project_name']}** | Hợp đồng: **{fmt_vnd(row['value'])} VNĐ** | Thưởng 0.5%: **+{fmt_vnd(row['value']*0.005)} VNĐ**  \n👷 *KTV nhận thưởng:* `{p_ktvs_display}` | Đề xuất: **{row['registered_by']}**")
                    with col_by:
                        if st.button("Duyệt Thưởng ✅", key=f"app_p_{row['id']}"):
                            c.execute("UPDATE project_logs SET status = 'Đã duyệt', approved_by = ?, approved_at = ? WHERE id = ?", 
                                      (st.session_state.fullname, get_vn_date_str(), row['id']))
                            conn.commit()
                            st.success(f"🎉 Đã phê duyệt cộng +{fmt_vnd(row['value']*0.005)} VNĐ chia trực tiếp cho KTV tham gia!")
                            st.rerun()
                    with col_bn:
                        if st.button("Bác Bỏ ❌", key=f"rej_p_{row['id']}"):
                            c.execute("UPDATE project_logs SET status = 'Bác bỏ', approved_by = ?, approved_at = ? WHERE id = ?", 
                                      (st.session_state.fullname, get_vn_date_str(), row['id']))
                            conn.commit()
                            st.warning("Đã bác bỏ đề xuất!")
                            st.rerun()
                            
            st.markdown("---")
            
            # Khối duyệt 100k ca bảo trì
            st.markdown("#### 2. Các đề xuất Thưởng Ca Bảo Trì Khẩn Cấp (100.000 đ):")
            pending_m = pd.read_sql_query("SELECT * FROM maintenance_logs WHERE status = 'Chờ duyệt'", conn)
            
            if pending_m.empty:
                st.success("✅ Hiện không có ca bảo trì nào đang chờ xét duyệt.")
            else:
                for idx, row in pending_m.iterrows():
                    col_m_det, col_m_by, col_m_bn = st.columns([3, 1, 1])
                    m_ktvs_display = row['participating_ktvs'] if ('participating_ktvs' in row and row['participating_ktvs']) else "Cả 5 KTV"
                    with col_m_det:
                        st.markdown(f"⚡ **Khách hàng:** {row['client_name']} | Khu vực: **{row['location']}**  \n👷 *KTV thực hiện nhận 100k:* `{m_ktvs_display}` | Báo cáo bởi: **{row['registered_by']}**")
                    with col_m_by:
                        if st.button("Phê Duyệt ✅", key=f"app_m_{row['id']}"):
                            c.execute("UPDATE maintenance_logs SET status = 'Đã duyệt', approved_by = ?, approved_at = ? WHERE id = ?", 
                                      (st.session_state.fullname, get_vn_date_str(), row['id']))
                            conn.commit()
                            st.success("🎉 Đã phê duyệt cộng +100.000 VNĐ chia cho KTV thực hiện!")
                            st.rerun()
                    with col_m_bn:
                        if st.button("Bác Bỏ ❌", key=f"rej_m_{row['id']}"):
                            c.execute("UPDATE maintenance_logs SET status = 'Bác bỏ', approved_by = ?, approved_at = ? WHERE id = ?", 
                                      (st.session_state.fullname, get_vn_date_str(), row['id']))
                            conn.commit()
                            st.warning("Đã bác bỏ ca bảo trì!")
                            st.rerun()

            st.markdown("---")
            # KHỐI LỊCH SỬ ĐÃ XỬ LÝ KÈM NÚT HOÀN TÁC (UNDO / REDO)
            st.markdown("#### 🔄 Lịch Sử Đã Phê Duyệt / Bác Bỏ (Khôi Phục Nếu Bấm Nhầm):")
            processed_p = pd.read_sql_query("SELECT * FROM project_logs WHERE status != 'Chờ duyệt' ORDER BY id DESC", conn)
            processed_m = pd.read_sql_query("SELECT * FROM maintenance_logs WHERE status != 'Chờ duyệt' ORDER BY id DESC", conn)
            
            with st.expander("📂 Xem danh sách đề xuất đã duyệt / bác bỏ & Nút Hoàn Tác (Undo)"):
                if processed_p.empty and processed_m.empty:
                    st.info("Chưa có lịch sử phê duyệt nào.")
                else:
                    if not processed_p.empty:
                        st.write("**Công trình lắp đặt:**")
                        for idx, row in processed_p.iterrows():
                            col_p1, col_p2 = st.columns([4, 1.2])
                            status_tag = "✅ ĐÃ DUYỆT" if row['status'] == 'Đã duyệt' else "❌ ĐÃ BÁC BỎ"
                            p_k_str = row['participating_ktvs'] if ('participating_ktvs' in row and row['participating_ktvs']) else "Cả 5 KTV"
                            with col_p1:
                                st.write(f"[{status_tag}] **{row['project_name']}** ({fmt_vnd(row['value'])} VNĐ) - Thưởng 0.5%: +{fmt_vnd(row['value']*0.005)} đ | KTV nhận: `{p_k_str}`")
                            with col_p2:
                                if st.button("↺ Hoàn Tác (Undo)", key=f"undo_p_{row['id']}"):
                                    c.execute("UPDATE project_logs SET status = 'Chờ duyệt', approved_by = '-', approved_at = '-' WHERE id = ?", (row['id'],))
                                    conn.commit()
                                    st.success("Đã hoàn tác đề xuất về trạng thái Chờ duyệt!")
                                    st.rerun()
                    if not processed_m.empty:
                        st.write("**Ca bảo trì:**")
                        for idx, row in processed_m.iterrows():
                            col_m1, col_m2 = st.columns([4, 1.2])
                            status_tag = "✅ ĐÃ DUYỆT" if row['status'] == 'Đã duyệt' else "❌ ĐÃ BÁC BỎ"
                            m_k_str = row['participating_ktvs'] if ('participating_ktvs' in row and row['participating_ktvs']) else "Cả 5 KTV"
                            with col_m1:
                                st.write(f"[{status_tag}] **{row['client_name']}** ({row['location']}) - Thưởng 100k | KTV nhận: `{m_k_str}`")
                            with col_m2:
                                if st.button("↺ Hoàn Tác (Undo)", key=f"undo_m_{row['id']}"):
                                    c.execute("UPDATE maintenance_logs SET status = 'Chờ duyệt', approved_by = '-', approved_at = '-' WHERE id = ?", (row['id'],))
                                    conn.commit()
                                    st.success("Đã hoàn tác ca bảo trì về trạng thái Chờ duyệt!")
                                    st.rerun()
                                    
            conn.close()

        # ------------------------------------------
        # ADMIN - CHỨC NĂNG 2: BẢNG LƯƠNG TỔNG QUAN
        # ------------------------------------------
        elif menu == "📊 Tính Toán Toàn Cảnh Bảng Lương":
            st.markdown("### 📊 Quỹ Lương Tích Lũy & Bảng Tính Thu Nhập Trọn Gói")
            
            # Chọn Kỳ Quyết Toán Theo Tháng
            cur_month_str = get_vn_now().strftime("%m/%Y")
            selected_month = st.selectbox("📅 Chọn kỳ quyết toán lương theo tháng:", [f"Tháng {cur_month_str}", "Tất cả các tháng tích lũy"])
            
            calc = calculate_individual_salaries(selected_month)
            
            # Hiển thị Dashboard chỉ số
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.markdown(f"<div class='metric-box'><span>💼 Quỹ cứng cố định</span><div class='metric-value'>{fmt_vnd(calc['base_pool'])} đ</div></div>", unsafe_allow_html=True)
            with col_m2:
                st.markdown(f"<div class='metric-box'><span>🏗️ Thưởng dự án (0.5%)</span><div class='metric-value' style='color:#4ADE80'>+{fmt_vnd(calc['p_bonus'])} đ</div></div>", unsafe_allow_html=True)
            with col_m3:
                st.markdown(f"<div class='metric-box'><span>⚡ Thưởng ca sửa chữa (100k)</span><div class='metric-value' style='color:#4ADE80'>+{fmt_vnd(calc['m_bonus'])} đ</div></div>", unsafe_allow_html=True)
            with col_m4:
                st.markdown(f"<div class='metric-box'><span>⚠️ Phạt lỗi chế tài</span><div class='metric-value' style='color:#FCA5A5'>-{fmt_vnd(calc['fine_amount'])} đ</div></div>", unsafe_allow_html=True)
                
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(f"""
            <div style='background-color: #1E293B; border: 2px dashed #FF7A00; padding: 25px; border-radius: 12px; text-align: center; margin-bottom: 25px;'>
                <h2 style='color: white; margin: 0;'>🔥 TỔNG QUỸ LƯƠNG CHUNG QUYẾT TOÁN ({selected_month.upper()}): <span style='color: #FF7A00;'>{fmt_vnd(calc['total_pool'])} đ</span></h2>
                <h4 style='color: #94A3B8; margin: 8px 0 0 0;'>⭐ Áp dụng Giải Pháp 1: Thưởng KPI 0.5% & 100k chia CHỈ CHO KTV TRỰC TIẾP LÀM CÔNG TRÌNH</h4>
            </div>
            """, unsafe_allow_html=True)
            
            # Khối thẻ KTV kèm hình ảnh
            st.markdown("#### 👥 Thống Kê Thu Nhập Thực Nhận Chi Tiết Từng Nhân Sự:")
            cols_ktv_s = st.columns(5)
            for i, ktv in enumerate(calc["ktv_salaries"]):
                with cols_ktv_s[i]:
                    st.markdown("<div class='ktv-card'>", unsafe_allow_html=True)
                    if os.path.exists(ktv["avatar"]):
                        st.image(ktv["avatar"], use_container_width=True)
                    st.markdown(f"#### {ktv['name']}</h4>", unsafe_allow_html=True)
                    st.markdown(f"<span class='role-title'>{ktv['title']}</span>", unsafe_allow_html=True)
                    st.markdown(f"<p style='margin:5px 0; font-size:0.95rem; font-weight:bold; color:#10B981;'>📞 {ktv.get('phone', '')}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p>Lương cứng: <b>7.000.000 đ</b></p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='color:#FF7A00;'>Thưởng KPI thi công: <b>+{fmt_vnd(ktv['kpi_bonus'])} đ</b></p>", unsafe_allow_html=True)
                    if ktv["allowance"] > 0:
                        st.markdown(f"<p style='color:#60A5FA;'>Phụ cấp: <b>+{fmt_vnd(ktv['allowance'])} đ</b></p>", unsafe_allow_html=True)
                    st.markdown(f"<span class='salary-tag'>THỰC NHẬN: {fmt_vnd(ktv['total_salary'])} đ</span>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
            
            # Bảng xuất lương chi tiết
            salary_data = []
            for ktv in calc["ktv_salaries"]:
                salary_data.append({
                    "Tài khoản": ktv["username"],
                    "KTV nhận lương": ktv["name"],
                    "Chức vụ": ktv["title"],
                    "Mức sàn cứng": "7.000.000 đ",
                    "Thưởng KPI Công Trình (Giải Pháp 1)": f"+{fmt_vnd(ktv['kpi_bonus'])} đ",
                    "Phụ cấp trách nhiệm": ktv["allowance_desc"],
                    "THỰC NHẬN TRONG THÁNG": f"{fmt_vnd(ktv['total_salary'])} đ"
                })
            st.table(pd.DataFrame(salary_data))

        # ------------------------------------------
        # ADMIN - CHỨC NĂNG 3: XEM NHẬT KÝ CHẤM CÔNG
        # ------------------------------------------
        elif menu == "🕒 Nhật Ký Chấm Công KTV":
            st.markdown("### 🕒 Nhật Ký Chấm Công & Bảng Ma Trận Công Tháng")
            
            now_dt = get_vn_now()
            days_in_month = calendar.monthrange(now_dt.year, now_dt.month)[1]
            
            tab_matrix, tab_detail, tab_leave_list = st.tabs(["📊 Bảng Ma Trận Công Excel Theo Tháng", "🖼️ Nhật Ký Chi Tiết & Ảnh Timemark", "🏖️ Lịch Sử Xin Nghỉ Phép (P)"])
            
            conn = get_connection()
            att_df_raw = pd.read_sql_query("SELECT date, username, fullname, participating_ktvs FROM attendance", conn)
            leave_df_raw = pd.read_sql_query("SELECT date, username, fullname, leave_type, reason FROM leave_logs", conn)
            
            with tab_matrix:
                st.markdown(f"#### 📅 Bảng Ma Trận Theo Dõi Ngày Công (Tháng {now_dt.strftime('%m/%Y')}):")
                st.markdown("""
                <div style='background-color: #1E293B; border: 1px solid #334155; padding: 10px 15px; border-radius: 8px; margin-bottom: 15px; font-size: 0.88rem;'>
                    <b>📌 BẢNG CHÚ GIẢI KÝ HIỆU CHẤM CÔNG:</b><br>
                    <span style='color:#4ADE80; font-weight:bold;'>✔️</span> : Có đi làm ca hiện trường | 
                    <span style='color:#FF7A00; font-weight:bold;'>P</span> : Nghỉ có phép (Nghỉ phép năm, ốm, việc riêng) | 
                    <span style='color:#EF4444; font-weight:bold;'>KP</span> : Nghỉ không phép | 
                    <span style='color:#94A3B8; font-weight:bold;'>CN</span> : Ngày Chủ Nhật nghỉ định kỳ | 
                    <span style='color:#64748B;'>—</span> : Ngày chưa đến / Ngày thường chưa có báo cáo
                </div>
                """, unsafe_allow_html=True)
                
                # Tạo bảng ma trận 5 KTV x Các ngày trong tháng
                matrix_rows = []
                for ktv in KTV_PROFILE_LIST:
                    row_data = {"Họ và Tên KTV": ktv["name"], "Chức vụ": ktv["title"]}
                    total_days_worked = 0
                    total_leave_days = 0
                    
                    for d in range(1, days_in_month + 1):
                        day_date = date(now_dt.year, now_dt.month, d)
                        is_sunday = (day_date.weekday() == 6)
                        
                        col_header = f"Ngày {d:02d} (CN)" if is_sunday else f"Ngày {d:02d}"
                        day_str = f"{now_dt.strftime('%Y-%m')}-{d:02d}"
                        
                        # 1. Kiểm tra có đi làm ca không
                        worked = False
                        if not att_df_raw.empty:
                            day_records = att_df_raw[att_df_raw["date"] == day_str]
                            for _, rec in day_records.iterrows():
                                p_list = rec["participating_ktvs"] if rec["participating_ktvs"] else rec["fullname"]
                                if ktv["name"] in p_list or rec["fullname"] == ktv["name"]:
                                    worked = True
                                    break
                                    
                        # 2. Kiểm tra có báo nghỉ phép không
                        has_leave = False
                        leave_code = "P"
                        if not leave_df_raw.empty:
                            l_records = leave_df_raw[(leave_df_raw["date"] == day_str) & (leave_df_raw["fullname"] == ktv["name"])]
                            if not l_records.empty:
                                has_leave = True
                                l_type = l_records.iloc[0]["leave_type"]
                                leave_code = "KP" if "không phép" in l_type.lower() else "P"
                        
                        if has_leave:
                            row_data[col_header] = leave_code
                            if leave_code == "P":
                                total_leave_days += 1
                        elif worked:
                            row_data[col_header] = "✔️"
                            total_days_worked += 1
                        else:
                            row_data[col_header] = "CN" if is_sunday else "—"
                            
                    row_data["Tổng ngày công đi làm"] = f"{total_days_worked} ngày"
                    row_data["Số ngày nghỉ phép (P)"] = f"{total_leave_days} ngày"
                    matrix_rows.append(row_data)
                
                st.dataframe(pd.DataFrame(matrix_rows), use_container_width=True)

            with tab_detail:
                att_df = pd.read_sql_query("SELECT id, date as 'Ngày', time as 'Giờ', username as 'Tài Khoản Báo Cáo', fullname as 'Trưởng Nhóm Báo Cáo', participating_ktvs as 'KTV Tham Gia', work_type as 'Loại Công Việc', note as 'Ghi Chú', photo_name as 'Ảnh Đính Kèm' FROM attendance ORDER BY id DESC", conn)
                
                if att_df.empty:
                    st.info("Chưa có bản ghi chấm công thực tế nào hằng ngày.")
                else:
                    st.dataframe(att_df.drop(columns=["id"]), use_container_width=True)
                    st.markdown("#### 🖼️ Xem & Kiểm Tra Ảnh Timemark Chi Tiết:")
                    
                    for idx, row in att_df.iterrows():
                        photo_file_name = row['Ảnh Đính Kèm']
                        ktv_avt = get_user_avatar(row['Tài Khoản Báo Cáo'])
                        ktvs_list = row['KTV Tham Gia'] if row['KTV Tham Gia'] else row['Trưởng Nhóm Báo Cáo']
                        
                        with st.expander(f"📷 [{row['Ngày']} {row['Giờ']}] Trưởng nhóm: {row['Trưởng Nhóm Báo Cáo']} - Ca: {row['Loại Công Việc']}"):
                            col_exp1, col_exp2 = st.columns([1, 3])
                            with col_exp1:
                                if ktv_avt and os.path.exists(ktv_avt):
                                    st.image(ktv_avt, caption=f"Trưởng Nhóm: {row['Trưởng Nhóm Báo Cáo']}", use_container_width=True)
                            with col_exp2:
                                st.write(f"**Danh sách KTV cùng tham gia:** `{ktvs_list}`")
                                st.write(f"**Ghi chú hiện trường:** {row['Ghi Chú'] if row['Ghi Chú'] else 'Không có'}")
                                st.write(f"**File ảnh Timemark:** `{photo_file_name}`")
                                photo_path = os.path.join(UPLOAD_DIR, photo_file_name)
                                if os.path.exists(photo_path):
                                    st.image(photo_path, caption=f"Ảnh Timemark đối chứng do {row['Trưởng Nhóm Báo Cáo']} tải lên", use_container_width=True)
                                else:
                                    st.warning(f"⚠️ Ảnh đính kèm ({photo_file_name}) chưa có trong hệ thống lưu trữ local.")

            with tab_leave_list:
                st.markdown("#### 🏖️ Danh Sách Lịch Sử Đăng Ký Nghỉ Phép KTV:")
                l_logs_df = pd.read_sql_query("SELECT id, date as 'Ngày Nghỉ', fullname as 'KTV Nghỉ Phép', leave_type as 'Loại Nghỉ Phép', reason as 'Lý Do Chi Tiết', logged_by as 'Người Đăng Ký' FROM leave_logs ORDER BY id DESC", conn)
                if l_logs_df.empty:
                    st.info("Chưa có lịch đăng ký nghỉ phép nào.")
                else:
                    st.dataframe(l_logs_df.drop(columns=["id"]), use_container_width=True)
                    
            conn.close()

        # ------------------------------------------
        # ADMIN - CHỨC NĂNG 4: NHẬP PHẠT CHẾ TÀI
        # ------------------------------------------
        elif menu == "⚠️ Ghi Nhận Lỗi Phạt":
            st.markdown("### ⚠️ Nhập Lỗi Phạt Chế Tài - Khấu Trừ Quỹ Lương Chung")
            
            with st.form("fine_form", clear_on_submit=True):
                fine_sel = st.selectbox(
                    "Chọn loại vi phạm chất lượng:",
                    ["Thi công chậm tiến độ / Ẩu lỗi kỹ thuật (Phạt 500k)", "Dịch vụ / Bảo trì kém bị khách phản phàn nàn (Phạt 100k)"]
                )
                reason_input = st.text_area("Lý do chi tiết dẫn đến áp dụng lệnh phạt chế tài (Bắt buộc):")
                submit_f = st.form_submit_button("XÁC NHẬN PHẠT TRỪ ⚠️")
                
                if submit_f:
                    if reason_input.strip() == "":
                        st.error("Vui lòng mô tả lý do vi phạm chi tiết!")
                    else:
                        amount = 500000 if "Thi công" in fine_sel else 100000
                        today_str = get_vn_date_str()
                        
                        conn = get_connection()
                        c = conn.cursor()
                        c.execute("""
                            INSERT INTO fine_logs (date, fine_type, amount, reason, logged_by)
                            VALUES (?, ?, ?, ?, ?)
                        """, (today_str, fine_sel, amount, reason_input.strip(), st.session_state.fullname))
                        conn.commit()
                        conn.close()
                        
                        st.success(f"🚨 Đã cập nhật thành công hình phạt trừ {fmt_vnd(amount)} đ vào cơ sở dữ liệu.")

        # ------------------------------------------
        # ADMIN - CHỨC NĂNG 5: DANH SÁCH KTV & ẢNH HỒ SƠ
        # ------------------------------------------
        elif menu == "👥 Danh Sách KTV & Ảnh Hồ Sơ":
            st.markdown("### 👥 Hồ Sơ Nhân Sự & Chức Vụ Khối Kỹ Thuật")
            st.write("Danh sách 5 Kỹ thuật viên chính thức tham gia cơ chế Quỹ Lương KPI Khối Kỹ Thuật:")
            
            grid_cols = st.columns(5)
            for idx, ktv in enumerate(KTV_PROFILE_LIST):
                with grid_cols[idx]:
                    st.markdown("<div class='ktv-card'>", unsafe_allow_html=True)
                    if os.path.exists(ktv["avatar"]):
                        st.image(ktv["avatar"], use_container_width=True)
                    st.markdown(f"#### {ktv['name']}</h4>", unsafe_allow_html=True)
                    st.markdown(f"<span class='role-title'>{ktv['title']}</span>", unsafe_allow_html=True)
                    st.markdown(f"<p style='margin:5px 0; font-size:0.95rem; font-weight:bold; color:#10B981;'>📞 {ktv.get('phone', '')}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p>Tài khoản: <code style='color:#FF7A00; font-size:0.95rem; font-weight:bold;'>{ktv['username']}</code></p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='margin-top:5px; font-size:0.8rem; color:#94A3B8;'>{ktv['note']}</p>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
