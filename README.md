# 📚 Attendance Tracker

**Attendance Tracker** is a powerful Streamlit web application that automatically scrapes your attendance data from the [MITS IMS Portal](http://mitsims.in) and provides intelligent calculators to help you strategically plan your classes!

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://ims-tracker.streamlit.app/)

---

## ✨ Features

### 🔐 Automated Data Scraping
- Securely logs into MIT SIMS using Playwright automation
- Fetches real-time attendance data for all your subjects
- No manual data entry required!

### 📊 Visual Dashboard
- Clear attendance summary with color-coded indicators
- Subject-wise breakdown with percentages
- Overall attendance metrics at a glance

### 🧮 Smart Calculators
**1. Classes to Attend Calculator**
- Calculate exactly how many classes you need to reach your target percentage
- Formula: `x = (T × C - 100 × A) / (100 - T)`

**2. Classes to Skip Calculator**
- Find out how many classes you can safely skip
- Formula: `x = (100 × A - T × C) / T`

### 📈 Additional Features
- **Color-Coded Indicators**
  - 🟢 Green (≥75%): Good attendance
  - 🟡 Yellow (60-74%): Moderate attendance
  - 🔴 Red (<60%): Low attendance
- **CSV Export**: Download your attendance data
- **Mobile Responsive**: Works on all devices
- **Real-time Calculations**: Instant results with formula breakdown

---

## 🧮 How It Works

### Example Calculation

**Current Status:**
- Total Attended (A) = 274 classes
- Total Conducted (C) = 361 classes
- Current Percentage = 75.9%

**Scenario 1: Reach 76% attendance**
x = (76 × 361 - 100 × 274) / (100 - 76)
x = (27,436 - 27,400) / 24
x = 36 / 24 = 1.5 ≈ 2 classes

text
✅ **Result: Attend 2 more classes**

**Scenario 2: Maintain 75% while skipping**
x = (100 × 274 - 75 × 361) / 75
x = (27,400 - 27,075) / 75
x = 325 / 75 = 4.33 ≈ 4 classes

text
✅ **Result: Can skip 4 classes safely**

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Git

### Installation

1. **Clone the repository**
git clone [REPO](https://github.com/likith2615/attendence_traker/)
cd attendance_tracker

text

2. **Install dependencies**
pip install -r requirements.txt

text

3. **Install Playwright browsers**
playwright install chromium

text

4. **Run the app**
streamlit run app.py

text

The app will open in your browser at `http://localhost:8501`

---

## 🌐 Deploy to Streamlit Cloud

1. Push this repo to your GitHub account
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Click **New App**
4. Select your repository and set `app.py` as the main file
5. Click **Deploy**!

---

## 📁 Project Structure
'''
attendance_tracker/
│
├── app.py # Main Streamlit application
├── requirements.txt # Python dependencies
├── packages.txt # System packages (optional)
├── README.md # This file
└── .streamlit/
└── config.toml # Streamlit configuration
'''
text

---

## 🛠️ Tech Stack

- **Frontend & Backend**: Streamlit
- **Web Automation**: Playwright (Python)
- **Data Processing**: Pandas
- **Deployment**: Streamlit Cloud

---

## 📸 Screenshots

### Main Dashboard
![Dashboard](https://i.postimg.cc/G3ftpzYL/Screenshot-2025-10-25-130955.png)



## 🔒 Security & Privacy

- ✅ Your credentials are **never stored**
- ✅ All scraping happens in your browser session
- ✅ No data is saved on our servers
- ✅ Open-source code for full transparency

---

## 🧪 Local Development

Create virtual environment
python -m venv venv

Activate it
Windows:
venv\Scripts\activate

Mac/Linux:
source venv/bin/activate

Install dependencies
pip install -r requirements.txt

Install Playwright
playwright install chromium

Run app
streamlit run app.py

text

---

## 📝 Requirements

**requirements.txt:**
streamlit
pandas
playwright

text

**packages.txt** (for Streamlit Cloud):
chromium

text

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Developed by [Likith Kumar Chippe](https://www.linkedin.com/in/likith-kumar-chippe/)**

Connect with me:
- [🔗 LinkedIn](https://www.linkedin.com/in/likith-kumar-chippe/)
- [📸 Instagram](https://instagram.com/ft_._likith)

---

## ⭐ Show Your Support

If this project helped you, please give it a ⭐ on GitHub!

---

## 🐛 Known Issues

- First deployment may take 2-3 minutes for Playwright to install
- Scraping may take 30-60 seconds depending on portal response time

---

## 📬 Contact

For questions or support, please open an issue or reach out via LinkedIn.

---

*Made with ❤️ using Streamlit and Playwright*
