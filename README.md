# attend.

> Subject-wise attendance tracker for JNTUACEA students.

[![Python](https://img.shields.io/badge/Python-3.11-black?style=flat-square)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-black?style=flat-square)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-black?style=flat-square)](LICENSE)

---

## Overview

**attend.** is a lightweight web application that fetches and presents attendance data from the JNTUACEA student portal (`classattendance.in`) in a clean, readable interface. Students enter their existing portal credentials — no separate account needed.

The app computes attendance percentages per subject, calculates how many classes can be skipped or must be attended to maintain the 75% threshold, and presents a day-by-day breakdown on demand.

---

## Features

- **Subject-wise breakdown** — percentage, present/absent count, and status for every subject
- **Smart calculator** — tells you exactly how many classes to attend or how many you can still skip per subject and overall
- **Day-by-day drill-down** — click any subject to expand a full date-wise Present / Absent history
- **Instant analysis** — color-coded status (safe / at-risk / critical) with actionable alerts
- **No data storage** — credentials are used solely to fetch data from the portal and discarded immediately

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python · Flask |
| Scraping | Requests · BeautifulSoup4 |
| Frontend | HTML · CSS · Vanilla JS |
| Server | Gunicorn |

---

## Project Structure

```
attend-web/
├── app.py               # Flask application & API routes
├── scraper.py           # Portal login & attendance scraper
├── templates/
│   └── index.html       # Frontend (single-page)
├── requirements.txt
└── Procfile
```

---

## API

### `POST /api/attendance`

Authenticates with the portal and returns full attendance data.

**Request**
```json
{
  "username": "22BD1A0501",
  "password": "yourpassword"
}
```

**Response**
```json
{
  "name": "Arjun Reddy",
  "roll": "22BD1A0501",
  "branch": "CSE",
  "overall": 83.2,
  "present": 151,
  "total": 182,
  "skip": 4,
  "need": 0,
  "subjects": [
    {
      "subject": "Machine Learning",
      "present": 34,
      "total": 38,
      "absent": 4,
      "percent": 89.5,
      "status": "safe",
      "skip": 5,
      "need": 0,
      "records": [
        { "date": "01-Jan-2025", "status": "Present" }
      ]
    }
  ]
}
```

**Error responses**

| Code | Meaning |
|---|---|
| `400` | Missing username or password |
| `401` | Invalid credentials |
| `404` | No subjects found for this semester |
| `500` | Scraper or server error |

---

## Privacy

- Credentials are transmitted directly to `classattendance.in` and are **never logged or stored**
- No database, no sessions, no cookies are used on this server
- All data processing happens in memory and is discarded after the response is sent

---

## License

MIT © 2025 Manjunath — [linkedin.com/in/t-manjunath-27b469381](https://www.linkedin.com/in/t-manjunath-27b469381)
