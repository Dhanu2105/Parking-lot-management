import mysql.connector
from datetime import datetime
from flask import Flask, request, render_template, redirect, session
from flask import flash
app = Flask(__name__)
app.secret_key = "secret123"

# DB connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="your password",
    database="parking_system",
    port=3306   # match your MySQL port
)

@app.route('/')
def home():
    return render_template('index.html')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    phone = request.form['phone']
    password = request.form['password']

    cursor = db.cursor(dictionary=True)

    cursor.execute(
        "SELECT * FROM employee WHERE phone=%s AND password=%s",
        (phone, password)
    )
    emp = cursor.fetchone()

    if not emp:
        return render_template('login.html', error="Invalid phone or password")

    session['employee_id'] = emp['employee_id']
    return redirect('/')

@app.route('/entry', methods=['GET', 'POST'])
def entry():
    # 🔒 Check login
    if 'employee_id' not in session:
        return redirect('/login')

    # 📄 Show form
    if request.method == 'GET':
        return render_template('entry.html')

    vehicle_number = request.form['vehicle_number']
    vehicle_type = request.form['vehicle_type']
    employee_id = session['employee_id']

    cursor = db.cursor()

    # 🔍 Check if vehicle already exists
    cursor.execute(
        "SELECT vehicle_id FROM vehicle WHERE vehicle_number=%s",
        (vehicle_number,)
    )
    existing = cursor.fetchone()

    if existing:
        vehicle_id = existing[0]
    else:
        # ➕ Insert new vehicle
        cursor.execute(
            "INSERT INTO vehicle (vehicle_number, vehicle_type) VALUES (%s, %s)",
            (vehicle_number, vehicle_type)
        )
        vehicle_id = cursor.lastrowid

    # 🚫 Check if already parked
    cursor.execute("""
        SELECT * FROM parking_record 
        WHERE vehicle_id = %s AND exit_time IS NULL
    """, (vehicle_id,))

    already_parked = cursor.fetchone()

    if already_parked:
        return "⚠️ Vehicle already parked!"

    # 🔍 Find free slot
    cursor.execute(
    "SELECT slot_id FROM parking_slot WHERE status='Free' AND slot_type=%s LIMIT 1",
    (vehicle_type,)
)
    slot = cursor.fetchone()

    if not slot:
        return "❌ No parking slots available!"

    slot_id = slot[0]

    # 🔄 Update slot status
    cursor.execute(
        "UPDATE parking_slot SET status='Occupied' WHERE slot_id=%s",
        (slot_id,)
    )

    # 📝 Insert parking record
    cursor.execute("""
        INSERT INTO parking_record (vehicle_id, slot_id, employee_id, entry_time)
        VALUES (%s, %s, %s, %s)
    """, (vehicle_id, slot_id, employee_id, datetime.now()))

    db.commit()

    # 🔁 Redirect to home
    return redirect('/')

@app.route('/exit', methods=['GET', 'POST'])
def exit():
    if 'employee_id' not in session:
        return redirect('/login')

    if request.method == 'GET':
        return render_template('exit.html')

    vehicle_number = request.form['vehicle_number']
    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT * FROM vehicle WHERE vehicle_number=%s", (vehicle_number,))
    v = cursor.fetchone()

    if not v:
        flash("Vehicle not found", "danger")
        return redirect('/')

    cursor.execute("""
        SELECT * FROM parking_record 
        WHERE vehicle_id=%s AND exit_time IS NULL
    """, (v['vehicle_id'],))
    r = cursor.fetchone()

    if not r:
        flash("Vehicle already exited or not parked", "warning")
        return redirect('/')
        

    # ✅ NOW INSIDE FUNCTION
    entry_time = r['entry_time']
    hours = int((datetime.now() - entry_time).total_seconds() / 3600) + 1

    vehicle_type = v['vehicle_type']

    # Pricing logic
    if vehicle_type == "Bike":
        first_hour = 10
        extra_per_hour = 5
    elif vehicle_type == "Car":
        first_hour = 20
        extra_per_hour = 10
    else:
        first_hour = 15
        extra_per_hour = 7

    # Fee calculation
    if hours <= 1:
        fee = first_hour
    else:
        fee = first_hour + (hours - 1) * extra_per_hour

    cursor.execute(
        "UPDATE parking_record SET exit_time=NOW(), fee=%s WHERE record_id=%s",
        (fee, r['record_id'])
    )

    cursor.execute(
        "UPDATE parking_slot SET status='Free' WHERE slot_id=%s",
        (r['slot_id'],)
    )

    db.commit()
    flash(f"Vehicle Exited. Fee: ₹{fee}", "success")
    return redirect('/')
    
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    app.run(debug=True)