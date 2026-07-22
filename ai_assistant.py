import sqlite3
import os
import json
from datetime import datetime, date, timedelta, timezone
import google.generativeai as genai

import psycopg2
import toml
import os

class SupabaseConnectionWrapper:
    def __init__(self, conn):
        self.conn = conn
    def cursor(self):
        return SupabaseCursorWrapper(self.conn.cursor())
    def commit(self):
        self.conn.commit()
    def close(self):
        self.conn.close()
    def rollback(self):
        self.conn.rollback()

class SupabaseCursorWrapper:
    def __init__(self, cursor):
        self.cursor = cursor
    def execute(self, query, params=None):
        query = query.replace('?', '%s')
        if params is None:
            self.cursor.execute(query)
        else:
            self.cursor.execute(query, params)
    def fetchall(self):
        return self.cursor.fetchall()
    def fetchone(self):
        return self.cursor.fetchone()
    def fetchmany(self, size):
        return self.cursor.fetchmany(size)
    @property
    def description(self):
        return self.cursor.description
    @property
    def rowcount(self):
        return self.cursor.rowcount
    def close(self):
        self.cursor.close()

def get_connection():
    try:
        import streamlit as st
        supabase_url = st.secrets.get('SUPABASE_DB_URL')
    except:
        try:
            secrets = toml.load(r'd:\IDE CC KPI Solar 24h\.streamlit\secrets.toml')
            supabase_url = secrets.get('SUPABASE_DB_URL')
        except:
            supabase_url = None
            
    if supabase_url:
        return SupabaseConnectionWrapper(psycopg2.connect(supabase_url))
    else:
        import sqlite3
        return sqlite3.connect('solar24h_local.db', check_same_thread=False)



DB_FILE = "solar24h_local.db"
VN_TZ = timezone(timedelta(hours=7))

def get_vn_now():
    return datetime.now(VN_TZ)

def get_vn_date_str():
    return get_vn_now().strftime("%Y-%m-%d")

def get_connection():
    return sqlite3.connect('solar24h_local.db', check_same_thread=False)

# --- 1. NHÓM ĐỀ XUẤT / DUYỆT THƯỞNG ---

def get_pending_proposals():
    """
    Lấy danh sách các đề xuất công trình mới (thưởng 0.5%) hoặc ca bảo trì (thưởng 100k) đang chờ phê duyệt.
    """
    conn = get_connection()
    c = conn.cursor()
    
    # Dự án thi công
    c.execute("SELECT id, date, project_name, value, registered_by, participating_ktvs FROM project_logs WHERE status = 'Chờ duyệt'")
    projects = []
    for r in c.fetchall():
        projects.append({
            "id": r[0],
            "date": r[1],
            "project_name": r[2],
            "value": r[3],
            "registered_by": r[4],
            "participating_ktvs": r[5]
        })
        
    # Ca bảo trì
    c.execute("SELECT id, date, client_name, location, registered_by, participating_ktvs FROM maintenance_logs WHERE status = 'Chờ duyệt'")
    maintenances = []
    for r in c.fetchall():
        maintenances.append({
            "id": r[0],
            "date": r[1],
            "client_name": r[2],
            "location": r[3],
            "registered_by": r[4],
            "participating_ktvs": r[5]
        })
    conn.close()
    
    return json.dumps({
        "pending_projects": projects,
        "pending_maintenances": maintenances
    }, ensure_ascii=False, indent=2)

def approve_proposal(proposal_type: str = "", proposal_id: int = None, approver_fullname: str = ""):
    """
    Phê duyệt một đề xuất công trình hoặc ca bảo trì bằng ID.
    
    Parameters:
        proposal_type: Loại đề xuất ('project' cho công trình mới, 'maintenance' cho ca bảo trì).
        proposal_id: ID của đề xuất cần duyệt.
        approver_fullname: Tên đầy đủ của người duyệt đề xuất (ví dụ: 'Trần Hoàng Sang', 'Hồ Minh Việt').
    """
    if not proposal_type or proposal_id is None:
        return "Lỗi: Vui lòng cung cấp đầy đủ loại đề xuất (proposal_type) và ID đề xuất (proposal_id)."
        
    conn = get_connection()
    c = conn.cursor()
    today_str = get_vn_date_str()
    
    try:
        if proposal_type == 'project':
            c.execute("SELECT project_name, value FROM project_logs WHERE id = ? AND status = 'Chờ duyệt'", (proposal_id,))
            row = c.fetchone()
            if not row:
                return f"Không tìm thấy đề xuất công trình chờ duyệt với ID {proposal_id}."
            c.execute("UPDATE project_logs SET status = 'Đã duyệt', approved_by = ?, approved_at = ? WHERE id = ?",
                      (approver_fullname, today_str, proposal_id))
            conn.commit()
            return f"Đã phê duyệt đề xuất công trình '{row[0]}' với giá trị {row[1]:,} VNĐ."
            
        elif proposal_type == 'maintenance':
            c.execute("SELECT client_name FROM maintenance_logs WHERE id = ? AND status = 'Chờ duyệt'", (proposal_id,))
            row = c.fetchone()
            if not row:
                return f"Không tìm thấy đề xuất ca bảo trì chờ duyệt với ID {proposal_id}."
            c.execute("UPDATE maintenance_logs SET status = 'Đã duyệt', approved_by = ?, approved_at = ? WHERE id = ?",
                      (approver_fullname, today_str, proposal_id))
            conn.commit()
            return f"Đã phê duyệt đề xuất bảo trì '{row[0]}' thành công."
        else:
            return "Loại đề xuất không hợp lệ (chỉ chấp nhận 'project' hoặc 'maintenance')."
    except Exception as e:
        return f"Lỗi khi thực hiện phê duyệt: {str(e)}"
    finally:
        conn.close()

def reject_proposal(proposal_type: str = "", proposal_id: int = None, approver_fullname: str = ""):
    """
    Bác bỏ một đề xuất công trình hoặc ca bảo trì bằng ID.
    
    Parameters:
        proposal_type: Loại đề xuất ('project' hoặc 'maintenance').
        proposal_id: ID của đề xuất cần bác bỏ.
        approver_fullname: Tên đầy đủ của người thực hiện bác bỏ.
    """
    if not proposal_type or proposal_id is None:
        return "Lỗi: Vui lòng cung cấp đầy đủ loại đề xuất (proposal_type) và ID đề xuất (proposal_id)."
        
    conn = get_connection()
    c = conn.cursor()
    today_str = get_vn_date_str()
    
    try:
        if proposal_type == 'project':
            c.execute("SELECT project_name FROM project_logs WHERE id = ? AND status = 'Chờ duyệt'", (proposal_id,))
            row = c.fetchone()
            if not row:
                return f"Không tìm thấy đề xuất công trình chờ duyệt với ID {proposal_id}."
            c.execute("UPDATE project_logs SET status = 'Bác bỏ', approved_by = ?, approved_at = ? WHERE id = ?",
                      (approver_fullname, today_str, proposal_id))
            conn.commit()
            return f"Đã bác bỏ đề xuất công trình '{row[0]}'."
            
        elif proposal_type == 'maintenance':
            c.execute("SELECT client_name FROM maintenance_logs WHERE id = ? AND status = 'Chờ duyệt'", (proposal_id,))
            row = c.fetchone()
            if not row:
                return f"Không tìm thấy đề xuất ca bảo trì chờ duyệt với ID {proposal_id}."
            c.execute("UPDATE maintenance_logs SET status = 'Bác bỏ', approved_by = ?, approved_at = ? WHERE id = ?",
                      (approver_fullname, today_str, proposal_id))
            conn.commit()
            return f"Đã bác bỏ đề xuất bảo trì '{row[0]}'."
        else:
            return "Loại đề xuất không hợp lệ."
    except Exception as e:
        return f"Lỗi khi thực hiện bác bỏ: {str(e)}"
    finally:
        conn.close()

# --- 2. NHÓM BÁO CÁO / CHẤM CÔNG ---

def add_attendance(work_type: str = "Thi công lắp đặt mới (Hệ Solar / Trạm sạc)", ktv_names: list = None, note: str = "", reporter_username: str = "", reporter_fullname: str = ""):
    """
    Báo cáo chấm công ca làm việc tại hiện trường cho một hoặc nhiều Kỹ thuật viên (KTV).
    
    Parameters:
        work_type: Loại công việc ('Thi công lắp đặt mới (Hệ Solar / Trạm sạc)', 'Bảo trì định kỳ / Khắc phục sự cố tủ điện, inverter', 'Hỗ trợ công việc lao động phổ thông, dọn dẹp kho').
        ktv_names: Danh sách tên đầy đủ của các KTV cùng tham gia ca làm việc này (ví dụ: ['Nguyễn Chí Thanh', 'Võ Thành Thiện']).
        note: Ghi chú chi tiết công việc hoặc tiến độ công trường.
        reporter_username: Tài khoản (username) của trưởng nhóm gửi báo cáo (ví dụ: 'thanhnc', 'namnh').
        reporter_fullname: Tên đầy đủ của trưởng nhóm gửi báo cáo.
    """
    if not ktv_names:
        return "Lỗi: Danh sách KTV tham gia (ktv_names) không được để trống."
    
    conn = get_connection()
    c = conn.cursor()
    now_vn = get_vn_now()
    date_str = now_vn.strftime("%Y-%m-%d")
    time_str = now_vn.strftime("%H:%M:%S")
    participating_str = ", ".join(ktv_names)
    photo_name = "ai_verified.png" # Đánh dấu ca chấm công tạo tự động bởi AI
    
    try:
        c.execute("""
            INSERT INTO attendance (date, time, username, fullname, work_type, note, photo_name, participating_ktvs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (date_str, time_str, reporter_username, reporter_fullname, work_type, note, photo_name, participating_str))
        conn.commit()
        return f"Đã ghi nhận chấm công thành công cho KTV: {participating_str} vào ngày {date_str} lúc {time_str}."
    except Exception as e:
        return f"Lỗi khi lưu chấm công: {str(e)}"
    finally:
        conn.close()

def register_leave(ktv_fullname: str = "", leave_type: str = "Nghỉ phép năm (P)", reason: str = "", logged_by_fullname: str = ""):
    """
    Đăng ký báo nghỉ phép cho một Kỹ thuật viên (KTV).
    
    Parameters:
        ktv_fullname: Tên đầy đủ của KTV xin nghỉ (ví dụ: 'Trần Công Vinh', 'Võ Thành Thiện').
        leave_type: Loại nghỉ phép ('Nghỉ phép năm (P)', 'Nghỉ việc riêng có phép (P)', 'Nghỉ bệnh / Khác (P)', 'Nghỉ không phép (KP)').
        reason: Lý do xin nghỉ phép chi tiết.
        logged_by_fullname: Tên đầy đủ của người đăng ký nghỉ phép (thường là Trưởng nhóm hoặc Admin).
    """
    if not ktv_fullname:
        return "Lỗi: Tên KTV xin nghỉ (ktv_fullname) không được để trống."
        
    import sys
    _main = sys.modules.get("__main__")
    if _main and hasattr(_main, "KTV_PROFILE_LIST"):
        KTV_PROFILE_LIST = getattr(_main, "KTV_PROFILE_LIST")
    else:
        KTV_PROFILE_LIST = __import__("app").KTV_PROFILE_LIST
    target_uname = "ktv"
    for k in KTV_PROFILE_LIST:
        if k["name"].strip() == ktv_fullname.strip():
            target_uname = k["username"]
            break
            
    conn = get_connection()
    c = conn.cursor()
    today_str = get_vn_date_str()
    
    try:
        c.execute("""
            INSERT INTO leave_logs (date, username, fullname, leave_type, reason, logged_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (today_str, target_uname, ktv_fullname, leave_type, reason, logged_by_fullname))
        conn.commit()
        
        # Gửi thông báo Zalo webhook
        try:
            import sys
            _main = sys.modules.get("__main__")
            if _main and hasattr(_main, "send_zalo_webhook"):
                send_zalo_webhook = getattr(_main, "send_zalo_webhook")
            else:
                send_zalo_webhook = __import__("app").send_zalo_webhook
            send_zalo_webhook(f"[Solar 24h AI Assistant] Đã ghi nhận lịch nghỉ phép cho KTV {ktv_fullname} ngày {today_str} ({leave_type}). Lý do: {reason}. Người thực hiện: {logged_by_fullname}.")
        except Exception:
            pass
            
        return f"Đã ghi nhận nghỉ phép thành công cho KTV {ktv_fullname} vào ngày {today_str} (Loại: {leave_type})."
    except Exception as e:
        return f"Lỗi khi lưu nghỉ phép: {str(e)}"
    finally:
        conn.close()

# --- 3. NHÓM ĐĂNG KÝ SẢN LƯỢNG ---


def delete_attendance(ktv_fullname: str, date_str: str = ""):
    """
    Xóa báo cáo chấm công (hủy chấm công) của một Kỹ thuật viên trong một ngày cụ thể.
    
    Parameters:
        ktv_fullname: Tên đầy đủ của KTV cần xóa chấm công (ví dụ: 'Nguyễn Chí Thanh', 'Trần Công Vinh').
        date_str: Ngày chấm công cần xóa (định dạng YYYY-MM-DD, mặc định là ngày hôm nay nếu để trống).
    """
    if not date_str:
        date_str = get_vn_date_str()
        
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT id, participating_ktvs, fullname FROM attendance WHERE date = ?", (date_str,))
        records = c.fetchall()
        deleted = False
        for rec in records:
            rec_id, p_ktvs, submitter = rec
            p_list = [x.strip() for x in p_ktvs.split(',')] if p_ktvs else [submitter]
            if ktv_fullname in p_list:
                if len(p_list) <= 1:
                    c.execute("DELETE FROM attendance WHERE id = ?", (rec_id,))
                else:
                    p_list.remove(ktv_fullname)
                    new_p_str = ", ".join(p_list)
                    c.execute("UPDATE attendance SET participating_ktvs = ? WHERE id = ?", (new_p_str, rec_id))
                deleted = True
        
        conn.commit()
        if deleted:
            return f"Đã xóa chấm công thành công cho KTV: {ktv_fullname} vào ngày {date_str}."
        else:
            return f"Không tìm thấy bản ghi chấm công nào của KTV {ktv_fullname} vào ngày {date_str} để xóa."
    except Exception as e:
        return f"Lỗi xóa chấm công: {str(e)}"
    finally:
        conn.close()

def delete_leave(ktv_fullname: str, date_str: str = ""):
    """
    Xóa báo cáo nghỉ phép (hủy đơn xin nghỉ) của một Kỹ thuật viên trong một ngày cụ thể.
    
    Parameters:
        ktv_fullname: Tên đầy đủ của KTV cần xóa đơn nghỉ phép (ví dụ: 'Nguyễn Chí Thanh', 'Trần Công Vinh').
        date_str: Ngày nghỉ phép cần xóa (định dạng YYYY-MM-DD, mặc định là ngày hôm nay nếu để trống).
    """
    if not date_str:
        date_str = get_vn_date_str()
        
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) FROM leave_logs WHERE date = ? AND fullname = ?", (date_str, ktv_fullname))
        if c.fetchone()[0] > 0:
            c.execute("DELETE FROM leave_logs WHERE date = ? AND fullname = ?", (date_str, ktv_fullname))
            conn.commit()
            return f"Đã xóa đơn nghỉ phép thành công cho KTV: {ktv_fullname} vào ngày {date_str}."
        else:
            return f"Không tìm thấy đơn nghỉ phép nào của KTV {ktv_fullname} vào ngày {date_str} để xóa."
    except Exception as e:
        return f"Lỗi xóa nghỉ phép: {str(e)}"
    finally:
        conn.close()

def register_project(project_name: str = "", contract_value: float = 0.0, ktv_names: list = None, registered_by_fullname: str = ""):
    """
    Đăng ký nghiệm thu công trình mới đã đóng điện để chờ duyệt thưởng 0.5%.
    
    Parameters:
        project_name: Tên dự án lắp đặt đã hoàn thành (ví dụ: 'Dự án Solar F8 Gò Công').
        contract_value: Giá trị hợp đồng thi công (VNĐ).
        ktv_names: Danh sách tên đầy đủ các KTV tham gia thi công công trình này để chia đều tiền thưởng.
        registered_by_fullname: Tên đầy đủ của Trưởng nhóm đăng ký đề xuất.
    """
    if not project_name:
        return "Lỗi: Tên dự án (project_name) không được để trống."
    if not ktv_names:
        return "Lỗi: Danh sách KTV tham gia (ktv_names) không được để trống."
        
    conn = get_connection()
    c = conn.cursor()
    today_str = get_vn_date_str()
    participating_str = ", ".join(ktv_names)
    
    try:
        c.execute("""
            INSERT INTO project_logs (date, project_name, value, registered_by, status, approved_by, approved_at, participating_ktvs)
            VALUES (?, ?, ?, ?, 'Chờ duyệt', '-', '-', ?)
        """, (today_str, project_name, contract_value, registered_by_fullname, participating_str))
        conn.commit()
        
        # Bắn thông báo Zalo webhook
        try:
            import sys
            _main = sys.modules.get("__main__")
            if _main and hasattr(_main, "send_zalo_webhook"):
                send_zalo_webhook = getattr(_main, "send_zalo_webhook")
            else:
                send_zalo_webhook = __import__("app").send_zalo_webhook
            if _main and hasattr(_main, "fmt_vnd"):
                fmt_vnd = getattr(_main, "fmt_vnd")
            else:
                fmt_vnd = __import__("app").fmt_vnd
            send_zalo_webhook(f"[Solar 24h AI Assistant] Trưởng nhóm {registered_by_fullname} báo cáo hoàn thành lắp đặt {project_name} ({fmt_vnd(contract_value)} đ) với {len(ktv_names)} KTV. Chờ phê duyệt thưởng 0.5%.")
        except Exception:
            pass
            
        return f"Đã gửi yêu cầu đề xuất thưởng 0.5% dự án '{project_name}' trị giá {contract_value:,.0f} VNĐ cho {len(ktv_names)} KTV thành công."
    except Exception as e:
        return f"Lỗi khi đăng ký dự án: {str(e)}"
    finally:
        conn.close()

def register_maintenance(client_name: str = "", location: str = "", ktv_names: list = None, registered_by_fullname: str = ""):
    """
    Đăng ký nghiệm thu ca bảo trì khân cấp hoàn thành để chờ duyệt thưởng 100k.
    
    Parameters:
        client_name: Tên khách hàng / trạm bảo trì (ví dụ: 'Bảo trì Trạm sạc Cái Bè').
        location: Địa điểm, khu vực xảy ra sự cố (ví dụ: 'Cái Bè, Tiền Giang').
        ktv_names: Danh sách tên các KTV trực tiếp sửa chữa.
        registered_by_fullname: Tên đầy đủ của Trưởng nhóm đăng ký đề xuất.
    """
    if not client_name:
        return "Lỗi: Tên khách hàng bảo trì (client_name) không được để trống."
    if not ktv_names:
        return "Lỗi: Danh sách KTV tham gia (ktv_names) không được để trống."
        
    conn = get_connection()
    c = conn.cursor()
    today_str = get_vn_date_str()
    participating_str = ", ".join(ktv_names)
    
    try:
        c.execute("""
            INSERT INTO maintenance_logs (date, client_name, location, registered_by, status, approved_by, approved_at, participating_ktvs)
            VALUES (?, ?, ?, ?, 'Chờ duyệt', '-', '-', ?)
        """, (today_str, client_name, location, registered_by_fullname, participating_str))
        conn.commit()
        
        # Bắn thông báo Zalo webhook
        try:
            import sys
            _main = sys.modules.get("__main__")
            if _main and hasattr(_main, "send_zalo_webhook"):
                send_zalo_webhook = getattr(_main, "send_zalo_webhook")
            else:
                send_zalo_webhook = __import__("app").send_zalo_webhook
            send_zalo_webhook(f"[Solar 24h AI Assistant] Trưởng nhóm {registered_by_fullname} báo cáo hoàn thành ca bảo trì {client_name} tại {location} cho {len(ktv_names)} KTV. Chờ phê duyệt từ Admin.")
        except Exception:
            pass
            
        return f"Đã gửi yêu cầu đề xuất thưởng ca bảo trì tại '{location}' cho {len(ktv_names)} KTV thành công."
    except Exception as e:
        return f"Lỗi khi đăng ký ca bảo trì: {str(e)}"
    finally:
        conn.close()

# --- 4. NHÓM CHẾ TÀI PHẠT ---

def log_fine(fine_type: str = "", reason: str = "", logged_by_fullname: str = ""):
    """
    Ghi nhận hình phạt chế tài trừ tiền vào quỹ lương chung đối với các trường hợp vi phạm.
    
    Parameters:
        fine_type: Loại vi phạm (Chọn một trong hai: 'Thi công chậm tiến độ / Ẩu lỗi kỹ thuật (Phạt 500k)' hoặc 'Dịch vụ / Bảo trì kém bị khách phản phàn nàn (Phạt 100k)').
        reason: Mô tả lý do vi phạm chi tiết.
        logged_by_fullname: Tên đầy đủ của Admin ghi nhận hình phạt.
    """
    if not fine_type:
        return "Lỗi: Loại vi phạm (fine_type) không được để trống."
        
    amount = 500000 if "Thi công" in fine_type else 100000
    conn = get_connection()
    c = conn.cursor()
    today_str = get_vn_date_str()
    
    try:
        c.execute("""
            INSERT INTO fine_logs (date, fine_type, amount, reason, logged_by)
            VALUES (?, ?, ?, ?, ?)
        """, (today_str, fine_type, amount, reason, logged_by_fullname))
        conn.commit()
        return f"Đã áp dụng phạt chế tài trừ -{amount:,} VNĐ đối với vi phạm: '{fine_type}' do: '{reason}'."
    except Exception as e:
        return f"Lỗi khi lưu hình phạt: {str(e)}"
    finally:
        conn.close()

# --- 5. NHÓM TRA CỨU TỔNG QUAN ---

def query_salaries(month_filter: str = "Tất cả các tháng tích lũy"):
    """
    Tra cứu bảng lương quyết toán và quỹ lương KPI tích lũy của cả đội trong tháng hiện tại hoặc tất cả các tháng.
    
    Parameters:
        month_filter: Lựa chọn tháng quyết toán (Ví dụ: 'Tháng 07/2026' hoặc 'Tất cả các tháng tích lũy').
    """
    try:
        import sys
        _main = sys.modules.get("__main__")
        if _main and hasattr(_main, "calculate_individual_salaries"):
            calculate_individual_salaries = getattr(_main, "calculate_individual_salaries")
        else:
            calculate_individual_salaries = __import__("app").calculate_individual_salaries
        if _main and hasattr(_main, "fmt_vnd"):
            fmt_vnd = getattr(_main, "fmt_vnd")
        else:
            fmt_vnd = __import__("app").fmt_vnd
        calc = calculate_individual_salaries(month_filter)
        
        summary = {
            "Kỳ quyết toán": month_filter,
            "Quỹ cứng cố định": f"{calc['base_pool']:,} VNĐ",
            "Tổng thưởng dự án (0.5%)": f"{calc['p_bonus']:,} VNĐ (từ {calc['p_val']:,} VNĐ doanh thu công trình đã duyệt)",
            "Tổng thưởng bảo trì (100k)": f"{calc['m_bonus']:,} VNĐ (từ {calc['m_count']} ca đã duyệt)",
            "Khấu trừ lỗi chế tài": f"-{calc['fine_amount']:,} VNĐ",
            "TỔNG QUỸ LƯƠNG QUYẾT TOÁN": f"{calc['total_pool']:,} VNĐ",
            "Thu nhập chi tiết từng KTV": []
        }
        
        for k in calc["ktv_salaries"]:
            summary["Thu nhập chi tiết từng KTV"].append({
                "Tài khoản": k["username"],
                "Họ tên": k["name"],
                "Chức danh": k["title"],
                "Lương sàn cứng": f"{k['base_salary']:,} VNĐ",
                "Thưởng KPI": f"{k['kpi_bonus']:,} VNĐ",
                "Phụ cấp trách nhiệm": k["allowance_desc"],
                "Thực nhận thực tế": f"{k['total_salary']:,} VNĐ"
            })
            
        return json.dumps(summary, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Lỗi khi tính toán bảng lương: {str(e)}"

def query_leaves(month_filter: str = "Tất cả các tháng tích lũy"):
    """
    Tra cứu danh sách đăng ký nghỉ phép của các Kỹ thuật viên (KTV) trong một tháng cụ thể hoặc tất cả các tháng.
    """
    try:
        import json
        conn = get_connection()
        c = conn.cursor()
        
        if month_filter != "Tất cả các tháng tích lũy":
            parts = month_filter.split(" ")
            if len(parts) >= 2:
                m_y = parts[1]
                try:
                    m, y = m_y.split("/")
                    like_pattern = f"{y}-{m}-%"
                    c.execute("SELECT date, fullname, leave_type, reason, logged_by FROM leave_logs WHERE date LIKE ?", (like_pattern,))
                except:
                    c.execute("SELECT date, fullname, leave_type, reason, logged_by FROM leave_logs")
            else:
                c.execute("SELECT date, fullname, leave_type, reason, logged_by FROM leave_logs")
        else:
            c.execute("SELECT date, fullname, leave_type, reason, logged_by FROM leave_logs")
            
        rows = c.fetchall()
        conn.close()
        
        if not rows:
            return f"Không tìm thấy dữ liệu nghỉ phép cho kỳ: {month_filter}"
            
        summary = {
            "Kỳ tra cứu": month_filter,
            "Tổng số ngày nghỉ": len(rows),
            "Chi tiết": []
        }
        for row in rows:
            summary["Chi tiết"].append({
                "Ngày nghỉ": row[0],
                "KTV": row[1],
                "Loại phép": row[2],
                "Lý do": row[3],
                "Người ghi nhận": row[4]
            })
            
        return json.dumps(summary, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"Lỗi khi tra cứu danh sách nghỉ phép: {str(e)}"

# --- HÀM CORE KẾT NỐI GEMINI ---

def ask_gemini_assistant(user_prompt: str, user_role: str, user_fullname: str, user_username: str, api_key: str, audio_data=None):
    """
    Hàm gọi Gemini để xử lý yêu cầu của người dùng (văn bản hoặc âm thanh), phân tích và thực thi các Function Calling thích hợp.
    """
    if not api_key:
        return "Vui lòng cấu hình API Key của bạn để sử dụng Trợ lý AI."
        
    genai.configure(api_key=api_key)
    
    today_vn = get_vn_date_str()
    system_instruction = f"""
Bạn là Trợ Lý AI của Web App Quản Trị Kỹ Thuật & KPI Solar 24H.
Thông tin nhân sự đang đăng nhập và ra lệnh cho bạn:
- Họ và Tên: {user_fullname}
- Tên tài khoản (username): {user_username}
- Quyền hạn (role): {user_role}
- Ngày hôm nay (Giờ Việt Nam): {today_vn}

HƯỚNG DẪN BẢO MẬT & PHÂN QUYỀN (RẤT QUAN TRỌNG):
1. Bạn chỉ được phép thực thi các tác vụ phù hợp với quyền hạn của người dùng. Nếu người dùng yêu cầu hành động vượt quá quyền hạn, hãy từ chối lịch sự bằng tiếng Việt.
   - Quyền Phê duyệt/Bác bỏ đề xuất (`approve_proposal`, `reject_proposal`) và Ghi nhận lỗi phạt chế tài (`log_fine`): CHỈ dành cho Admin (user_role là 'Admin', ví dụ: 'Trần Hoàng Sang', 'Hồ Minh Việt').
   - Quyền Báo cáo Chấm công (`add_attendance`), báo nghỉ phép (`register_leave`), đăng ký dự án (`register_project`), đăng ký bảo trì (`register_maintenance`): CHỈ dành cho Trưởng Nhóm (là Admin, hoặc trong Họ tên / Chức danh có cụm từ "Trưởng Nhóm" như 'Nguyễn Chí Thanh' và 'Nguyễn Hoàng Nam'). KTV bình thường KHÔNG được phép thực hiện, mà phải nhờ Trưởng nhóm làm thay.
   - KTV bình thường (role KTV) chỉ có quyền hỏi han, tra cứu ngày công, tính lương cá nhân, xem quỹ lương chung (`query_salaries`).
   - Mọi người dùng đều có quyền xem danh sách nghỉ phép (`query_leaves`).
2. Khi gọi các hàm đăng ký hoặc cập nhật, hãy luôn truyền đúng thông tin người thực hiện là {user_fullname} hoặc {user_username} theo đúng tham số yêu cầu.
3. Luôn phản hồi bằng tiếng Việt thân thiện, lịch sự, chuyên nghiệp, xúc tích. Trình bày thông tin rõ ràng bằng Markdown.
4. NẾU người dùng gửi tin nhắn thoại (dữ liệu âm thanh), bạn BẮT BUỘC phải nghe và dịch (chép lại) toàn bộ lời thoại tiếng Việt của họ, rồi ghi ngay ở dòng đầu tiên của câu trả lời theo cú pháp chính xác: `[Bản dịch thoại: "nội dung lời thoại của người dùng"]` (phải có dấu ngoặc kép bao quanh nội dung dịch và nằm trong ngoặc vuông). Sau đó mới thực hiện tác vụ và trả lời phần tiếp theo ở các dòng dưới.

Danh sách nhân sự trong hệ thống (kèm SĐT để tra cứu và đối chiếu):
1. Hồ Minh Việt (username: viethm) - Giám Đốc | SĐT: 0909.363.579
2. Trần Hoàng Sang (username: sangth) - Trưởng Phòng HR | SĐT: 0888.003.205
3. Nguyễn Chí Thanh (username: thanhnc) - Trưởng Nhóm Thi Công | SĐT: 0971.847.084
4. Nguyễn Hoàng Nam (username: namnh) - Trưởng Nhóm Bảo Trì | SĐT: 078.336.7989
5. Võ Thành Thiện (username: thienvt) - Kỹ Thuật Viên | SĐT: 0328.400.801
6. Trần Công Vinh (username: vinhtc) - Kỹ Thuật Viên | SĐT: 0898.044.598
7. Phạm Hồng Thái (username: thaiph) - Kỹ Thuật Viên | SĐT: 0362.240.392
"""

    fallback_models = [
        "gemini-3.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-flash-lite-latest",
        "gemini-pro-latest",
        "gemini-flash-latest"
    ]
    
    last_error = None
    for model_name in fallback_models:
        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_instruction,
                tools=[
                    get_pending_proposals,
                    approve_proposal,
                    reject_proposal,
                    add_attendance,
                    delete_attendance,
                    register_leave,
                    delete_leave,
                    register_project,
                    register_maintenance,
                    log_fine,
                    query_salaries,
                    query_leaves
                ]
            )
            chat = model.start_chat(enable_automatic_function_calling=True)
            if audio_data:
                response = chat.send_message([audio_data, user_prompt])
            else:
                response = chat.send_message(user_prompt)
            return response.text
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "quota" in err_str.lower() or "limit" in err_str.lower():
                last_error = e
                continue
            else:
                return f"Lỗi từ Gemini API ({model_name}): {err_str}"
                
    return f"Lỗi từ Gemini API (Tất cả mô hình đều hết hạn ngạch/quota): {str(last_error)}"
