# 🌾 agri-radar: Agri-Remote-Sensing Intelligence Daily Brief Agent

An **autonomous intelligence agent** that monitors global agri-remote-sensing-related news every day, filters for relevance using an LLM, and pushes a concise digest to your team.

Built for a **Surveying & Mapping Master's student** whose advisor focuses on agricultural remote sensing. It tracks **disaster-focused remote sensing** (drought, flood, pest/extreme weather), smart agriculture, and related industry developments.

**Demo**: see the **Pages site** linked from this repo for today's actual output.

---

## What it does

| Capability | Detail |
|---|---|
| 📡 **Daily collection** | 4 major remote-sensing Q1 journals (RSE/ISPRS/TGRS/JSTARS), cutting-edge institutions (CAS-AIR, Wuhan University RS, BNU RS, UMD Geography), satellite industry (吉林一号/长光卫星/JL-1, Planet, Maxar/Vantor, ESA Sentinel), government agri-departments (CN Ministry of Agriculture, USDA, JMA, Embrapa etc.), agri-business (COFCO, Syngenta, ABCD traders, Beidahuang) |
| 🧠 **LLM triage** | Uses an OpenAI-compatible API (Kimi/DeepSeek/GLM/Claude/GPT etc., pluggable) to score + filter + summarize in Chinese |
| 🎯 **Topic weighting** | Learns from your feedback (⭐/👎/keywords) via a transparent weight table you can inspect |
| 👁️ **Topic tracking** | Named watchlist (吉林一号, PhiSat-2, etc.) — alerts only on material changes |
| 📢 **Push channels** | Feishu custom-bot webhook (primary) |
| 💻 **Zero-install** frontend | GitHub Pages static dashboard this repo ships |

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  ① Collection (Python, stdlib only)                  │
│     RSS APIs · Google News · Crossref                │
│         ↓                                            │
│  ② State store (SQLite)                              │
│     items · source_prefs · topic_prefs · watchlist   │
│         ↓                                            │
│  ③ LLM Triage (1 call/day, pluggable model)          │
│     scores → sections 科研 / 产业界 / 政府 / 公司      │
│         ↓                                            │
│  ④ Push (Feishu card message · Pages site)           │
└──────────────────────────────────────────────────────┘
```

## Screenshots

| Feishu daily card | GitHub Pages dashboard |
|---|---|
| (push from the bot) | (auto-updated every day from Actions) |

## Quick start (Docker)

```bash
git clone https://github.com/HelloHui00/agri-radar.git
cd agri-radar
cp config/server.example.json config/server.json
# edit server.json with your LLM key + Feishu webhook
docker compose up -d
```

## Quick start (manual)

```bash
python scripts/collect.py > data/run.jsonl
python scripts/ingest.py data/run.jsonl
python scripts/brief.py            # produces output/brief_YYYY-MM-DD.md
python scripts/feishu_push.py output/brief_YYYY-MM-DD.md
```

## Configuration

| File | Purpose |
|---|---|
| `config/sources.json` | Declarative news sources (RSS / Google News / Crossref / arXiv). Add a new source = add one JSON entry |
| `config/watching.json` | Watchlist topics to be alerted on |
| `config/topics.json` | Topic taxonomy for feedback weighting |
| `config/server.example.json` | LLM + Feishu + proxy template |

## Roadmap

- [x] Daily auto-collection & triage
- [x] Feishu push
- [x] Feedback weighting mechanism
- [x] GitHub Pages dashboard (auto-deploy)
- [ ] Docker / docker-compose one-liner
- [ ] WeChat Work / DingTalk push
- [ ] Web dashboard with auth, multi-user
- [ ] English summary toggle

## License

MIT (see `LICENSE`)
