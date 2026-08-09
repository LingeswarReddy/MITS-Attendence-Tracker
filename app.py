import streamlit as st
import pandas as pd
import math
import os
import re
import time

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


# ═════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ═════════════════════════════════════════════════════════════════════════════

for key, default in [
    ("attendance_data", None),
    ("last_roll", ""),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ═════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="MITS IMS Attendance Portal",
    page_icon="🎓",
    layout="wide"
)


# ═════════════════════════════════════════════════════════════════════════════
# CSS
# ═════════════════════════════════════════════════════════════════════════════

st.markdown(
    """
    <style>

    .stApp {
        background: linear-gradient(to right, #f5f7fa, #e4ecf7);
    }

    .mits-header {
        text-align: center;
        padding: 20px;
    }

    .mits-title {
        font-size: 48px;
        font-weight: bold;
        color: #d32f2f;
    }

    .mits-subtitle {
        font-size: 20px;
        color: #1e3c72;
        margin-top: -10px;
    }

    .hero-box {
        background: linear-gradient(to right, #1e3c72, #2a5298);
        padding: 40px;
        border-radius: 15px;
        text-align: center;
        color: white;
        margin-bottom: 30px;
        box-shadow: 0px 8px 20px rgba(0,0,0,0.2);
    }

    .footer {
        text-align: center;
        padding: 30px;
        font-size: 14px;
        color: gray;
    }

    label {
        color: black !important;
        font-weight: bold !important;
    }

    div[data-testid="stExpander"] summary {
        color: black !important;
        font-weight: bold;
    }

    </style>
    """,
    unsafe_allow_html=True
)


# ═════════════════════════════════════════════════════════════════════════════
# PLAYWRIGHT BROWSER
# ═════════════════════════════════════════════════════════════════════════════

@st.cache_resource
def get_playwright_browser():
    """
    Start Playwright and Chromium once per Streamlit server.
    This avoids starting/installing the browser for every login.
    """

    playwright = sync_playwright().start()

    browser = None

    # Try Playwright-managed Chromium first
    try:
        browser = playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-zygote",
                "--disable-software-rasterizer",
            ]
        )
    except Exception:
        # Try common system Chromium locations
        chromium_locations = [
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
        ]

        for executable in chromium_locations:
            if os.path.exists(executable):
                try:
                    browser = playwright.chromium.launch(
                        executable_path=executable,
                        headless=True,
                        args=[
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                            "--no-zygote",
                        ]
                    )
                    break
                except Exception:
                    pass

    if browser is None:
        playwright.stop()
        raise RuntimeError(
            "Chromium could not be started. "
            "Install Playwright Chromium using 'playwright install chromium' "
            "or install Chromium in the deployment environment."
        )

    return playwright, browser


# ═════════════════════════════════════════════════════════════════════════════
# PAGE TEXT
# ═════════════════════════════════════════════════════════════════════════════

def get_page_text(page):
    """
    Get visible text from the current page and all frames.
    """

    chunks = []

    try:
        text = page.locator("body").inner_text(timeout=5000)

        if text:
            chunks.append(text)

    except Exception:
        pass

    try:
        for frame in page.frames:
            if frame == page.main_frame:
                continue

            try:
                text = frame.locator("body").inner_text(timeout=3000)

                if text:
                    chunks.append(text)

            except Exception:
                pass

    except Exception:
        pass

    return "\n".join(chunks)


# ═════════════════════════════════════════════════════════════════════════════
# ATTENDANCE PARSER
# ═════════════════════════════════════════════════════════════════════════════

def parse_attendance(text):

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    if not lines:
        return []

    result = []

    # ---------------------------------------------------------
    # Method 1: Expected IMS table order
    # ---------------------------------------------------------

    start = -1

    for i in range(1, len(lines) - 1):

        current = lines[i].upper()
        previous = lines[i - 1].upper()
        next_line = lines[i + 1].upper()

        if (
            "CLASSES ATTENDED" in current
            and "SUBJECT CODE" in previous
            and "TOTAL CONDUCTED" in next_line
        ):
            start = i + 3
            break

    # ---------------------------------------------------------
    # Method 2: Search for attendance headings
    # ---------------------------------------------------------

    if start == -1:

        for i in range(len(lines) - 1):

            current = lines[i].lower()
            next_line = lines[i + 1].lower()

            if (
                "attended" in current
                and "conduct" in next_line
            ):
                start = i + 2
                break

    # ---------------------------------------------------------
    # Method 3: Search for percentage table
    # ---------------------------------------------------------

    if start == -1:

        for i, line in enumerate(lines):

            low = line.lower()

            if (
                "attendance" in low
                and "%" in low
            ):
                start = i + 1
                break

    if start == -1:
        return []

    # ---------------------------------------------------------
    # Parse rows
    # ---------------------------------------------------------

    i = start

    while i < len(lines):

        # Need at least 4 values
        if i + 3 >= len(lines):
            break

        sno = lines[i]
        subject = lines[i + 1]
        attended = lines[i + 2]
        conducted = lines[i + 3]

        percentage = ""

        if i + 4 < len(lines):
            percentage = lines[i + 4]

        # Stop conditions
        if (
            "note" in sno.lower()
            or "note" in subject.lower()
            or "total" in sno.lower()
            or "total" in subject.lower()
        ):
            break

        # S.No must be numeric
        if not sno.isdigit():

            # Search next possible row
            i += 1
            continue

        # Attended / Conducted must be numeric
        if not attended.isdigit() or not conducted.isdigit():

            i += 1
            continue

        a = int(attended)
        c = int(conducted)

        if c <= 0:
            i += 1
            continue

        # Calculate percentage ourselves
        calculated_percentage = round((a / c) * 100, 2)

        result.append(
            {
                "s_no": sno,
                "subject": subject,
                "attended": str(a),
                "conducted": str(c),
                "percentage": f"{calculated_percentage:.2f}%"
            }
        )

        i += 5

    return result


# ═════════════════════════════════════════════════════════════════════════════
# FIND ATTENDANCE PAGE
# ═════════════════════════════════════════════════════════════════════════════

def open_attendance_page(page):

    current_text = get_page_text(page)

    low = current_text.lower()

    # Already on attendance page
    if (
        "attended" in low
        and "conducted" in low
    ):
        return True

    # Try common attendance links
    selectors = [
        "a[href*='attendance']",
        "a[href*='Attendance']",
        "a[href*='attd']",
        "a[href*='ATTD']",
        "a:has-text('Attendance')",
        "a:has-text('ATTENDANCE')",
        "button:has-text('Attendance')",
        "text=Attendance",
    ]

    for selector in selectors:

        try:

            locator = page.locator(selector)

            count = locator.count()

            if count > 0:

                for index in range(min(count, 3)):

                    try:

                        locator.nth(index).click(
                            timeout=3000
                        )

                        time.sleep(5)

                        text = get_page_text(page)

                        low = text.lower()

                        if (
                            "attended" in low
                            or "conducted" in low
                        ):
                            return True

                    except Exception:
                        continue

        except Exception:
            continue

    return False


# ═════════════════════════════════════════════════════════════════════════════
# MITS LOGIN + SCRAPER
# ═════════════════════════════════════════════════════════════════════════════

def scrape_attendance(roll, password, progress_callback=None):

    playwright = None
    browser = None
    context = None
    page = None

    def progress(value, message):

        if progress_callback:
            progress_callback(value, message)

    try:

        # ---------------------------------------------------------
        # Start browser
        # ---------------------------------------------------------

        progress(
            10,
            "🌐 Starting secure browser..."
        )

        playwright, browser = get_playwright_browser()

        context = browser.new_context(
            viewport={
                "width": 1280,
                "height": 900
            },
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            ignore_https_errors=True,
        )

        page = context.new_page()

        # ---------------------------------------------------------
        # MITS website
        # ---------------------------------------------------------

        progress(
            20,
            "🌐 Opening MITS IMS..."
        )

        page.goto(
            "http://mitsims.in/",
            wait_until="domcontentloaded",
            timeout=45000
        )

        time.sleep(3)

        # ---------------------------------------------------------
        # Student login
        # ---------------------------------------------------------

        progress(
            30,
            "🔐 Opening student login..."
        )

        clicked = False

        selectors = [
            "#studentLink",
            "a#studentLink",
            "a[href*='student']",
            "a:has-text('Student')",
            "text=Student",
        ]

        for selector in selectors:

            try:

                locator = page.locator(selector)

                if locator.count() > 0:

                    locator.first.click(
                        timeout=5000
                    )

                    clicked = True
                    break

            except Exception:
                continue

        if not clicked:

            # JavaScript fallback
            try:

                page.evaluate(
                    """
                    () => {
                        const links =
                            document.querySelectorAll('a');

                        for (const link of links) {

                            const text =
                                (link.innerText || '').toLowerCase();

                            const id =
                                (link.id || '').toLowerCase();

                            if (
                                id === 'studentlink'
                                || text.includes('student')
                            ) {
                                link.click();
                                return true;
                            }
                        }

                        return false;
                    }
                    """
                )

            except Exception:
                pass

        time.sleep(3)

        # ---------------------------------------------------------
        # Login form
        # ---------------------------------------------------------

        progress(
            40,
            "🔑 Waiting for login form..."
        )

        login_inputs = None

        possible_selectors = [
            "#stuLogin input.login_box",
            "#stuLogin input",
            "input.login_box",
        ]

        for selector in possible_selectors:

            try:

                locator = page.locator(selector)

                if locator.count() >= 2:

                    login_inputs = locator
                    break

            except Exception:
                continue

        if login_inputs is None:

            # Check page text for diagnostic information
            current_text = get_page_text(page)

            raise RuntimeError(
                "MITS login form was not found. "
                "The IMS website may have changed or may be unavailable. "
                f"Page text: {current_text[:300]}"
            )

        # ---------------------------------------------------------
        # Fill credentials
        # ---------------------------------------------------------

        progress(
            50,
            "🔐 Entering credentials..."
        )

        login_inputs.nth(0).fill(roll)

        time.sleep(0.3)

        login_inputs.nth(1).fill(password)

        time.sleep(0.5)

        # ---------------------------------------------------------
        # Submit
        # ---------------------------------------------------------

        progress(
            55,
            "🚀 Signing into MITS IMS..."
        )

        submitted = False

        submit_selectors = [
            "#stuLogin button[type='submit']",
            "#stuLogin button",
            "#stuLogin input[type='submit']",
            "button[type='submit']",
            "input[type='submit']",
        ]

        for selector in submit_selectors:

            try:

                locator = page.locator(selector)

                if locator.count() > 0:

                    locator.first.click(
                        timeout=5000
                    )

                    submitted = True
                    break

            except Exception:
                continue

        if not submitted:

            try:

                login_inputs.nth(1).press("Enter")
                submitted = True

            except Exception:
                pass

        if not submitted:

            raise RuntimeError(
                "Could not submit the MITS login form."
            )

        # ---------------------------------------------------------
        # Wait for login
        # ---------------------------------------------------------

        progress(
            65,
            "⏳ Waiting for MITS dashboard..."
        )

        # Wait for navigation if possible
        try:

            page.wait_for_load_state(
                "domcontentloaded",
                timeout=15000
            )

        except Exception:
            pass

        # Give JavaScript/ajax enough time
        time.sleep(8)

        # ---------------------------------------------------------
        # Get page text
        # ---------------------------------------------------------

        progress(
            72,
            "📊 Reading attendance information..."
        )

        all_text = get_page_text(page)

        # ---------------------------------------------------------
        # Credential validation
        # ---------------------------------------------------------

        low = all_text.lower()

        invalid_messages = [
            "invalid",
            "incorrect",
            "wrong password",
            "invalid credentials",
            "login failed",
            "authentication failed",
        ]

        for message in invalid_messages:

            if message in low:

                raise RuntimeError(
                    "Invalid credentials. "
                    "Please verify your roll number and password."
                )

        # ---------------------------------------------------------
        # Navigate to attendance
        # ---------------------------------------------------------

        progress(
            80,
            "📚 Finding attendance page..."
        )

        attendance_found = open_attendance_page(page)

        if attendance_found:

            time.sleep(3)

            all_text = get_page_text(page)

        # ---------------------------------------------------------
        # Parse attendance
        # ---------------------------------------------------------

        progress(
            90,
            "🧮 Processing attendance..."
        )

        data = parse_attendance(all_text)

        # ---------------------------------------------------------
        # If parser failed, provide useful error
        # ---------------------------------------------------------

        if not data:

            # Save some information for debugging
            preview = re.sub(
                r"\s+",
                " ",
                all_text
            ).strip()

            raise RuntimeError(
                "Login may have succeeded, but the attendance "
                "table could not be detected. "
                "The MITS IMS page structure may have changed. "
                f"Page preview: {preview[:500]}"
            )

        progress(
            100,
            "✅ Attendance loaded successfully!"
        )

        return data

    except PlaywrightTimeoutError as exc:

        raise RuntimeError(
            "MITS IMS took too long to respond. "
            "The portal may be slow or temporarily unavailable."
        ) from exc

    except Exception as exc:

        raise RuntimeError(
            str(exc)
        ) from exc

    finally:

        # Close browser context
        try:

            if context:
                context.close()

        except Exception:
            pass


# ═════════════════════════════════════════════════════════════════════════════
# MATH FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def pct(attended, conducted):

    if conducted <= 0:
        return 0.0

    return (
        attended / conducted
    ) * 100.0


def classes_needed(attended, conducted, target):

    if (
        target <= 0
        or target >= 100
        or conducted <= 0
        or pct(attended, conducted) >= target
    ):
        return 0

    return max(
        0,
        math.ceil(
            (
                target * conducted
                - 100 * attended
            )
            /
            (100 - target)
        )
    )


def classes_skip(attended, conducted, target):

    if target <= 0 or conducted <= 0:
        return float("inf")

    if pct(attended, conducted) < target:
        return 0

    return max(
        0,
        math.floor(
            (
                100 * attended
                - target * conducted
            )
            /
            target
        )
    )


# ═════════════════════════════════════════════════════════════════════════════
# HEADER
# ═════════════════════════════════════════════════════════════════════════════

st.markdown(
    """
    <style>

    @keyframes slide-full {

        0% {
            transform: translateX(-100vw);
        }

        100% {
            transform: translateX(100vw);
        }

    }

    .floating-title {

        position: relative;
        white-space: nowrap;
        display: inline-block;
        font-size: 28px;
        font-weight: bold;
        color: blue;
        animation: slide-full 25s linear infinite;

    }

    </style>

    <div style="overflow:hidden; width:100%;">

        <div class="floating-title">

            MITS IMS Attendance Tracker by Lingeswar

        </div>

    </div>
    """,
    unsafe_allow_html=True
)


st.markdown(
    """
    <div class="mits-header">

        <div class="mits-title">
            MITS
        </div>

        <div class="mits-subtitle">

            MADANAPALLE INSTITUTE OF TECHNOLOGY &amp; SCIENCE

            <br>

            <h2>
                DEEMED TO BE UNIVERSITY
            </h2>

            Dept. of Computer Science &amp; Engineering

        </div>

    </div>
    """,
    unsafe_allow_html=True
)


# ═════════════════════════════════════════════════════════════════════════════
# HERO
# ═════════════════════════════════════════════════════════════════════════════

st.markdown(
    """
    <div class="hero-box">

        <h2>
            🔥 Smart Attendance Tracker
        </h2>

        <p>
            Track • Analyze • Plan Your Classes
        </p>

    </div>
    """,
    unsafe_allow_html=True
)


# ═════════════════════════════════════════════════════════════════════════════
# WARNING
# ═════════════════════════════════════════════════════════════════════════════

st.markdown(
    """
    <div style="
        background:#ffebee;
        border:3px solid red;
        padding:25px;
        border-radius:12px;
        text-align:center;
        margin-bottom:20px;
    ">

        <span style="
            font-size:30px;
            font-weight:bold;
            color:#b71c1c;
        ">

            ⚠️ Due to Technical Issue Attendance Showing May Be Wrong

        </span>

        <br><br>

        <span style="
            font-size:22px;
            font-weight:bold;
            color:#000;
        ">

            Previous Semester Subjects Are Also Being Added in IMS Portal

        </span>

    </div>
    """,
    unsafe_allow_html=True
)


# ═════════════════════════════════════════════════════════════════════════════
# LOGIN TITLE
# ═════════════════════════════════════════════════════════════════════════════

st.markdown(
    """
    <h3 style="color:red;">
        🔐 Student Login Portal
    </h3>
    """,
    unsafe_allow_html=True
)


st.markdown(
    """
    <div style="
        background:black;
        padding:20px;
        border-radius:10px;
        text-align:center;
    ">

        <h2 style="
            color:yellow;
            margin:0;
        ">

            Enter your MITS IMS credentials

        </h2>

    </div>
    """,
    unsafe_allow_html=True
)


# ═════════════════════════════════════════════════════════════════════════════
# LOGIN FORM
# ═════════════════════════════════════════════════════════════════════════════

with st.form("attendance_form"):

    roll = st.text_input(
        "🎓 Roll Number",
        value=st.session_state.last_roll,
        placeholder="Enter your university roll number"
    )

    password = st.text_input(
        "🔑 Password",
        type="password",
        placeholder="Enter your IMS password"
    )

    submitted = st.form_submit_button(
        "🚀 Fetch Attendance",
        use_container_width=True
    )


# ═════════════════════════════════════════════════════════════════════════════
# LOGIN ACTION
# ═════════════════════════════════════════════════════════════════════════════

if submitted:

    if not roll or not password:

        st.error(
            "❌ Please enter both roll number and password."
        )

    else:

        st.session_state.last_roll = roll.strip()

        progress_bar = st.progress(0)

        status = st.empty()

        try:

            def update_progress(value, message):

                progress_bar.progress(value)

                status.markdown(
                    f"""
                    <p style="
                        color:black;
                        font-weight:bold;
                    ">
                        {message}
                    </p>
                    """,
                    unsafe_allow_html=True
                )

            data = scrape_attendance(
                roll.strip(),
                password,
                progress_callback=update_progress
            )

            st.session_state.attendance_data = data

            progress_bar.progress(100)

            status.markdown(
                """
                <p style="
                    color:green;
                    font-weight:bold;
                ">
                    ✅ Attendance loaded successfully!
                </p>
                """,
                unsafe_allow_html=True
            )

            time.sleep(1)

            progress_bar.empty()
            status.empty()

            st.success(
                f"✅ Loaded {len(data)} subjects!"
            )

            st.balloons()

        except Exception as exc:

            progress_bar.empty()
            status.empty()

            st.error(
                f"❌ Error: {exc}"
            )

            st.info(
                """
                💡 If this happens repeatedly on the deployed website
                but works on your computer, the problem is most likely
                the deployment server's browser/network environment,
                not your MITS credentials.
                """
            )


# ═════════════════════════════════════════════════════════════════════════════
# RESULTS
# ═════════════════════════════════════════════════════════════════════════════

if st.session_state.attendance_data:

    df = pd.DataFrame(
        st.session_state.attendance_data
    )

    df.columns = [
        "S.No",
        "Subject",
        "Attended",
        "Conducted",
        "Percentage"
    ]

    df["Attended"] = df["Attended"].astype(int)

    df["Conducted"] = df["Conducted"].astype(int)

    df["Pct"] = df.apply(
        lambda row: pct(
            row["Attended"],
            row["Conducted"]
        ),
        axis=1
    )

    # ---------------------------------------------------------
    # Overall calculations
    # ---------------------------------------------------------

    total_attended = int(
        df["Attended"].sum()
    )

    total_conducted = int(
        df["Conducted"].sum()
    )

    overall_percentage = pct(
        total_attended,
        total_conducted
    )

    # ---------------------------------------------------------
    # Metrics
    # ---------------------------------------------------------

    m1, m2, m3 = st.columns(3)

    m1.markdown(
        f"""
        <div style="
            background-color:#f0f2f6;
            padding:20px;
            border-radius:10px;
            text-align:center;
        ">

            <span style="
                font-size:18px;
                color:black;
            ">

                📊 Overall Attendance

            </span>

            <br>

            <span style="
                font-size:28px;
                font-weight:bold;
                color:black;
            ">

                {overall_percentage:.1f}%

            </span>

        </div>
        """,
        unsafe_allow_html=True
    )

    m2.markdown(
        f"""
        <div style="
            background-color:#f0f2f6;
            padding:20px;
            border-radius:10px;
            text-align:center;
        ">

            <span style="
                font-size:18px;
                color:black;
            ">

                ✅ Total Attended

            </span>

            <br>

            <span style="
                font-size:28px;
                font-weight:bold;
                color:black;
            ">

                {total_attended}

            </span>

        </div>
        """,
        unsafe_allow_html=True
    )

    m3.markdown(
        f"""
        <div style="
            background-color:#f0f2f6;
            padding:20px;
            border-radius:10px;
            text-align:center;
        ">

            <span style="
                font-size:18px;
                color:black;
            ">

                📚 Total Conducted

            </span>

            <br>

            <span style="
                font-size:28px;
                font-weight:bold;
                color:black;
            ">

                {total_conducted}

            </span>

        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <p style="
            color:black;
            font-size:16px;
        ">

            Simple average across subjects:
            <strong>
                {df["Pct"].mean():.1f}%
            </strong>

        </p>
        """,
        unsafe_allow_html=True
    )

    # ---------------------------------------------------------
    # Attendance table
    # ---------------------------------------------------------

    st.markdown(
        """
        <h4 style="color:black;">
            📈 Attendance Details
        </h4>
        """,
        unsafe_allow_html=True
    )

    def color_percentage(value):

        try:

            percentage = float(
                str(value).replace("%", "")
            )

        except Exception:

            return ""

        if percentage >= 75:

            return (
                "background-color:#d4edda;"
                "color:#155724;"
                "font-weight:bold"
            )

        if percentage >= 60:

            return (
                "background-color:#fff3cd;"
                "color:#856404"
            )

        return (
            "background-color:#f8d7da;"
            "color:#721c24;"
            "font-weight:bold"
        )

    display_df = df[
        [
            "S.No",
            "Subject",
            "Attended",
            "Conducted",
            "Pct"
        ]
    ].copy()

    display_df["Pct"] = display_df[
        "Pct"
    ].map(
        lambda value: f"{value:.2f}%"
    )

    display_df = display_df.rename(
        columns={
            "Pct": "Percentage"
        }
    )

    st.dataframe(
        display_df.style.map(
            color_percentage,
            subset=["Percentage"]
        ),
        use_container_width=True
    )

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    st.markdown(
        """
        <h3 style="color:#2e7d32;">
            📊 Attendance Summary
        </h3>
        """,
        unsafe_allow_html=True
    )

    target = 75

    st.markdown(
        f"""
        <p style="
            color:red;
            font-weight:bold;
            font-size:18px;
        ">

            Overall: {overall_percentage:.2f}%

        </p>
        """,
        unsafe_allow_html=True
    )

    st.progress(
        min(overall_percentage, 100.0) / 100.0
    )

    summary1, summary2 = st.columns(2)

    below_target = int(
        (df["Pct"] < target).sum()
    )

    summary1.markdown(
        f"""
        <div style="
            background:linear-gradient(
                to right,
                #ffebee,
                #ffcdd2
            );

            padding:20px;
            border-radius:12px;
            text-align:center;
        ">

            <div style="
                font-size:18px;
                color:#c62828;
                font-weight:bold;
            ">

                ⚠️ Subjects Below Target

            </div>

            <div style="
                font-size:28px;
                font-weight:bold;
                color:#b71c1c;
            ">

                {below_target}

            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    # ---------------------------------------------------------
    # Best subject
    # ---------------------------------------------------------

    best_subject = df.sort_values(
        "Pct",
        ascending=False
    ).iloc[0]

    summary2.markdown(
        f"""
        <div style="
            background:linear-gradient(
                to right,
                #e8f5e9,
                #c8e6c9
            );

            padding:20px;
            border-radius:12px;
            text-align:center;
        ">

            <div style="
                font-size:18px;
                color:#2e7d32;
                font-weight:bold;
            ">

                ⭐ Best Subject

            </div>

            <div style="
                font-size:22px;
                font-weight:bold;
                color:#1b5e20;
            ">

                {str(best_subject["Subject"])[:22]}
                ({best_subject["Pct"]:.1f}%)

            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    # ---------------------------------------------------------
    # Chart
    # ---------------------------------------------------------

    st.bar_chart(
        df.set_index("Subject")["Pct"],
        height=400
    )

    # ---------------------------------------------------------
    # Attendance Strategy
    # ---------------------------------------------------------

    with st.expander(
        "🎯 Attendance Strategy"
    ):

        selected_subject = st.selectbox(
            "Choose subject",
            df["Subject"].tolist()
        )

        selected_row = df[
            df["Subject"] == selected_subject
        ].iloc[0]

        attended = int(
            selected_row["Attended"]
        )

        conducted = int(
            selected_row["Conducted"]
        )

        subject_percentage = float(
            selected_row["Pct"]
        )

        st.markdown(
            f"""
            <div style="
                background:#f5f5f5;
                padding:10px;
                border-radius:8px;
                color:black;
                font-weight:bold;
            ">

                {selected_subject}
                —
                current: {subject_percentage:.2f}%

            </div>
            """,
            unsafe_allow_html=True
        )

        if subject_percentage >= target:

            skip = classes_skip(
                attended,
                conducted,
                target
            )

            st.markdown(
                f"""
                <div style="
                    color:green;
                    font-weight:bold;
                ">

                    ✅ Already above {target}%.

                </div>
                """,
                unsafe_allow_html=True
            )

            skip_value = (
                "∞"
                if skip == float("inf")
                else str(int(skip))
            )

            st.markdown(
                f"""
                <div style="
                    color:orange;
                    font-weight:bold;
                ">

                    Can skip up to
                    <span style="color:red;">
                        {skip_value}
                    </span>
                    class(es).

                </div>
                """,
                unsafe_allow_html=True
            )

        else:

            needed = classes_needed(
                attended,
                conducted,
                target
            )

            st.markdown(
                f"""
                <div style="
                    background:#e6f2ff;
                    padding:10px;
                    border-radius:8px;
                    color:black;
                    font-weight:bold;
                ">

                    Need
                    <span style="color:red;">
                        {int(needed)}
                    </span>
                    more classes to reach {target}%.

                </div>
                """,
                unsafe_allow_html=True
            )

    # ---------------------------------------------------------
    # Download
    # ---------------------------------------------------------

    st.download_button(
        "📥 Download CSV",
        display_df.to_csv(index=False),
        file_name=(
            f"MITS_attendance_"
            f"{st.session_state.last_roll}.csv"
        ),
        mime="text/csv",
        use_container_width=True
    )


# ═════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═════════════════════════════════════════════════════════════════════════════

st.markdown("---")

st.markdown(
    """
    <div class="footer">

        © 2026 MITS Attendance Tracker
        | Made with ❤️ for CSE Dept

        <br>

        Built by <strong>Lingeswar</strong>

    </div>
    """,
    unsafe_allow_html=True
)
