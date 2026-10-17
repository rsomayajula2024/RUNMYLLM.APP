#!/usr/bin/env python3
"""
RunMyLLM.app — weekly model updater (GitHub Actions, every Monday).

data/models.json is the hand-curated source of truth. This script:
  1. loads it,
  2. scrapes ollama.com's "newest" + "popular" pages for new sizes of
     families we already track and adds them (flagged "auto": true),
  3. lists brand-new families it saw but doesn't know, in the job summary,
     so a human can curate them,
  4. writes last_checked every run; bumps last_updated only when the
     model list actually changed.

Safety rules (the old script broke these and wiped the site to 3 models):
  * it NEVER removes models,
  * if the network/parse fails it changes nothing but last_checked,
  * it refuses to write a list smaller than the one it loaded.
"""

import json
import os
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "models.json"
PAGES = [
    "https://ollama.com/search?o=newest",
    "https://ollama.com/search?o=popular",
]

# Ollama base name -> (company key, display family, default ctx)
# Only families listed here are auto-extended. Add a line to track a new family.
KNOWN = {
    "llama3.1": ("meta", "Llama 3.1", 131072), "llama3.2": ("meta", "Llama 3.2", 131072),
    "llama3.3": ("meta", "Llama 3.3", 131072),
    "gemma3": ("google", "Gemma 3", 131072), "gemma4": ("google", "Gemma 4", 262144),
    "qwen3": ("alibaba", "Qwen3", 40960), "qwen3.5": ("alibaba", "Qwen3.5", 262144),
    "qwen3.6": ("alibaba", "Qwen3.6", 262144), "qwen3.8": ("alibaba", "Qwen3.8", 262144),
    "qwen3-coder": ("alibaba", "Qwen3-Coder", 262144), "qwen3-vl": ("alibaba", "Qwen3-VL", 262144),
    "qwen2.5-coder": ("alibaba", "Qwen2.5-Coder", 32768),
    "deepseek-r1": ("deepseek", "DeepSeek-R1", 131072),
    "gpt-oss": ("openai", "gpt-oss", 131072),
    "mistral-small3.2": ("mistral", "Mistral Small", 131072), "magistral": ("mistral", "Magistral", 131072),
    "devstral": ("mistral", "Devstral", 131072),
    "phi4": ("microsoft", "Phi-4", 16384), "phi4-reasoning": ("microsoft", "Phi-4", 32768),
    "nemotron-3.5-lightning": ("nvidia", "Nemotron 3.5", 1048576),
    "nemotron-3.5-bolt": ("nvidia", "Nemotron 3.5", 262144),
    "nemotron-3.5-super": ("nvidia", "Nemotron 3.5", 1048576),
    "granite4.2": ("ibm", "Granite", 131072),
    "exaone3.5": ("lg", "EXAONE 3.5", 32768), "olmo2": ("allenai", "OLMo 2", 4096),
}

# Families that are not chat LLMs (embeddings, decision models) — never report them.
IGNORE = re.compile(r"embed|rerank|decider|clef|nimble|tev1|^d1$|guard|bge|minilm")

SIZE_RE = re.compile(r"^(\d+(?:\.\d+)?)([mb])$")


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "runmyllm-updater/2.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def parse_search_html(html):
    """Return {family: [size tags]} from an ollama.com search page.
    Each result is an <li x-test-model ...> containing href="/library/<name>"
    and <span x-test-size ...>8b</span> chips. Cloud-only results have no size chips."""
    out = {}
    for block in re.split(r"<li[^>]*\bx-test-model\b", html)[1:]:
        m = re.search(r'href="/library/([a-z0-9._-]+)"', block)
        if not m:
            continue
        sizes = re.findall(r"x-test-size[^>]*>\s*([^<\s]+)\s*<", block)
        out[m.group(1)] = [s.lower() for s in sizes]
    return out


def size_to_b(tag):
    m = SIZE_RE.match(tag)
    if not m:
        return None
    n = float(m.group(1))
    return round(n / 1000, 3) if m.group(2) == "m" else n


def summary(lines):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    text = "\n".join(lines) + "\n"
    print(text)
    if path:
        with open(path, "a") as f:
            f.write(text)


def main():
    data = json.loads(DATA.read_text())
    models = data["models"]
    before = len(models)
    have_tags = {m.get("ollama_tag") for m in models if m.get("ollama_tag")}
    have_names = {m["name"] for m in models}
    today = date.today().isoformat()

    seen = {}
    for url in PAGES:
        try:
            for fam, sizes in parse_search_html(fetch(url)).items():
                seen.setdefault(fam, set()).update(sizes)
        except Exception as e:  # network or layout change: report, don't break
            print(f"warning: could not read {url}: {e}")

    if not seen:
        # Fail the job (GitHub emails you) and leave models.json untouched.
        summary([f"## RunMyLLM model check — {today}",
                 "❌ Could not read ollama.com (network or page layout changed). Nothing was changed."])
        sys.exit(1)

    added, unknown = [], []
    for fam, sizes in sorted(seen.items()):
        if fam not in KNOWN:
            if sizes and not IGNORE.search(fam):
                unknown.append(f"{fam} ({', '.join(sorted(sizes))})")
            continue
        company, family, ctx = KNOWN[fam]
        for s in sorted(sizes):
            params = size_to_b(s)
            tag = f"{fam}:{s}"
            name = f"{family} {s.upper()}"
            if params is None or tag in have_tags or name in have_names:
                continue
            models.append({
                "company": company, "name": name, "family": family, "params": params,
                "ctx": ctx, "dl": f"https://ollama.com/library/{tag}",
                "ollama_tag": tag, "released": today[:7], "auto": True,
            })
            have_tags.add(tag); have_names.add(name)
            added.append(tag)

    if len(models) < before:  # belt and braces — must never happen
        sys.exit("refusing to write: model list shrank")

    data["last_checked"] = today
    if added:
        data["last_updated"] = today
    data["model_count"] = len(models)
    DATA.write_text(json.dumps(data, indent=1) + "\n")

    lines = [f"## RunMyLLM model check — {today}",
             f"- Ollama families read: **{len(seen)}**",
             f"- Models: {before} → **{len(models)}**"]
    if added:
        lines.append("- Added: " + ", ".join(f"`{t}`" for t in added))
    if unknown:
        lines.append("\n### New families not tracked yet (add to KNOWN + models.json if worth listing)")
        lines += [f"- {u}" for u in unknown[:40]]
    summary(lines)


if __name__ == "__main__":
    main()
