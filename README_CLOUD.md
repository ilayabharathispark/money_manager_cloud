# 💰 Money Manager Cloud (Product Edition)

A multi-tenant, AI-powered personal finance management application ready for deployment on **Google Cloud Run** with **zero idle hosting cost ($0/month)**.

Any user can sign up, configure their own bank alert sender email and AI keys, and automatically sync and categorize their expenses in an Apple Liquid Glass dashboard.

---

## 🏗️ Architecture & Features

```
D:\money_manager_cloud\
├── app/
│   ├── dashboard.py         ← Apple Liquid Glass UI, Auth & Multi-Tab Analytics
│   ├── database.py          ← Multi-tenant SQLite engine (Per-user private DBs)
│   ├── sync.py              ← User-scoped concurrent sync orchestrator
│   ├── email_reader.py      ← Dual sync (Gmail App Password IMAP + OAuth 2.0)
│   ├── ai_parser.py         ← Gemini 2.5 Flash / Groq parser with per-user keys
│   └── categories.py        ← Categorization taxonomy & merchant classifier
├── scripts/
│   └── validate_db.py       ← SQLite PRAGMA integrity check & diagnostic tool
├── data/
│   ├── auth.db              ← Salted SHA-256 user authentication credentials
│   └── users/
│       ├── user_1.db        ← User 1 isolated database
│       └── user_2.db        ← User 2 isolated database
├── .streamlit/
│   └── config.toml          ← Cloud Run headless production configuration
├── Dockerfile               ← Lightweight, optimized container image
├── deploy_cloud_run.bat     ← One-click Windows deployment script
├── deploy_cloud_run.sh      ← One-click Linux/Mac deployment script
├── requirements.txt         ← Production dependencies
└── README_CLOUD.md
```

### Key Differences from Local Version:
1. **Multi-User Isolation**: Each user has their own private database (`user_{id}.db`). No user can ever see another user's financial transactions.
2. **Zero Lock Contention**: 100 users can sync at the exact same moment without database locking collisions.
3. **Dual Gmail Connection**:
   - **Method 1 (Instant):** Users can simply provide a 16-character **Google App Password** (no Google Cloud Console project required for the end user!).
   - **Method 2 (Enterprise):** Standard OAuth 2.0 Token.
4. **Per-User Configuration**: AI API keys, bank sender emails, and offline savings (Cash, PF, Gold, Mutual Funds) are managed directly from the UI and saved in each user's private database.

---

## 💵 How Hosting Cost is Kept at $0.00 / Month

This project is tuned specifically for Google Cloud's **Always Free Tier**:

| Service | Always Free Monthly Limit | Money Manager Usage | Monthly Cost |
| :--- | :--- | :--- | :--- |
| **Cloud Run** | 2,000,000 requests / month | Request-based only | **$0.00** |
| **Cloud Run Compute** | 360,000 vCPU-seconds | Scale to zero (`min-instances=0`) | **$0.00** |
| **Cloud Run Memory** | 180,000 GiB-seconds | 512 MiB allocation | **$0.00** |
| **Cloud Storage (GCS)** | 5 GB-months storage | ~10 MB for 100 SQLite DBs | **$0.00** |
| **Gemini AI API** | Free rate tier in AI Studio | 15 RPM free | **$0.00** |
| **Total Monthly Cost** | | | **$0.00** |

> **Scale to Zero Guarantee**: When no one is browsing the website, Cloud Run scales down to **0 running instances**. CPU and memory usage drop to absolute zero, so you are never charged for idle time.

---

## 🚀 Quick Deployment to Google Cloud (2 Steps)

### Prerequisites:
1. A Google Cloud account with billing enabled (new accounts get $300 free credits, but the above usage fits into the permanent free tier).
2. [Google Cloud SDK (gcloud CLI)](https://cloud.google.com/sdk/docs/install) installed on your machine.

---

### Step 1: Deploy with One Click

#### On Windows:
Open PowerShell or Command Prompt, navigate to `D:\money_manager_cloud`, and run:
```cmd
deploy_cloud_run.bat
```

#### On Linux / Mac:
```bash
chmod +x deploy_cloud_run.sh
./deploy_cloud_run.sh
```

The script will automatically:
1. Enable Cloud Run and Cloud Storage APIs.
2. Create a persistent Google Cloud Storage bucket (`<project-id>-money-data`).
3. Build and deploy the container to Cloud Run with scale-to-zero flags (`--min-instances 0 --max-instances 1 --memory 512Mi`).
4. Mount the Cloud Storage bucket to `/data` so SQLite databases persist across restarts.
5. Output your public HTTPS URL (e.g., `https://money-manager-cloud-xxxx.a.run.app`).

---

## 🔍 How to Validate the SQLite Database

You can validate database integrity anytime using multiple methods:

### 1. From the Dashboard UI
1. Sign in to your Money Manager dashboard.
2. Open the **"🔍 Database Validation"** tab.
3. Click **"Run PRAGMA integrity_check"**.
4. The dashboard will check every B-tree page, index, and table, and report `100% Validated. Zero Corruption.`

### 2. From the Command Line (Locally or in Container)
Run the built-in diagnostic script:
```bash
python scripts/validate_db.py
```
Output:
```
============================================================
🔍 MONEY MANAGER CLOUD — DATABASE VALIDATION & HEALTH CHECK
============================================================
📁 Storage Directory: D:\money_manager_cloud\data
🔒 Auth Database:     D:\money_manager_cloud\data\auth.db
👥 Users Directory:   D:\money_manager_cloud\data\users
------------------------------------------------------------
✅ [auth.db] Integrity Status: OK | Registered Users: 1
   ✅ user_1.db          | Status: OK   | Transactions: 42   | Deleted Tombstones: 0
============================================================
🎉 All database integrity checks passed successfully!
============================================================
```

### 3. In Google Cloud Console
1. Open [Google Cloud Console](https://console.cloud.google.com/) → **Cloud Storage** → **Buckets**.
2. Click your bucket (`<project-id>-money-data`).
3. Click into `users/` → select `user_1.db`.
4. Click **Download** to inspect it locally with **DB Browser for SQLite**.

---

## 💻 Local Testing (Before Cloud Deploy)

You can run the cloud application locally to test the multi-user flow:

```bash
cd D:\money_manager_cloud
pip install -r requirements.txt
python -m streamlit run app/dashboard.py
```

1. Open `http://localhost:8080`.
2. Click **Create Account** and register a user.
3. Go to **⚙️ Settings & Bank Alert**:
   - Enter your bank alert sender email (e.g. `alerts@hdfcbank.net`).
   - Enter your Gmail and a 16-character [Google App Password](https://myaccount.google.com/apppasswords).
   - Enter your free [Gemini API Key](https://aistudio.google.com/apikey).
   - Click **Save All Settings**.
4. Click **📬 Sync Bank Alerts** in the sidebar.
