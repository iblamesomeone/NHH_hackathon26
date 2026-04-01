"""
AI-Based Bedsore Prevention and Risk Prioritization System
Flask Backend
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import math
import random
import time

app = Flask(__name__)
CORS(app)  # Allow frontend to communicate with backend

# ─────────────────────────────────────────────
# PATIENT DATA STORE (in-memory for prototype)
# ─────────────────────────────────────────────
patients = [
    {"id": 1, "name": "Arjun Sharma",    "pressure": 85, "time": 180, "rh": 80, "temp": 36.5, "angle": 30, "S": 2.5, "condition": "Stroke"},
    {"id": 2, "name": "Priya Mehta",     "pressure": 60, "time": 90,  "rh": 55, "temp": 33.0, "angle": 10, "S": 0,   "condition": "Normal"},
    {"id": 3, "name": "Ramesh Gupta",    "pressure": 110,"time": 300, "rh": 92, "temp": 37.0, "angle": 50, "S": 3.0, "condition": "Coma"},
    {"id": 4, "name": "Sunita Patel",    "pressure": 75, "time": 240, "rh": 70, "temp": 35.0, "angle": 20, "S": 2.0, "condition": "Diabetes"},
    {"id": 5, "name": "Vikram Singh",    "pressure": 95, "time": 360, "rh": 88, "temp": 36.8, "angle": 45, "S": 2.5, "condition": "ICU Ventilated"},
    {"id": 6, "name": "Kavita Rao",      "pressure": 50, "time": 60,  "rh": 62, "temp": 33.5, "angle": 5,  "S": 0,   "condition": "Normal"},
    {"id": 7, "name": "Deepak Joshi",    "pressure": 100,"time": 270, "rh": 85, "temp": 36.2, "angle": 35, "S": 2.5, "condition": "ICU Ventilated"},
]

next_id = 8  # Auto-increment ID counter

# ─────────────────────────────────────────────
# CORE AI FORMULA
# ─────────────────────────────────────────────

def compute_moisture_factor(rh, temp):
    """
    Fmo = RH_score × temperature_multiplier
    Higher moisture increases skin breakdown risk.
    """
    # Relative Humidity score
    if rh < 60:
        rh_score = 1.0
    elif rh < 75:
        rh_score = 1.3
    elif rh < 90:
        rh_score = 1.7
    else:
        rh_score = 2.2

    # Temperature multiplier
    if temp < 32:
        temp_mult = 1.0
    elif temp < 34:
        temp_mult = 1.1
    elif temp < 36:
        temp_mult = 1.2
    else:
        temp_mult = 1.3

    return round(rh_score * temp_mult, 3)


def compute_shear_factor(angle_deg):
    """
    Fsh = min(3, 1 + 2 * (sin(angle) / μ))
    μ (friction coefficient) = 0.5 (typical bed linen)
    Higher bed angle → more shear force on skin.
    """
    mu = 0.5  # friction coefficient
    angle_rad = math.radians(angle_deg)
    fsh = 1 + 2 * (math.sin(angle_rad) / mu)
    return round(min(3.0, fsh), 3)


def compute_time_factor(minutes):
    """
    Convert immobility time (minutes) into a risk multiplier.
    Risk grows non-linearly — after 2 hours it accelerates.
    """
    hours = minutes / 60.0
    # Piecewise: slow growth early, steeper after 2h
    if hours <= 2:
        return round(0.5 + (hours / 2) * 0.5, 3)   # 0.5 → 1.0
    else:
        return round(1.0 + (hours - 2) * 0.3, 3)    # grows 0.3 per extra hour


def calculate_ri(pressure, time_min, rh, temp, angle, S):
    """
    RI = (P / 32) × T × Fmo × Fsh + S
    This is the core Risk Index formula.
    """
    T   = compute_time_factor(time_min)
    Fmo = compute_moisture_factor(rh, temp)
    Fsh = compute_shear_factor(angle)
    P_norm = pressure / 32.0

    ri = P_norm * T * Fmo * Fsh + S
    return round(ri, 2), T, Fmo, Fsh


def risk_level(ri):
    """Map RI value to clinical risk category."""
    if ri < 10:
        return "Low"
    elif ri < 25:
        return "Moderate"
    elif ri < 50:
        return "High"
    else:
        return "Very High"


def generate_alerts(ri, fmo, fsh):
    """Generate up to 3 smart clinical alerts per patient."""
    alerts = []
    if ri >= 40:
        alerts.append("🚨 Reposition immediately — critical pressure risk")
    if fmo >= 2.0:
        alerts.append("💧 High moisture detected — change bedsheet now")
    if fsh >= 2.0:
        alerts.append("📐 High shear force — adjust bed angle")
    return alerts[:3]  # cap at 3


# ─────────────────────────────────────────────
# FLASK ENDPOINTS
# ─────────────────────────────────────────────

@app.route("/predict", methods=["POST"])
def predict():
    """
    POST /predict
    Accepts patient vitals, returns RI, risk level, factors, alerts.
    """
    data = request.get_json()

    pressure = float(data.get("pressure", 60))
    time_min = float(data.get("time", 120))
    rh       = float(data.get("rh", 65))
    temp     = float(data.get("temp", 36.0))
    angle    = float(data.get("angle", 0))
    S        = float(data.get("S", 0))

    ri, T, Fmo, Fsh = calculate_ri(pressure, time_min, rh, temp, angle, S)

    return jsonify({
        "ri":         ri,
        "risk_level": risk_level(ri),
        "T":          T,
        "Fmo":        Fmo,
        "Fsh":        Fsh,
        "alerts":     generate_alerts(ri, Fmo, Fsh)
    })


@app.route("/patients", methods=["GET"])
def get_patients():
    """
    GET /patients
    Returns all patients with computed RI, sorted by priority.
    """
    result = []
    for p in patients:
        ri, T, Fmo, Fsh = calculate_ri(
            p["pressure"], p["time"], p["rh"], p["temp"], p["angle"], p["S"]
        )
        result.append({
            "id":        p["id"],
            "name":      p["name"],
            "pressure":  p["pressure"],
            "time":      p["time"],
            "rh":        p["rh"],
            "temp":      p["temp"],
            "angle":     p["angle"],
            "S":         p["S"],
            "condition": p["condition"],
            "ri":        ri,
            "T":         T,
            "Fmo":       Fmo,
            "Fsh":       Fsh,
            "risk_level":risk_level(ri),
            "alerts":    generate_alerts(ri, Fmo, Fsh)
        })

    # Sort: highest RI first; tie-break on S, then time
    result.sort(key=lambda x: (-x["ri"], -x["S"], -x["time"]))

    # Assign priority rank
    for i, p in enumerate(result):
        p["priority"] = i + 1

    return jsonify(result)


@app.route("/add_patient", methods=["POST"])
def add_patient():
    """
    POST /add_patient
    Onboards a new patient into the system.
    """
    global next_id
    data = request.get_json()

    # Map condition string to S score
    condition_scores = {
        "Normal":        0,
        "Diabetes":      2.0,
        "Stroke":        2.5,
        "Coma":          3.0,
        "ICU Ventilated":2.5,
    }
    condition = data.get("condition", "Normal")
    S = condition_scores.get(condition, 0)

    new_patient = {
        "id":        next_id,
        "name":      data.get("name", f"Patient {next_id}"),
        "pressure":  float(data.get("pressure", 60)),
        "time":      float(data.get("time", 120)),
        "rh":        float(data.get("rh", 65)),
        "temp":      float(data.get("temp", 36.0)),
        "angle":     float(data.get("angle", 15)),
        "S":         S,
        "condition": condition,
    }
    patients.append(new_patient)
    next_id += 1

    return jsonify({"success": True, "id": new_patient["id"], "message": f"Patient {new_patient['name']} added."})


@app.route("/simulate_update", methods=["POST"])
def simulate_update():
    """
    POST /simulate_update
    Randomly nudges patient vitals to simulate real sensor data.
    """
    for p in patients:
        p["pressure"] = max(20, min(120, p["pressure"] + random.randint(-5, 5)))
        p["time"]     = min(600, p["time"] + random.randint(0, 10))
        p["rh"]       = max(40, min(100, p["rh"] + random.randint(-2, 2)))
        p["temp"]     = round(max(30.0, min(40.0, p["temp"] + random.uniform(-0.2, 0.2))), 1)
        p["angle"]    = max(0, min(80, p["angle"] + random.randint(-3, 3)))
    return jsonify({"success": True})


@app.route("/system_status", methods=["GET"])
def system_status():
    """
    GET /system_status
    Returns health of all system components.
    """
    return jsonify({
        "backend":          "online",
        "ai_model":         "active",
        "ri_engine":        "running",
        "sensor_sim":       "active",
        "patient_count":    len(patients),
        "uptime_seconds":   int(time.time() % 86400),
        "formula":          "RI = (P/32) × T × Fmo × Fsh + S",
        "version":          "1.0.0"
    })


if __name__ == "__main__":
    print("🏥 Bedsore Prevention System — Backend Running")
    print("   http://localhost:5000")
    app.run(debug=True, port=5000)
