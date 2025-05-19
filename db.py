from flask_mysqldb import MySQL

mysql = MySQL()

def init_db(app):
    mysql.init_app(app)

def get_db():
    conn = mysql.connection
    conn.autocommit(False)  # Force manual commit
    return conn
