# JobIQ

JobIQ is a simple web-based project that analyzes uploaded CVs and provides relevant job recommendations.  
It contains a **Python backend** (API / logic) and a **HTML-CSS frontend** for the user interface.

---

## 🗂️ Project Structure

```
JobIQ/
│
├── backend/
│   ├── main.py             # main backend script
│   ├── models.py           # additional Python modules
│   ├── requirements.txt    # list of Python dependencies
│   ├── .env                # environment variables (not uploaded)
│   └── venv/               # local virtual environment (ignored)
│
├── frontend/
│   ├── index.html
│   ├── index.css
│   ├── login.html
│   ├── analyze.html
│   ├── result.html
│   └── upload_cv.html
│
└── .gitignore
```

---

## ⚙️ Setup Instructions

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/yash-vikas-kale/JobIQ.git
cd JobIQ/backend
```

### 2️⃣ Create a Virtual Environment
```bash
python -m venv venv
```

### 3️⃣ Activate the Virtual Environment
#### On Windows:
```bash
venv\Scripts\activate
```
#### On macOS / Linux:
```bash
source venv/bin/activate
```

### 4️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```

### 5️⃣ Install Gemini
```bash
pip install google-generativeai
```

### 6️⃣ Set Up Environment Variables
Create `.env` inside `backend` with:
```
API_KEY=your_api_key_here
DATABASE_URL=your_database_url_here
```

### 7️⃣ Run the Backend
```bash
python main.py
```

Server runs at `http://127.0.0.1:8000`

### 8️⃣  View the Frontend
Open `frontend/index.html` in your browser.

---

## 🧰 Notes
* Do not upload `.env` or `venv` to GitHub.
* To commit changes:
  ```bash
  git add .
  git commit -m "update"
  git push
  ```
* To deactivate:
  ```bash
  deactivate
  ```

---

## 👤 Team Member
**Yash Kale** <br>
**Jitesh Choudhary** <br>
**Ruturaj Borawake** <br>
**Ayush Saraf** <br>
