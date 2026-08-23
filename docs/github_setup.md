# GitHub Pages setup

This repo ships a **`viewer/`** directory that is served as GitHub Pages.

## How it works

1. GitHub Actions workflow `.github/workflows/daily-brief.yml` runs every day at 07:30 BJT
2. It fetches news, generates the brief, converts it to HTML, and pushes to `docs/` (or commit to a 'gh-pages' branch)
3. GitHub Pages serves that as `https://hellohui00.github.io/agri-radar/`

No server, no cost. A full historical archive is kept under `docs/archive/YYYY-MM-DD.html`.

## First-time setup (you need to do once in repo settings)

Repo → Settings → Pages:
- **Source**: `Deploy from a branch`
- **Branch**: `main`, folder `/docs`

Save, and after your first Actions run completes, your dashboard will be live at
`https://hellohui00.github.io/agri-radar/`.
