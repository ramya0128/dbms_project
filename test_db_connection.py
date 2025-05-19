from flask import Flask
from config import Config
from db import get_db, init_db

app = Flask(__name__)
app.config.from_object(Config)
init_db(app)

with app.app_context():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print("✅ MySQL version:", version)
    except Exception as e:
        print("❌ Error connecting to DB:", e)
    finally:
        try:
            cursor.close()
            
        except:
            pass
