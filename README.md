# Avocado Sales Dashboard

Interactive Dash dashboard for exploring weekly avocado sales, prices, types, and regional market patterns across the US.

## Features

- Multi-page Dash app with top navigation tabs.
- Clean, Notion-like visual style.
- Collapsible side filter panel.
- Combined period controls with presets and custom week-based ranges.
- Optional comparison period controls.
- Combined region controls with multi-select regions and region groups.
- Excludes `TotalUS` from regional aggregations by default.
- Executive KPI cards.
- Biggest-market rankings.
- Regional price and opportunity charts.
- Sales and price evolution charts.
- Week-over-week percentage change in line-chart hover tooltips.
- Indexed sales and price charts where the first visible week equals 100.

## Project Structure

```text
avocado-dashboard/
├── app.py
├── avocado.csv
├── requirements.txt
├── Procfile
├── README.md
└── action_plan.md
```

## Local Setup

### 1. Create and open the project folder

```bash
mkdir avocado-dashboard
cd avocado-dashboard
```

### 2. Add the files

Place the following files in the folder:

- `app.py`
- `avocado.csv`
- `requirements.txt`
- `Procfile`
- `README.md`
- `action_plan.md`

The CSV must be named exactly:

```text
avocado.csv
```

### 3. Create a virtual environment

```bash
python -m venv .venv
```

Activate it.

On macOS/Linux:

```bash
source .venv/bin/activate
```

On Windows:

```bash
.venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Run the app locally

```bash
python app.py
```

Open the local URL shown in your terminal, usually:

```text
http://127.0.0.1:8050
```

## Push to GitHub

### 1. Initialize Git

```bash
git init
```

### 2. Add files

```bash
git add app.py avocado.csv requirements.txt Procfile .python-version .gitignore README.md action_plan.md
```

### 3. Commit

```bash
git commit -m "Initial avocado dashboard"
```

### 4. Create a GitHub repository

On GitHub:

1. Click **New repository**.
2. Name it, for example, `avocado-dashboard`.
3. Keep it public or private.
4. Do not initialize with a README if you already have one locally.

### 5. Connect local repo to GitHub

Replace `YOUR_USERNAME` with your GitHub username.

```bash
git remote add origin https://github.com/YOUR_USERNAME/avocado-dashboard.git
git branch -M main
git push -u origin main
```

## Host on Render Free Tier

### 1. Create a new Render Web Service

1. Go to [Render](https://render.com/).
2. Sign in or create an account.
3. Click **New +**.
4. Choose **Web Service**.
5. Connect your GitHub account if prompted.
6. Select your `avocado-dashboard` repository.

### 2. Configure the service

Use these settings:

| Setting | Value |
|---|---|
| Runtime | Python |
| Build command | `pip install -r requirements.txt` |
| Start command | `gunicorn app:server` |
| Instance type | Free |

Render does not read the `Procfile`; the start command above is what it uses.

The `.python-version` file (containing `3.12`) is required: Render's default
Python for new services is 3.14, and the pinned pandas version does not install there.

On the Free instance the app sleeps after 15 minutes without visitors and takes
about a minute to wake up on the next visit.

### 3. Deploy

Click **Create Web Service**.

Render will build and deploy the app. Once deployment finishes, Render will provide a public URL for the dashboard.

## Updating the Dashboard

After making code changes locally:

```bash
git add .
git commit -m "Update dashboard"
git push
```

Render will automatically redeploy from GitHub if auto-deploy is enabled.

## Notes

- Keep `avocado.csv` next to `app.py` (or set the `AVOCADO_CSV_PATH` environment variable).
- Region level: "Metro markets" (default) and "Broad US regions" are never mixed. The 8 broad regions
  (California, GreatLakes, Midsouth, Northeast, Plains, SouthCentral, Southeast, West) add up exactly
  to TotalUS and contain the metro markets, so mixing them would double-count volume.
- The app expects these columns: `date`, `average_price`, `total_volume`, `type`, and `region`.
- The app uses a simple average for `average_price` rather than changing the dataset's analytical meaning.
- Regional group definitions are configured in `app.py` and can be refined later.
