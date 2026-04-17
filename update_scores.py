#!/usr/bin/env python3
"""
Weekly Top Chef score updater.
Fetches Wikipedia page directly, passes content to Claude API to score,
then rewrites index.html with updated scores and episode summaries.
"""

import os
import re
import json
import urllib.request
import urllib.error
from datetime import date

API_KEY = os.environ["ANTHROPIC_API_KEY"]

WIKIPEDIA_URL = "https://en.wikipedia.org/w/api.php?action=query&titles=Top_Chef:_Carolinas&prop=revisions&rvprop=content&format=json&formatversion=2"

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

SYSTEM_PROMPT = """You are a scoring assistant for Family Fantasy Top Chef 2026.

Contestants: Duyen Ha, Rhoda Magbitang, Jonathan Dearden, Brandon Dearden, Jennifer Lee Jackson, Anthony Jones, Laurence Louie, Oscar Diaz, Sieger Bayer, Sherry Cardoso, Justin Tootla, Nana Araba Wilmot, Brittany Cochran, Day Joseph, Jassi Bindra.

SCORING RULES:
- Quickfire win: +1 per chef (each member of winning team gets +1 for team quickfires)
- Elimination winner: +2 ONLY (do NOT also give +1 top group)
- Top group (not winner): +1 each
- Bottom group (not eliminated): -1 each
- Eliminated: -2 ONLY (do NOT also give -1 bottom group)
- Finalist: +3, Season winner: +5
- EPISODE 3 SPECIAL RULE ONLY: every chef not in top group and not eliminated gets -1

VERIFIED SCORES eps 1-6 (do not change):
Ep1: Day Joseph -2
Ep2: Rhoda Magbitang +2, Laurence Louie +1, Sieger Bayer +1, Jennifer Lee Jackson +1, Nana Araba Wilmot -1, Justin Tootla -1, Jassi Bindra -2
Ep3: Laurence +2, Anthony +2, Brandon +1, Nana -2, Duyen -1, Rhoda -1, Jonathan -1, Jennifer -1, Oscar -1, Sieger -1, Sherry -1, Justin -1, Brittany -1
Ep4: Sieger +3, Laurence +1, Sherry +1, Justin +1, Jennifer 0, Anthony -1, Brittany -2
Ep5: Brandon +1, Anthony +2, Sherry +1, Duyen +1, Laurence -1, Oscar -1, Rhoda -2
Ep6: No quickfire. Laurence +2 (winner), Sherry +1 (top), Brandon +1 (top), Oscar +1 (smores challenge), Jonathan -1 (bottom), Justin -1 (bottom), Sieger -2 (eliminated)

The user will provide the raw Wikipedia page content. Use it to find any new episodes beyond ep5, score them, and return ONLY raw JSON with no markdown or explanation:
{
  "episodes": [
    {"ep": 1, "scores": {"Chef Name": points}},
    ...all aired episodes including eps 1-5 with verified scores above...
  ],
  "eliminated": ["Chef Name", ...in elimination order],
  "lastEpisode": <number of last aired episode>,
  "summaries": [
    {
      "ep": 1,
      "title": "Episode title",
      "date": "Mon DD, YYYY",
      "html": "Paragraph summary. MUST mention: who won the Quickfire (or note if there was none), the elimination challenge winner, top group chefs, bottom group chefs, and who was eliminated. Use these exact span formats: <span class=\\"pill pill-qf\\">Quickfire</span> <span class=\\"pill pill-win\\">winning dish</span> <span class=\\"pill pill-top\\">top group</span> <span class=\\"pill pill-bot\\">bottom</span> <span class=\\"pill pill-elim\\">eliminated</span>. Bold chef names with <strong>Name</strong>. Write fluid narrative prose with brief context about the challenge and why the eliminated chef went home."
    }
  ]
}
Only include non-zero scores per episode (include net-zero as 0 when offsetting scores cancel out)."""


def fetch_wikipedia():
    """Fetch raw Wikipedia page content via the MediaWiki API."""
    req = urllib.request.Request(
        WIKIPEDIA_URL,
        headers={"User-Agent": "TopChefFantasyScorer/1.0"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    pages = data["query"]["pages"]
    content = pages[0]["revisions"][0]["content"]
    print(f"Total Wikipedia content: {len(content)} chars")
    # Take up to 40000 chars to capture the full episode table
    return content[:40000]


def call_claude(wiki_content):
    """Send Wikipedia content to Claude and get scoring JSON back."""
    # Sanitize wiki content - remove control characters that break JSON encoding
    wiki_clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', wiki_content)
    # Truncate to avoid token limits - 30000 chars gives plenty of room for episode tables
    wiki_clean = wiki_clean[:30000]

    message = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4000,
        "system": SYSTEM_PROMPT,
        "messages": [{
            "role": "user",
            "content": "Here is the current Wikipedia page for Top Chef: Carolinas. Please score all aired episodes and return the JSON.\n\n" + wiki_clean
        }]
    }

    payload = json.dumps(message, ensure_ascii=True).encode("utf-8")

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

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise ValueError(f"API error {e.code}: {error_body}")

    text = "".join(b["text"] for b in data["content"] if b["type"] == "text")
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError(f"No JSON found in response. Got: {text[:500]}")
    return json.loads(match.group(0))


def build_contestants_js(data):
    MAX_EPS = 14
    chef_pts = {c["name"]: [0] * MAX_EPS for c in CONTESTANTS}

    # Apply Claude's scores first
    for ep in data["episodes"]:
        idx = ep["ep"] - 1
        if 0 <= idx < MAX_EPS:
            for chef, pts in ep["scores"].items():
                if chef in chef_pts:
                    chef_pts[chef][idx] = pts

    # Always override with verified scores for eps 1-6 — these never change
    VERIFIED = {
        "Day Joseph":            [ -2,  0,  0,  0,  0,  0],
        "Rhoda Magbitang":       [  0,  2, -1,  0, -2,  0],
        "Jonathan Dearden":      [  0,  0, -1,  0,  0, -1],
        "Brandon Dearden":       [  0,  0,  1,  0,  1,  1],
        "Jennifer Lee Jackson":  [  0,  1, -1,  0,  0,  0],
        "Anthony Jones":         [  0,  0,  2, -1,  2,  0],
        "Laurence Louie":        [  0,  1,  2,  1, -1,  2],
        "Oscar Diaz":            [  0,  0, -1,  0, -1,  1],
        "Sieger Bayer":          [  0,  1, -1,  3,  0, -2],
        "Sherry Cardoso":        [  0,  0, -1,  1,  1,  1],
        "Justin Tootla":         [  0, -1, -1,  1,  0, -1],
        "Nana Araba Wilmot":     [  0, -1, -2,  0,  0,  0],
        "Brittany Cochran":      [  0,  0, -1, -2,  0,  0],
        "Jassi Bindra":          [  0, -2,  0,  0,  0,  0],
        "Duyen Ha":              [  0,  0, -1,  0,  1,  0],
    }
    for chef, scores in VERIFIED.items():
        if chef in chef_pts:
            for i, s in enumerate(scores):
                chef_pts[chef][i] = s

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

    # Always use verified eliminated list — merge Claude's list with known eliminations
    VERIFIED_ELIMINATED = ["Day Joseph", "Jassi Bindra", "Nana Araba Wilmot", "Brittany Cochran", "Rhoda Magbitang", "Sieger Bayer"]
    claude_eliminated = data.get("eliminated", [])
    # Add any new eliminations Claude found beyond ep 6
    eliminated = list(VERIFIED_ELIMINATED)
    for chef in claude_eliminated:
        if chef not in eliminated:
            eliminated.append(chef)

    # --- Update contestants array ---
    new_contestants = build_contestants_js(data)
    html = re.sub(
        r"const contestants = \[[\s\S]*?\];",
        f"const contestants = [\n{new_contestants}\n];",
        html
    )

    # --- Update activeCols ---
    html = re.sub(r"const activeCols = \d+;", f"const activeCols = {last_ep};", html)

    # --- Update eliminatedNames ---
    elim_json = json.dumps(eliminated)
    html = re.sub(
        r"const eliminatedNames = new Set\(\[.*?\]\);",
        f"const eliminatedNames = new Set({elim_json});",
        html
    )

    # --- Update draft order strikethroughs ---
    for chef in eliminated:
        # Only update if not already marked eliminated
        html = re.sub(
            rf'(<span class="pick-name")( data-chef="{re.escape(chef)}")?(>)({re.escape(chef)})(</span>)',
            rf'<span class="pick-name eliminated"\2>\4\5',
            html
        )

    # --- Append only NEW episode summary cards (preserve existing ones) ---
    new_summaries = data.get("summaries", [])
    start_marker = '<div class="ep-summaries">'
    end_marker = '  </div>\n\n  <div class="footer">'

    start_idx = html.find(start_marker)
    end_idx = html.find(end_marker)

    if start_idx != -1 and end_idx != -1:
        existing_block = html[start_idx:end_idx]
        new_cards = []
        for s in new_summaries:
            ep_marker = f'<span class="ep-num">Ep {s["ep"]}</span>'
            if ep_marker not in existing_block:
                # This episode isn't in the HTML yet — add it
                card = f"""      <div class="ep-card">
        <div class="ep-card-header">
          <span class="ep-num">Ep {s['ep']}</span>
          <span class="ep-title">{s['title']}</span>
          <span class="ep-date">{s['date']}</span>
        </div>
        <div class="ep-card-body">
          {s['html']}
        </div>
      </div>"""
                new_cards.append(card)

        if new_cards:
            # Insert new cards just before the closing </div></div>
            insert_point = html.rfind('    </div>\n  </div>\n\n  <div class="footer">')
            if insert_point != -1:
                insertion = "\n\n" + "\n\n".join(new_cards) + "\n\n"
                html = html[:insert_point] + insertion + html[insert_point:]
                print(f"   Added {len(new_cards)} new episode summary card(s)")
        else:
            print("   No new episode summaries to add")
    else:
        print("⚠️  Warning: could not find ep-summaries markers in HTML")

    # --- Update footer ---
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
    print("Fetching Wikipedia page...")
    wiki_content = fetch_wikipedia()
    print(f"Got {len(wiki_content)} chars from Wikipedia")

    print("Sending to Claude for scoring...")
    try:
        data = call_claude(wiki_content)
    except Exception as e:
        print(f"❌ Claude API error: {e}")
        raise
    print(f"Got scoring data through Episode {data['lastEpisode']}")

    update_html(data)
