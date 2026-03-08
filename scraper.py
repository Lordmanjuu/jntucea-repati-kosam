import requests
from bs4 import BeautifulSoup
import concurrent.futures

BASE_URL = "https://jntuaceastudents.classattendance.in/"

def login(username: str, password: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })

    login_page = session.get(BASE_URL, timeout=15, allow_redirects=True)
    if login_page.status_code != 200:
        raise ValueError("Failed to load login page.")

    soup = BeautifulSoup(login_page.text, "html.parser")

    secretcode = None
    secret_input = (
        soup.find("input", {"name": "secretcode"}) or
        soup.find("input", {"id": "secretcode"})
    )
    if secret_input and secret_input.get("value"):
        secretcode = secret_input.get("value")

    payload = {"username": username, "password": password}
    if secretcode:
        payload["secretcode"] = secretcode

    session.headers.update({
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": BASE_URL.rstrip("/"),
        "Referer": BASE_URL,
    })

    res = session.post(BASE_URL, data=payload, timeout=15, allow_redirects=True)
    if res.status_code != 200:
        raise ValueError("Login request failed.")
    if "studenthome.php" not in res.url.lower():
        raise ValueError("Login failed. Please check your roll number and password.")

    return session


def get_student_details(session: requests.Session) -> dict:
    home_res = session.get(BASE_URL + "studenthome.php", timeout=10)
    if home_res.status_code != 200:
        raise ValueError("Failed to load student home.")

    soup = BeautifulSoup(home_res.text, "html.parser")
    details = {}

    for card in soup.find_all("div", class_="card"):
        header = card.find("div", class_="card-header")
        if header and "My Details" in header.text:
            for li in card.find_all("li", class_="list-group-item"):
                strong = li.find("strong")
                if strong:
                    key   = strong.text.replace(":", "").strip()
                    value = li.text.replace(strong.text, "").strip()
                    details[key] = value
            break

    def _get_input(*names):
        for n in names:
            el = soup.find("input", {"name": n})
            if el and el.get("value"):
                return el.get("value")
        return None

    details["student_id"] = _get_input("roll_no", "student_id", "admission")
    details["class_id"]   = _get_input("class_id")
    details["classname"]  = _get_input("classname")
    details["acad_year"]  = _get_input("acad_year")
    return details


def get_subjects(session: requests.Session, student_info: dict) -> list:
    payload = {
        "student_id": student_info.get("student_id"),
        "class_id":   student_info.get("class_id"),
        "classname":  student_info.get("classname"),
        "acad_year":  student_info.get("acad_year"),
    }
    res  = session.post(BASE_URL + "studentsubjects.php", data=payload, timeout=15)
    soup = BeautifulSoup(res.text, "html.parser")
    subjects = []
    for form in soup.find_all("form"):
        data = {}
        for inp in form.find_all("input"):
            if inp.get("name"):
                data[inp["name"]] = inp.get("value", "")
        if data:
            subjects.append(data)
    return subjects


def fetch_single(session, payload):
    try:
        res   = session.post(BASE_URL + "studentsubatt.php", data=payload, timeout=15)
        soup  = BeautifulSoup(res.text, "html.parser")
        table = soup.find("table", class_="table")
        if not table:
            raise ValueError("no table")

        records = []
        for row in table.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) >= 3:
                records.append({
                    "date":   cols[0].text.strip(),
                    "status": cols[2].text.strip(),
                })

        total   = len(records)
        present = sum(1 for r in records if r["status"] == "Present")
        pct     = round((present / total) * 100, 1) if total else 0

        return {
            "subject": payload.get("sub_fullname", "Unknown"),
            "start":   records[0]["date"] if records else "",
            "end":     records[-1]["date"] if records else "",
            "total":   total,
            "present": present,
            "absent":  total - present,
            "percent": pct,
            "records": records,
        }
    except Exception:
        return {
            "subject": payload.get("sub_fullname", "Unknown"),
            "start": "", "end": "",
            "total": 0, "present": 0, "absent": 0, "percent": 0,
            "records": [],
        }


def fetch_all_attendance(session, subjects):
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(fetch_single, session, s): s for s in subjects}
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())
    return results
