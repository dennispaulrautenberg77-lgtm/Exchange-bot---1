import json
import os
from config import IBAN as DEFAULT_IBAN, INHABER as DEFAULT_INHABER, FEES as DEFAULT_FEES

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "banned_users": [],
            "all_users": [],
            "iban": DEFAULT_IBAN,
            "inhaber": DEFAULT_INHABER,
            "fees": DEFAULT_FEES.copy()
        }
    with open(DATA_FILE, "r") as f:
        data = json.load(f)
    if "iban" not in data:
        data["iban"] = DEFAULT_IBAN
    if "inhaber" not in data:
        data["inhaber"] = DEFAULT_INHABER
    if "fees" not in data:
        data["fees"] = DEFAULT_FEES.copy()
    if "banned_users" not in data:
        data["banned_users"] = []
    if "all_users" not in data:
        data["all_users"] = []
    return data

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_iban():
    return load_data()["iban"]

def get_inhaber():
    return load_data()["inhaber"]

def get_fees():
    return load_data()["fees"]

def set_iban(iban, inhaber):
    data = load_data()
    data["iban"] = iban
    data["inhaber"] = inhaber
    save_data(data)

def set_fee(method, value):
    data = load_data()
    data["fees"][method] = value
    save_data(data)

def ban_user(user_id):
    data = load_data()
    if user_id not in data["banned_users"]:
        data["banned_users"].append(user_id)
    save_data(data)

def unban_user(user_id):
    data = load_data()
    data["banned_users"] = [u for u in data["banned_users"] if u != user_id]
    save_data(data)

def is_banned(user_id):
    return user_id in load_data()["banned_users"]

def get_banned_users():
    return load_data().get("banned_users", [])

def add_user(user_id):
    data = load_data()
    if user_id not in data.get("all_users", []):
        data.setdefault("all_users", []).append(user_id)
        save_data(data)
def get_all_users():
    return load_data().get("all_users", [])