"""
Crypto Daily Suggestion Bot
Fetches top losers from CoinGecko and uses Claude to suggest the best coin to invest in.
"""

import os
import json
import requests
import anthropic
from datetime import datetime


COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd"
    "&order=price_change_percentage_24h_asc"
    "&per_page=20"
    "&page=1"
    "&sparkline=false"
    "&price_change_percentage=24h"
)


def fetch_top_losers() -> list[dict]:
    """Fetch top 20 losers from CoinGecko (sorted by 24h % change ascending)."""
    headers = {"accept": "application/json"}
    response = requests.get(COINGECKO_URL, headers=headers, timeout=15)
    response.raise_for_status()
    coins = response.json()
    # Keep only relevant fields
    losers = [
        {
            "rank": c.get("market_cap_rank"),
            "name": c.get("name"),
            "symbol": c.get("symbol", "").upper(),
            "price_usd": c.get("current_price"),
            "change_24h_pct": c.get("price_change_percentage_24h"),
            "market_cap_usd": c.get("market_cap"),
            "volume_24h_usd": c.get("total_volume"),
            "high_24h": c.get("high_24h"),
            "low_24h": c.get("low_24h"),
            "ath": c.get("ath"),
            "ath_change_pct": c.get("ath_change_percentage"),
        }
        for c in coins
        if c.get("price_change_percentage_24h") is not None
        and c.get("price_change_percentage_24h") < 0
    ]
    return losers


def analyze_with_claude(losers: list[dict]) -> str:
    """Send losers data to Claude and get an investment suggestion."""
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    data_str = json.dumps(losers, indent=2)
    today = datetime.now().strftime("%B %d, %Y")

    prompt = f"""Today is {today}. Below is a list of the top crypto losers over the last 24 hours from CoinGecko.

TOP LOSERS DATA:
{data_str}

Based on this data, please analyze each coin and suggest ONE best coin to consider investing in today. Your analysis should cover:

1. **Overview of the losers** — brief summary of the market situation
2. **Top pick** — which coin and why (consider market cap rank, volume, how far it is from ATH, magnitude of the dip)
3. **Key reasons** — bullet points explaining the choice
4. **Risk factors** — what to watch out for
5. **Disclaimer** — standard investment disclaimer

Be concise and direct. Format your response clearly with headers."""

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=1024,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()

    text_blocks = [b.text for b in response.content if b.type == "text"]
    return "\n".join(text_blocks)


def run_daily_suggestion():
    """Main entry point: fetch losers, analyze, print and save result."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'='*60}")
    print(f"  Crypto Daily Suggestion Bot — {timestamp}")
    print(f"{'='*60}\n")

    print("Fetching top losers from CoinGecko...")
    try:
        losers = fetch_top_losers()
    except requests.RequestException as e:
        print(f"ERROR: Failed to fetch data — {e}")
        return

    if not losers:
        print("No losers data found. Skipping analysis.")
        return

    print(f"Found {len(losers)} losing coins. Sending to Claude for analysis...\n")

    try:
        suggestion = analyze_with_claude(losers)
    except anthropic.APIError as e:
        print(f"ERROR: Claude API call failed — {e}")
        return

    print(suggestion)

    # Save to file
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"suggestion_{datetime.now().strftime('%Y-%m-%d')}.txt")
    with open(log_file, "w") as f:
        f.write(f"Crypto Daily Suggestion — {timestamp}\n")
        f.write("=" * 60 + "\n\n")
        f.write(suggestion)
        f.write("\n\n--- Raw Losers Data ---\n")
        f.write(json.dumps(losers, indent=2))

    print(f"\n[Saved to {log_file}]")


if __name__ == "__main__":
    run_daily_suggestion()
