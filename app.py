# flight tracker - app.py
# run with: python app.py
# open http://<your-pc-ip>:5001 on your tablet

from flask import Flask, jsonify, render_template
import requests
import os

app = Flask(__name__)

# --- YOUR LOCATION ---
MY_LAT = 51.500522
MY_LON = -0.044615
RADIUS_NM = 12   # ~22km radius in nautical miles

AIRLINE_FALLBACK = {
    "BAW": ("British Airways", "BA"),     "EZY": ("easyJet", "U2"),
    "RYR": ("Ryanair", "FR"),             "DLH": ("Lufthansa", "LH"),
    "AFR": ("Air France", "AF"),          "KLM": ("KLM", "KL"),
    "UAE": ("Emirates", "EK"),            "TOM": ("TUI Airways", "BY"),
    "VIR": ("Virgin Atlantic", "VS"),     "AAL": ("American Airlines", "AA"),
    "UAL": ("United Airlines", "UA"),     "DAL": ("Delta Air Lines", "DL"),
    "SAS": ("Scandinavian Airlines", "SK"), "IBE": ("Iberia", "IB"),
    "VLG": ("Vueling", "VY"),             "THY": ("Turkish Airlines", "TK"),
    "QTR": ("Qatar Airways", "QR"),       "ETD": ("Etihad Airways", "EY"),
    "SIA": ("Singapore Airlines", "SQ"),  "CPA": ("Cathay Pacific", "CX"),
    "QFA": ("Qantas", "QF"),              "ACA": ("Air Canada", "AC"),
    "WZZ": ("Wizz Air", "W6"),            "SWR": ("Swiss International", "LX"),
    "FIN": ("Finnair", "AY"),             "LOT": ("LOT Polish Airlines", "LO"),
    "FDX": ("FedEx", "FX"),               "UPS": ("UPS Airlines", "5X"),
    "EXS": ("Jet2", "LS"),               "AUA": ("Austrian Airlines", "OS"),
}

aircraft_cache = {}
route_cache    = {}
airline_cache  = {}


def get_aircraft(icao24):
    if icao24 in aircraft_cache:
        return aircraft_cache[icao24]
    try:
        r = requests.get(f"https://hexdb.io/api/v1/aircraft/{icao24}", timeout=5)
        d = r.json()
        result = {
            "type":      f"{d.get('Manufacturer','')} {d.get('Type','')}".strip(),
            "icao_type": d.get("ICAOTypeCode", ""),
        }
    except Exception:
        result = {"type": "", "icao_type": ""}
    aircraft_cache[icao24] = result
    return result


def get_route(callsign):
    """Use adsbdb — returns full airport objects with names, no parsing needed."""
    if not callsign or callsign == "???":
        return {"origin": "", "origin_name": "", "destination": "", "destination_name": ""}
    if callsign in route_cache:
        return route_cache[callsign]
    try:
        r = requests.get(
            f"https://api.adsbdb.com/v0/callsign/{callsign}",
            timeout=5,
        )
        d = r.json()
        fr = d.get("response", {}).get("flightroute", {})
        orig = fr.get("origin", {})
        dest = fr.get("destination", {})
        result = {
            "origin":           orig.get("iata_code", "") or orig.get("icao_code", ""),
            "origin_name":      orig.get("name", ""),
            "destination":      dest.get("iata_code", "") or dest.get("icao_code", ""),
            "destination_name": dest.get("name", ""),
        }
    except Exception:
        result = {"origin": "", "origin_name": "", "destination": "", "destination_name": ""}
    route_cache[callsign] = result
    return result


def get_airline(callsign):
    if not callsign or callsign == "???":
        return {"name": "", "iata": ""}
    prefix = callsign[:3].upper()
    if prefix in airline_cache:
        return airline_cache[prefix]
    result = {"name": "", "iata": ""}
    try:
        r = requests.get(f"https://hexdb.io/api/v1/operator/{callsign}", timeout=5)
        d = r.json()
        if isinstance(d, dict) and isinstance(d.get("Name"), str) and d["Name"]:
            result = {"name": d["Name"], "iata": d.get("IATA", "")}
    except Exception:
        pass
    if not result["name"] and prefix in AIRLINE_FALLBACK:
        name, iata = AIRLINE_FALLBACK[prefix]
        result = {"name": name, "iata": iata}
    airline_cache[prefix] = result
    return result


def fetch_flights():
    try:
        r = requests.get(
            f"https://api.airplanes.live/v2/point/{MY_LAT}/{MY_LON}/{RADIUS_NM}",
            timeout=10,
        )
        data = r.json()
    except Exception as e:
        return {"error": str(e), "flights": []}

    flights = []
    for s in (data.get("ac") or []):
        alt = s.get("alt_baro")
        if alt == "ground" or alt is None or s.get("lat") is None:
            continue

        icao24   = s.get("hex", "")
        callsign = (s.get("flight") or "???").strip()
        heading  = s.get("track")
        vrate    = s.get("baro_rate")  # ft/min
        t_pos    = s.get("seen_pos", 0)

        aircraft = get_aircraft(icao24)
        route    = get_route(callsign)
        airline  = get_airline(callsign)

        if   vrate is None: status = "CRUISING"
        elif vrate > 300:   status = "CLIMBING"
        elif vrate < -300:  status = "DESCENDING"
        else:               status = "CRUISING"

        flights.append({
            "callsign":           callsign,
            "airline_name":       airline["name"],
            "airline_iata":       airline["iata"],
            "aircraft_type":      aircraft["type"],
            "icao_type":          aircraft["icao_type"],
            "origin":             route["origin"],
            "origin_name":        route["origin_name"],
            "destination":        route["destination"],
            "destination_name":   route["destination_name"],
            "altitude_ft":        round(alt),
            "heading":            heading or 0,
            "status":             status,
            "time_position":      t_pos,
        })

    flights.sort(key=lambda f: f["time_position"])  # lower = more recently seen
    return {"flights": flights, "count": len(flights)}


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/flights")
def flights():
    return jsonify(fetch_flights())

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"Overhead → http://localhost:{port}")
    app.run(host="0.0.0.0", port=port)