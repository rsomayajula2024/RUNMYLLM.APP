# RunMyLLM.app

> Will your LLM run on this machine? Pick a model, choose your hardware, see exactly where the memory goes.

**Live:** [runmyllm.app](https://runmyllm.app)

---

## What it does

- Supports 40+ models across Meta, Mistral, Google, Microsoft, Alibaba, DeepSeek, Cohere, 01.AI
- Hardware coverage: Apple M-series, NVIDIA, AMD, Intel Arc, CPU-only
- Shows exact memory breakdown: weights + KV cache + overhead
- Quantization options: FP16, Q8, Q4, Q3, Q2
- Context length slider (512 → 32K tokens)
- Direct Ollama run commands with one-click copy
- **Auto-updates weekly** via GitHub Actions

---

## Repo structure

```
runmyllm/
├── index.html                     # Main app (single file, no framework)
├── data/
│   └── models.json                # Model list — updated weekly automatically
├── scripts/
│   └── update_models.py           # Fetches latest models from Ollama + HuggingFace
├── .github/
│   └── workflows/
│       └── update-models.yml      # Runs every Monday 06:00 UTC
└── README.md
```

---

## Deploy to Vercel (5 minutes)

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "initial commit"
gh repo create runmyllm --public --push
```

### Step 2 — Deploy on Vercel

1. Go to [vercel.com](https://vercel.com) → **New Project**
2. Import your `runmyllm` GitHub repo
3. Framework preset: **Other** (it's static HTML)
4. Root directory: `/` (default)
5. Click **Deploy** — done

### Step 3 — Connect your domain

1. In Vercel → your project → **Settings → Domains**
2. Add `runmyllm.app`
3. Vercel shows you two DNS records to add at your registrar (Namecheap / Google Domains)
4. SSL is automatic

---

## Weekly auto-update

GitHub Actions runs `scripts/update_models.py` every Monday at 06:00 UTC.

The script:
1. Fetches popular models from Ollama's API
2. Merges with the curated list in the script (for HuggingFace-only models)
3. Writes `data/models.json` with today's date
4. Commits and pushes — Vercel auto-redeploys

**Manual trigger:** Go to Actions tab → "Weekly Model Update" → "Run workflow"

### Adding a new model manually

Edit `data/models.json` and add an entry:

```json
{
  "company": "meta",
  "name": "Llama 4 Scout 17B",
  "params": 17,
  "family": "Llama 4",
  "ctx": 128000,
  "dl": "https://ollama.com/library/llama4:scout",
  "ollama_tag": "llama4:scout"
}
```

Valid company keys: `meta` `mistral` `google` `microsoft` `alibaba` `deepseek` `cohere` `01ai`

---

## Stack

- Pure HTML/CSS/JS — no framework, no build step
- Google Fonts (Space Grotesk + JetBrains Mono)
- GitHub Actions for weekly data refresh
- Vercel for hosting (free tier)

---

## License

MIT
