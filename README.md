# 🎓 MITS IMS Attendance Tracker

**MITS IMS Attendance Tracker** is a smart Streamlit web application designed for students of **Madanapalle Institute of Technology & Science**. It automatically fetches your attendance from the IMS portal and provides real-time analytics to help you manage your classes strategically.

🚀 **Live App:** [mits-attendence-tracker-lingeswar.streamlit.app](https://mits-attendence-tracker-lingeswar.streamlit.app/)

---

## ✨ Features

### 🔐 Automated Scraper
- **Zero Manual Entry:** Securely logs into the [MITS IMS Portal](http://mitsims.in) using Playwright.
- **Deep Extraction:** Navigates through portal iframes to pull precise subject-wise data.
- **Session Based:** Your credentials are used only for the active fetch and are never stored.

### 📊 Attendance Dashboard
- **Overall Metrics:** View Total Attended vs. Total Conducted classes.
- **Visual Progress:** Dynamic progress bars and color-coded indicators:
  - 🟢 **Green (≥75%)**: Safe zone.
  - 🟡 **Yellow (60-74%)**: Warning zone.
  - 🔴 **Red (<60%)**: Critical/Low attendance.
- **Interactive Charts:** High-quality bar charts comparing attendance across all subjects.

### 🎯 Attendance Strategy (Smart Math)
The app calculates exactly what you need to do to maintain or reach the **75% target**:

1. **Classes to Attend**: If you are below 75%, it calculates the required "streak" of classes needed.
   $$x = \lceil \frac{0.75 \cdot C - A}{0.25} \rceil$$
2. **Classes to Skip**: If you are above 75%, it calculates how many classes you can safely miss without dropping below the threshold.
   $$x = \lfloor \frac{A - 0.75 \cdot C}{0.75} \rfloor$$

---

## 🚀 Quick Start (Local Setup)

### Prerequisites
- Python 3.9 or higher
- [Playwright](https://playwright.dev/python/)

### Installation

1. **Clone the repository**
   ```bash
   git clone [https://github.com/lingeswar/mits-attendance-tracker.git]
   cd mits-attendance-tracker
   ---

## 📄 License

This project is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for the full text. 

*Summary: You are free to use, copy, and modify this software, but it is provided "as-is" without any warranty.*