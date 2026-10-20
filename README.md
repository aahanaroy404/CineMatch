# CineMatch — Recommender Systems Mini-Project

CineMatch is a movie discovery website with persistent accounts, private ratings, item-based collaborative filtering, real MovieLens popularity suggestions, offline rating evaluation, and a small protected admin dashboard. The new project is self-contained and keeps the React + Vite / Python + FastAPI stack from the original.

## Requirements

- Python 3.10 or newer
- Node.js 20 or newer and npm
- MovieLens Latest Small CSV files (included in this local copy under `data/ml-latest-small/`; the folder is ignored by Git)
- Internet access the first time installing packages, unless package caches are available

## Install and run on Windows PowerShell

From the `CineMatch-Updated` project root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.main:app --reload --port 8000
```

In a second PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The API documentation is at <http://localhost:8000/docs> and the health check is <http://localhost:8000/api/health>.

The database is initialized automatically at `data/cinematch.sqlite3` when the backend starts. You do not need to run a separate migration command. If PowerShell prevents virtual-environment activation, use `\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt` and `\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000`.

## Accounts and security

Create a normal account in the website using a valid email and a password of at least 10 characters. Passwords are hashed with PBKDF2-HMAC-SHA256 and a random salt; plaintext passwords are never saved. Login issues an opaque, random, 12-hour session cookie marked HttpOnly and SameSite=Lax. The corresponding token hash is stored in SQLite so logout can invalidate the session. The browser never receives the stored token value in JSON.

Ratings are stored by user ID and movie ID in SQLite. The API derives the user identity and role from the server-validated session. A registration request cannot set a role. Every admin statistics request checks the database-backed role on the server.

### Create the first administrator

Only do this once, from the project root, in a trusted local terminal:

```powershell
python -m backend.bootstrap_admin
```

The command securely prompts for the name, email, and password (hidden input). Use a unique password of at least 12 characters. It creates an admin only if no admin account exists. Later runs refuse to create another admin. No default credentials are built in or shown in the website.

## Dataset

This project copy includes MovieLens Latest Small's `movies.csv` and `ratings.csv` under `data/ml-latest-small/`. If you remove the ignored dataset directory, download the dataset from [GroupLens](https://grouplens.org/datasets/movielens/latest/) and restore those two CSV files there. CineMatch requires the actual data and does not substitute mock records. Follow GroupLens attribution and usage requirements in academic submissions.

The **Popular picks** cold-start list is calculated from dataset average rating and rating count; it requires at least 25 source ratings and sorts by average rating, then count. These are clearly labeled as popular, not personalized.

## Recommendations and profile

The user-item matrix contains explicit MovieLens ratings. Movie pairs are compared with sparse cosine similarity. Unrated cells have no stored rating and add no product to the similarity numerator or observed column norms; they are never interpreted as dislikes. For an unseen movie, the model adds a similarity-weighted average of the user's rating deviations from their own average, normalized by the sum of absolute similarity weights. Predictions are clipped to the dataset's 0.5–5 range. Rated titles are excluded from personalized recommendations. The model asks for at least two ratings corresponding to dataset titles; when there are too few, the profile explains the limitation and shows clearly labeled popular suggestions.

The **For You** navigation opens the recommendations section on the Profile page. The Profile page stacks the user's rated movies and their recommendation list, and users can edit or remove their own ratings there. Ratings persist across logout and login.

The How it Works page explains the process in four short steps. The Evaluation page uses a deterministic 80/20 split with seed 42, computes similarities from training ratings only, and reports RMSE, MAE, valid predictions, and split counts. Held-out ratings without similar training neighbors are excluded from errors and reported as unpredicted. With the included MovieLens data, the measured values are RMSE **0.9202** and MAE **0.7103** over 19,351 valid predictions (80,668 train, 20,168 test, 817 unpredicted).

## Admin dashboard statistics

Only an account created using the one-time bootstrap can load `/api/admin/stats`. The dashboard exposes aggregate counts only:

- registered accounts;
- current user ratings stored in the app (an edited rating remains one rating);
- MovieLens titles loaded by the app;
- recommendations actually returned to profile refresh requests, including popular suggestions.

The recommendation counter adds the number of movie suggestions returned in each successful profile response. It does not count page visits with zero suggestions, and it does not count rating predictions that were computed but not returned. No user list, email, password hash, token, or rating detail is exposed through admin statistics.

## Configuration

Optional environment variables are listed in `.env.example`:

- `CINEMATCH_DB`: override the SQLite file path (default `data/cinematch.sqlite3`).
- `CINEMATCH_SECURE_COOKIE=1`: mark the session cookie Secure when serving behind HTTPS. Keep the default `0` for local HTTP development.

No signing secret is needed because sessions use random opaque tokens stored as hashes in the database. Keep the SQLite file and `.env` private; database files and secrets are ignored by Git.

## Project layout

```text
CineMatch-Updated/
├── backend/
│   ├── auth.py                 # password hashing and cookie sessions
│   ├── bootstrap_admin.py      # one-time interactive admin setup
│   ├── data_loader.py          # MovieLens loading and catalog statistics
│   ├── database.py             # SQLite schema and connection setup
│   ├── evaluation.py           # leakage-free held-out metrics
│   ├── main.py                 # API routes and server-side authorization
│   ├── recommender.py          # item-based cosine model
│   └── requirements.txt
├── data/
│   └── ml-latest-small/        # movies.csv and ratings.csv
├── frontend/
│   ├── src/App.jsx             # auth, discover, profile, evaluation, admin UI
│   ├── src/style.css           # dark cinematic responsive theme
│   └── package.json
├── .env.example
├── .gitignore
└── PROJECT_REPORT.md
```

This is an educational local application, not a production identity provider. Use HTTPS, a strong administrator password, backups, and standard deployment hardening before exposing it to a public network.
