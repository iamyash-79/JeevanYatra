from flask import Flask, render_template, request, g, redirect, session, url_for, flash, jsonify, current_app, send_file, abort, Response
import pandas as pd
import sqlite3, os, json, random, string, smtplib, ssl, time, razorpay, uuid, io, threading
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask_login import LoginManager, current_user, login_required, logout_user
from email.message import EmailMessage
import mysql.connector

app = Flask(__name__)
app.secret_key = 'zeedkkt4r1'
app.permanent_session_lifetime = timedelta(days=1)

client = razorpay.Client(auth=("rzp_live_R81ZX2l4Pf301W", "ekgW6W3rvJBT49pbbBxIrj6l"))

MAIL_SERVER = 'smtp.zoho.in'
MAIL_PORT = 465
MAIL_USE_SSL = True

APP_NAME = 'JeevanYatra'
EMAIL_ADDRESS = "contact@jeevanyatra.co.in"
EMAIL_PASSWORD = "JkWF0C7i6gha"

PARTNER_EMAIL = 'partner@jeevanyatra.co.in'
PARTNER_PASSWORD = 'bNuPEv3FYhFB'

def generate_random_otp(length=6):
    import random
    return ''.join(random.choices('0123456789', k=length))

def send_otp_to_email(email, otp):
    import smtplib, ssl
    from email.message import EmailMessage

    subject = f"{APP_NAME} - OTP Verification"
    body = f"""Hello,

Your OTP for {APP_NAME} is: {otp}

This code is valid for 5 minutes. Please do not share it with anyone.

Regards,
{APP_NAME} Team
"""

    # Create an EmailMessage object for proper headers
    message = EmailMessage()
    message['From'] = f"{APP_NAME} <{EMAIL_ADDRESS}>"
    message['To'] = email
    message['Subject'] = subject
    message.set_content(body)

    try:
        context = ssl.create_default_context()
        # Connect to your hosting mail server
        with smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT, context=context) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(message)
        return True
    except Exception as e:
        print("OTP send error:", e)
        return False

def get_mysql_connection():
    return mysql.connector.connect(
        host="localhost",
        user="jeevanya_database",
        password="Jeevanyatra@79",
        database="jeevanya_database",
        auth_plugin='mysql_native_password'
    )

# ✅ Fetch all rows
def fetch_all(table_name):
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        return cursor.fetchall()
    except:
        return []
    finally:
        cursor.close()
        conn.close()

# ✅ Log each visit
@app.before_request
def log_traffic():
    ip = request.remote_addr
    now = datetime.now()
    one_hour_ago = now - timedelta(hours=1)

    conn = get_mysql_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*) FROM visits
        WHERE ip = %s AND timestamp >= %s
    """, (ip, one_hour_ago))
    already_logged = cursor.fetchone()[0]

    if already_logged == 0:
        cursor.execute("""
            INSERT INTO visits (ip, user_agent, page, timestamp)
            VALUES (%s, %s, %s, %s)
        """, (ip, request.headers.get('User-Agent'), request.path, now))
        conn.commit()  # ✅ IMPORTANT

    cursor.close()
    conn.close()

# ✅ Total visitors count
def get_total_visitors():
    conn = get_mysql_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM visits")
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count

# ✅ Inject visitor count in all templates
@app.context_processor
def inject_traffic():
    return {"total_visitors": get_total_visitors()}

# ✅ Date format filters
def utc_to_local(utc_str):
    utc_time = datetime.strptime(utc_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=ZoneInfo("UTC"))
    local_time = utc_time.astimezone(ZoneInfo("Asia/Kolkata"))
    return local_time.strftime("%d/%m/%y %I:%M %p")

@app.template_filter('datetimeformat')
def format_datetime(value):
    try:
        utc = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        ist = utc + timedelta(hours=5, minutes=30)
        return ist.strftime("%d/%m/%Y %I:%M %p")
    except Exception:
        return value

# ✅ Inject footer packages
@app.context_processor
def inject_packages():
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, title FROM packages LIMIT 5")
    packages = cursor.fetchall()
    cursor.close()
    conn.close()
    return dict(footer_packages=packages)

# ✅ Inject current user
@app.context_processor
def inject_user():
    return dict(current_user=current_user)

# ✅ Get logged-in user
def get_user():
    user_id = session.get("user_id")
    user_meta = session.get("user")
    if not user_id or not user_meta:
        return None

    role = user_meta.get("role")
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    table = "admins" if role in ("admin", "owner", "master_admin", "founder") else "users"

    cursor.execute("""
        SELECT id, full_name, email, profile_image, role, contact, gender_id
        FROM {} WHERE id = %s
    """.format(table), (user_id,))

    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row

# ✅ Get admin role
def get_admin_role(user_id):
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT role FROM admins WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row["role"] if row else None

# ✅ Get master_admin id
def get_master_admin_id(user_id):
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT role FROM admins WHERE id = %s", (user_id,))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        if admin and admin["role"].lower() == "master_admin":
            return user_id
    except Exception as e:
        print("Error in get_master_admin_id:", e)
    return None

# ✅ Get founder id
def get_founder_id(user_id):
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT role FROM admins WHERE id = %s", (user_id,))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()
        if admin and admin["role"].lower() == "founder":
            return user_id
    except Exception as e:
        print("Error in get_founder_id:", e)
    return None

# ✅ Login handler
def handle_login(expected_role):
    email = request.form.get("email")
    password = request.form.get("password")

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if user and check_password_hash(user["password"], password):
        if user["role"] != expected_role:
            flash("Invalid login for this portal.", "error")
            return redirect(request.path)

        session["user_id"] = user["id"]
        flash("Logged in successfully!", "success")
        return redirect(url_for("owner_dashboard"))

    flash("Invalid credentials", "error")
    return redirect(request.path)

# ✅ Static Robots.txt and Sitemap Routes
@app.route("/robots.txt")
def robots_txt():
    return Response(
        "User-agent: *\nDisallow: /owner/\nSitemap: https://jeevanyatra.co.in/sitemap.xml",
        mimetype="text/plain"
    )

@app.route("/sitemap.xml")
def sitemap():
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id FROM packages")
    packages = cursor.fetchall()
    cursor.close()
    conn.close()

    urls = [
        "https://jeevanyatra.co.in/",
        "https://jeevanyatra.co.in/about_us",
        "https://jeevanyatra.co.in/contact",
        "https://jeevanyatra.co.in/packages"
    ]

    for pkg in packages:
        urls.append(f"https://jeevanyatra.co.in/package/{pkg['id']}")

    sitemap_xml = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        "<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>"
    ]
    for url in urls:
        sitemap_xml.append(f"<url><loc>{url}</loc></url>")
    sitemap_xml.append("</urlset>")

    return Response("\n".join(sitemap_xml), mimetype="application/xml")

@app.route("/")
def user_home():
    user = get_user()

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    # 🎯 Fetch random featured packages
    cursor.execute("""
        SELECT id, title, location, duration, price, start_date, image_url, inclusions
        FROM packages
        ORDER BY RAND()
    """)
    featured_packages = []
    for row in cursor.fetchall():
        featured_packages.append({
            "id": row["id"],
            "title": row["title"],
            "location": row["location"],
            "duration": row["duration"],
            "price": row["price"],
            "start_date": row["start_date"],
            "image_url": row["image_url"],
            "inclusions": row["inclusions"].split(",") if row["inclusions"] else []
        })

    # 🎯 Fetch approved general reviews (package_id IS NULL)
    cursor.execute("""
        SELECT name, rating, content, created_at
        FROM reviews
        WHERE package_id IS NULL AND approved = 1
        ORDER BY created_at DESC
        LIMIT 10
    """)
    general_reviews = cursor.fetchall()

    cursor.close()
    conn.close()

    # ✅ SEO meta info
    seo_title = "JeevanYatra"
    seo_description = "Discover top travel destinations and exclusive tour packages in India with Jeevan Yatra. Plan your next adventure today!"
    seo_keywords = (
        "Jeevan Yatra, jeevanyatra, jivanyatra, जीवनयात्रा, जीवन यात्रा, Travel Packages India, Adventure Trips, Holiday Packages, India Tours, "
        "Ujjain tours, Mahakal darshan, Kedarnath yatra, Badrinath tours, Gangotri yatra, Yamunotri darshan, "
        "Char dham tours, Amarnath yatra, Jagannath tours, Puri yatra, Tirupati tours, Vaishno devi tours, "
        "Varanasi tours, Kashi darshan, Ganga darshan, JeevanYatra, JeevanYatra tours, JeevanYatra travel, JeevanYatra booking, JeevanYatra packages, JeevanYatra reviews, "
        "JeevanYatra contact, Family tours India, Family trips, Honeymoon tours India, Weekend trips, Holiday packages, Budget trips, Adventure tours, Customized tours, "
        "Couple packages, Best tours India, Best tours in Chhattisgarh, Best tours in CG, Best travellers in CG, Best traveller in CG, Raipur tours, Bilaspur tours, " 
        "Durg tours, Bhilai tours, Jagdalpur tours, Bastar tourism, Chhattisgarh travel, Chhattisgarh tourism, CG holiday packages, "
        "Cheap tours India, Affordable packages, Low cost yatra, Discounted packages, Best budget tours, Online booking tours, Travel agent CG, Best travel deals, " 
        "India tour packages, Tour booking online, Top tours India, Best tour agency CG, Best travel company CG, Trusted travel agency, Tour operator in CG, " 
        "Travel guide CG, Best darshan tours, Pilgrimage agent India, Religious tours India, Spiritual travel CG, CG darshan tours"
    )

    return render_template(
        "user_home.html",
        user=user,
        full_name=user["full_name"] if user else None,
        featured_packages=featured_packages,
        general_reviews=general_reviews,
        seo_title=seo_title,
        seo_description=seo_description,
        seo_keywords=seo_keywords
    )

# ✅ Review submission route
@app.route("/submit_review", methods=["POST"])
def submit_general_review():
    name = request.form.get("name")
    rating = int(request.form.get("rating"))
    content = request.form.get("content")

    conn = get_mysql_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reviews (package_id, name, rating, content)
        VALUES (%s, %s, %s, %s)
    """, (None, name, rating, content))  # package_id = NULL
    conn.commit()
    cursor.close()
    conn.close()

    flash("Thanks For Your Review.")
    return redirect(url_for("user_home"))

# ✅ Packages list page
@app.route("/packages")
def packages():
    user = get_user()

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM packages")
    packages = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        "packages.html",
        user=user,
        full_name=user["full_name"] if user else None,
        packages=packages
    )
    
@app.route("/package/<int:package_id>")
def package_details(package_id):
    user = get_user()

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch package details
    cursor.execute("SELECT * FROM packages WHERE id = %s", (package_id,))
    package = cursor.fetchone()

    if not package:
        conn.close()
        return "Package not found", 404

    # Split inclusions
    inclusions_str = package.get("inclusions", "")
    package["inclusions"] = [i.strip() for i in inclusions_str.split(",") if i.strip()]

    # Fetch only approved reviews
    cursor.execute(
        "SELECT * FROM reviews WHERE package_id = %s AND approved = 1 ORDER BY id DESC",
        (package_id,)
    )
    reviews = cursor.fetchall()

    conn.close()
    return render_template(
        "package_details.html",
        package=package,
        reviews=reviews,
        user=user,
        full_name=user["full_name"] if user else None
    )


@app.route("/submit_review/<int:package_id>", methods=["POST"])
def submit_review(package_id):
    name = request.form.get("name")
    rating = int(request.form.get("rating"))
    content = request.form.get("content")

    conn = get_mysql_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO reviews (package_id, name, rating, content)
        VALUES (%s, %s, %s, %s)
    """, (package_id, name, rating, content))
    conn.commit()
    conn.close()

    flash("Thanks For Your Review.")
    return redirect(url_for("package_details", package_id=package_id))


@app.route("/book_package/<int:package_id>", methods=["GET"])
def book_package(package_id):
    user = get_user()

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch package
    cursor.execute("""
        SELECT id, title, location, duration, price, inclusions, image_url, boardings, start_date, bus_id
        FROM packages
        WHERE id = %s
    """, (package_id,))
    package = cursor.fetchone()

    if not package:
        conn.close()
        return "Package not found", 404

    # Split boardings
    boardings = package["boardings"].split(",") if package["boardings"] else []
    package["boardings"] = boardings

    # Fetch available seats
    cursor.execute("""
        SELECT available_seats FROM seats
        WHERE bus_id = %s AND package_id = %s
    """, (package["bus_id"], package["id"]))
    seats_row = cursor.fetchone()
    package["available_seats"] = seats_row["available_seats"] if seats_row else "N/A"

    # Fetch full user details
    full_user = None
    if user:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user["id"],))
        full_user = cursor.fetchone()

    conn.close()
    return render_template("book_package.html", package=package, user=full_user)

@app.route("/payment_success", methods=["POST"])
def payment_success():
    from datetime import datetime

    package_id = request.form.get("package_id")
    total_adults = int(request.form.get("total_adults") or 1)
    total_child = int(request.form.get("total_children") or 0)
    paid_amount = int(float(request.form.get("total_price")))
    razorpay_payment_id = request.form.get("razorpay_payment_id")
    boarding_point = request.form.get("boarding_point")
    booking_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    payment_type = request.form.get("payment_type_hidden") or "Full"

    full_price = paid_amount * 2 if payment_type == "Partial" else paid_amount

    primary = {
        "name": request.form.get("primary_name"),
        "mobile": request.form.get("primary_mobile"),
        "email": (request.form.get("primary_email") or "").strip().lower(),
        "gender": request.form.get("primary_gender"),
        "age": request.form.get("primary_age")
    }

    gender_map = {"Male": 1, "Female": 2, "Other": 3}
    gender_id = gender_map.get(primary["gender"], None)

    accompanying_adults = []
    for i in range(1, total_adults):
        name = request.form.get(f"accompanying_name_{i}")
        mobile = request.form.get(f"accompanying_mobile_{i}")
        age = request.form.get(f"accompanying_age_{i}")
        gender = request.form.get(f"accompanying_gender_{i}")
        if name:
            accompanying_adults.append({
                "name": name,
                "mobile": mobile,
                "age": age,
                "gender": gender_map.get(gender, None)
            })

    accompanying_children = []
    for i in range(1, total_child + 1):
        name = request.form.get(f"child_name_{i}")
        age = request.form.get(f"child_age_{i}")
        if name:
            accompanying_children.append({"name": name, "age": age})

    # ---------------------------
    # STEP 1: CAPTURE PAYMENT
    # ---------------------------
    try:
        capture_amount = paid_amount * 100
        client.payment.capture(razorpay_payment_id, capture_amount)
    except razorpay.errors.BadRequestError as e:
        flash(f"Payment capture failed: {str(e)}", "danger")
        return redirect(url_for("package_details", package_id=package_id))

    # ---------------------------
    # STEP 2: CONNECT TO MYSQL DB
    # ---------------------------
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    # ---------------------------
    # STEP 3: Determine user_id
    # ---------------------------
    user_id = session.get("user_id")

    if user_id:
        cursor.execute("""
            UPDATE users
            SET full_name = %s, contact = %s, gender_id = %s
            WHERE id = %s
        """, (primary["name"], primary["mobile"], gender_id, user_id))
    else:
        cursor.execute("SELECT id FROM users WHERE email = %s", (primary["email"],))
        existing_user = cursor.fetchone()

        if existing_user:
            user_id = existing_user["id"]
            cursor.execute("""
                UPDATE users
                SET full_name = %s, contact = %s, gender_id = %s
                WHERE id = %s
            """, (primary["name"], primary["mobile"], gender_id, user_id))
        else:
            cursor.execute("""
                INSERT INTO users (full_name, email, contact, dob, gender_id, role)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                primary["name"], primary["email"], primary["mobile"], None, gender_id, "user"
            ))
            user_id = cursor.lastrowid

    # ---------------------------
    # STEP 4: Get package details
    # ---------------------------
    cursor.execute("""
        SELECT bus_id, owner_id, start_date FROM packages WHERE id = %s
    """, (package_id,))
    package_row = cursor.fetchone()

    if not package_row:
        conn.close()
        return "Invalid package ID", 400

    bus_id = package_row["bus_id"]
    owner_id = package_row["owner_id"]
    start_date = package_row["start_date"]

    # ---------------------------
    # STEP 5: Create booking
    # ---------------------------
    cursor.execute("""
        INSERT INTO bookings (
            user_id, owner_id, package_id, primary_name, primary_mobile,
            primary_email, primary_gender, primary_age, accompanying_adults,
            total_adults, accompanying_children, total_child, boarding_point,
            booking_time, start_date, total_price, paid_amount,
            razorpay_payment_id, payment_type, status
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s
        )
    """, (
        user_id, owner_id, package_id, primary["name"], primary["mobile"],
        primary["email"], gender_id, primary["age"], json.dumps(accompanying_adults),
        total_adults, json.dumps(accompanying_children), total_child,
        boarding_point, booking_time, start_date, full_price, paid_amount,
        razorpay_payment_id, payment_type, "Booked"
    ))

    booking_id = cursor.lastrowid

    # ---------------------------
    # STEP 6: Update seats
    # ---------------------------
    cursor.execute("""
        UPDATE seats
        SET available_seats = available_seats - %s
        WHERE package_id = %s AND bus_id = %s
    """, (total_adults, package_id, bus_id))

    conn.commit()
    conn.close()

    flash("Your package is successfully booked!", "success")
    return redirect(url_for("ticket_page", booking_id=booking_id))


@app.route("/ticket/<int:booking_id>")
def ticket_page(booking_id):
    user_id = session.get("user_id")
    user = get_user() if user_id else None

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM bookings WHERE id = %s", (booking_id,))
    booking = cursor.fetchone()
    conn.close()

    if not booking:
        return "Ticket not found", 404

    booking["primary_gender"] = int(booking["primary_gender"]) if booking["primary_gender"] else None

    return render_template(
        "ticket.html",
        booking=booking,
        user=user,
        full_name=user["full_name"] if user else None
    )

@app.route("/user_booking")
def user_booking():
    if "user_id" not in session:
        return redirect("/")

    user = get_user()
    user_id = session["user_id"]

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            id,
            booking_time,
            total_adults,
            total_child,
            total_price,
            paid_amount,
            payment_type,
            boarding_point,
            package_id,
            start_date,
            status,
            refund_status,
            refund_amount
        FROM bookings
        WHERE user_id = %s
        ORDER BY booking_time DESC
    """, (user_id,))

    bookings = []
    today = datetime.now().date()

    for row in cursor.fetchall():
        try:
            start_date = datetime.strptime(str(row["start_date"]), "%Y-%m-%d %H:%M:%S").date()
        except ValueError:
            start_date = datetime.strptime(str(row["start_date"]), "%Y-%m-%d").date()

        row["start_date"] = start_date
        row["days_left"] = (start_date - today).days
        bookings.append(row)

    conn.close()

    return render_template(
        "user_booking.html",
        bookings=bookings,
        user=user,
        full_name=user["full_name"] if user else None
    )


@app.route("/user_settings")
def user_settings():
    user = get_user()

    if user and user.get("role") == "owner":
        return redirect(url_for("owner_dashboard"))

    return render_template("user_settings.html", user=user)


@app.route("/mobile_settings")
def mobile_settings():
    user = get_user()
    return render_template("mobile_settings.html", user=user)


@app.route("/deactivate-account", methods=["POST"])
def deactivate_account():
    user = get_user()
    if not user:
        return jsonify(success=False, message="Not logged in.")

    if user["role"] in ["admin", "owner", "master_admin"]:
        return jsonify(success=False, message="Admins and master_admins cannot deactivate.")

    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = %s", (user["id"],))
        conn.commit()
        conn.close()
        session.clear()
        return jsonify(success=True)
    except Exception as e:
        return jsonify(success=False, message=str(e))
        
        
@app.route("/user_account", methods=["GET", "POST"])
def user_account():
    user = get_user()

    if not user:
        return redirect(url_for("user_home"))

    if user.get("role") == "owner":
        return redirect(url_for("owner_dashboard"))

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        gender_id = request.form.get("gender_id", 1)
        dob = request.form.get("dob")

        # Remove image if requested
        if 'remove_image' in request.form:
            cursor.execute("UPDATE users SET profile_image = NULL WHERE id = %s", (user["id"],))

        # Handle new image upload
        image = request.files.get("image")
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            upload_folder = os.path.join(current_app.root_path, "static/images")
            os.makedirs(upload_folder, exist_ok=True)
            filepath = os.path.join(upload_folder, filename)
            image.save(filepath)

            image_url = f"/static/images/{filename}"
            cursor.execute("UPDATE users SET profile_image = %s WHERE id = %s", (image_url, user["id"]))

        # Update profile info
        cursor.execute("UPDATE users SET full_name = %s, gender_id = %s, dob = %s WHERE id = %s",
                       (full_name, gender_id, dob, user["id"]))
        conn.commit()

        # Reload updated user
        cursor.execute("SELECT * FROM users WHERE id = %s", (user["id"],))
        updated_user = cursor.fetchone()
        conn.close()

        session["user"] = {
            "email": updated_user["email"],
            "role": updated_user["role"],
            "name": updated_user["full_name"],
            "contact": updated_user["contact"]
        }

        flash("Account updated successfully.", "success")
        return redirect(url_for("user_account"))

    # ✅ GET request
    cursor.execute("SELECT * FROM users WHERE id = %s", (user["id"],))
    fresh_user = cursor.fetchone()
    conn.close()

    return render_template("user_account.html", user=fresh_user)


@app.route("/change-info", methods=["POST"])
def change_info():
    user = get_user()
    if not user:
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for("user_account"))

    email = request.form.get("email", "").strip()
    contact = request.form.get("contact", "").strip()

    if not email and not contact:
        flash("Please provide at least one field to update.", "error")
        return redirect(url_for("user_account"))

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    # ✅ Update email if needed
    if email and email != user["email"]:
        if not session.get("otp_verified"):
            flash("Please verify OTP before changing your email.", "error")
            conn.close()
            return redirect(url_for("user_account"))
        cursor.execute("UPDATE users SET email = %s WHERE id = %s", (email, user["id"]))

    # ✅ Update contact if needed
    if contact and contact != user.get("contact"):
        cursor.execute("UPDATE users SET contact = %s WHERE id = %s", (contact, user["id"]))

    conn.commit()

    # ✅ Reload fresh user and update session
    cursor.execute("SELECT * FROM users WHERE id = %s", (user["id"],))
    updated_user = cursor.fetchone()

    session["user"] = {
        "email": updated_user["email"],
        "role": updated_user["role"],
        "name": updated_user["full_name"],
        "contact": updated_user["contact"]
    }

    # ✅ Clear OTP session
    for key in ["otp_code", "otp_email", "otp_expiry", "otp_verified"]:
        session.pop(key, None)

    conn.close()
    flash("Information updated successfully.", "success")
    return redirect(url_for("user_account"))


@app.route("/send-user-otp", methods=["POST"])
def send_user_otp():
    email = request.json.get("email", "").strip()
    if not email:
        return jsonify(success=False, message="Email is required.")

    user_id = session.get("user_id")
    is_logged_in = bool(user_id)

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    existing_user = cursor.fetchone()

    # ✅ Logged in: changing email
    if is_logged_in:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        current_user = cursor.fetchone()
        if not current_user:
            conn.close()
            return jsonify(success=False, message="User not found.")

        if email == current_user["email"]:
            conn.close()
            return jsonify(success=False, message="This is already your current email.")

        if existing_user:
            conn.close()
            return jsonify(success=False, message="This email is already in use.")

    # ✅ Not logged in: new user creation
    elif not existing_user:
        try:
            cursor.execute("""
                INSERT INTO users (email, full_name, role, contact)
                VALUES (%s, '', 'user', '0000000000')
            """, (email,))
            conn.commit()
        except Exception as e:
            conn.close()
            return jsonify(success=False, message="Registration failed: " + str(e))

    conn.close()

    # ✅ Send OTP
    otp = generate_random_otp()
    session["user_otp_email"] = email
    session["user_otp_code"] = otp
    session["user_otp_expiry"] = time.time() + 300  # 5 min

    if send_otp_to_email(email, otp):
        return jsonify(success=True, message="OTP sent to email.")
    else:
        return jsonify(success=False, message="Failed to send OTP.")


@app.route("/verify-user-otp", methods=["POST"])
def verify_user_otp():
    user_otp = request.json.get("otp", "").strip()
    stored_otp = session.get("user_otp_code")
    target_email = session.get("user_otp_email")
    expiry = session.get("user_otp_expiry", 0)

    if not user_otp or not stored_otp or not target_email:
        return jsonify(verified=False, message="Session expired or missing data.")
    if time.time() > expiry:
        return jsonify(verified=False, message="OTP expired. Please try again.")
    if user_otp != stored_otp:
        return jsonify(verified=False, message="Incorrect OTP.")

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    user_id = session.get("user_id")

    # ✅ Case 1: Logged in (update email)
    if user_id:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        current = cursor.fetchone()
        if not current:
            conn.close()
            return jsonify(verified=False, message="User not found.")

        cursor.execute("SELECT * FROM users WHERE email = %s", (target_email,))
        if cursor.fetchone():
            conn.close()
            return jsonify(verified=False, message="Email already in use.")

        cursor.execute("UPDATE users SET email = %s WHERE id = %s", (target_email, user_id))
        conn.commit()
        session["user"]["email"] = target_email
        conn.close()
        return jsonify(verified=True, message="Email updated successfully.")

    # ✅ Case 2: Not logged in (login via OTP)
    cursor.execute("SELECT * FROM users WHERE email = %s", (target_email,))
    user = cursor.fetchone()
    conn.close()

    if not user:
        return jsonify(verified=False, message="User not found.")
    if user["role"] in ("admin", "owner", "master_admin"):
        return jsonify(verified=False, message="Admins not allowed here.")

    session["user_id"] = user["id"]
    session["user"] = {
        "email": user["email"],
        "role": user["role"],
        "name": user["full_name"] or ""
    }

    return jsonify(verified=True, message="Logged in successfully.")

@app.route('/user_contact', methods=["GET", "POST"])
def user_contact():
    user = get_user()

    if user and user.get("role") in ("owner"):
        return redirect(url_for("owner_dashboard"))

    if request.method == "POST":
        flash("Messaging system is disabled.", "info")

    return render_template("user_contact.html", full_name=user["full_name"] if user else "", user=user)

@app.route("/custom")
def custom():
    user = get_user()
    return render_template("custom.html", user=user)

@app.route("/about_us")
def about_us():
    user = get_user()
    return render_template("about_us.html", user=user)

@app.route("/contact")
def contact():
    user = get_user()
    return render_template("contact.html", user=user)

@app.route("/privacy_policy")
def privacy_policy():
    user = get_user()
    return render_template("privacy_policy.html", user=user)

@app.route("/terms")
def terms():
    user = get_user()
    return render_template("terms.html", user=user)

@app.route("/refund")
def refund():
    user = get_user()
    return render_template("refund.html", user=user)

# owner and master_admins route ====owner and master_admins route=======owner and master_admins route=============owner and master_admins route=============owner and master_admins route===================owner and master_admins route======

@app.route("/partner", methods=["GET", "POST"])
def partner():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        subject = request.form.get("subject")
        message = request.form.get("message")

        # Admin Email
        admin_msg = EmailMessage()
        admin_msg['From'] = f"Partner <{PARTNER_EMAIL}>"
        admin_msg['To'] = PARTNER_EMAIL
        admin_msg['Subject'] = f"New Contact - {subject}"
        admin_msg.add_alternative(f"""
            <h3>New Inquiry from Website:</h3>
            <ul>
                <li><strong>Name:</strong> {name}</li>
                <li><strong>Email:</strong> {email}</li>
                <li><strong>Phone:</strong> {phone}</li>
                <li><strong>Subject:</strong> {subject}</li>
                <li><strong>Message:</strong><br>{message}</li>
            </ul>
        """, subtype="html")

        # User Auto-Reply
        user_msg = EmailMessage()
        user_msg['From'] = f"Partner - JeevanYatra <{PARTNER_EMAIL}>"
        user_msg['To'] = email
        user_msg['Subject'] = "Thanks for contacting JeevanYatra"
        user_msg.add_alternative(f"""
            <p>Dear {name},</p>
            <p>Thank you for reaching out to <strong>JeevanYatra</strong>! 🌞<br>
            We have received your message and our team will get back to you shortly.</p>
            <p><strong>Your submitted details:</strong><br>
            Subject: {subject}<br>
            Phone: {phone}<br>
            Message: {message}</p>
            <p>Warm regards,<br>
            <strong>Team JeevanYatra</strong></p>
        """, subtype="html")

        try:
            # Send emails using your hosting server
            with smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT) as smtp:
                smtp.login(PARTNER_EMAIL, PARTNER_PASSWORD)
                smtp.send_message(admin_msg)
                smtp.send_message(user_msg)

            # Set session flag for modal popup
            session['show_popup'] = True
            return redirect(url_for('partner'))

        except Exception as e:
            print("Error sending email:", e)
            # Show popup even if email fails
            session['show_popup'] = True
            return redirect(url_for('partner'))

    # GET request
    show_popup = session.pop('show_popup', False)
    return render_template("partner.html", title="📞 Contact JeevanYatra", show_popup=show_popup)

@app.route("/owner_login", methods=["GET", "POST"])
def owner_login():
    if "user_id" in session:
        return redirect(url_for("owner_dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("Email and password are required.", "error")
            return redirect(url_for("owner_login"))

        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admins WHERE LOWER(email) = %s", (email,))
        admin = cursor.fetchone()
        conn.close()

        if not admin or not admin["password"]:
            flash("Invalid email or password", "error")
            return redirect(url_for("owner_login"))

        if not check_password_hash(admin["password"], password):
            flash("Invalid email or password", "error")
            return redirect(url_for("owner_login"))

        db_role = (admin.get("role") or "user").strip().lower()
        if db_role not in ("owner", "master_admin", "founder"):
            flash("You are not authorized to log in as owner.", "error")
            return redirect(url_for("owner_login"))

        session["user_id"] = admin["id"]
        session["user_type"] = "admin"
        session["user"] = {
            "id": admin["id"],
            "email": admin["email"],
            "role": db_role,
            "full_name": admin["full_name"]
        }

        return redirect(url_for("owner_dashboard"))

    return render_template("owner_login.html")


@app.route("/owner_dashboard")
def owner_dashboard():
    if "user_id" not in session:
        return redirect(url_for("owner_login"))

    owner_id = session["user_id"]

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM admins WHERE id = %s", (owner_id,))
    user_row = cursor.fetchone()

    if not user_row:
        conn.close()
        flash("Admin account not found.", "error")
        return redirect(url_for("owner_login"))

    user = dict(user_row)
    role = (user.get("role") or "owner").strip().lower()

    if role in ("founder", "master_admin"):
        cursor.execute("SELECT COUNT(*) AS count FROM packages")
        total_packages = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) AS count FROM bookings")
        total_bookings = cursor.fetchone()["count"]

        cursor.execute("SELECT SUM(total_price) AS total FROM bookings")
        total_earnings = cursor.fetchone()["total"] or 0

        cursor.execute("""
            SELECT title, location, start_date
            FROM packages
            WHERE start_date IS NOT NULL
            ORDER BY start_date ASC
            LIMIT 1
        """)
        next_package = cursor.fetchone()

    else:
        cursor.execute("SELECT COUNT(*) AS count FROM packages WHERE owner_id = %s", (owner_id,))
        total_packages = cursor.fetchone()["count"]

        cursor.execute("""
            SELECT COUNT(*) AS count
            FROM bookings
            WHERE package_id IN (SELECT id FROM packages WHERE owner_id = %s)
        """, (owner_id,))
        total_bookings = cursor.fetchone()["count"]

        cursor.execute("""
            SELECT SUM(total_price) AS total
            FROM bookings
            WHERE package_id IN (SELECT id FROM packages WHERE owner_id = %s)
        """, (owner_id,))
        total_earnings = cursor.fetchone()["total"] or 0

        cursor.execute("""
            SELECT title, location, start_date
            FROM packages
            WHERE owner_id = %s AND start_date IS NOT NULL
            ORDER BY start_date ASC
            LIMIT 1
        """, (owner_id,))
        next_package = cursor.fetchone()

    conn.close()

    return render_template("owner_dashboard.html",
        user=user,
        total_packages=total_packages,
        total_bookings=total_bookings,
        total_earnings=total_earnings,
        next_package=next_package
    )


@app.route("/manage_bookings")
def manage_bookings():
    if "user_id" not in session:
        return redirect("/owner_login")

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM admins WHERE id = %s", (session["user_id"],))
    admin = cursor.fetchone()

    if not admin:
        conn.close()
        flash("Admin not found", "error")
        return redirect("/owner_login")

    role = admin["role"].lower()
    is_master = role == "master_admin"
    is_founder = role == "founder"

    # 🔹 Fetch bookings
    if is_master or is_founder:
        cursor.execute("SELECT * FROM bookings ORDER BY booking_time DESC")
        raw_rows = cursor.fetchall()
    else:
        cursor.execute("SELECT id FROM packages WHERE owner_id = %s", (session["user_id"],))
        package_ids = [row["id"] for row in cursor.fetchall()]

        if package_ids:
            placeholders = ",".join(["%s"] * len(package_ids))
            cursor.execute(
                f"SELECT * FROM bookings WHERE package_id IN ({placeholders}) ORDER BY booking_time DESC",
                tuple(package_ids)
            )
            raw_rows = cursor.fetchall()
        else:
            raw_rows = []

    bookings = []
    for row in raw_rows:
        booking = dict(row)
        if is_master or is_founder:
            cursor.execute("SELECT full_name FROM admins WHERE id = %s", (row["owner_id"],))
            owner = cursor.fetchone()
            booking["owner_name"] = owner["full_name"] if owner else "Unknown"
        bookings.append(booking)

    # 🔹 Fetch packages
    if is_master or is_founder:
        cursor.execute("SELECT id, title, price, boardings FROM packages")
    else:
        cursor.execute("SELECT id, title, price, boardings FROM packages WHERE owner_id = %s", (session["user_id"],))
    packages_raw = cursor.fetchall()

    packages = []
    for row in packages_raw:
        pkg = dict(row)
        pkg["boardings"] = [b.strip() for b in (pkg["boardings"] or "").split(",") if b.strip()]
        packages.append(pkg)

    conn.close()

    return render_template(
        "manage_bookings.html",
        bookings=bookings,
        is_master=is_master,
        is_founder=is_founder,
        packages=packages,
        user=admin
    )

@app.route("/book_trip", methods=["POST"])
def book_trip():
    if "user_id" not in session:
        return redirect(url_for("owner_login"))

    data = request.form
    package_id = data.get("package_id")

    if not package_id:
        flash("Please select a package.", "error")
        return redirect("/manage_bookings")

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    # 🔹 Get current admin
    cursor.execute("SELECT * FROM admins WHERE id = %s", (session["user_id"],))
    admin = cursor.fetchone()

    if not admin:
        flash("Admin not found.", "error")
        conn.close()
        return redirect("/manage_bookings")

    role = admin["role"].lower()
    is_master = role == "master_admin"
    is_founder = role == "founder"

    # 🔹 Package access check
    if not (is_master or is_founder):
        cursor.execute(
            "SELECT * FROM packages WHERE id = %s AND owner_id = %s",
            (package_id, session["user_id"])
        )
    else:
        cursor.execute("SELECT * FROM packages WHERE id = %s", (package_id,))
    package = cursor.fetchone()

    if not package:
        flash("Invalid or unauthorized package.", "error")
        conn.close()
        return redirect("/manage_bookings")

    # Booking details
    primary_name = data.get("primary_name")
    primary_mobile = data.get("primary_mobile")
    primary_email = data.get("primary_email")
    primary_gender_str = data.get("primary_gender", "").lower()
    primary_age = data.get("primary_age")
    boarding_point = data.get("boarding_point")

    try:
        paid_amount = float(data.get("paid_amount", "0") or 0)
    except ValueError:
        paid_amount = 0.0

    payment_type = "cash"
    raw_start_date = package["start_date"]

    # ✅ Gender handling
    if primary_gender_str in ("male", "1"):
        primary_gender = 1
    elif primary_gender_str in ("female", "2"):
        primary_gender = 2
    else:
        primary_gender = 3

    try:
        total_adults = int(data.get("total_adults", 1))
        total_child = int(data.get("total_child", 0))
    except ValueError:
        flash("Invalid passenger count.", "error")
        conn.close()
        return redirect("/manage_bookings")

    price = float(package["price"])
    total_price = (total_adults * price) + (total_child * price * 0.5)

    # 🔹 Check seats
    cursor.execute("SELECT available_seats FROM seats WHERE package_id = %s", (package_id,))
    seat_row = cursor.fetchone()
    if not seat_row or seat_row["available_seats"] < total_adults:
        flash("Not enough seats available.", "error")
        conn.close()
        return redirect("/manage_bookings")

    # 🔹 Insert booking
    cursor.execute("""
        INSERT INTO bookings (
            user_id, owner_id, package_id, primary_name, primary_mobile, primary_email,
            primary_gender, primary_age, boarding_point, booking_time, start_date,
            total_price, paid_amount, payment_type, total_adults, total_child, status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s)
    """, (
        session["user_id"], package["owner_id"], package_id, primary_name, primary_mobile,
        primary_email, primary_gender, primary_age, boarding_point,
        raw_start_date, total_price, paid_amount, payment_type,
        total_adults, total_child, "booked"
    ))

    # 🔹 Deduct seats
    cursor.execute(
        "UPDATE seats SET available_seats = available_seats - %s WHERE package_id = %s",
        (total_adults, package_id)
    )

    conn.commit()
    conn.close()

    flash("Trip booked successfully.", "success")
    return redirect("/manage_bookings")


# ✅ Cancel Booking
@app.route("/cancel_booking/<int:booking_id>", methods=["POST"])
def cancel_booking(booking_id):
    if "user_id" not in session:
        return "Unauthorized", 401

    user_id = session["user_id"]
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch user role
    cursor.execute("SELECT role FROM admins WHERE id = %s", (user_id,))
    admin = cursor.fetchone()
    role = admin["role"].lower() if admin else "user"

    # Fetch booking
    if role in ("master_admin", "founder"):
        cursor.execute("SELECT * FROM bookings WHERE id = %s", (booking_id,))
    else:
        cursor.execute("SELECT * FROM bookings WHERE id = %s AND user_id = %s", (booking_id, user_id))
    booking = cursor.fetchone()

    if not booking:
        return "Booking not found", 404
    if booking["status"] == "cancelled":
        return "Already cancelled", 400

    # Calculate days left
    start_date = datetime.strptime(str(booking["start_date"]), "%Y-%m-%d %H:%M:%S").date()
    days_left = (start_date - datetime.now().date()).days

    if days_left >= 7:
        cancel_percent = 0.10
    elif days_left >= 4:
        cancel_percent = 0.20
    elif days_left >= 2:
        cancel_percent = 0.40
    else:
        return "Cannot cancel within 1 day of trip", 400

    # Refund calculation
    total_price = booking["total_price"]
    paid_amount = booking["paid_amount"]
    refund_amount = round(paid_amount - (total_price * cancel_percent), 2)
    if refund_amount <= 0:
        refund_amount = 1.00

    # Refund through Razorpay (if applicable)
    if booking.get("razorpay_payment_id"):
        try:
            client.payment.refund(booking["razorpay_payment_id"], {"amount": int(refund_amount * 100)})
            refund_status = "Completed"
        except Exception:
            refund_status = "Pending"
    else:
        refund_status = "Not Applicable"

    # Update booking
    cursor.execute("""
        UPDATE bookings
        SET status = %s, cancel_time = NOW(), refund_status = %s,
            refund_amount = %s, refund_time = NOW()
        WHERE id = %s
    """, ("cancelled", refund_status, refund_amount, booking_id))

    # Restore seats
    cursor.execute("""
        UPDATE seats SET available_seats = available_seats + %s WHERE package_id = %s
    """, (booking["total_adults"], booking["package_id"]))

    conn.commit()
    conn.close()

    return f"Booking cancelled successfully. Refund: ₹{refund_amount} ({refund_status})", 200


# ✅ Delete Booking
@app.route("/delete_booking/<int:booking_id>")
def delete_booking(booking_id):
    if "user_id" not in session:
        return redirect("/owner_login")

    user_id = session["user_id"]
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT owner_id FROM bookings WHERE id = %s", (booking_id,))
    booking = cursor.fetchone()
    if not booking:
        flash("Booking not found.", "error")
        conn.close()
        return redirect("/manage_bookings")

    owner_id = booking["owner_id"]
    cursor.execute("SELECT role FROM admins WHERE id = %s", (user_id,))
    role = cursor.fetchone()["role"].lower()

    if not (user_id == owner_id or role in ("master_admin", "founder")):
        flash("You do not have permission to delete this booking.", "error")
        conn.close()
        return redirect("/manage_bookings")

    cursor.execute("DELETE FROM bookings WHERE id = %s", (booking_id,))
    conn.commit()
    conn.close()

    flash("Booking deleted successfully.", "success")
    return redirect("/manage_bookings")
    
@app.route("/download_bookings")
def download_bookings():
    if "user_id" not in session:
        return redirect("/owner_login")

    conn_admins = get_mysql_connection()
    cursor_admin = conn_admins.cursor(dictionary=True)
    cursor_admin.execute("SELECT * FROM admins WHERE id = %s", (session["user_id"],))
    admin = cursor_admin.fetchone()
    cursor_admin.close()
    conn_admins.close()

    if not admin:
        flash("Admin not found", "error")
        return redirect("/owner_login")

    role = admin["role"].lower()
    is_master = role == "master_admin"
    is_founder = role == "founder"
    admin_id = session["user_id"]

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    if is_master or is_founder:
        cursor.execute("SELECT * FROM bookings ORDER BY booking_time DESC")
        rows = cursor.fetchall()
    else:
        cursor.execute("SELECT id FROM packages WHERE owner_id = %s", (admin_id,))
        package_ids = [row["id"] for row in cursor.fetchall()]

        if not package_ids:
            cursor.close()
            conn.close()
            flash("No bookings found.", "info")
            return redirect("/manage_bookings")

        placeholders = ",".join(["%s"] * len(package_ids))
        query = f"SELECT * FROM bookings WHERE package_id IN ({placeholders}) ORDER BY booking_time DESC"
        cursor.execute(query, tuple(package_ids))
        rows = cursor.fetchall()

    bookings = []

    for booking in rows:
        if is_master or is_founder:
            cursor.execute("SELECT owner_id FROM packages WHERE id = %s", (booking["package_id"],))
            package = cursor.fetchone()
            if package:
                conn_admin = get_mysql_connection()
                cur2 = conn_admin.cursor(dictionary=True)
                cur2.execute("SELECT full_name FROM admins WHERE id = %s", (package["owner_id"],))
                owner = cur2.fetchone()
                conn_admin.close()
                booking["owner_name"] = owner["full_name"] if owner else "Unknown"
            else:
                booking["owner_name"] = "Unknown"
        bookings.append(booking)

    cursor.close()
    conn.close()

    if not bookings:
        flash("No bookings to export.", "info")
        return redirect("/manage_bookings")

    import io, pandas as pd
    output = io.BytesIO()
    df = pd.DataFrame(bookings)

    if "owner_name" in df.columns:
        cols = ["owner_name"] + [c for c in df.columns if c != "owner_name"]
        df = df[cols]

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Bookings", index=False)
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name="bookings.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.route('/manage_reviews')
def manage_reviews():
    if "user_id" not in session:
        return redirect(url_for("owner_login"))

    owner_id = session["user_id"]

    conn_admins = get_mysql_connection()
    cur_admin = conn_admins.cursor(dictionary=True)
    cur_admin.execute("SELECT * FROM admins WHERE id = %s", (owner_id,))
    owner = cur_admin.fetchone()
    conn_admins.close()

    if not owner:
        flash("Admin not found.", "error")
        return redirect(url_for("owner_login"))

    role = owner["role"].lower()

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    if role in ["founder", "master_admin"]:
        cursor.execute("SELECT * FROM reviews ORDER BY created_at DESC")
        reviews = cursor.fetchall()
    else:
        cursor.execute("SELECT id FROM buses WHERE owner_id = %s", (owner_id,))
        bus_ids = [b["id"] for b in cursor.fetchall()]

        if not bus_ids:
            reviews = []
        else:
            placeholders_bus = ",".join(["%s"] * len(bus_ids))
            query_package = f"SELECT id FROM packages WHERE bus_id IN ({placeholders_bus})"
            cursor.execute(query_package, tuple(bus_ids))
            package_ids = [p["id"] for p in cursor.fetchall()]

            if not package_ids:
                reviews = []
            else:
                placeholders_pkg = ",".join(["%s"] * len(package_ids))
                query_review = f"SELECT * FROM reviews WHERE package_id IN ({placeholders_pkg}) ORDER BY created_at DESC"
                cursor.execute(query_review, tuple(package_ids))
                reviews = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "manage_reviews.html",
        reviews=reviews,
        user=owner,
        is_founder=(role == "founder"),
        is_master_admin=(role == "master_admin")
    )


@app.route('/approve_review/<int:review_id>', methods=['POST'])
def approve_review(review_id):
    conn = get_mysql_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE reviews SET approved = 1 WHERE id = %s", (review_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('manage_reviews'))


@app.route('/reject_review/<int:review_id>', methods=['POST'])
def reject_review(review_id):
    conn = get_mysql_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reviews WHERE id = %s", (review_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('manage_reviews'))


@app.route('/delete_review/<int:review_id>', methods=['POST'])
def delete_review(review_id):
    conn = get_mysql_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reviews WHERE id = %s", (review_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('manage_reviews'))


@app.route("/manage_packages")
def manage_packages():
    if "user_id" not in session:
        return redirect(url_for("owner_login"))

    owner_id = session["user_id"]

    conn_admin = get_mysql_connection()
    cur_admin = conn_admin.cursor(dictionary=True)
    cur_admin.execute("SELECT * FROM admins WHERE id = %s", (owner_id,))
    owner = cur_admin.fetchone()
    conn_admin.close()

    if not owner:
        flash("Admin not found.", "error")
        return redirect(url_for("owner_login"))

    role = owner["role"].lower()

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    if role in ["founder", "master_admin"]:
        cursor.execute("SELECT * FROM packages")
        packages = cursor.fetchall()
        cursor.execute("SELECT * FROM buses")
        buses = cursor.fetchall()
    else:
        cursor.execute("SELECT * FROM buses WHERE owner_id = %s", (owner_id,))
        buses = cursor.fetchall()
        bus_ids = [bus["id"] for bus in buses]

        if not bus_ids:
            packages = []
        else:
            placeholders = ",".join(["%s"] * len(bus_ids))
            query = f"SELECT * FROM packages WHERE bus_id IN ({placeholders})"
            cursor.execute(query, tuple(bus_ids))
            packages = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "manage_packages.html",
        packages=packages,
        buses=buses,
        user=owner,
        is_founder=(role == "founder"),
        is_master_admin=(role == "master_admin")
    )


@app.route("/add_package", methods=["POST"])
def add_package():
    if "user_id" not in session:
        return redirect(url_for("owner_login"))

    user_id = session["user_id"]
    data = request.form

    conn_admin = get_mysql_connection()
    cur_admin = conn_admin.cursor(dictionary=True)
    cur_admin.execute("SELECT * FROM admins WHERE id = %s", (user_id,))
    admin = cur_admin.fetchone()
    conn_admin.close()

    is_master_or_founder = admin and admin["role"].lower() in ("master_admin", "founder")

    title = data.get("title", "").strip()
    location = data.get("location", "").strip()
    duration = data.get("duration", "").strip()
    price = data.get("price", "").strip()
    inclusions = data.get("inclusions", "").strip()
    itinerary = data.get("itinerary", "").strip()
    hotel_info = data.get("hotel_info", "").strip()
    bus_id = data.get("bus_id")
    boardings = data.get("boardings", "").strip()
    start_date = data.get("start_date", "").strip()
    start_time = data.get("start_time", "").strip()

    try:
        start_datetime_obj = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
        start_datetime_str = start_datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        flash("Invalid start date/time format", "error")
        return redirect("/manage_packages")

    image_url = ""
    file = request.files.get("image_file")
    if file and file.filename != "":
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext in ["jpg", "jpeg", "png", "gif"]:
            filename = secure_filename(file.filename)
            upload_dir = os.path.join("static", "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            image_url = f"/static/uploads/{filename}"

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM buses WHERE id = %s", (bus_id,))
    bus = cursor.fetchone()
    if not bus:
        conn.close()
        flash("Invalid bus selected", "error")
        return redirect("/manage_packages")

    package_owner_id = bus["owner_id"]

    if not is_master_or_founder and package_owner_id != user_id:
        conn.close()
        flash("You do not own the selected bus.", "error")
        return redirect("/manage_packages")

    total_seats = bus["total_seats"]

    cursor.execute("""
        INSERT INTO packages
        (owner_id, title, location, duration, price, inclusions, itinerary, hotel_info, image_url, bus_id, boardings, start_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        package_owner_id, title, location, duration, price, inclusions,
        itinerary, hotel_info, image_url, bus_id, boardings, start_datetime_str
    ))
    package_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO seats (bus_id, package_id, total_seats, available_seats, travel_date)
        VALUES (%s, %s, %s, %s, %s)
    """, (bus_id, package_id, total_seats, total_seats, start_datetime_str))

    conn.commit()
    conn.close()

    flash("Package added successfully", "success")
    return redirect("/manage_packages")


@app.route("/update_package", methods=["POST"])
def update_package():
    if "user_id" not in session:
        return redirect(url_for("owner_login"))

    user_id = session["user_id"]
    data = request.form
    pkg_id = data.get("id")

    conn_admin = get_mysql_connection()
    cur_admin = conn_admin.cursor(dictionary=True)
    cur_admin.execute("SELECT * FROM admins WHERE id = %s", (user_id,))
    admin = cur_admin.fetchone()
    conn_admin.close()

    is_master_or_founder = admin and admin["role"].lower() in ("master_admin", "founder")

    title = data.get("title", "").strip()
    location = data.get("location", "").strip()
    duration = data.get("duration", "").strip()
    price = data.get("price", "").strip()
    inclusions = data.get("inclusions", "").strip()
    itinerary = data.get("itinerary", "").strip()
    hotel_info = data.get("hotel_info", "").strip()
    bus_id = data.get("bus_id")
    boardings = data.get("boardings", "").strip()
    start_date = data.get("start_date", "").strip()
    start_time = data.get("start_time", "").strip()

    try:
        start_datetime_obj = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
        start_datetime_str = start_datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        flash("Invalid start date/time format", "error")
        return redirect("/manage_packages")

    image_url = None
    file = request.files.get("image_file")
    if file and file.filename != "":
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext in ["jpg", "jpeg", "png", "gif"]:
            filename = secure_filename(file.filename)
            upload_dir = os.path.join("static", "uploads")
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, filename)
            file.save(file_path)
            image_url = f"/static/uploads/{filename}"

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM packages WHERE id = %s", (pkg_id,))
    existing_pkg = cursor.fetchone()
    if not existing_pkg:
        conn.close()
        flash("Package not found", "error")
        return redirect("/manage_packages")

    cursor.execute("SELECT * FROM buses WHERE id = %s", (bus_id,))
    bus = cursor.fetchone()
    if not bus:
        conn.close()
        flash("Invalid bus selected", "error")
        return redirect("/manage_packages")

    new_owner_id = bus["owner_id"]

    if not is_master_or_founder and new_owner_id != user_id:
        conn.close()
        flash("You do not own the selected bus.", "error")
        return redirect("/manage_packages")

    total_seats = bus["total_seats"]

    if image_url:
        cursor.execute("""
            UPDATE packages SET
            owner_id=%s, title=%s, location=%s, duration=%s, price=%s, inclusions=%s, itinerary=%s, hotel_info=%s, image_url=%s, bus_id=%s, boardings=%s, start_date=%s
            WHERE id=%s
        """, (
            new_owner_id, title, location, duration, price, inclusions, itinerary,
            hotel_info, image_url, bus_id, boardings, start_datetime_str, pkg_id
        ))
    else:
        cursor.execute("""
            UPDATE packages SET
            owner_id=%s, title=%s, location=%s, duration=%s, price=%s, inclusions=%s, itinerary=%s, hotel_info=%s, bus_id=%s, boardings=%s, start_date=%s
            WHERE id=%s
        """, (
            new_owner_id, title, location, duration, price, inclusions, itinerary,
            hotel_info, bus_id, boardings, start_datetime_str, pkg_id
        ))

    cursor.execute("SELECT * FROM seats WHERE package_id = %s", (pkg_id,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE seats
            SET bus_id=%s, total_seats=%s, available_seats=%s, travel_date=%s
            WHERE package_id=%s
        """, (bus_id, total_seats, total_seats, start_datetime_str, pkg_id))
    else:
        cursor.execute("""
            INSERT INTO seats (bus_id, package_id, total_seats, available_seats, travel_date)
            VALUES (%s, %s, %s, %s, %s)
        """, (bus_id, pkg_id, total_seats, total_seats, start_datetime_str))

    conn.commit()
    conn.close()

    flash("Package updated successfully", "success")
    return redirect("/manage_packages")


@app.route("/delete_package/<int:pkg_id>")
def delete_package(pkg_id):
    if "user_id" not in session:
        return redirect(url_for("owner_login"))

    owner_id = session["user_id"]

    conn_admin = get_mysql_connection()
    cursor_admin = conn_admin.cursor(dictionary=True)
    cursor_admin.execute("SELECT * FROM admins WHERE id = %s", (owner_id,))
    admin = cursor_admin.fetchone()
    cursor_admin.close()
    conn_admin.close()

    if not admin:
        flash("Admin not found", "error")
        return redirect(url_for("owner_login"))

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM packages WHERE id = %s", (pkg_id,))
    package = cursor.fetchone()

    if not package:
        cursor.close()
        conn.close()
        return "Package not found", 404

    is_master_or_founder = admin["role"].lower() in ("master_admin", "founder")
    owns_package = str(package["owner_id"]) == str(owner_id)

    if not is_master_or_founder and not owns_package:
        cursor.execute("SELECT * FROM buses WHERE id = %s", (package["bus_id"],))
        bus = cursor.fetchone()
        if not bus or str(bus["owner_id"]) != str(owner_id):
            cursor.close()
            conn.close()
            return "Unauthorized", 403

    # Delete related seats (not bookings)
    cursor.execute("DELETE FROM seats WHERE package_id = %s", (pkg_id,))
    cursor.execute("DELETE FROM packages WHERE id = %s", (pkg_id,))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Package deleted successfully", "success")
    return redirect("/manage_packages")



@app.route("/manage_buses")
def manage_buses():
    if "user_id" not in session:
        return redirect(url_for("owner_login"))

    owner_id = session["user_id"]

    conn_admin = get_mysql_connection()
    cursor_admin = conn_admin.cursor(dictionary=True)
    cursor_admin.execute("SELECT * FROM admins WHERE id = %s", (owner_id,))
    owner = cursor_admin.fetchone()
    cursor_admin.close()
    conn_admin.close()

    if not owner:
        session.pop("user_id", None)
        flash("Invalid session. Please login again.", "error")
        return redirect(url_for("owner_login"))

    role = owner["role"].strip().lower()
    is_founder = role in ("founder", "master_admin")

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    if is_founder:
        cursor.execute("SELECT * FROM buses")
    else:
        cursor.execute("SELECT * FROM buses WHERE owner_id = %s", (owner_id,))
    buses = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "manage_buses.html",
        buses=buses,
        user=owner,
        is_founder=is_founder
    )



@app.route("/add_bus", methods=["POST"])
def add_bus():
    if "user_id" not in session:
        return redirect(url_for("owner_login"))

    data = request.form
    amenities_str = ",".join(request.form.getlist("amenities"))

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        INSERT INTO buses (owner_id, bus_name, bus_type, total_seats, plate_number, amenities, driver_name, driver_contact)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        session["user_id"],
        data["bus_name"],
        data["bus_type"],
        data["total_seats"],
        data["plate_number"],
        amenities_str,
        data["driver_name"],
        data["driver_contact"]
    ))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Bus added successfully", "success")
    return redirect("/manage_buses")



@app.route("/update_bus", methods=["POST"])
def update_bus():
    if "user_id" not in session:
        return redirect(url_for("owner_login"))

    user_id = session["user_id"]
    data = request.form
    bus_id = data["bus_id"]
    amenities_str = ",".join(request.form.getlist("amenities"))

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM buses WHERE id = %s", (bus_id,))
    bus = cursor.fetchone()
    if not bus:
        cursor.close()
        conn.close()
        return "Bus not found", 404

    conn_admin = get_mysql_connection()
    cursor_admin = conn_admin.cursor(dictionary=True)
    cursor_admin.execute("SELECT * FROM admins WHERE id = %s", (user_id,))
    admin = cursor_admin.fetchone()
    cursor_admin.close()
    conn_admin.close()

    is_owner = str(bus["owner_id"]) == str(user_id)
    is_superuser = admin and admin["role"].lower() in ("master_admin", "founder")

    if not is_owner and not is_superuser:
        cursor.close()
        conn.close()
        return "Unauthorized", 403

    cursor.execute("""
        UPDATE buses
        SET bus_name = %s, bus_type = %s, total_seats = %s, plate_number = %s,
            amenities = %s, driver_name = %s, driver_contact = %s
        WHERE id = %s
    """, (
        data["bus_name"],
        data["bus_type"],
        data["total_seats"],
        data["plate_number"],
        amenities_str,
        data["driver_name"],
        data["driver_contact"],
        bus_id
    ))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Bus updated successfully", "success")
    return redirect("/manage_buses")



@app.route("/delete_bus/<int:bus_id>")
def delete_bus(bus_id):
    if "user_id" not in session:
        return redirect(url_for("owner_login"))

    user_id = session["user_id"]
    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT owner_id FROM buses WHERE id = %s", (bus_id,))
    bus = cursor.fetchone()

    if not bus:
        cursor.close()
        conn.close()
        flash("Bus not found", "error")
        return redirect("/manage_buses")

    bus_owner_id = bus["owner_id"]

    is_master = get_master_admin_id(user_id) is not None
    is_founder = get_founder_id(user_id) is not None

    if str(bus_owner_id) != str(user_id) and not is_master and not is_founder:
        cursor.close()
        conn.close()
        flash("You are not authorized to delete this bus", "error")
        return redirect("/manage_buses")

    # Set bus_id to NULL in related packages
    cursor.execute("UPDATE packages SET bus_id = NULL WHERE bus_id = %s", (bus_id,))

    # Delete bus
    cursor.execute("DELETE FROM buses WHERE id = %s", (bus_id,))

    conn.commit()
    cursor.close()
    conn.close()

    flash("Bus deleted successfully", "success")
    return redirect("/manage_buses")


@app.route("/owner_create", methods=["GET", "POST"])
def owner_create():
    if "user_id" not in session:
        return redirect(url_for("owner_login"))

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM admins WHERE id = %s", (session["user_id"],))
    admin = cursor.fetchone()

    if not admin or admin.get("role", "").strip().lower() not in ["founder", "master_admin"]:
        cursor.close()
        conn.close()
        abort(403)

    is_founder = admin["role"].strip().lower() in ["founder", "master_admin"]

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        contact = request.form.get("contact", "").strip()
        address = request.form.get("address", "").strip()

        if not full_name or not email or not contact or not address:
            flash("All fields are required.", "owner_error")
            cursor.close()
            conn.close()
            return redirect(url_for("owner_create"))

        if not session.get("owner_otp_verified_create"):
            flash("OTP verification is required before submission.", "owner_error")
            cursor.close()
            conn.close()
            return redirect(url_for("owner_create"))

        cursor.execute("SELECT * FROM admins WHERE email = %s", (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            flash("Email already exists.", "owner_error")
            cursor.close()
            conn.close()
            return redirect(url_for("owner_create"))

        default_password = "1234"
        password_hash = generate_password_hash(default_password)

        try:
            cursor.execute("""
                INSERT INTO admins (full_name, email, contact, address, password, role)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (full_name, email, contact, address, password_hash, "owner"))
            conn.commit()

            flash("✅ Owner created successfully.", "owner_success")

            session.pop("owner_create_otp", None)
            session.pop("owner_create_email", None)
            session.pop("owner_otp_verified_create", None)
            session.pop("owner_otp_expiry_create", None)

        except Exception as e:
            print("Owner creation error:", e)
            flash("Owner created, but an error occurred.", "owner_error")

    cursor.execute("SELECT id, full_name, email, contact FROM admins WHERE role = 'owner'")
    admins = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template(
        "owner_create.html",
        user=admin,
        admins=admins,
        is_founder=is_founder
    )


@app.route('/delete_owner/<int:owner_id>', methods=['POST'])
def delete_owner(owner_id):
    if "user_id" not in session:
        return redirect(url_for("owner_login"))

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM admins WHERE id = %s", (session["user_id"],))
    admin = cursor.fetchone()

    if not admin or admin.get("role") not in ["founder", "master_admin"]:
        cursor.close()
        conn.close()
        abort(403)

    # Delete owner's buses and related packages
    travel_conn = get_mysql_connection()
    travel_cursor = travel_conn.cursor(dictionary=True)

    travel_cursor.execute("SELECT id FROM buses WHERE owner_id = %s", (owner_id,))
    buses = travel_cursor.fetchall()
    for bus in buses:
        bus_id = bus["id"]
        travel_cursor.execute("UPDATE packages SET bus_id = NULL WHERE bus_id = %s", (bus_id,))
        travel_cursor.execute("DELETE FROM buses WHERE id = %s", (bus_id,))
    travel_conn.commit()

    travel_cursor.close()
    travel_conn.close()

    cursor.execute("DELETE FROM admins WHERE id = %s AND role = 'owner'", (owner_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash("Owner and their buses deleted successfully.", "success")
    return redirect(url_for('owner_create'))


@app.route("/owner_settings", methods=["GET", "POST"])
def owner_settings():
    if "user_id" not in session:
        return redirect(url_for("owner_login"))

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        if full_name:
            cursor.execute("UPDATE admins SET full_name = %s WHERE id = %s", (full_name, session["user_id"]))
            conn.commit()
            flash("✅ Name updated successfully!", "success")
        cursor.close()
        conn.close()
        return redirect(url_for("owner_settings"))

    cursor.execute("SELECT * FROM admins WHERE id = %s", (session["user_id"],))
    user_row = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user_row:
        flash("User not found.", "error")
        return redirect(url_for("owner_login"))

    return render_template("owner_settings.html", user=user_row)


@app.route('/change-password', methods=['POST'])
def change_password():
    user_id = session.get("user_id")
    user_meta = session.get("user")

    if not user_id or not user_meta:
        flash("You must be logged in to change password.", "error")
        return redirect(url_for("owner_login"))

    old_password = request.form.get("old_password", "").strip()
    new_password = request.form.get("new_password", "").strip()
    confirm_password = request.form.get("confirm_password", "").strip()

    if not old_password or not new_password or not confirm_password:
        flash("All password fields are required.", "error")
        return redirect(url_for("owner_settings"))

    if new_password != confirm_password:
        flash("New password and confirm password do not match.", "error")
        return redirect(url_for("owner_settings"))

    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT password FROM admins WHERE id = %s", (user_id,))
        row = cursor.fetchone()

        if not row:
            flash("User not found.", "error")
            cursor.close()
            conn.close()
            return redirect(url_for("owner_settings"))

        stored_hash = row["password"]
        if not check_password_hash(stored_hash, old_password):
            flash("Current password is incorrect.", "error")
            cursor.close()
            conn.close()
            return redirect(url_for("owner_settings"))

        new_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE admins SET password = %s WHERE id = %s", (new_hash, user_id))
        conn.commit()

        flash("Password changed successfully.", "success")

    except Exception as e:
        print("Error changing password:", e)
        flash("An error occurred. Please try again.", "error")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("owner_settings"))


@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get("email")
    mode = data.get("mode")

    if mode != "change":
        return jsonify({"success": False, "message": "Invalid mode."})

    if not email:
        return jsonify({"success": False, "message": "Email is required."})

    otp = generate_random_otp()
    session["change_otp"] = otp
    session["change_email"] = email

    success = send_otp_to_email(email, otp)
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"success": False, "message": "Failed to send OTP."})


@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    otp = data.get("otp")
    mode = data.get("mode")

    if mode != "change":
        return jsonify({"verified": False, "message": "Invalid mode."})

    if not otp:
        return jsonify({"verified": False, "message": "OTP is required."})

    expected_otp = session.get("change_otp")

    if expected_otp and otp == expected_otp:
        session.pop("change_otp", None)
        return jsonify({"verified": True})

    return jsonify({"verified": False, "message": "Incorrect OTP."})


@app.route('/change-ownerinfo', methods=['POST'])
def change_ownerinfo():
    user_id = session.get("user_id")
    if not user_id:
        flash("You must be logged in to change info.", "error")
        return redirect(url_for("owner_login"))

    new_email = request.form.get("email", "").strip()
    new_contact = request.form.get("contact", "").strip()

    if new_email:
        saved_email = session.get("change_email")
        if saved_email != new_email:
            flash("Email OTP not verified or does not match the entered email.", "error")
            return redirect(url_for("owner_settings"))

    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)

        if new_email:
            cursor.execute("UPDATE admins SET email = %s WHERE id = %s", (new_email, user_id))
            session.pop("change_email", None)

        if new_contact:
            cursor.execute("UPDATE admins SET contact = %s WHERE id = %s", (new_contact, user_id))

        conn.commit()
        flash("Information updated successfully.", "success")

    except Exception as e:
        print("Error updating info:", e)
        flash("An error occurred while updating information.", "error")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("owner_settings"))


# misclaneous ====misclaneous=======misclaneous=============misclaneous=============misclaneous===================misclaneous=============misclaneous================misclaneous=================misclaneous=

@app.route('/view')
def view_all():
    user = get_user()
    role = user.get("role", "").strip().lower() if user else None

    conn = get_mysql_connection()
    cursor = conn.cursor(dictionary=True)

    data = {}

    # Fetch packages (available for all roles)
    cursor.execute("SELECT * FROM packages")
    data["packages"] = cursor.fetchall()

    # For master admin and founder, include all additional data
    if role in ["master_admin", "founder"]:
        cursor.execute("SELECT * FROM users")
        data["users"] = cursor.fetchall()

        cursor.execute("SELECT * FROM buses")
        data["buses"] = cursor.fetchall()

        cursor.execute("SELECT * FROM seats")
        data["seats"] = cursor.fetchall()

        cursor.execute("SELECT * FROM bookings")
        data["bookings"] = cursor.fetchall()

        cursor.execute("SELECT * FROM reviews")
        data["reviews"] = cursor.fetchall()

    # Only founder can view admins
    if role == "founder":
        cursor.execute("SELECT * FROM admins")
        data["admins"] = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('view.html', data=data)


@app.route("/logout")
def logout():
    user = session.get("user")
    role = user.get("role") if user else None  # safe fallback

    # Remove user session data
    session.pop("user", None)
    session.pop("user_id", None)

    # Redirect based on role
    if role in ("owner", "master_admin", "founder"):
        return redirect(url_for("owner_login"))

    # Detect if request is from mobile device
    user_agent = request.headers.get('User-Agent', '').lower()
    is_mobile = "mobi" in user_agent or "android" in user_agent or "iphone" in user_agent

    # Redirect mobile users to mobile login/home
    if is_mobile:
        return redirect("/mobile")

    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)