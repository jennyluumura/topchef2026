#!/usr/bin/env python3
"""
Weekly Top Chef score updater.
Calls Anthropic API with web search to get latest episode results,
then rewrites index.html with updated scores and episode summaries.
"""

import os
import re
import json
import urllib.request
from datetime import date

API_KEY = os.environ["ANTHROPIC_API_KEY"]

CONTESTANTS = [
    {"pick": 1,  "name": "Duyen Ha",             "team": "Cader Tots"},
    {"pick": 2,  "name": "Rhoda Magbitang",       "team": "Coli-flower"},
    {"pick": 3,  "name": "Jonathan Dearden",      "team": "Mom/Dad"},
    {"pick": 4,  "name": "Brandon Dearden",       "team": "Mom/Dad"},
    {"pick": 5,  "name": "Jennifer Lee Jackson",  "team": "Coli-flower"},
    {"pick": 6,  "name": "Anthony Jones",         "team": "Cader Tots"},
    {"pick": 7,  "name": "Laurence Louie",        "team": "Cader Tots"},
    {"pick": 8,  "name": "Oscar Diaz",            "team": "Coli-flower"},
    {"pick": 9,  "name": "Sieger Bayer",          "team": "Mom/Dad"},
    {"pick": 10, "name": "Sherry Cardoso",        "team": "Mom/Dad"},
    {"pick": 11, "name": "Justin Tootla",         "team": "Coli-flower"},
    {"pick": 12, "name": "Nana Araba Wilmot",     "team": "Cader Tots"},
    {"pick": 13, "name": "Brittany Cochran",      "team": "Cader Tots"},
    {"pick": 14, "name": "Day Joseph",            "team": "Coli-flower"},
    {"pick": 15, "name": "Jassi Bindra",          "team": "Mom/Dad"},
]

SYSTEM_PROMPT = """Fantasy Top Chef 2026 scoring assistant. Search Wikipedia and recent news for "Top Chef Carolinas season 23" episode results.

Contestants: Duyen Ha, Rhoda Magbitang, Jonathan Dearden, Brandon Dearden, Jennifer Lee Jackson, Anthony Jones, Laurence Louie, Oscar Diaz, Sieger Bayer, Sherry Cardoso, Justin Tootla, Nana Araba Wilmot, Brittany Cochran, Day Joseph, Jassi Bindra.

SCORING RULES:
- Quickfire win: +1 per chef (each member of winning team gets +1 for team quickfires)
- Elimination winner: +2 ONLY (do NOT also give +1 top group)
- Top group (not winner): +1 each
- Bottom group (not eliminated): -1 each
- Eliminated: -2 ONLY (do NOT also give -1 bottom group)
- Finalist: +3, Season winner: +5
- EPISODE 3 SPECIAL RULE ONLY: every chef not in top group and not eliminated gets -1

VERIFIED SCORES eps 1-5 (do not change):
Ep1: Day Joseph -2
Ep2: Rhoda +2, Laurence +1, Sieger +1, Jennifer +1, Nana -1, Justin -1, Jassi -2
Ep3: Laurence +2, Anthony +2, Brandon +1, Nana -2, Duyen -1, Rhoda -1, Jonathan -1, Jennifer -1, Oscar -1, Sieger -1, Sherry -1, Justin -1, Brittany -1
Ep4: Sieger +3, Laurence +1, Sherry +1, Justin +1, Jennifer 0, Anthony -1, Brittany -2
Ep5: Brandon +1, Anthony +2, Sherry +1, Duyen +1, Laurence -1, Oscar -1, Rhoda -2

Search for any episodes beyond ep5 and score them. Return ONLY raw JSON, no markdown, no explanation:
{
  "episodes": [
    {"ep": 1, "scores": {"Chef Name": points}},
    ...all aired episodes...
  ],
  "eliminated": ["Chef Name", ...in order],
  "lastEpisode": <number>,
  "summaries": [
    {
      "ep": 1,
      "title": "Episode title",
      "date": "Mon DD, YYYY",
      "html": "Paragraph summary with inline pill spans. Use these exact span formats: <span class=\\"pill pill-qf\\">Quickfire</span> <span class=\\"pill pill-win\\">winning dish</span> <span class=\\"pill pill-top\\">top group</span> <span class=\\"pill pill-bot\\">bottom</span> <span class=\\"pill pill-elim\\">eliminated</span>. Bold chef names with <strong>Name</strong>. Write fluid narrative prose, not bullet points."
    },
    ...one per aired episode...
  ]
}

Only include non-zero scores per episode (except net-zero from offsetting scores, include those as 0)."""

USER_MESSAGE = "Search for the latest Top Chef Carolinas Season 23 episode results and return the full scoring JSON."


def call_api():
    payload = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 3000,
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": USER_MESSAGE}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST"
    )

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    text = "".join(b["text"] for b in data["content"] if b["type"] == "text")
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON found in API response")
    return json.loads(match.group(0))


def build_contestants_js(data):
    MAX_EPS = 14
    chef_pts = {c["name"]: [0] * MAX_EPS for c in CONTESTANTS}
    for ep in data["episodes"]:
        idx = ep["ep"] - 1
        if 0 <= idx < MAX_EPS:
            for chef, pts in ep["scores"].items():
                if chef in chef_pts:
                    chef_pts[chef][idx] = pts

    lines = []
    for c in CONTESTANTS:
        pts = ", ".join(str(p) for p in chef_pts[c["name"]])
        name_pad = " " * max(0, 22 - len(c["name"]))
        team_pad = " " * max(0, 11 - len(c["team"]))
        lines.append(
            f'  {{ pick: {c["pick"]:<2}, name: "{c["name"]}",{name_pad}'
            f' team: "{c["team"]}",{team_pad} pts: [{pts}] }},'
        )
    return "\n".join(lines)


def build_summaries_html(data):
    cards = []
    for s in data.get("summaries", []):
        cards.append(f"""      <div class="ep-card">
        <div class="ep-card-header">
          <span class="ep-num">Ep {s['ep']}</span>
          <span class="ep-title">{s['title']}</span>
          <span class="ep-date">{s['date']}</span>
        </div>
        <div class="ep-card-body">
          {s['html']}
        </div>
      </div>""")
    return "\n\n".join(cards)


def update_html(data):
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    last_ep = data["lastEpisode"]
    eliminated = data["eliminated"]

    # Update contestants array
    new_contestants = build_contestants_js(data)
    html = re.sub(
        r"const contestants = \[[\s\S]*?\];",
        f"const contestants = [\n{new_contestants}\n];",
        html
    )

    # Update activeCols
    html = re.sub(r"const activeCols = \d+;", f"const activeCols = {last_ep};", html)

    # Update eliminatedNames
    elim_json = json.dumps(eliminated)
    html = re.sub(
        r"const eliminatedNames = new Set\(\[.*?\]\);",
        f"const eliminatedNames = new Set({elim_json});",
        html
    )

    # Update episode summary cards
    new_cards = build_summaries_html(data)
    html = re.sub(
        r'(<div class="ep-summaries">)[\s\S]*?(</div>\s*\n\s*</div>\s*\n\n\s*<div class="footer">)',
        f'<div class="ep-summaries">\n\n{new_cards}\n\n    </div>\n  </div>\n\n  <div class="footer">',
        html
    )

    # Update footer
    today = date.today().strftime("%B %-d, %Y")
    html = re.sub(
        r"Updated through Episode \d+[^<]*",
        f"Updated through Episode {last_ep} &nbsp;·&nbsp; Top Chef: Carolinas Season 23 &nbsp;·&nbsp; Last updated {today}",
        html
    )

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    print(f"✅ Updated through Episode {last_ep} on {today}")
    print(f"   Eliminated so far: {', '.join(eliminated)}")


if __name__ == "__main__":
    print("Fetching latest Top Chef Carolinas results...")
    data = call_api()
    print(f"Got data through Episode {data['lastEpisode']}")
    update_html(data)
