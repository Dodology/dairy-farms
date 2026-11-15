import streamlit as st
import sqlite3, hashlib, hmac, os, re, smtplib, secrets
import pandas as pd
from datetime import date
from email.message import EmailMessage

st.set_page_config(page_title="Dairy Farms", page_icon="🐄", layout="wide",
                   initial_sidebar_state="collapsed")
DB = "dairy_farms.db"


# ---------- DATABASE ----------
def db():
    c = sqlite3.connect(DB)
    c.execute("PRAGMA foreign_keys = ON")
    return c


def init_db():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        user_id INTEGER PRIMARY KEY AUTOINCREMENT, full_name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
        country TEXT, phone TEXT, role TEXT);
    CREATE TABLE IF NOT EXISTS farms(
        farm_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        farm_name TEXT NOT NULL, governorate TEXT, location TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id));
    CREATE TABLE IF NOT EXISTS animals(
        id INTEGER PRIMARY KEY AUTOINCREMENT, farm_id INTEGER NOT NULL,
        animal_type TEXT, tag TEXT NOT NULL, breed TEXT, birth_date TEXT,
        sex TEXT, origin TEXT, mother_tag TEXT, mother_breed TEXT,
        mother_milk REAL, father_tag TEXT, father_breed TEXT, grandam_milk REAL,
        UNIQUE(farm_id, tag), FOREIGN KEY(farm_id) REFERENCES farms(farm_id));
    CREATE TABLE IF NOT EXISTS milk(
        id INTEGER PRIMARY KEY AUTOINCREMENT, animal_id INTEGER NOT NULL,
        calving_date TEXT NOT NULL, record_date TEXT NOT NULL,
        weekly_total REAL NOT NULL, feed TEXT, notes TEXT,
        FOREIGN KEY(animal_id) REFERENCES animals(id));
    """)
    c.commit()
    c.close()


init_db()


def hp(p):
    s = os.urandom(16)
    return s.hex() + ":" + hashlib.pbkdf2_hmac("sha256", p.encode(), s, 200000).hex()


def vp(p, h):
    s, k = h.split(":")
    return hmac.compare_digest(
        hashlib.pbkdf2_hmac("sha256", p.encode(), bytes.fromhex(s), 200000).hex(), k)


# ---------- STATE ----------
for k, v in {"lang": "en", "page": "auth", "stack": [], "user": None,
             "farm_id": None, "animal_type": None}.items():
    st.session_state.setdefault(k, v)

EN = lambda: st.session_state.lang == "en"


def tr(e, a):
    return e if EN() else a


def go(p):
    st.session_state.stack.append(st.session_state.page)
    st.session_state.page = p
    st.rerun()


def back():
    if st.session_state.stack:
        st.session_state.page = st.session_state.stack.pop()
        st.rerun()


# ---------- LANGUAGE SWITCH + STYLE ----------
_, lc = st.columns([6, 2])
with lc:
    ch = st.radio("lang", ["English", "العربية"], horizontal=True,
                  index=0 if EN() else 1, label_visibility="collapsed")
new = "en" if ch == "English" else "ar"
if new != st.session_state.lang:
    st.session_state.lang = new
    st.rerun()

st.markdown("""
<style>
.stApp{background-color:#1B1028;}
.hero{background:#D98CB3;padding:60px 55px;border-radius:25px;color:white;animation:fadeln 1.2s ease;}
.tag{font-size:16px;color:#E9D8F0;letter-spacing:2px;margin-bottom:20px;}
.hero h1{font-size:60px;color:#E9D8F0;line-height:1.1;}
.hero p{font-size:20px;color:#7446A8;}
@keyframes fadeln{from{opacity:0;transform:translateY(25px);}to{opacity:1;transform:translateY(0);}}
</style>""", unsafe_allow_html=True)
if not EN():
    st.markdown("<style>.stApp{direction:rtl;text-align:right;}</style>", unsafe_allow_html=True)

# ---------- DATA ----------
ROLES = {"Farmer": "مزارع", "Veterinarian": "طبيب بيطري", "Researcher": "باحث",
         "Farm Manager": "مدير مزرعة", "Farm Owner": "مالك المزرعة"}
COUNTRIES = {"Egypt": ("مصر", "+20"), "Saudi Arabia": ("السعودية", "+966"),
             "UAE": ("الإمارات", "+971"), "Kuwait": ("الكويت", "+965"),
             "Qatar": ("قطر", "+974"), "Oman": ("عمان", "+968"),
             "Jordan": ("الأردن", "+962"), "Sudan": ("السودان", "+249"),
             "Libya": ("ليبيا", "+218"), "Morocco": ("المغرب", "+212"),
             "Other": ("أخرى", "")}
GOVS = dict(p.split(":") for p in (
    "Cairo:القاهرة,Giza:الجيزة,Alexandria:الإسكندرية,Qalyubia:القليوبية,Sharqia:الشرقية,"
    "Dakahlia:الدقهلية,Gharbia:الغربية,Menoufia:المنوفية,Beheira:البحيرة,"
    "Kafr El Sheikh:كفر الشيخ,Damietta:دمياط,Port Said:بورسعيد,Ismailia:الإسماعيلية,"
    "Suez:السويس,Faiyum:الفيوم,Beni Suef:بني سويف,Minya:المنيا,Asyut:أسيوط,Sohag:سوهاج,"
    "Qena:قنا,Luxor:الأقصر,Aswan:أسوان,Red Sea:البحر الأحمر,New Valley:الوادي الجديد,"
    "Matrouh:مطروح,North Sinai:شمال سيناء,South Sinai:جنوب سيناء").split(","))
ANIMALS = {"Cow": ("🐄 Cows", "🐄 الأبقار"), "Buffalo": ("🐃 Buffaloes", "🐃 الجاموس"),
           "Camel": ("🐪 Camels", "🐪 الجمال"), "Sheep": ("🐑 Sheep", "🐑 الأغنام"),
           "Goat": ("🐐 Goats", "🐐 الماعز")}
BREEDS = {
    "Cow": {"Holstein": "هولشتاين", "Friesian": "فريزيان", "Jersey": "جيرسي", "Brown Swiss": "براون سويس"},
    "Buffalo": {"Egyptian Buffalo": "الجاموس المصري", "Murrah": "موراه", "Nili-Ravi": "نيلي رافي"},
    "Camel": {"Dromedary": "الجمل العربي", "Bactrian": "الجمل ذو السنامين"},
    "Sheep": {"Rahmani": "رحماني", "Ossimi": "أوسيمي", "Barki": "برقي", "Suffolk": "سوفولك"},
    "Goat": {"Zaraibi": "زرايبي", "Damascus": "دمشقي", "Saanen": "سانين", "Boer": "بور"}}
UNK = "Unknown"


def lab(d):
    return lambda k: k if EN() else d.get(k, k)


def send_mail(to, pw):
    try:
        cfg = st.secrets["smtp"]
        m = EmailMessage()
        m["Subject"], m["From"], m["To"] = "Dairy Farms - New Password", cfg["user"], to
        m.set_content(f"Your new temporary password: {pw}\nكلمة المرور المؤقتة: {pw}")
        with smtplib.SMTP(cfg["host"], int(cfg.get("port", 587))) as s:
            s.starttls()
            s.login(cfg["user"], cfg["password"])
            s.send_message(m)
        return True
    except Exception:
        return False


def login_user(uid):
    c = db()
    u = c.execute("SELECT user_id,full_name FROM users WHERE user_id=?", (uid,)).fetchone()
    f = c.execute("SELECT farm_id,farm_name FROM farms WHERE user_id=? ORDER BY farm_id DESC",
                  (uid,)).fetchone()
    c.close()
    st.session_state.user = {"id": u[0], "name": u[1], "farm": f[1]}
    st.session_state.farm_id = f[0]
    st.session_state.stack = []
    st.session_state.page = "dashboard"
    st.rerun()


def register_user(name, em, pw, country, phone, role, farm, gov, loc):
    c = db()
    try:
        cur = c.execute(
            "INSERT INTO users(full_name,email,password_hash,country,phone,role) VALUES(?,?,?,?,?,?)",
            (name, em, hp(pw), country, phone, role))
        uid = cur.lastrowid
        c.execute("INSERT INTO farms(user_id,farm_name,governorate,location) VALUES(?,?,?,?)",
                  (uid, farm, gov, loc))
        c.commit()
        return uid
    except sqlite3.IntegrityError:
        c.rollback()
        return None
    finally:
        c.close()


# ---------- AUTH ----------
if st.session_state.user is None:
    st.markdown("""<div class="hero"><div class="tag">WELCOME TO DAIRY FARMS</div>
    <h1>Dairy<br>Farms.</h1><p>Smarter Farming. Better Production.</p></div>""",
                unsafe_allow_html=True)
    st.write("")
    t1, t2, t3 = st.tabs([tr("Log In", "تسجيل الدخول"),
                          tr("Create Account", "إنشاء حساب"),
                          tr("Forgot Password", "نسيت كلمة المرور")])
    with t1:
        with st.form("login"):
            e = st.text_input(tr("Email", "البريد الإلكتروني"))
            p = st.text_input(tr("Password", "كلمة المرور"), type="password")
            ok = st.form_submit_button(tr("Log In", "دخول"), use_container_width=True)
        if ok:
            c = db()
            r = c.execute("SELECT user_id,password_hash FROM users WHERE email=?",
                          (e.strip().lower(),)).fetchone()
            c.close()
            if r and vp(p, r[1]):
                login_user(r[0])
            else:
                st.error(tr("Incorrect email or password.", "البريد أو كلمة المرور غير صحيحة."))
    with t2:
        st.caption(tr("Don't have an account? Create one.", "ماعندكش حساب؟ أنشئ حساب جديد."))
        country = st.selectbox(tr("Country", "البلد"), list(COUNTRIES),
                               format_func=lab({k: v[0] for k, v in COUNTRIES.items()}))
        code = COUNTRIES[country][1]
        with st.form("register_form"):
            name = st.text_input(tr("Full Name", "الاسم بالكامل"))
            email = st.text_input(tr("Email", "البريد الإلكتروني"), key="re")
            pw = st.text_input(tr("Password (8+ characters)", "كلمة المرور (8 أحرف على الأقل)"),
                               type="password", key="rp")
            pw2 = st.text_input(tr("Confirm Password", "تأكيد كلمة المرور"), type="password")
            phone = st.text_input(tr(f"Phone Number ({code})", f"رقم التليفون ({code})"))
            role = st.selectbox(tr("Your Role on the Farm", "دورك في المزرعة"), list(ROLES),
                                format_func=lab(ROLES))
            farm = st.text_input(tr("Farm Name", "اسم المزرعة"))
            if country == "Egypt":
                gov = st.selectbox(tr("Governorate", "المحافظة"), list(GOVS), format_func=lab(GOVS))
            else:
                gov = st.text_input(tr("State / Region", "المنطقة / الولاية"))
            loc = st.text_input(tr("Farm Location / Address", "لوكيشن / عنوان المزرعة"))
            submit = st.form_submit_button(tr("Create Account", "إنشاء الحساب"), use_container_width=True)
        if submit:
            em = email.strip().lower()
            missing = []
            if not name.strip():
                missing.append(tr("Full Name", "الاسم بالكامل"))
            if not em:
                missing.append(tr("Email", "البريد الإلكتروني"))
            if not pw:
                missing.append(tr("Password", "كلمة المرور"))
            if not farm.strip():
                missing.append(tr("Farm Name", "اسم المزرعة"))
            if missing:
                st.error(tr("Missing: ", "ناقص: ") + ", ".join(missing))
            elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", em):
                st.error(tr("Invalid email.", "البريد الإلكتروني غير صحيح."))
            elif len(pw) < 8:
                st.error(tr("Password must be at least 8 characters.", "كلمة المرور 8 أحرف على الأقل."))
            elif pw != pw2:
                st.error(tr("Passwords do not match.", "كلمتا المرور غير متطابقتين."))
            else:
                uid = register_user(name.strip(), em, pw, country,
                                    code + phone.strip().lstrip("0"), role,
                                    farm.strip(), gov, loc.strip())
                if uid is None:
                    st.error(tr("This email is already registered.", "هذا البريد مسجل بالفعل."))
                else:
                    st.session_state.new_id = uid
                    login_user(uid)
    with t3:
        with st.form("forgot"):
            fe = st.text_input(tr("Your account email", "بريد حسابك"))
            go_f = st.form_submit_button(tr("Send new password", "ابعت كلمة مرور جديدة"))
        if go_f:
            c = db()
            r = c.execute("SELECT user_id FROM users WHERE email=?", (fe.strip().lower(),)).fetchone()
            if r:
                tmp = secrets.token_urlsafe(8)
                if send_mail(fe.strip().lower(), tmp):
                    c.execute("UPDATE users SET password_hash=? WHERE user_id=?", (hp(tmp), r[0]))
                    c.commit()
                else:
                    r = None
                    st.error(tr("Email service is not configured yet.",
                                "خدمة الإيميل لسه مش متظبطة."))
            c.close()
            if r:
                st.success(tr("If the email exists, a new password was sent.",
                              "لو الإيميل موجود، اتبعتله كلمة مرور جديدة."))
    st.stop()

# ---------- LOGGED-IN HEADER ----------
u = st.session_state.user
h1, h2, h3 = st.columns([5, 2, 1])
h1.markdown(f"**🐄 Dairy Farms** · 👤 {u['name']} · 🏡 {u['farm']} · ID: DF-{u['id']:04d}")
if h3.button(tr("Log Out", "خروج")):
    for k in ("user", "farm_id"):
        st.session_state[k] = None
    st.session_state.page, st.session_state.stack = "auth", []
    st.rerun()
if st.session_state.stack and h2.button(tr("← Back", "رجوع →")):
    back()
st.divider()
page = st.session_state.page
FID = st.session_state.farm_id

# ---------- DASHBOARD ----------
if page == "dashboard":
    st.title(tr("Farm Dashboard", "لوحة التحكم"))
    if st.session_state.get("new_id"):
        st.success(tr(f"Account created! Your ID is DF-{u['id']:04d}",
                      f"تم إنشاء الحساب! رقمك DF-{u['id']:04d}"))
        st.session_state.new_id = None
    c = db()
    n = c.execute("SELECT COUNT(*) FROM animals WHERE farm_id=?", (FID,)).fetchone()[0]
    c.close()
    st.metric(tr("Registered Animals", "الحيوانات المسجلة"), n)
    a, b = st.columns(2)
    if a.button(tr("🐄 Animals", "🐄 الحيوانات"), use_container_width=True):
        go("categories")
    if b.button(tr("🥛 Milk Records & Charts", "🥛 تسجيل اللبن والجرافات"), use_container_width=True):
        go("milk")

# ---------- CATEGORIES ----------
elif page == "categories":
    st.title(tr("Animal Categories", "فئات الحيوانات"))
    cols = st.columns(3)
    for i, (k, v) in enumerate(ANIMALS.items()):
        if cols[i % 3].button(v[0] if EN() else v[1], key=f"cat{k}", use_container_width=True):
            st.session_state.animal_type = k
            go("animal_form")

# ---------- ANIMAL FORM ----------
elif page == "animal_form":
    at = st.session_state.animal_type
    st.title(tr(f"Register: {ANIMALS[at][0][2:]}", f"تسجيل: {ANIMALS[at][1][2:]}"))
    br = list(BREEDS[at])
    bl = lab(BREEDS[at])
    with st.form("animal"):
        st.subheader(tr("Animal", "الحيوان"))
        tag = st.text_input(tr("Animal ID / Tag Number", "رقم الحيوان / رقم الأذن"))
        breed = st.selectbox(tr("Breed", "السلالة"), br, format_func=bl)
        bd = st.date_input(tr("Date of Birth", "تاريخ الميلاد"), value=date.today(),
                           min_value=date(1990, 1, 1))
        sex = st.selectbox(tr("Sex", "النوع"), ["Female", "Male"],
                           format_func=lab({"Female": "أنثى", "Male": "ذكر"}))
        origin = st.selectbox(tr("Origin", "المصدر"), ["Born on farm", "Purchased"],
                              format_func=lab({"Born on farm": "مولود بالمزرعة", "Purchased": "مشتراه"}))
        st.subheader(tr("Mother (optional)", "الأم (اختياري)"))
        mt = st.text_input(tr("Mother ID", "رقم الأم"))
        mb = st.selectbox(tr("Mother's Breed", "سلالة الأم"), [UNK] + br,
                          format_func=lambda x: tr("Unknown", "غير معروف") if x == UNK else bl(x))
        mm = st.number_input(tr("Mother's avg daily milk (L, 0 = unknown)", "متوسط إنتاج الأم اليومي (لتر، 0 = غير معروف)"),
                             min_value=0.0, step=0.5)
        st.subheader(tr("Father (optional)", "الأب (اختياري)"))
        ft = st.text_input(tr("Father ID", "رقم الأب"))
        fb = st.selectbox(tr("Father's Breed", "سلالة الأب"), [UNK] + br,
                          format_func=lambda x: tr("Unknown", "غير معروف") if x == UNK else bl(x))
        gm = st.number_input(tr("Father's mother avg daily milk (L, 0 = unknown)", "متوسط إنتاج أم الأب اليومي (لتر، 0 = غير معروف)"),
                             min_value=0.0, step=0.5)
        ok = st.form_submit_button(tr("Save Animal", "حفظ الحيوان"), use_container_width=True)
    if ok:
        if not tag.strip():
            st.error(tr("Animal ID is required.", "رقم الحيوان مطلوب."))
        else:
            c = db()
            try:
                c.execute("""INSERT INTO animals(farm_id,animal_type,tag,breed,birth_date,sex,origin,
                    mother_tag,mother_breed,mother_milk,father_tag,father_breed,grandam_milk)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                          (FID, at, tag.strip(), breed, bd.isoformat(), sex, origin, mt.strip() or None,
                           None if mb == UNK else mb, mm or None, ft.strip() or None,
                           None if fb == UNK else fb, gm or None))
                c.commit()
                st.success(tr("Animal saved!", "تم حفظ الحيوان!"))
            except sqlite3.IntegrityError:
                st.error(tr("This ID already exists on your farm.", "الرقم ده موجود بالفعل في مزرعتك."))
            finally:
                c.close()

# ---------- MILK RECORDS ----------
elif page == "milk":
    st.title(tr("Weekly Milk Record", "تسجيل اللبن الأسبوعي"))
    c = db()
    an = pd.read_sql_query("SELECT id,tag,breed FROM animals WHERE farm_id=? ORDER BY tag", c, params=(FID,))
    if an.empty:
        st.info(tr("Register an animal first.", "سجل حيوان الأول."))
    else:
        sel = st.selectbox(tr("Animal", "الحيوان"), an.id.tolist(),
                           format_func=lambda i: an.loc[an.id == i, "tag"].iloc[0])
        with st.form("milk"):
            cd = st.date_input(tr("Calving date of this season", "تاريخ الولادة لهذا الموسم"))
            rd = st.date_input(tr("Week ending / record date", "تاريخ التسجيل"), value=date.today())
            wt = st.number_input(tr("Total milk this week (L)", "إجمالي لبن الأسبوع (لتر)"),
                                 min_value=0.0, step=1.0)
            feed = st.text_input(tr("Feeding system this week", "نظام التغذية هذا الأسبوع"))
            nt = st.text_area(tr("Notes (optional)", "ملاحظات (اختياري)"))
            ok = st.form_submit_button(tr("Save", "حفظ"), use_container_width=True)
        if ok:
            if wt <= 0 or rd < cd:
                st.error(tr("Enter milk > 0 and a record date after calving.",
                            "ادخل كمية أكبر من صفر وتاريخ بعد الولادة."))
            else:
                c.execute("INSERT INTO milk(animal_id,calving_date,record_date,weekly_total,feed,notes) VALUES(?,?,?,?,?,?)",
                          (sel, cd.isoformat(), rd.isoformat(), wt, feed, nt))
                c.commit()
                st.success(tr("Saved. Charts updated.", "تم الحفظ. الجرافات اتحدثت."))
        if st.button(tr("📈 View Charts", "📈 عرض الجرافات"), use_container_width=True):
            c.close()
            go("charts")
    c.close()

# ---------- CHARTS ----------
elif page == "charts":
    st.title(tr("Milk Production Charts", "جرافات إنتاج اللبن"))
    c = db()
    df = pd.read_sql_query("""SELECT m.*,a.tag,a.breed,a.mother_milk,a.grandam_milk FROM milk m
        JOIN animals a ON a.id=m.animal_id WHERE a.farm_id=?""", c, params=(FID,))
    c.close()
    if df.empty:
        st.info(tr("No milk records yet.", "مفيش سجلات لسه."))
    else:
        df["week"] = (pd.to_datetime(df.record_date) - pd.to_datetime(df.calving_date)).dt.days // 7 + 1
        df["daily"] = df.weekly_total / 7
        tags = sorted(df.tag.unique())
        one = st.selectbox(tr("Animal", "الحيوان"), tags)
        d = df[df.tag == one]
        st.subheader(tr("Curve: seasons & mother (avg daily L by week after calving)",
                        "المنحنى: المواسم والأم (متوسط لتر/يوم لكل أسبوع بعد الولادة)"))
        pv = d.pivot_table(index="week", columns="calving_date", values="daily", aggfunc="mean").sort_index()
        pv.columns = [tr("Season ", "موسم ") + str(x) for x in pv.columns]
        for col, name in (("mother_milk", tr("Mother", "الأم")), ("grandam_milk", tr("Father's mother", "أم الأب"))):
            v = d[col].dropna()
            if not v.empty:
                pv[name] = v.iloc[0]
        st.line_chart(pv)
        st.subheader(tr("Monthly total (L)", "الإنتاج الشهري (لتر)"))
        mo = d.assign(m=pd.to_datetime(d.record_date).dt.to_period("M").astype(str)).groupby("m").weekly_total.sum()
        st.bar_chart(mo)
        st.subheader(tr("Breed comparison (avg daily L)", "مقارنة السلالات (متوسط لتر/يوم)"))
        st.line_chart(df.pivot_table(index="week", columns="breed", values="daily", aggfunc="mean").sort_index())
        st.subheader(tr("Combined curves", "المنحنيات مجمعة"))
        pick = st.multiselect(tr("Animals", "الحيوانات"), tags, default=tags[:5])
        if pick:
            st.line_chart(df[df.tag.isin(pick)].pivot_table(index="week", columns="tag",
                                                            values="daily", aggfunc="mean").sort_index())
