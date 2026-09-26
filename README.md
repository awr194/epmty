# 🇨🇿 Czech Business Model Radar & Adaptation Engine

A Streamlit app that finds proven small-business and micro-SaaS models from around the world and checks whether they would work in the **Czech Republic**. For each model it estimates feasibility, CZK unit economics (OSVČ paušální daň vs. s.r.o.), local competitors and a 14-day go-to-market plan for Prague.

## Features

| | |
|---|---|
| **Sources** | A curated set of **500 proven models from 60+ countries** across 12 categories: the USA, UK, Germany, France, Russia, Ukraine, Poland, India, Brazil, Japan, Korea, Australia, Africa and more (e.g. Plausible, Basecamp, Tilda, amoCRM, YCLIENTS, Booksy, Zoho, Doctolib, Jobber). Filterable by country of origin, live **Hacker News "Show HN"** launches (Algolia API), the live **Product Hunt** RSS feed, and your own ideas. |
| **Radar dashboard** | Filters for category, source, minimum feasibility score and CZK potential, plus full-text search. It includes an opportunity scatter map and a card for each idea. |
| **Deep-Dive Czech Report** | Gives a Czech Feasibility Score (0-100) with a factor breakdown. It also covers Czech target audiences, pricing tiers in CZK, a revenue ramp, a monthly cost base, the recommended legal form and tax notes, local incumbents (Heureka, Shoptet, Fakturoid, Reservio, Qerko and others) and a 3-step, 14-day GTM roadmap. It ends with risks and a localisation checklist. |
| **Three engines** | **Claude** (Anthropic API with structured outputs) or **Google Gemini** (JSON response schema) when an API key is set. Otherwise an **offline heuristic engine** runs, which is instant and needs no key. If an API call fails, the app falls back to the offline engine automatically. |
| **Export** | Markdown and PDF. The PDF keeps Czech diacritics. |

## Project structure

```
app.py            Streamlit dashboard (filters, cards, deep-dive, exports)
analyzer.py       Scoring model, Czech market assumptions, report schema, Claude & Gemini engines
data_loader.py    Data model, first 30 curated models, Show HN / Product Hunt fetchers
curated_more.py   70 more curated models (merged by data_loader)
catalog/          400 more models from around the world, one file per region
exporter.py       Markdown and PDF report export
requirements.txt  Python dependencies
packages.txt      System packages for Streamlit Cloud (DejaVu fonts for the PDF)
.streamlit/       Theme config + secrets example
```

## Run locally

**Windows (cmd or PowerShell):**

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

If PowerShell blocks activation because of its execution policy, skip activation and run
`.venv\Scripts\python -m streamlit run app.py` instead.

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501 and runs in **offline demo mode** by default.

### Enable LLM analysis (optional)

The app supports two LLM providers. You only need one of them.

| Provider | Where to get a key | Secret / env variable | Default model |
|---|---|---|---|
| Anthropic Claude | [console.anthropic.com](https://console.anthropic.com) | `ANTHROPIC_API_KEY` | `claude-opus-5` |
| Google Gemini | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) (has a free tier) | `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) | `gemini-2.5-flash` |

You can supply keys in any of these ways:

- Paste them into **🔑 API keys** in the sidebar. They are kept only for your browser session.
- Set environment variables. In Windows cmd: `set GEMINI_API_KEY=AIza...`. On macOS/Linux: `export GEMINI_API_KEY=AIza...`
- Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in the keys.

With the engine set to **Auto**, the app uses Claude if its key is present, otherwise Gemini, otherwise the offline engine. You can also pick **Claude** or **Gemini** explicitly and choose the model in the sidebar. The Gemini model box also accepts any model id you type. A deep-dive typically takes 20-90 seconds.

## Free deployment: Streamlit Community Cloud

1. Push this folder to a **public or private GitHub repo**. `.gitignore` already excludes `.venv` and `secrets.toml`.
2. Go to **https://share.streamlit.io** and sign in with GitHub.
3. Click **Create app → Deploy a public app from GitHub**, then pick the repo, the branch and `app.py` as the main file.
4. Optional: under **Advanced settings → Python version**, choose 3.12 or newer.
5. Optional: under **Advanced settings → Secrets**, paste one or both keys:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   GEMINI_API_KEY = "AIza..."
   ```
6. Click **Deploy**. `requirements.txt` and `packages.txt`, which installs fonts for the PDF, are picked up automatically.

Your app will be live at `https://<your-app>.streamlit.app`. It redeploys on every push.

> On a public deployment, anyone who opens the app uses your API keys. Leave the secret out to run a free demo in offline mode, or keep the app private in its sharing settings.

## About the data

- **Models 1-100** have hand-written Czech segments and named Czech competitors.
- **Models 101-500** (`catalog/`) have real global facts (name, country, website, niche, revenue model, typical price, problem) and Czech-market ratings. Where Czech competitors are known they are named; otherwise the report shows a *category-level Czech landscape*, labelled "check relevance for this model". Run a Claude or Gemini Deep-Dive for a model-specific competitor analysis.
- The target market is always **Czechia**; the country field shows where the model was proven.

## How scoring works

Each model has Czech-market ratings from 1 to 5: demand, competition, build complexity, regulatory burden and localisation moat. It also has a serviceable-market estimate. The weights are:

| Factor | Weight |
|---|---|
| Local demand | 28 % |
| Competitive whitespace | 20 % |
| Build & ops simplicity | 14 % |
| Regulatory ease | 10 % |
| Localisation moat | 14 % |
| Proven international traction (log MRR) | 14 % |

**CZK potential** is calculated as: US price × USD/CZK × purchasing-power factor (B2B 0.75, B2C 0.60) × month-12 customers. You can change every assumption in the sidebar, including the exchange rate, the paušální daň bands and s.r.o. accounting costs.

## Caveats

- International revenue figures are approximate self-reported numbers from founders' public posts. Treat them as a traction signal, not audited data.
- Tax figures such as the paušální daň bands and the VAT threshold are **rounded 2026 approximations**. Check them with an accountant or on [financnisprava.cz](https://www.financnisprava.cz).
- Competitor lists are starting points for your own research. Items marked "verify" in reports need confirmation.
