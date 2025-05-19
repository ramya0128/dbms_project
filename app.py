from flask import Flask, request, jsonify, send_from_directory, render_template, redirect, url_for
from config import Config
from db import init_db, get_db
from flask_cors import CORS
from routes.patient_routes import patient_bp
import os
import logging
from MySQLdb.cursors import DictCursor
import traceback

app = Flask(__name__, static_folder='frontend', static_url_path='', template_folder='frontend')

CORS(app)
app.config.from_object(Config)

# Initialize DB
init_db(app)

# Register blueprints
app.register_blueprint(patient_bp)

# Setup logging
logging.basicConfig(level=logging.INFO)

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:path>')
def serve_static_file(path):
    file_path = os.path.join(app.static_folder, path)
    if os.path.exists(file_path):
        return send_from_directory(app.static_folder, path)
    return "File not found", 404

@app.route('/register')
def show_register():
    conn, cursor = None, None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT HID, HNAME FROM hospital")
        hospitals = cursor.fetchall()
        return render_template("register.html", hospitals=hospitals)
    except Exception as e:
        app.logger.error(f"❌ Error loading register form: {e}")
        return "Error loading form", 500
    finally:
        if cursor:
            try: cursor.close()
            except: pass

@app.route('/submit', methods=['POST'])
def submit_data():
    data = request.form
    conn, cursor = None, None
    try:
        conn = get_db()
        cursor = conn.cursor()

        pid = data['pid']
        did = data.get('did')
        dcontact = data.get('DCONTACT')
        preferred_hospital = data.get('preferredHospital')

        # Validate hospital exists if provided
        if preferred_hospital:
            cursor.execute("SELECT HID FROM hospital WHERE HID = %s", (preferred_hospital,))
            if not cursor.fetchone():
                return jsonify({"error": "Invalid Hospital ID - Hospital doesn't exist"}), 400

        # Validate doctor exists if provided
        if did:
            cursor.execute("SELECT DID FROM doctor WHERE DID = %s", (did,))
            if not cursor.fetchone():
                return jsonify({"error": "Invalid Doctor ID - Doctor doesn't exist"}), 400

        # Insert patient basic information
        cursor.execute("""
            INSERT INTO patient (PID, fname, lname, age, dob, gender, address, contact,email)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s,%s)
        """, (
            pid, data.get('fname'), data.get('lname'), data.get('age'),
            data.get('dob'), data.get('gender'), data.get('address'), data.get('contact'),data.get('email')
        ))

        # Insert lifestyle factors
        cursor.execute("""
            INSERT INTO lifestyle_factor (PID, smoking_status, alcohol_consumption, drug_intake, physical_activity, diet_preferences)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            pid,
            data.get('smoking_status') == 'on',
            data.get('alcohol_consumption') == 'on',
            data.get('drug_intake') == 'on',
            data.get('physical_activity'),
            data.get('diet_preferences')
        ))

        # Insert health information
        cursor.execute("""
            INSERT INTO information (PID, bodyweight, bmi, bloodtype,surgery_date,heart_block_percentage,heart_attack_type,prevattack_history,cholestrol,blood_pressure,heartrate,diabetes)
            VALUES (%s, %s, %s, %s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            pid,
            data.get('bodyweight'),
            data.get('bmi'),
            data.get('bloodtype'),
            data.get('surgery_date'),
            data.get('heart_block_percentage'),
            data.get('heart_attack_type'),
            data.get('prevattack_history'),
            data.get('cholestrol'),
            data.get('blood_pressure'),
            data.get('heartrate'),
            data.get('diabetes'),
            
        ))

        # Insert treatment details
        cursor.execute("""
            INSERT INTO treatments (PID, treatment_plan, monitoring_data, surgery_details)
            VALUES (%s, %s, %s, %s)
        """, (
            pid,
            data.get('treatment_plan'),
            data.get('monitoring_data'),
            data.get('surgery_details')
        ))

        # Insert patient history
        cursor.execute("""
            INSERT INTO patienthistory (PID,  medicalhistory, familyhistory)
            VALUES (%s, %s, %s)
        """, (
            pid,
        
            data.get('medical_history'),
            data.get('family_history')
        ))

        # Insert emergency details - updated to match form field names
        cursor.execute("""
            INSERT INTO emergency_details (
                PID, 
                preferredHospital, 
                EMERGENCY_CONTACT, 
                DID, 
                DCONTACT, 
                HOSNO, 
                HNAME,
                ename
            ) VALUES (%s, %s, %s, %s, %s, %s, %s,%s)
        """, (
            pid,
            preferred_hospital,  # Using the validated hospital ID
            data.get('emergency_contact'),
            did,
            dcontact,
            data.get('HOSNO'),   # Note: uppercase to match form
            data.get('HNAME') ,
            data.get('ename')      # Note: uppercase to match form
        ))

        conn.commit()
        app.logger.info(f"✅ Data inserted for PID: {pid}")
        return redirect(url_for('all_tables'))

    except Exception as e:
        app.logger.error(f"❌ Insert error: {e}")
        if conn:
            conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            try: cursor.close()
            except: pass
@app.route('/get_patients')
def get_patients():
    conn, cursor = None, None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM patient")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        patients = [dict(zip(columns, row)) for row in rows]
        return jsonify(patients)
    except Exception as e:
        app.logger.error(f"❌ Error fetching patient data: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            try: cursor.close()
            except: pass


@app.route('/delete', methods=['POST'])
def delete_patient():
    pid = request.form.get('pid')
    conn, cursor = None, None

    try:
        conn = get_db()
        cursor = conn.cursor()

        tables = ['lifestyle_factor', 'emergency_details', 'information', 'treatments', 'patienthistory']
        for table in tables:
            cursor.execute(f"DELETE FROM {table} WHERE PID = %s", (pid,))

        cursor.execute("DELETE FROM patient WHERE PID = %s", (pid,))
        conn.commit()

        app.logger.info(f"🗑️ Deleted patient with PID: {pid}")
        return redirect('/delete.html?deleted=true')

    except Exception as e:
        app.logger.error(f"❌ Error deleting patient: {e}")
        return f"<h3>Error deleting patient: {str(e)}</h3>", 500
    finally:
        if cursor:
            try: cursor.close()
            except: pass

@app.route('/update', methods=['POST'])
def update_patient():
    data = request.form
    conn, cursor = None, None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE patient SET 
                fname = %s,
                lname = %s,
                age = %s,
                contact = %s,
                address = %s
            WHERE PID = %s
        """, (
            data.get('fname'),
            data.get('lname'),
            data.get('age'),
            data.get('contact'),
            data.get('address'),
            data.get('pid')
        ))
        conn.commit()
        app.logger.info(f"✅ Patient updated: PID {data.get('pid')}")
        return '''
            <script>
              alert("Patient updated successfully!");
              window.location.href = "/update.html";
            </script>
        '''
    except Exception as e:
        app.logger.error(f"❌ Update error: {e}")
        if conn:
            conn.rollback()
        return f"<h3>Error updating patient: {str(e)}</h3>", 500
    finally:
        if cursor:
            try: cursor.close()
            except: pass

@app.route('/all_tables')
def all_tables():
    conn, cursor = None, None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES")
        table_names = [row[0] for row in cursor.fetchall()]

        tables = []
        for table in table_names:
            cursor.execute(f"SELECT * FROM `{table}`")
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            formatted_rows = [dict(zip(columns, row)) for row in rows]
            tables.append({"name": table, "data": formatted_rows})

        return jsonify(tables)

    except Exception as e:
        app.logger.error(f"❌ Error fetching tables: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            try: cursor.close()
            except: pass

import traceback

@app.route("/emergency-records")
def emergency_records():
    try:
        conn = get_db()
        with conn.cursor(DictCursor) as cursor:
            query = """
                SELECT 
                    P.PID,
                    P.fname AS first_name,
                    P.lname AS last_name,
                    P.age,
                    P.gender,
                    I.bodyweight,
                    I.bmi,
                    I.bloodtype,
                    PH.medicalhistory,
                    PH.familyhistory,
                    T.treatment_plan,
                    T.monitoring_data,
                    T.surgery_details
                FROM PATIENT P
                JOIN INFORMATION I ON P.PID = I.PID
                JOIN PATIENTHISTORY PH ON P.PID = PH.PID
                JOIN TREATMENTS T ON P.PID = T.PID;
            """
            cursor.execute(query)
            records = cursor.fetchall()

        app.logger.info(f"✅ Fetched full patient emergency records: {records}")
        return render_template("emergency_records.html", records=records)

    except Exception as e:
        tb = traceback.format_exc()
        app.logger.error(f"❌ Exception in /emergency-records: {e}\nTraceback:\n{tb}")
        return f"<h3>Error fetching emergency records: {str(e)}</h3>", 500


@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({"success": False, "message": "Username and password required"})

        conn = get_db()
        cursor = conn.cursor()

        query = "SELECT * FROM users WHERE username = %s AND password_hash = %s"
        cursor.execute(query, (username, password))
        user = cursor.fetchone()

        if user:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Invalid credentials"})

    except Exception as e:
        print("Error during login:", e)
        return jsonify({"success": False, "message": f"Server error: {str(e)}"})
    finally:
        try: cursor.close()
        except: pass

if __name__ == '__main__':
    print("🚀 Starting Flask app...")
    try:
        app.run(debug=True)
    except Exception as e:
        print(f"❌ Error starting Flask app: {e}")