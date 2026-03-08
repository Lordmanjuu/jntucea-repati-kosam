from flask import Flask, render_template, request, jsonify
from scraper import login, get_student_details, get_subjects, fetch_all_attendance
import os

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/attendance", methods=["POST"])
def get_attendance():
    data     = request.get_json()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return jsonify({"error": "Roll number and password are required."}), 400

    try:
        session      = login(username, password)
        info         = get_student_details(session)
        subjects_raw = get_subjects(session, info)

        if not subjects_raw:
            return jsonify({"error": "No subjects found. Semester may not be active yet."}), 404

        subjects = fetch_all_attendance(session, subjects_raw)

        total_p  = sum(s["present"] for s in subjects)
        total_c  = sum(s["total"]   for s in subjects)
        overall  = round((total_p / total_c) * 100, 1) if total_c else 0

        def need(p, t):
            n = (0.75 * t - p) / 0.25
            return max(int(n) + (1 if n % 1 > 0 else 0), 0)

        def skip(p, t):
            return max(int(p - 0.75 * t), 0)

        # Enrich each subject
        for s in subjects:
            s["need"]   = need(s["present"], s["total"])
            s["skip"]   = skip(s["present"], s["total"])
            s["status"] = "safe" if s["percent"] >= 85 else ("warn" if s["percent"] >= 75 else "danger")

        return jsonify({
            "name":     info.get("Name", info.get("name", username)),
            "roll":     info.get("Roll No", info.get("student_id", username)),
            "branch":   info.get("Branch", info.get("classname", "")),
            "overall":  overall,
            "present":  total_p,
            "total":    total_c,
            "skip":     skip(total_p, total_c),
            "need":     need(total_p, total_c),
            "subjects": sorted(subjects, key=lambda x: x["percent"]),
        })

    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": f"Something went wrong: {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
