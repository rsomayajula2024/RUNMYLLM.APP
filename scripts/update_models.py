#!/usr/bin/env python3
"""
RunMyLLM.app — Weekly model updater
Runs via GitHub Actions every Monday. Fetches latest models from
Ollama library and merges with curated list, writes data/models.json.
"""

import json
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

# ── CURATED BASE LIST ─────────────────────────────────────────────────────
# Hand-curated entries for models NOT on Ollama (HuggingFace-only, etc.)
CURATED_EXTRA = [
    {
        "company": "meta",
        "name": "Llama 3.1 405B",
        "params": 405,
        "family": "Llama 3.1",
        "ctx": 128000,
        "dl": "https://huggingface.co/meta-llama/Llama-3.1-405B",
        "ollama_tag": "llama3.1:405b"
    },
    {
        "company": "mistral",
        "name": "Mistral Large 2",
        "params": 123,
        "family": "Mistral",
        "ctx": 128000,
        "dl": "https://huggingface.co/mistralai/Mistral-Large-Instruct-2407",
        "ollama_tag": None
    },
    {
        "company": "deepseek",
        "name": "DeepSeek-V3 671B",
        "params": 671,
        "family": "DeepSeek-V3",
        "ctx": 128000,
        "dl": "https://huggingface.co/deepseek-ai/DeepSeek-V3",
        "ollama_tag": None
    },
]

# Company routing — map Ollama model namespace prefixes to our company keys
COMPANY_MAP = {
    "llama":        "meta",
    "llama2":       "meta",
    "llama3":       "meta",
    "mistral":      "mistral",
    "mixtral":      "mistral",
    "mistral-small": "mistral",
    "gemma":        "google",
    "gemma2":       "google",
    "gemma3":       "google",
    "phi":          "microsoft",
    "phi3":         "microsoft",
    "phi4":         "microsoft",
    "phi4-mini":    "microsoft",
    "qwen":         "alibaba",
    "qwen2":        "alibaba",
    "qwen2.5":      "alibaba",
    "qwq":          "alibaba",
    "deepseek":     "deepseek",
    "deepseek-r1":  "deepseek",
    "deepseek-v3":  "deepseek",
    "command-r":    "cohere",
    "yi":           "01ai",
}

FAMILY_MAP = {
    "llama3.2": "Llama 3.2", "llama3.1": "Llama 3.1", "llama3": "Llama 3",
    "llama2": "Llama 2", "mistral": "Mistral", "mixtral": "Mixtral",
    "mistral-small3.1": "Mistral", "gemma2": "Gemma 2", "gemma3": "Gemma 3",
    "phi3": "Phi-3", "phi4": "Phi-4", "phi4-mini": "Phi-4",
    "qwen2": "Qwen2", "qwen2.5": "Qwen2.5", "qwq": "QwQ",
    "deepseek-r1": "DeepSeek-R1", "command-r": "Command R",
    "command-r-plus": "Command R+", "yi": "Yi",
}

SUPPORTED_PREFIXES = set(COMPANY_MAP.keys())


def fetch_ollama_models():
    """Fetch model list from Ollama's public search API."""
    url = "https://ollama.com/api/tags"
    # Ollama doesn't have a clean public API for listing all models,
    # so we query their search endpoint which returns popular models.
    # Fallback: use their library search with empty query.
    try:
        req = urllib.request.Request(
            "https://ollama.com/search?q=&sort=popular&limit=200",
            headers={"Accept": "application/json", "User-Agent": "runmyllm-updater/1.0"}
        )
        # Note: Ollama's search returns HTML; we use their JSON-LD or parse
        # their /api/models endpoint instead
        api_url = "https://ollama.com/api/models?sort=popular&limit=200"
        req2 = urllib.request.Request(
            api_url,
            headers={"Accept": "application/json", "User-Agent": "runmyllm-updater/1.0"}
        )
        with urllib.request.urlopen(req2, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return data.get("models", [])
    except Exception as e:
        print(f"⚠ Ollama API fetch failed: {e}. Using curated list only.")
        return []


def parse_params(name_str):
    """Extract param count in billions from model name string like 'llama3:8b'."""
    import re
    # Match patterns: 8b, 70b, 0.5b, 8x7b (MoE), 671b
    moe = re.search(r'(\d+)x(\d+)b', name_str.lower())
    if moe:
        # For MoE, active params ~ total params (conservative)
        return int(moe.group(1)) * int(moe.group(2))
    single = re.search(r'(\d+(?:\.\d+)?)b', name_str.lower())
    if single:
        return float(single.group(1))
    return None


def resolve_company(model_name):
    name_lower = model_name.lower().replace("_", "-")
    for prefix, company in sorted(COMPANY_MAP.items(), key=lambda x: -len(x[0])):
        if name_lower.startswith(prefix.lower()):
            return company
    return None


def resolve_family(tag):
    tag_lower = tag.lower().split(":")[0]
    for key, family in sorted(FAMILY_MAP.items(), key=lambda x: -len(x[0])):
        if tag_lower.startswith(key.lower()):
            return family
    return tag_lower.title()


def build_model_entry(ollama_model):
    """Convert an Ollama API model record to our schema."""
    tag = ollama_model.get("name", "")
    name_part = tag.split(":")[0]
    size_part = tag.split(":")[1] if ":" in tag else ""

    company = resolve_company(name_part)
    if not company:
        return None

    params = parse_params(size_part) or parse_params(name_part)
    if not params:
        return None

    family = resolve_family(name_part)
    display_name = f"{family} {size_part.upper()}" if size_part else family

    # ctx: use pull_count or description hints; default by size
    ctx = 128000 if params <= 70 else 32768

    return {
        "company": company,
        "name": display_name,
        "params": params,
        "family": family,
        "ctx": ctx,
        "dl": f"https://ollama.com/library/{tag}",
        "ollama_tag": tag,
        "pulls": ollama_model.get("pull_count", 0),
    }


def dedupe(models):
    """Remove duplicates by (company, name), keeping higher pull count."""
    seen = {}
    for m in models:
        key = (m["company"], m["name"])
        if key not in seen or m.get("pulls", 0) > seen[key].get("pulls", 0):
            seen[key] = m
    return list(seen.values())


def sort_models(models):
    company_order = ["meta", "google", "mistral", "microsoft", "alibaba", "deepseek", "cohere", "01ai"]
    def sort_key(m):
        co = company_order.index(m["company"]) if m["company"] in company_order else 99
        return (co, m["params"])
    return sorted(models, key=sort_key)


def main():
    print("🔄 RunMyLLM model updater starting...")

    # 1. Fetch from Ollama
    raw_ollama = fetch_ollama_models()
    print(f"  Fetched {len(raw_ollama)} models from Ollama API")

    # 2. Parse
    parsed = []
    for m in raw_ollama:
        entry = build_model_entry(m)
        if entry:
            parsed.append(entry)
    print(f"  Parsed {len(parsed)} valid entries")

    # 3. Merge with curated extras
    all_models = parsed + CURATED_EXTRA
    all_models = dedupe(all_models)
    all_models = sort_models(all_models)

    # 4. Remove pull count from output (internal only)
    for m in all_models:
        m.pop("pulls", None)

    # 5. Write
    output = {
        "last_updated": date.today().isoformat(),
        "model_count": len(all_models),
        "models": all_models
    }

    out_path = Path(__file__).parent.parent / "data" / "models.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"✅ Written {len(all_models)} models to {out_path}")
    print(f"   Last updated: {output['last_updated']}")


if __name__ == "__main__":
    main()
