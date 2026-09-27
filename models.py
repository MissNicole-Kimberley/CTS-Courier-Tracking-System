import sqlite3
from datetime import datetime

DB = "ctms.db"
Database = "ctms.db"

# ----- DATABASE CONTEXT MANAGER -----
class Database:
    """Handles all DB connections safely"""
    def __enter__(self):
        self.conn = sqlite3.connect(DB)
        self.conn.row_factory = sqlite3.Row
        return self.conn.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.commit()
        self.conn.close()

# ----- MODELS -----
class User:
    def __init__(self, username, password, role):
        self.username = username
        self.password = password
        self.role = role

    @staticmethod
    def authenticate(username, password, role):
        with Database() as cur:
            cur.execute("SELECT * FROM users WHERE username=? AND password=? AND role=?", (username, password, role))
            row = cur.fetchone()
        if row:
            return User(row["username"], row["password"], row["role"]), None
        else:
            with Database() as cur:
                cur.execute("SELECT * FROM users WHERE username=?", (username,))
                u = cur.fetchone()
                if not u:
                    return None, "❌ Username not found"
                elif u["password"] != password:
                    return None, "❌ Wrong password"
                elif u["role"] != role:
                    return None, "❌ Wrong role selected"
            return None, "❌ Invalid credentials"

    @staticmethod
    def register(username, password):
        with Database() as cur:
            cur.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", (username, password, "Customer"))

    @staticmethod
    def get_all_by_role(role):
        with Database() as cur:
            cur.execute("SELECT * FROM users WHERE role=?", (role,))
            return cur.fetchall()

class Parcel:
    def __init__(self, tracking_number, sender, receiver, status="Received", location="", date_sent=None, cost_of_items=0, weight=0, description="", parcel_price=0):
        self.tracking_number = tracking_number
        self.sender = sender
        self.receiver = receiver
        self.status = status
        self.location = location
        self.date_sent = date_sent or datetime.now().strftime("%Y-%m-%d")
        self.cost_of_items = cost_of_items
        self.weight = weight
        self.description = description
        self.parcel_price = parcel_price
        self.last_update = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def save(self):
        with Database() as cur:
            cur.execute("""
                INSERT INTO parcels (tracking_number, sender, receiver, status, date_created, location, date_sent, cost, weight, description, parcel_price)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (self.tracking_number, self.sender, self.receiver, self.status, self.last_update, self.location, self.date_sent, self.cost_of_items, self.weight, self.description, self.parcel_price))

    @staticmethod
    def update_status(tracking_number, status):
        with Database() as cur:
            cur.execute("UPDATE parcels SET status=?, last_update=? WHERE tracking_number=?", (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), tracking_number))

    @staticmethod
    def get_all():
        with Database() as cur:
            cur.execute("SELECT * FROM parcels")
            return cur.fetchall()

    @staticmethod
    def get_by_user(username):
        with Database() as cur:
            cur.execute("SELECT * FROM parcels WHERE sender=? OR receiver=?", (username, username))
            return cur.fetchall()

    @staticmethod
    def get_by_tracking(tracking_number):
        with Database() as cur:
            cur.execute("SELECT * FROM parcels WHERE tracking_number=?", (tracking_number,))
            return cur.fetchone()

class Report:
    @staticmethod
    def parcel_status_counts():
        with Database() as cur:
            cur.execute("SELECT status, COUNT(*) as count FROM parcels GROUP BY status")
            return {row["status"]: row["count"] for row in cur.fetchall()}

    @staticmethod
    def total_users():
        with Database() as cur:
            cur.execute("SELECT role, COUNT(*) as count FROM users GROUP BY role")
            return {row["role"]: row["count"] for row in cur.fetchall()}

# ----- INIT DATABASE -----
def init_db():
    with Database() as cur:
        # Users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'Customer'
            )
        """)
        # Parcels table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS parcels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_number TEXT UNIQUE NOT NULL,
                sender TEXT NOT NULL,
                receiver TEXT NOT NULL,
                location TEXT NOT NULL,
                date_sent TEXT NOT NULL,
                cost REAL NOT NULL,
                weight REAL NOT NULL,
                description TEXT NOT NULL,
                parcel_price REAL NOT NULL,
                status TEXT NOT NULL DEFAULT 'Received',
                last_update TEXT NOT NULL
            )
        """)
        # Activities table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)

# ----- SEED FUNCTIONS -----
def seed_default_users():
    defaults = [
        ("Zara Grace", "ZGT2006", "Customer"),
        ("Hanny Yobu", "YB1414", "Customer"),
        ("Wanangwa Chirwa", "CH2005", "Customer"),
        ("Hannah HowaHowa", "HWH2004", "Customer"),
        ("Madalitso Hlongo", "M464.L1T50", "Customer"),
        ("Promise Sulwa Chirambo", "5UL.W4", "Customer"),
        ("Grace Nyirenda", "GR4C3.N", "Customer"),
        ("Olive Grace", "0L1V3.GR4C3", "Customer"),
        ("Taonga Sakala", "T40n94.5", "Customer"),
        ("Vanessa Mhango", "VM2005", "Customer"),
        ("Prisca Gunsalu", "PR15C4", "Customer"),
        ("Caroline Nkhoma", "C4R0L1N3", "Customer"),
        ("Nohakhelha Muhime", "N0H4.MH", "Customer"),
        ("Monice Chirwa", "M0.N1C3", "Customer"),
        ("Chikondi Kubwense", "CH1K0N61", "Employee"),
        ("Aisha Kylie", "M155.KYL13", "Employee"),
        ("Ruth Masangwi", "RM2006", "Employee"),
        ("T. Katenga-Kaunda", "TKK123", "Employee"),
        ("Nicole Kimberley Edward", "K1M.83RL3Y", "Manager"),
    ]
    with Database() as cur:
        for u, p, r in defaults:
            cur.execute(
                "INSERT OR IGNORE INTO users (username, password, role) VALUES (?,?,?)",
                (u, p, r)
            )

def seed_default_parcels():
    defaults = [
        ("CTS1001", "Zara Grace", "Hanny Yobu", "Lilongwe Hub", "2025-08-27", 25000, 2.5, "Clothes and shoes", 12000, "In Transit"),
        ("CTS1002", "Hanny Yobu", "Wanangwa Chirwa", "Blantyre Office", "2025-08-03", 15000, 1.2, "Books and stationery", 6000, "Delivered"),
        ("CTS1003", "Wanangwa Chirwa", "Hannah HowaHowa", "Mzuzu Depot", "2025-08-28", 400000, 4.8, "Electronics (phone + charger)", 25000, "In Transit"),
        ("CTS1004", "Hannah HowaHowa", "Zara Grace", "Lilongwe Hub", "2025-08-07", 10000, 0.8, "Cosmetics", 5000, "Out for Delivery"),
        ("CTS1005", "Madalitso Hlongo", "Promise Sulwa Chirambo", "Zomba Office", "2025-08-09", 3000, 0.6, "Stationary", 1500, "Delivered"),
        ("CTS1006", "Grace Nyirenda", "Olive Grace", "Blantyre Office", "2025-08-22", 9000, 0.5, "Perfumes", 4000, "In Transit"),
        ("CTS1007", "Nohakhelha Muhime", "Vanessa Mhango", "Mzuzu Depot", "2025-06-07", 10000, 1, "Clothes", 5000, "Out for Delivery"),
        ("CTS1008", "Prisca Gunsalu", "Caroline Nkhoma", "Lilongwe Hub", "2025-08-27", 10000, 1, "Groceries", 5000, "In Transit"),
        ("CTS1009", "Monice Chirwa", "Taonga Sakala", "Blantyre Office", "2025-08-11", 10000, 1, "Clothes", 5000, "Delivered"),
    ]
    with Database() as cur:
        for tn, sender, receiver, location, date_sent, cost, weight, desc, price, status in defaults:
            cur.execute("""
                INSERT OR IGNORE INTO parcels 
                (tracking_number, sender, receiver, location, date_sent, cost, weight, description, parcel_price, status, last_update)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """, (tn, sender, receiver, location, date_sent, cost, weight, desc, price, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

class Activity:
    @staticmethod
    def log(message):
        with Database() as cur:
            cur.execute("INSERT INTO activities (message, timestamp) VALUES (?, ?)", (message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

    @staticmethod
    def recent(limit=5):
        with Database() as cur:
            cur.execute("SELECT * FROM activities ORDER BY id DESC LIMIT ?", (limit,))
            return cur.fetchall()
