from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response, send_file
from models import User, Parcel, Report, Activity, init_db, seed_default_users, seed_default_parcels
import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from datetime import datetime

DB = "ctms.db"
app = Flask(__name__)
app.secret_key = "supersecret"   # needed for sessions
# -------------------- WELCOME PAGE --------------------
@app.route("/")
def home():
    return redirect(url_for("welcome"))

@app.route("/welcome")
def welcome():
    # If already logged in, skip welcome and go straight to the user’s dashboard
    if "role" in session:
        return redirect(url_for(session["role"].lower()))
    return render_template("welcome.html")


# -------------------- AUTH ROUTES --------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    # If already logged in, don’t show login again
    if "role" in session:
        return redirect(url_for(session["role"].lower()))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")

        # authenticate returns (user, error)
        user, error = User.authenticate(username, password, role)
        if user:
            session["username"] = user.username
            session["role"] = user.role
            flash(f"✅ Welcome back, {user.username}", "success")
            return redirect(url_for(user.role.lower()))
        else:
            flash(error, "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # Only customers can register (role is fixed inside the form/logic)
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("❌ Please fill in all fields", "error")
            return render_template("register.html")

        User.register(username, password)
        Activity.log(f"New customer registered: {username}")
        flash("✅ Registration successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# -------------------- DASHBOARDS --------------------
@app.route("/customer", methods=["GET", "POST"])
def customer():
    if session.get("role") != "Customer":
        flash("❌ Please login as Customer", "error")
        return redirect(url_for("login"))

    parcels = Parcel.get_by_user(session["username"])
    
    # Calculate user-specific parcel counts
    pending_count = sum(1 for p in parcels if p['status'] == 'Received')
    delivered_count = sum(1 for p in parcels if p['status'] == 'Delivered')
    in_transit_count = sum(1 for p in parcels if p['status'] == 'In Transit')
    
    return render_template("customer.html", 
                         username=session["username"], 
                         parcels=parcels,
                         pending_count=pending_count,
                         delivered_count=delivered_count,
                         in_transit_count=in_transit_count)

# Shipments tab
@app.route("/customer/my shipments")
def view_myshipments():
    if session.get("role") != "Customer":
        flash("❌ Please login as Customer", "error")
        return redirect(url_for("login"))

    parcels = Parcel.get_by_user(session["username"])
    return render_template("customer_myshipments.html", parcels=parcels)

# Tracking tab
@app.route("/customer/track parcel", methods=["GET", "POST"])
def view_trackparcel():
    if session.get("role") != "Customer":
        flash("❌ Please login as Customer", "error")
        return redirect(url_for("login"))
    
    tracked = None
    
    if request.method == "POST":
        tn = request.form.get("tracking_number", "").strip()
        if tn:
            tracked = Parcel.get_by_tracking(tn)
            if not tracked:
                flash("❌ Tracking number not found", "error")

    return render_template(
        "customer_trackparcel.html",
        username=session["username"],
        tracked=tracked
    )

@app.route("/employee", methods=["GET", "POST"])
def employee():
    if session.get("role") != "Employee":
        flash("❌ Please login as Employee", "error")
        return redirect(url_for("login"))

    # Get all parcels for employee dashboard stats
    parcels = Parcel.get_all()
    total_parcels = len(parcels)
    in_transit_count = sum(1 for p in parcels if p['status'] == 'In Transit')
    delivered_count = sum(1 for p in parcels if p['status'] == 'Delivered')

    return render_template("employee.html", 
                         username=session["username"],
                         total_parcels=total_parcels,
                         in_transit_count=in_transit_count,
                         delivered_count=delivered_count)

# Add New Parcel tab
@app.route("/employee/Add New Parcel", methods=["GET", "POST"])
def view_newparcel():
    if session.get("role") != "Employee":
        flash("❌ Please login as Employee", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        form = request.form
        if form.get("action") == "add":
            tn = form.get("tracking_number", "").strip()
            sender = form.get("sender", "").strip()
            receiver = form.get("receiver", "").strip()
            location = form.get("location", "").strip()
            date_sent = form.get("date_sent", "").strip()
            cost_of_items = form.get("cost_of_items", 0)
            weight = form.get("weight", 0)
            description = form.get("description", "").strip()
            parcel_price = form.get("parcel_price", 0)

            if not tn or not sender or not receiver:
                flash("❌ Tracking number, sender, and receiver are required", "error")
            else:
                Parcel(
                    tn, sender, receiver,
                    location=location,
                    date_sent=date_sent,
                    cost_of_items=cost_of_items,
                    weight=weight,
                    description=description,
                    parcel_price=parcel_price
                ).save()
                Activity.log(f"Parcel {tn} added by {session['username']}")
                flash("✅ Parcel added successfully!", "success")

    # Get customers for the sender dropdown
    customers_raw = User.get_all_by_role("Customer")
    customers = [{"username": row["username"]} for row in customers_raw]
    
    # Return the template for both GET and POST requests
    return render_template("employee_newparcel.html", username=session["username"], customers=customers)


# Today's Deliveries tab
@app.route("/employee/deliveries")
def view_deliveries():
    if session.get("role") != "Employee":
        flash("❌ Please login as Employee", "error")
        return redirect(url_for("login"))
    
    # Get today's deliveries (parcels with status "Delivered" or "Out for Delivery")
    parcels = Parcel.get_all()
    todays_deliveries = [p for p in parcels if p['status'] in ['Delivered', 'Out for Delivery']]
    
    return render_template("employee_deliveries.html", 
                         username=session["username"], 
                         deliveries=todays_deliveries)

# Updates & Parcels tab
@app.route("/employee/Updates & Parcels", methods=["GET", "POST"])
def view_updates():
    if session.get("role") != "Employee":
        flash("❌ Please login as Employee", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        form = request.form
        if form.get("action") == "add":
            tn = form.get("tracking_number", "").strip()
            sender = form.get("sender", "").strip()
            receiver = form.get("receiver", "").strip()
            location = form.get("location", "").strip()
            date_sent = form.get("date_sent", "").strip()
            cost_of_items = form.get("cost_of_items", 0)
            weight = form.get("weight", 0)
            description = form.get("description", "").strip()
            parcel_price = form.get("parcel_price", 0)

            if not tn or not sender or not receiver:
                flash("❌ Tracking number, sender, and receiver are required", "error")
                
        elif form.get("action") == "update":
            tn = form.get("tracking_number", "").strip()
            status = form.get("status", "").strip()
            if not tn or not status:
                flash("❌ Tracking number and status are required", "error")
            else:
                Parcel.update_status(tn, status)
                Activity.log(f"Parcel {tn} status updated to {status}")
                flash("✅ Parcel status updated!", "success")

    # Fetch parcels and customers for dropdown
    parcels = Parcel.get_all()
    with Database() as cur:
        cur.execute("SELECT username FROM users WHERE role='Customer'")
        customers_raw = cur.fetchall()
    customers = [{"username": row["username"]} for row in customers_raw]

    return render_template("employee_updates.html", 
                       username=session["username"], 
                       parcels=parcels, 
                       customers=customers)
                           
@app.route("/manager")
def manager():
    if session.get("role") != "Manager":
        flash("❌ Please login as Manager", "error")
        return redirect(url_for("login"))

    parcels = Parcel.get_all()
    status_counts = Report.parcel_status_counts()
    user_counts = Report.total_users()
    activities = Activity.recent(5)

    return render_template(
        "manager.html",
        username=session["username"],
        parcels=parcels,
        status_counts=status_counts,
        user_counts=user_counts,
        activities=activities
    )
# Customers tab
@app.route("/manager/customers")
def view_customers():
    if session.get("role") != "Manager":
        flash("❌ Please login as Manager", "error")
        return redirect(url_for("login"))

    customers = User.get_all_by_role("Customer")
    return render_template("manager_customers.html", customers=customers)

# Shipments tab
@app.route("/manager/shipments")
def view_shipments():
    if session.get("role") != "Manager":
        flash("❌ Please login as Manager", "error")
        return redirect(url_for("login"))

    parcels = Parcel.get_all()
    return render_template("manager_shipments.html", parcels=parcels)

# Employees tab
@app.route("/manager/employees")
def view_employees():
    if session.get("role") != "Manager":
        flash("❌ Please login as Manager", "error")
        return redirect(url_for("login"))

    employees = User.get_all_by_role("Employee")
    return render_template("manager_employees.html", employees=employees)

# Reports tab
@app.route("/manager/reports")
def manager_reports():
    if session.get("role") != "Manager":
        flash("❌ Unauthorized access", "error")
        return redirect(url_for("login"))

    # get data from DB
    status_counts = Report.parcel_status_counts()
    user_counts = Report.total_users()
    parcels = Parcel.get_all()

    return render_template(
        "manager_reports.html",
        status_counts=status_counts,
        user_counts=user_counts,
        parcels=parcels
    )
@app.route("/manager/reports/pdf")
def manager_reports_pdf():
    if "username" not in session or session.get("role") != "Manager":
        flash("❌ Unauthorized access", "error")
        return redirect(url_for("login"))

    manager_name = session["username"]

    # Fetch data
    status_counts = Report.parcel_status_counts()
    user_counts = Report.total_users()
    parcels = Parcel.get_all()

    # Create PDF in memory
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # --- HEADER with logo ---
    logo_path = os.path.join(app.static_folder, "logo.png")
    if os.path.exists(logo_path):
        from reportlab.platypus import Image
        img = Image(logo_path, 1.2*inch, 1.2*inch)
        elements.append(img)

    elements.append(Paragraph("<b>CTS Courier Management System</b>", styles['Title']))
    elements.append(Paragraph("📑 Manager Report", styles['Heading2']))
    elements.append(Paragraph(f"👤 Report generated by: <b>{manager_name}</b>", styles['Normal']))
    elements.append(Spacer(1, 12))

    # User counts
    elements.append(Paragraph("👥 User Role Summary:", styles['Heading2']))
    for role, count in user_counts.items():
        elements.append(Paragraph(f"{role}: {count}", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Parcel status
    elements.append(Paragraph("📦 Parcel Status Summary:", styles['Heading2']))
    for status, count in status_counts.items():
        elements.append(Paragraph(f"{status}: {count}", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Parcel table
    elements.append(Paragraph("📋 Parcel Details:", styles['Heading2']))
    data = [["Tracking #", "Sender", "Receiver", "Status", "Last Update",
             "Location", "Date Sent", "Cost of Items", "Weight (kg)", "Description", "Parcel Price"]]

    for p in parcels:
        data.append([
            p["tracking_number"],
            p["sender"],
            p["receiver"],
            p["status"],
            p["last_update"],
            p.get("location", "-"),
            p.get("date_sent", "-"),
            p.get("cost_of_items", "-"),   # ✅ FIXED
            p.get("weight", "-"),
            p.get("description", "-"),
            p.get("parcel_price", "-")
        ])

    table = Table(data, repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#16A34A")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
    ]))

    # --- Scaling to fit A4 ---
    from reportlab.pdfgen import canvas
    temp_canvas = canvas.Canvas(None, pagesize=A4)
    table_width, _ = table.wrapOn(temp_canvas, 0, 0)

    page_width, page_height = A4
    max_width = page_width - 40

    if table_width and table_width > max_width:
        scale_factor = max_width / table_width
        table._argW = [w * scale_factor for w in table._argW]

    elements.append(table)

    # --- FOOTER with generated date ---
    def footer(canvas, doc):
        canvas.saveState()
        footer_text = f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} • CTS Courier"
        canvas.setFont('Helvetica-Oblique', 8)
        canvas.drawString(inch, 0.5*inch, footer_text)
        canvas.restoreState()

    doc.build(elements, onFirstPage=footer, onLaterPages=footer)

    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="manager_report.pdf", mimetype="application/pdf")
# -------------------- MAIN --------------------
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False) 