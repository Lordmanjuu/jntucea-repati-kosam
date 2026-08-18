from flask import Flask, render_template, request, jsonify
from scraper import AttendanceScraper
import os

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/attendance", methods=["POST"])
def attendance():
    data     = request.get_json()
    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    if not username or not password:
        return jsonify({"error": "Roll number mariyu password rendu kavali bro! 😅"}), 400

    try:
        scraper = AttendanceScraper()
        result  = scraper.get_attendance(username, password)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": f"Server ki emi ayyindo teliyatledu 😭 — {str(e)}"}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
