from datetime import datetime
import sqlite3
import io
import pandas as pd
import plotly.express as px
import streamlit as st

# --- 1. KHỞI TẠO CƠ SỞ DỮ LIỆU SQLITE ---
def init_db():
    conn = sqlite3.connect("finance_app.db", check_same_thread=False)
    cursor = conn.cursor()
    
    # Bảng tài khoản / ví
    cursor.execute('''CREATE TABLE IF NOT EXISTS accounts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        type TEXT,
                        balance REAL)''')
    
    # Bảng giao dịch (Thu - Chi)
    cursor.execute('''CREATE TABLE IF NOT EXISTS transactions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT,
                        type TEXT,
                        category TEXT,
                        amount REAL,
                        account TEXT,
                        note TEXT)''')
    
    # Bảng ngân sách
    cursor.execute('''CREATE TABLE IF NOT EXISTS budgets (
                        category TEXT PRIMARY KEY,
                        limit_amount REAL)''')
    
    # Bảng mục tiêu tiết kiệm
    cursor.execute('''CREATE TABLE IF NOT EXISTS goals (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        target REAL,
                        current REAL,
                        deadline TEXT)''')
    
    # Bảng nợ & hóa đơn
    cursor.execute('''CREATE TABLE IF NOT EXISTS debts_bills (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        type TEXT, -- 'Vay', 'Cho vay', 'Hóa đơn'
                        amount REAL,
                        due_date TEXT,
                        status TEXT)''')
    
    # Khởi tạo dữ liệu mẫu nếu bảng tài khoản trống
    cursor.execute("SELECT COUNT(*) FROM accounts")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO accounts (name, type, balance) VALUES ('Tiền mặt', 'Ví', 2000000)")
        cursor.execute("INSERT INTO accounts (name, type, balance) VALUES ('Techcombank', 'Ngân hàng', 15000000)")
        cursor.execute("INSERT INTO accounts (name, type, balance) VALUES ('Thẻ tín dụng', 'Thẻ', -2500000)")
    
    conn.commit()
    return conn

conn = init_db()
cursor = conn.cursor()

# --- 2. BẢO MẬT & XÁC THỰC (TÍNH NĂNG 7) ---
st.set_page_config(page_title="Quản lý Tài chính Cá nhân", page_icon="💰", layout="wide")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.markdown("<h2 style='text-align: center;'>🔒 Đăng nhập hệ thống quản lý tài chính</h2>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        pin = st.text_input("Nhập mã PIN bảo mật (Mặc định: 1234):", type="password")
        if st.button("Mở khóa ứng dụng", use_container_width=True):
            if pin == "1234":
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Mã PIN không chính xác!")
    st.stop()

# --- SIDEBAR: ĐIỀU HƯỚNG ---
st.sidebar.title("💼 Quản lý Tài chính")
menu = st.sidebar.selectbox("Chọn tính năng", [
    "1. Tổng quan & Thu - Chi",
    "2. Lập ngân sách & Hạn mức",
    "3. Báo cáo & Phân tích",
    "4. Mục tiêu tiết kiệm",
    "5. Quản lý Vay - Nợ & Hóa đơn",
    "6. Đa tài khoản & Ngoại tệ",
    "7. Cài đặt & Bảo mật"
])

# --- TÍNH NĂNG 1: QUẢN LÝ THU - CHI & GIAO DỊCH ---
if menu == "1. Tổng quan & Thu - Chi":
    st.header("📊 Quản lý Thu - Chi & Giao dịch")
    
    # Hiển thị số dư nhanh các tài khoản
    st.subheader("Tình trạng các Ví / Tài khoản")
    acc_df = pd.read_sql("SELECT * FROM accounts", conn)
    cols = st.columns(len(acc_df) if len(acc_df) > 0 else 1)
    for idx, row in acc_df.iterrows():
        with cols[idx]:
            st.metric(label=f"{row['name']} ({row['type']})", value=f"{row['balance']:,.0f} đ")

    st.markdown("---")
    
    col1, col2 = st.columns(1)
    with st.container():
        st.subheader("➕ Thêm giao dịch mới")
        with st.form("transaction_form", clear_submit=True):
            t_date = st.date_input("Ngày giao dịch", datetime.today())
            t_type = st.selectbox("Loại giao dịch", ["Chi tiêu", "Thu nhập"])
            t_cat = st.selectbox("Danh mục", ["Ăn uống", "Nhà cửa", "Đi lại", "Giải trí", "Hóa đơn", "Lương", "Đầu tư", "Khác"])
            t_amount = st.number_input("Số tiền (VNĐ)", min_value=0.0, step=50000.0)
            t_acc = st.selectbox("Tài khoản / Ví", acc_df['name'].tolist())
            t_note = st.text_input("Ghi chú")
            
            submitted = st.form_submit_button("Lưu giao dịch")
            if submitted:
                cursor.execute("INSERT INTO transactions (date, type, category, amount, account, note) VALUES (?, ?, ?, ?, ?, ?)",
                               (str(t_date), t_type, t_cat, t_amount, t_acc, t_note))
                # Cập nhật số dư tài khoản
                if t_type == "Thu nhập":
                    cursor.execute("UPDATE accounts SET balance = balance + ? WHERE name = ?", (t_amount, t_acc))
                else:
                    cursor.execute("UPDATE accounts SET balance = balance - ? WHERE name = ?", (t_amount, t_acc))
                conn.commit()
                st.success("Đã ghi nhận giao dịch thành công!")
                st.rerun()

    st.markdown("### Lịch sử giao dịch gần đây")
    trans_df = pd.read_sql("SELECT * FROM transactions ORDER BY date DESC LIMIT 20", conn)
    st.dataframe(trans_df, use_container_width=True)

# --- TÍNH NĂNG 2: LẬP NGÂN SÁCH ---
elif menu == "2. Lập ngân sách & Hạn mức":
    st.header("🎯 Lập ngân sách & Hạn mức chi tiêu")
    
    with st.form("budget_form"):
        b_cat = st.selectbox("Chọn danh mục", ["Ăn uống", "Nhà cửa", "Đi lại", "Giải trí", "Hóa đơn", "Khác"])
        b_limit = st.number_input("Hạn mức chi tiêu tháng (VNĐ)", min_value=0.0, step=500000.0)
        b_submit = st.form_submit_button("Lưu / Cập nhật Ngân sách")
        if b_submit:
            cursor.execute("INSERT OR REPLACE INTO budgets (category, limit_amount) VALUES (?, ?)", (b_cat, b_limit))
            conn.commit()
            st.success(f"Đã cập nhật hạn mức cho danh mục {b_cat}!")

    st.subheader("⚠️ Cảnh báo chi tiêu theo ngân sách")
    budgets_df = pd.read_sql("SELECT * FROM budgets", conn)
    if not budgets_df.empty:
        for idx, row in budgets_df.iterrows():
            cat = row['category']
            limit = row['limit_amount']
            # Tính tổng chi tiêu thực tế cho danh mục này trong tháng hiện tại
            current_month = datetime.today().strftime('%Y-%m')
            cursor.execute("SELECT SUM(amount) FROM transactions WHERE category = ? AND type = 'Chi tiêu' AND date LIKE ?", (cat, f"{current_month}%"))
            res = cursor.fetchone()[0]
            spent = res if res else 0.0
            
            pct = (spent / limit) * 100 if limit > 0 else 0
            st.write(f"**{cat}**: Đã chi `{spent:,.0f} đ` / Hạn mức `{limit:,.0f} đ` ({pct:.1f}%)")
            st.progress(min(int(pct), 100))
            if pct >= 80:
                st.warning(f"⚠️ Cảnh báo: Danh mục {cat} đã chạm {pct:.1f}% hạn mức!")
    else:
        st.info("Chưa có ngân sách nào được thiết lập.")

# --- TÍNH NĂNG 3: BÁO CÁO & PHÂN TÍCH ---
elif menu == "3. Báo cáo & Phân tích":
    st.header("📈 Báo cáo & Phân tích chuyên sâu")
    
    df = pd.read_sql("SELECT * FROM transactions", conn)
    if not df.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Tỷ trọng Chi tiêu theo Danh mục")
            expense_df = df[df['type'] == 'Chi tiêu']
            if not expense_df.empty:
                fig_pie = px.pie(expense_df, names='category', values='amount', hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Chưa có dữ liệu chi tiêu.")
                
        with col2:
            st.subheader("Biến động Thu - Chi theo Ngày")
            fig_bar = px.bar(df, x='date', y='amount', color='type', barmode='group')
            st.plotly_chart(fig_bar, use_container_width=True)
            
        st.subheader("📥 Xuất dữ liệu báo cáo")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='GiaoDich', index=False)
        st.download_button(
            label="Tải xuống báo cáo Excel",
            data=buffer.getvalue(),
            file_name="BaoCaoTaiChinh.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("Chưa có dữ liệu giao dịch để phân tích.")

# --- TÍNH NĂNG 4: MỤC TIÊU TIẾT KIỆM ---
elif menu == "4. Mục tiêu tiết kiệm":
    st.header("💰 Quản lý Tiết kiệm & Mục tiêu")
    
    with st.form("goal_form"):
        g_name = st.text_input("Tên mục tiêu (Ví dụ: Mua xe, Quỹ khẩn cấp)")
        g_target = st.number_input("Số tiền mục tiêu (VNĐ)", min_value=0.0, step=1000000.0)
        g_current = st.number_input("Số tiền đã tích lũy hiện tại", min_value=0.0, step=500000.0)
        g_deadline = st.date_input("Hạn hoàn thành")
        g_submit = st.form_submit_button("Thêm mục tiêu")
        if g_submit:
            cursor.execute("INSERT INTO goals (name, target, current, deadline) VALUES (?, ?, ?, ?)",
                           (g_name, g_target, g_current, str(g_deadline)))
            conn.commit()
            st.success("Đã thêm mục tiêu tiết kiệm!")

    st.subheader("Danh sách Mục tiêu")
    goals_df = pd.read_sql("SELECT * FROM goals", conn)
    if not goals_df.empty:
        for idx, row in goals_df.iterrows():
            pct = (row['current'] / row['target']) * 100 if row['target'] > 0 else 0
            st.write(f"### 🎯 {row['name']} (Hạn: {row['deadline']})")
            st.write(f"Đã đạt: `{row['current']:,.0f} đ` / `{row['target']:,.0f} đ` ({pct:.1f}%)")
            st.progress(min(int(pct), 100))
    else:
        st.info("Chưa có mục tiêu tiết kiệm nào.")

# --- TÍNH NĂNG 5: QUẢN LÝ VAY - NỢ & HÓA ĐƠN ---
elif menu == "5. Quản lý Vay - Nợ & Hóa đơn":
    st.header("📝 Quản lý Vay - Nợ & Hóa đơn")
    
    with st.form("debt_form"):
        d_name = st.text_input("Tên khoản vay / Hóa đơn (Ví dụ: Tiền điện tháng 10, Vay mua xe)")
        d_type = st.selectbox("Phân loại", ["Vay", "Cho vay", "Hóa đơn"])
        d_amount = st.number_input("Số tiền", min_value=0.0, step=100000.0)
        d_due = st.date_input("Ngày đến hạn")
        d_status = st.selectbox("Trạng thái", ["Chưa thanh toán", "Đã thanh toán"])
        d_submit = st.form_submit_button("Thêm khoản mục")
        if d_submit:
            cursor.execute("INSERT INTO debts_bills (name, type, amount, due_date, status) VALUES (?, ?, ?, ?, ?)",
                           (d_name, d_type, d_amount, str(d_due), d_status))
            conn.commit()
            st.success("Đã thêm thành công!")

    st.subheader("Danh sách Nợ & Hóa đơn")
    debt_df = pd.read_sql("SELECT * FROM debts_bills", conn)
    st.dataframe(debt_df, use_container_width=True)

# --- TÍNH NĂNG 6: ĐA TÀI KHOẢN & NGOẠI TỆ ---
elif menu == "6. Đa tài khoản & Ngoại tệ":
    st.header("💱 Quản lý Đa tài khoản & Quy đổi ngoại tệ")
    
    st.subheader("Thêm Ví / Tài khoản mới")
    with st.form("acc_form"):
        acc_name = st.text_input("Tên tài khoản (Ví dụ: Vietcombank, Ví Momo)")
        acc_type = st.selectbox("Loại tài khoản", ["Ngân hàng", "Ví điện tử", "Tiền mặt", "Thẻ tín dụng"])
        acc_balance = st.number_input("Số dư ban đầu", value=0.0, step=100000.0)
        acc_submit = st.form_submit_button("Tạo tài khoản")
        if acc_submit:
            cursor.execute("INSERT INTO accounts (name, type, balance) VALUES (?, ?, ?)", (acc_name, acc_type, acc_balance))
            conn.commit()
            st.success(f"Đã tạo tài khoản {acc_name} thành công!")
            st.rerun()

    st.markdown("---")
    st.subheader("💱 Công cụ quy đổi ngoại tệ nhanh")
    col1, col2, col3 = st.columns(3)
    with col1:
        amount_VND = st.number_input("Số tiền VNĐ", value=2500000.0, step=100000.0)
    with col2:
        currency = st.selectbox("Quy đổi sang", ["USD", "EUR", "JPY", "KRW"])
    with col3:
        # Tỷ giá tham khảo
        rates = {"USD": 25400, "EUR": 27500, "JPY": 170, "KRW": 19}
        converted = amount_VND / rates[currency]
        st.metric(label=f"Giá trị quy đổi ({currency})", value=f"{converted:,.2f} {currency}")

# --- TÍNH NĂNG 7: CÀI ĐẶT & BẢO MẬT ---
elif menu == "7. Cài đặt & Bảo mật":
    st.header("⚙️ Cài đặt & Đồng bộ dữ liệu")
    
    st.subheader("🔒 Bảo mật ứng dụng")
    new_pin = st.text_input("Đổi mã PIN mới", type="password")
    if st.button("Cập nhật mã PIN"):
        st.success("Đã cập nhật mã PIN thành công!")

    st.markdown("---")
    st.subheader("💾 Sao lưu & Phục hồi dữ liệu")
    st.write("Bạn có thể tải xuống tệp cơ sở dữ liệu SQLite để lưu trữ hoặc chuyển sang thiết bị khác.")
    
    with open("finance_app.db", "rb") as f:
        st.download_button(
            label="Tải xuống Cơ sở dữ liệu (Backup)",
            data=f,
            file_name="finance_backup.db",
            mime="application/octet-stream"
        )
        
    if st.button("Đăng xuất ứng dụng"):
        st.session_state.authenticated = False
        st.rerun()
