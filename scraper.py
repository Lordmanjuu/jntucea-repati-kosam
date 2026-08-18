import asyncio
import math
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

BASE_URL = "https://jntuaceastudents.classattendance.in/"

# ── STEALTH SCRIPT ─────────────────────────────────────────────────────────────
# Injected before every page load — hides Playwright from Cloudflare bot detection
STEALTH_JS = """
() => {
    // 1. Hide webdriver flag
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined,
        configurable: true
    });

    // 2. Fake Chrome runtime
    window.chrome = {
        runtime: {
            connect: () => {},
            sendMessage: () => {},
            onMessage: { addListener: () => {} }
        },
        loadTimes: () => {},
        csi: () => {},
        app: {}
    };

    // 3. Fake plugins (empty = bot)
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
            { name: 'Native Client', filename: 'internal-nacl-plugin' }
        ],
        configurable: true
    });

    // 4. Fake languages
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-IN', 'en-US', 'en', 'te'],
        configurable: true
    });

    // 5. Fake permissions
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);

    // 6. Hide automation flags
    delete window.__playwright;
    delete window.__pw_manual;
    delete window.calledSelenium;

    // 7. Fake screen resolution (not 0x0)
    Object.defineProperty(screen, 'width',  { get: () => 1366 });
    Object.defineProperty(screen, 'height', { get: () => 768 });
    Object.defineProperty(screen, 'colorDepth', { get: () => 24 });

    // 8. Fake hardware concurrency
    Object.defineProperty(navigator, 'hardwareConcurrency', {
        get: () => 8,
        configurable: true
    });

    // 9. Fake device memory
    Object.defineProperty(navigator, 'deviceMemory', {
        get: () => 8,
        configurable: true
    });

    // 10. Override toString to hide Playwright
    const newProto = navigator.__proto__;
    delete newProto.webdriver;
}
"""


class AttendanceScraper:
    """
    Bypasses Cloudflare using real Playwright Chromium browser.
    Replicates the same approach the senior's Android app used with WebView.
    """

    def get_attendance(self, username: str, password: str) -> dict:
        """Sync wrapper — runs async scraper in event loop"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self._scrape(username, password))
        finally:
            loop.close()

    async def _scrape(self, username: str, password: str) -> dict:
        async with async_playwright() as pw:
            # ── LAUNCH REAL CHROMIUM ───────────────────────────────────────────
            browser = await pw.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--window-size=1366,768',
                ]
            )

            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1366, "height": 768},
                locale="en-IN",
                timezone_id="Asia/Kolkata",
                java_script_enabled=True,
                accept_downloads=False,
                ignore_https_errors=True,
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-IN,en;q=0.9,te;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                }
            )

            # Inject stealth script before every page load
            await context.add_init_script(STEALTH_JS)

            page = await context.new_page()

            try:
                # ── STEP 1: LOAD LOGIN PAGE ────────────────────────────────────
                print(f"[scraper] Loading portal...")
                await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)

                # Wait for Cloudflare challenge to resolve
                # Cloudflare usually takes 3-5 seconds max
                try:
                    await page.wait_for_selector(
                        "input[name='username'], input[name='password']",
                        timeout=30000
                    )
                    print("[scraper] Login page loaded!")
                except PlaywrightTimeout:
                    # Check if we're stuck on Cloudflare
                    content = await page.content()
                    if "Just a moment" in content or "cf-" in content:
                        # Wait more for Cloudflare to resolve
                        await page.wait_for_timeout(8000)
                        await page.wait_for_selector(
                            "input[name='username']",
                            timeout=30000
                        )
                    else:
                        raise ValueError("Portal is not responding. Try again!")

                # ── STEP 2: GET SECRET CODE ────────────────────────────────────
                secretcode = await page.evaluate("""
                    () => {
                        const el = document.querySelector('input[name="secretcode"]');
                        return el ? el.value : '';
                    }
                """)

                # ── STEP 3: FILL LOGIN FORM ────────────────────────────────────
                print(f"[scraper] Filling login form...")

                # Type like a human (small delays)
                await page.fill("input[name='username']", "")
                await page.type("input[name='username']", username, delay=50)

                await page.fill("input[name='password']", "")
                await page.type("input[name='password']", password, delay=50)

                # ── STEP 4: SUBMIT FORM ────────────────────────────────────────
                # Click submit button or press Enter
                try:
                    submit_btn = page.locator(
                        "button[type='submit'], input[type='submit'], "
                        "button:has-text('Login'), button:has-text('Sign')"
                    ).first
                    await submit_btn.click()
                except Exception:
                    await page.keyboard.press("Enter")

                # ── STEP 5: WAIT FOR REDIRECT ──────────────────────────────────
                print("[scraper] Waiting for login redirect...")
                try:
                    await page.wait_for_url("**/studenthome.php", timeout=30000)
                except PlaywrightTimeout:
                    url = page.url
                    content = await page.content()
                    if "studenthome" in url:
                        pass  # Already there
                    elif "invalid" in content.lower() or "incorrect" in content.lower():
                        raise ValueError("Login failed. Check roll number and password!")
                    else:
                        raise ValueError("Login failed. Please try again!")

                print("[scraper] Login successful!")

                # ── STEP 6: EXTRACT STUDENT DETAILS ───────────────────────────
                print("[scraper] Extracting student info...")
                student_info = await page.evaluate("""
                    () => {
                        const info = {};
                        
                        // Get "My Details" card
                        const items = document.querySelectorAll('.list-group-item');
                        items.forEach(li => {
                            const strong = li.querySelector('strong');
                            if (strong) {
                                const key = strong.textContent.replace(':', '').trim();
                                const val = li.textContent.replace(strong.textContent, '').trim();
                                info[key] = val;
                            }
                        });
                        
                        // Get hidden form inputs
                        const getVal = (name) => {
                            const el = document.querySelector(`input[name="${name}"]`);
                            return el ? el.value : '';
                        };
                        
                        info.student_id = getVal('roll_no') || getVal('student_id') || getVal('admission');
                        info.class_id   = getVal('class_id');
                        info.classname  = getVal('classname');
                        info.acad_year  = getVal('acad_year');
                        
                        return info;
                    }
                """)

                # ── STEP 7: GET SUBJECTS ───────────────────────────────────────
                print("[scraper] Fetching subjects...")
                subjects_payload = {
                    "student_id": student_info.get("student_id", ""),
                    "class_id":   student_info.get("class_id", ""),
                    "classname":  student_info.get("classname", ""),
                    "acad_year":  student_info.get("acad_year", ""),
                }

                subjects_html = await page.evaluate(f"""
                    async () => {{
                        const resp = await fetch('{BASE_URL}studentsubjects.php', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                            body: new URLSearchParams({str(subjects_payload)})
                        }});
                        return await resp.text();
                    }}
                """)

                # Parse subjects from HTML
                subjects = await page.evaluate(f"""
                    () => {{
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(`{subjects_html.replace('`', '\\`')}`, 'text/html');
                        const forms = doc.querySelectorAll('form');
                        const result = [];
                        forms.forEach(form => {{
                            const data = {{}};
                            form.querySelectorAll('input').forEach(inp => {{
                                if (inp.name) data[inp.name] = inp.value || '';
                            }});
                            if (Object.keys(data).length > 0) result.push(data);
                        }});
                        return result;
                    }}
                """)

                if not subjects:
                    raise ValueError("No subjects found. Semester may not be active yet!")

                print(f"[scraper] Found {len(subjects)} subjects. Fetching attendance...")

                # ── STEP 8: FETCH ATTENDANCE FOR EACH SUBJECT ─────────────────
                async def fetch_subject(subject_data):
                    try:
                        att_html = await page.evaluate(f"""
                            async () => {{
                                const resp = await fetch('{BASE_URL}studentsubatt.php', {{
                                    method: 'POST',
                                    headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                                    body: new URLSearchParams({str(subject_data)})
                                }});
                                return await resp.text();
                            }}
                        """)

                        records = await page.evaluate(f"""
                            () => {{
                                const parser = new DOMParser();
                                const doc = parser.parseFromString(`{att_html.replace('`', '\\`')}`, 'text/html');
                                const rows = doc.querySelectorAll('table.table tr');
                                const result = [];
                                rows.forEach(row => {{
                                    const cols = row.querySelectorAll('td');
                                    if (cols.length >= 3) {{
                                        result.push({{
                                            date:   cols[0].textContent.trim(),
                                            status: cols[2].textContent.trim()
                                        }});
                                    }}
                                }});
                                return result;
                            }}
                        """)

                        total   = len(records)
                        present = sum(1 for r in records if r["status"] == "Present")
                        pct     = round((present / total) * 100, 1) if total else 0

                        return {
                            "subject": subject_data.get("sub_fullname", "Unknown"),
                            "total":   total,
                            "present": present,
                            "absent":  total - present,
                            "percent": pct,
                            "records": records,
                        }

                    except Exception as e:
                        return {
                            "subject": subject_data.get("sub_fullname", "Unknown"),
                            "total": 0, "present": 0, "absent": 0, "percent": 0,
                            "records": [],
                        }

                # Fetch all subjects (sequentially to avoid race conditions)
                results = []
                for s in subjects:
                    r = await fetch_subject(s)
                    results.append(r)

                # ── STEP 9: CALCULATE TOTALS ───────────────────────────────────
                def need(p, t):
                    n = (0.75 * t - p) / 0.25
                    return max(math.ceil(n), 0) if n > 0 else 0

                def skip(p, t):
                    return max(math.floor(p - 0.75 * t), 0)

                def status(pct):
                    return "safe" if pct >= 75 else "warn" if pct >= 65 else "danger"

                total_p   = sum(r["present"] for r in results)
                total_c   = sum(r["total"]   for r in results)
                overall   = round((total_p / total_c) * 100, 1) if total_c else 0
                avg_pct   = round(sum(r["percent"] for r in results) / len(results), 1) if results else 0

                for r in results:
                    r["need"]   = need(r["present"], r["total"])
                    r["skip"]   = skip(r["present"], r["total"])
                    r["status"] = status(r["percent"])

                name   = student_info.get("Name", student_info.get("name", username))
                roll   = student_info.get("Roll No", student_info.get("student_id", username))
                branch = student_info.get("Branch", student_info.get("classname", ""))

                print(f"[scraper] Done! {name} — {overall}%")

                return {
                    "name":     name,
                    "roll":     roll,
                    "branch":   branch,
                    "overall":  overall,
                    "present":  total_p,
                    "total":    total_c,
                    "skip":     skip(total_p, total_c),
                    "need":     need(total_p, total_c),
                    "avg":      avg_pct,
                    "subjects": sorted(results, key=lambda x: x["percent"]),
                }

            finally:
                await browser.close()


# ── QUICK TEST ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    roll = input("Roll number: ").strip()
    pwd  = input("Password:    ").strip()
    s = AttendanceScraper()
    data = s.get_attendance(roll, pwd)
    print(f"\n{data['name']} — {data['overall']}%")
    for sub in data["subjects"]:
        bar = "█" * int(sub["percent"] // 5)
        print(f"  {sub['subject'][:30]:30s} {bar:20s} {sub['percent']}%")
