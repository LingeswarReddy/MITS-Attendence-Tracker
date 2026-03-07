import streamlit as st
import pandas as pd
import math
import subprocess
import sys
import os
import tempfile
import json
import textwrap

# ── session state ──────────────────────────────────────────────────────────
for key, default in [
    ("attendance_data", None),
    ("last_roll", ""),
    ("show_overall_calc", False),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── playwright install ─────────────────────────────────────────────────────
@st.cache_resource
def install_playwright_browsers():
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True, capture_output=True, timeout=300, text=True,
        )
        return True
    except Exception:
        return False

install_playwright_browsers()

# ── page config & CSS ──────────────────────────────────────────────────────
st.set_page_config(page_title="MITS IMS Attendance Portal", page_icon="🎓", layout="wide")
st.markdown("""
<style>
.stApp { background: linear-gradient(to right, #f5f7fa, #e4ecf7); }
.mits-header { text-align: center; padding: 20px; }
.mits-title  { font-size: 48px; font-weight: bold; color: #d32f2f; }
.mits-subtitle { font-size: 20px; color: #1e3c72; margin-top: -10px; }
.hero-box {
    background: linear-gradient(to right, #1e3c72, #2a5298);
    padding: 40px; border-radius: 15px; text-align: center;
    color: white; margin-bottom: 30px;
    box-shadow: 0px 8px 20px rgba(0,0,0,0.2);
}
.login-card {
    background: white; padding: 30px; border-radius: 15px;
    box-shadow: 0px 6px 18px rgba(0,0,0,0.1);
}
.footer { text-align: center; padding: 30px; font-size: 14px; color: gray; }
.login-text {
    color: #f5a623; font-weight: bold; font-style: italic;
    font-size: 22px; text-align: center;
}
</style>
""", unsafe_allow_html=True)


# ── scraper code written as a clean separate file ─────────────────────────
SCRAPER_CODE = textwrap.dedent('''\
import asyncio
import sys
import json
import subprocess

try:
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        capture_output=True, timeout=60
    )
except Exception:
    pass

from playwright.async_api import async_playwright
from playwright.async_api import TimeoutError as PWTimeout


async def get_all_text(ctx):
    """
    Collect innerText from every open page and every iframe inside each page.
    Returns one big combined string.
    """
    chunks = []
    for pg in ctx.pages:
        try:
            t = await pg.evaluate("() => document.body ? document.body.innerText : ''")
            if t:
                chunks.append(t)
        except Exception:
            pass
        # also check iframes
        try:
            frames = pg.frames
            for fr in frames:
                try:
                    t = await fr.evaluate("() => document.body ? document.body.innerText : ''")
                    if t:
                        chunks.append(t)
                except Exception:
                    pass
        except Exception:
            pass
    return "\\n".join(chunks)


def parse_attendance(text):
    lines = [l.strip() for l in text.split("\\n") if l.strip()]

    start = -1
    for i in range(1, len(lines) - 1):
        if (lines[i] == "CLASSES ATTENDED" and
                lines[i - 1] == "SUBJECT CODE" and
                lines[i + 1] == "TOTAL CONDUCTED"):
            start = i + 3
            break

    # fallback: find "attended" near "conducted"
    if start == -1:
        for i in range(len(lines) - 1):
            if ("attended" in lines[i].lower() and
                    "conduct" in lines[i + 1].lower()):
                start = i + 2
                break

    if start == -1:
        return []

    result = []
    i = start
    while i + 3 < len(lines):
        sno  = lines[i]
        subj = lines[i + 1]
        att  = lines[i + 2]
        cond = lines[i + 3]
        pct  = lines[i + 4] if i + 4 < len(lines) else "0"

        if not sno or not subj or not att or not cond:
            break
        if "note" in sno.lower() or "note" in subj.lower():
            break
        if "@" in sno or "@" in subj:
            break
        if not sno.isdigit() or not att.isdigit() or not cond.isdigit():
            i += 1
            continue

        result.append({
            "s_no":       sno,
            "subject":    subj,
            "attended":   att,
            "conducted":  cond,
            "percentage": pct + "%"
        })
        i += 5

    return result


async def main(roll, password):
    pw = None
    browser = None
    try:
        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-zygote",
            ],
        )
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await ctx.new_page()

        # ── 1. Homepage ───────────────────────────────────────────────────
        await page.goto("http://mitsims.in/", wait_until="domcontentloaded", timeout=40000)
        await asyncio.sleep(3)

        # ── 2. Student login tab ──────────────────────────────────────────
        clicked = False
        for sel in ["a#studentLink", "#studentLink", "a[href*=student]"]:
            try:
                await page.click(sel, timeout=5000)
                clicked = True
                break
            except Exception:
                pass

        if not clicked:
            # JS fallback
            await page.evaluate("""
() => {
    var all = document.querySelectorAll('a');
    for (var i = 0; i < all.length; i++) {
        if (all[i].id === 'studentLink' ||
            (all[i].innerText && all[i].innerText.toLowerCase().indexOf('student') !== -1)) {
            all[i].click();
            break;
        }
    }
}
""")
        await asyncio.sleep(3)

        # ── 3. Wait for login form ────────────────────────────────────────
        form_found = False
        for _ in range(12):
            try:
                await page.wait_for_selector(
                    "#stuLogin input.login_box", state="visible", timeout=2000
                )
                form_found = True
                break
            except PWTimeout:
                await asyncio.sleep(1)

        if not form_found:
            await browser.close()
            await pw.stop()
            print(json.dumps({"success": False, "error": "Login form not found — site may be down"}))
            return

        # ── 4. Fill credentials ───────────────────────────────────────────
        # Use page.fill — most reliable Playwright Python API
        try:
            await page.fill("#stuLogin input.login_box:nth-of-type(1)", roll)
            await asyncio.sleep(0.3)
            await page.fill("#stuLogin input.login_box:nth-of-type(2)", password)
        except Exception:
            # fallback: fill by index using locator
            inputs = page.locator("#stuLogin input.login_box")
            await inputs.nth(0).fill(roll)
            await asyncio.sleep(0.3)
            await inputs.nth(1).fill(password)

        await asyncio.sleep(0.5)

        # ── 5. Submit ─────────────────────────────────────────────────────
        submitted = False
        for btn in [
            "#stuLogin button[type=submit]",
            "#stuLogin button",
            "#stuLogin input[type=submit]",
        ]:
            try:
                await page.click(btn, timeout=5000)
                submitted = True
                break
            except Exception:
                pass

        if not submitted:
            # try pressing Enter on the password field
            try:
                loc = page.locator("#stuLogin input.login_box").nth(1)
                await loc.press("Enter")
                submitted = True
            except Exception:
                pass

        if not submitted:
            print(json.dumps({"success": False, "error": "Could not click submit button"}))
            await browser.close()
            await pw.stop()
            return

        # ── 6. Wait for dashboard to load (use asyncio, NOT page methods) ─
        # Give the site up to 20 s to fully load after login
        await asyncio.sleep(20)

        # ── 7. Collect text from ALL pages + iframes ──────────────────────
        all_text = await get_all_text(ctx)

        # If still empty, wait more and try again
        if len(all_text.strip()) < 50:
            await asyncio.sleep(10)
            all_text = await get_all_text(ctx)

        # ── 8. Check credentials ──────────────────────────────────────────
        low = all_text.lower()
        if len(all_text.strip()) < 20:
            # truly blank — likely login failed silently
            await browser.close()
            await pw.stop()
            print(json.dumps({"success": False, "error": "Page blank after login — please verify credentials"}))
            return

        if "invalid" in low or "incorrect" in low or "wrong password" in low:
            await browser.close()
            await pw.stop()
            print(json.dumps({"success": False, "error": "Invalid credentials — check roll number / password"}))
            return

        # ── 9. Try to navigate to attendance page if not already there ────
        if "attended" not in low and "conducted" not in low:
            # Try clicking any attendance link
            for pg in ctx.pages:
                try:
                    for att_sel in [
                        "a[href*=attendance]",
                        "a[href*=Attendance]",
                        "a[href*=attd]",
                        "a[href*=ATTD]",
                    ]:
                        links = await pg.query_selector_all(att_sel)
                        if links:
                            await links[0].click()
                            await asyncio.sleep(8)
                            break
                except Exception:
                    pass

            # re-collect text
            all_text = await get_all_text(ctx)

        # ── 10. Parse ─────────────────────────────────────────────────────
        data = parse_attendance(all_text)

        await browser.close()
        await pw.stop()

        if data:
            print(json.dumps({"success": True, "data": data}))
        else:
            print(json.dumps({
                "success": False,
                "error": "Logged in but could not find attendance table. Site layout may have changed."
            }))

    except Exception as exc:
        try:
            if browser:
                await browser.close()
        except Exception:
            pass
        try:
            if pw:
                await pw.stop()
        except Exception:
            pass
        print(json.dumps({"success": False, "error": str(exc)}))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], sys.argv[2]))
''')


def scrape_attendance(roll: str, password: str) -> list:
    fd, path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(SCRAPER_CODE)

        env = os.environ.copy()
        env["PLAYWRIGHT_BROWSERS_PATH"] = os.path.expanduser("~/.cache/ms-playwright")

        try:
            proc = subprocess.run(
                [sys.executable, path, roll, password],
                capture_output=True, text=True, timeout=180, env=env,
            )
        except subprocess.TimeoutExpired:
            raise Exception("Timed out after 180 s — please try again")
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass

    if proc.returncode != 0:
        raise Exception(f"Scraper crashed:\n{proc.stderr.strip()[:400]}")

    stdout = proc.stdout.strip()
    if not stdout:
        raise Exception(f"No output from scraper.\nstderr: {proc.stderr.strip()[:300]}")

    json_line = ""
    for line in reversed(stdout.splitlines()):
        if line.strip().startswith("{"):
            json_line = line.strip()
            break

    if not json_line:
        raise Exception(f"No JSON in output:\n{stdout[:300]}")

    try:
        result = json.loads(json_line)
    except json.JSONDecodeError as e:
        raise Exception(f"JSON parse error: {e}")

    if not result.get("success"):
        raise Exception(result.get("error", "Unknown error"))

    return result.get("data", [])


# ── math helpers ───────────────────────────────────────────────────────────
def pct(a, c):
    return (a / c * 100.0) if c > 0 else 0.0

def classes_needed(a, c, t):
    if t <= 0 or t >= 100 or c <= 0 or pct(a, c) >= t:
        return 0
    return max(0, math.ceil((t * c - 100 * a) / (100 - t)))

def classes_skip(a, c, t):
    if t <= 0 or c <= 0:
        return float("inf")
    if pct(a, c) < t:
        return 0
    return max(0, math.floor((100 * a - t * c) / t))


# ══════════════════════════════════════════════════════════════════════════
#  UI
# ══════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@keyframes slide-full {
    0%   { transform: translateX(-100vw); }
    100% { transform: translateX(100vw); }
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
""", unsafe_allow_html=True)
st.markdown("""
<div class="mits-header">
  <div class="mits-title">MITS</div>
  <div class="mits-subtitle">
    MADANAPALLE INSTITUTE OF TECHNOLOGY &amp; SCIENCE<br>
    <h2>DEEMED TO BE UNIVERSITY</h2>
    Dept. of Computer Science &amp; Engineering
  </div>
</div>""", unsafe_allow_html=True)

st.markdown("""
<div class="hero-box">
  <h2>🔥 Smart Attendance Tracker</h2>
  <p>Track &bull; Analyze &bull; Plan Your Classes</p>
</div>""", unsafe_allow_html=True)
st.markdown("""
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
""", unsafe_allow_html=True)
st.markdown('<h3 style="color:red;">🔐 Student Login Portal</h3>', unsafe_allow_html=True)
st.markdown("""
<div style="background:black; padding:20px; border-radius:10px;text-align:center;">
  <h2 style="color:yellow; margin:0;">
    Enter your MITS IMS credentials
  </h2>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.login-text {
    color: yellow;
    font-weight: bold;
}

label {
    color: black !important;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)
# ── login form ─────────────────────────────────────────────────────────────
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
if submitted:
    if not roll or not password:
        st.error("❌ Please enter both roll number and password")
    else:
        st.session_state.last_roll = roll
        bar  = st.progress(0)
        info = st.empty()
        try:
            info.markdown("<span style='color:black;'>🔍 Launching browser…</span>", unsafe_allow_html=True)
            bar.progress(10)
            info.markdown("<span style='color:black;'>🔐 Logging into MITS IMS…</span>", unsafe_allow_html=True)
            bar.progress(30)
            info.markdown("<span style='color:black;'>📊 Attendance is loaded from IMS Portal — please wait up to 60 s…</span>", unsafe_allow_html=True)
            bar.progress(60)

            data = scrape_attendance(roll, password)

            bar.progress(100)
            info.markdown("<span style='color:black;'>✅ Done!</span>", unsafe_allow_html=True)
            bar.empty()
            info.empty()

            st.session_state.attendance_data = data
            st.success(f"✅ Loaded {len(data)} subjects!")
            st.balloons()

        except Exception as e:
            bar.empty()
            info.empty()
            st.error(f"❌ Error: {e}")

# ── results ────────────────────────────────────────────────────────────────
if st.session_state.attendance_data:
    df = pd.DataFrame(st.session_state.attendance_data)
    df.columns = ["S.No", "Subject", "Attended", "Conducted", "Percentage"]
    df["Attended"]  = df["Attended"].astype(int)
    df["Conducted"] = df["Conducted"].astype(int)
    df["Pct"] = df.apply(lambda r: pct(r["Attended"], r["Conducted"]), axis=1)

    ta = int(df["Attended"].sum())
    tc = int(df["Conducted"].sum())
    op = pct(ta, tc)

    m1, m2, m3 = st.columns(3)
    m1.markdown(
    f"<div style='background-color:#f0f2f6; padding:20px; border-radius:10px; text-align:center;'>"
    f"<span style='font-size:18px; color:black;'>📊 Overall Attendance</span><br>"
    f"<span style='font-size:28px; font-weight:bold; color:black;'>{op:.1f}%</span>"
    f"</div>", unsafe_allow_html=True
    )
    m2.markdown(
    f"<div style='background-color:#f0f2f6; padding:20px; border-radius:10px; text-align:center;'>"
    f"<span style='font-size:18px; color:black;'>✅ Total Attended</span><br>"
    f"<span style='font-size:28px; font-weight:bold; color:black;'>{ta}</span>"
    f"</div>", unsafe_allow_html=True
    )
    m3.markdown(
    f"<div style='background-color:#f0f2f6; padding:20px; border-radius:10px; text-align:center;'>"
    f"<span style='font-size:18px; color:black;'>📚 Total Conducted</span><br>"
    f"<span style='font-size:28px; font-weight:bold; color:black;'>{tc}</span>"
    f"</div>", unsafe_allow_html=True
    )
    st.markdown(
    f"<p style='color:black; font-size:16px;'>Simple average across subjects: {df['Pct'].mean():.1f}%</p>", 
    unsafe_allow_html=True
    )

    st.markdown("<h4 style='color:black;'>📈 Attendance Details</h4>", unsafe_allow_html=True)

    def color_pct(val):
        try:
            p = float(str(val).rstrip("%"))
        except Exception:
            return ""
        if p >= 75:
            return "background-color:#d4edda;color:#155724;font-weight:bold"
        if p >= 60:
            return "background-color:#fff3cd;color:#856404"
        return "background-color:#f8d7da;color:#721c24;font-weight:bold"

    disp = df[["S.No", "Subject", "Attended", "Conducted", "Pct"]].copy()
    disp["Pct"] = disp["Pct"].map(lambda x: f"{x:.2f}%")
    disp = disp.rename(columns={"Pct": "Percentage"})
    st.dataframe(disp.style.map(color_pct, subset=["Percentage"]), use_container_width=True)

    st.markdown("<h3 style='color:#2e7d32;'>📊 Attendance Summary</h3>", unsafe_allow_html=True)
    tgt = 75
    st.markdown(
    f"<p style='color:red; font-weight:bold; font-size:18px;'>Overall: {op:.2f}%</p>",
    unsafe_allow_html=True
    )
    st.progress(min(op, 100.0) / 100.0)
    i1, i2 = st.columns(2)
    i1.markdown(
    f"""
    <div style='background: linear-gradient(to right, #ffebee, #ffcdd2);
                padding:20px;
                border-radius:12px;
                text-align:center;'>
        <div style='font-size:18px; color:#c62828; font-weight:bold;'>
            ⚠️ Subjects Below Target
        </div>
        <div style='font-size:28px; font-weight:bold; color:#b71c1c;'>
            {int((df["Pct"] < tgt).sum())}
        </div>
    </div>
    """,
    unsafe_allow_html=True
    )
    best = df.sort_values("Pct", ascending=False).iloc[0]
    i2.markdown(
    f"""
    <div style='background: linear-gradient(to right, #e8f5e9, #c8e6c9);
                padding:20px;
                border-radius:12px;
                text-align:center;'>
        <div style='font-size:18px; color:#2e7d32; font-weight:bold;'>
            ⭐ Best Subject
        </div>
        <div style='font-size:22px; font-weight:bold; color:#1b5e20;'>
            {str(best['Subject'])[:22]}… ({best['Pct']:.1f}%)
        </div>
    </div>
    """,
    unsafe_allow_html=True
    )
    st.bar_chart(df.set_index("Subject")["Pct"], height=400)
    st.markdown("""
    <style>
    div[data-testid="stExpander"] summary {
    color: black !important;
    font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)
    with st.expander("🎯 Attendance Strategy"):
        sel = st.selectbox("Choose subject", df["Subject"].tolist())
        r   = df[df["Subject"] == sel].iloc[0]
        sa, sc, sp = int(r["Attended"]), int(r["Conducted"]), float(r["Pct"])
        st.markdown(
            f"<div style='background:#f5f5f5; padding:10px; border-radius:8px; "
            f"color:black; font-weight:bold;'>"
            f"{sel} — current: {sp:.2f}%"
            f"</div>",
            unsafe_allow_html=True
        )
        if sp >= tgt:
            sk = classes_skip(sa, sc, tgt)
            st.markdown(
                f"<div style='color:green; font-weight:bold;'>"
                f"✅ Already above {tgt}%."
                f"</div>",
                unsafe_allow_html=True
            )
            st.markdown(
                f"<div style='color:orange; font-weight:bold;'>"
                f"Can skip up to <span style='color:red;'>"
                f"{'∞' if sk == float('inf') else int(sk)}"
                f"</span> class(es)."
                f"</div>",
                unsafe_allow_html=True
            )
        else:
            nd = classes_needed(sa, sc, tgt)
            st.markdown(
                f"<div style='background:#e6f2ff; padding:10px; border-radius:8px; "
                f"color:black; font-weight:bold;'>"
                f"Need <span style='color:red;'>{int(nd)}</span> more classes "
                f"to reach {tgt}%."
                f"</div>",
                unsafe_allow_html=True
            )



    st.download_button(
        "📥 Download CSV", disp.to_csv(index=False),
        f"MITS_attendance_{st.session_state.last_roll}.csv",
        "text/csv", use_container_width=True,
    )
st.markdown("---")
st.markdown("""
<div class="footer">
  © 2026 MITS Attendance Tracker | Made with ❤️ for CSE Dept<br>
  Built by <strong>Lingeswar</strong>

</div>""", unsafe_allow_html=True)
