#!/usr/bin/env python3
"""Refresh brief-data.json from Yahoo Finance quotes and headline feeds.

Uses only the Python standard library. Quote figures are the latest daily
chart print (regular-session close when the equity session is over). Group
analysis is a factual read of those moves, not a recommendation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "brief-data.json"
CENTRAL = ZoneInfo("America/Chicago")
NOTICE_MENTION = "@chriso22"
PAGES_URL = "https://chriso22.github.io/daily-investment-brief/"
USER_AGENT = (
    "daily-investment-brief/1.0 "
    "(+https://github.com/chriso22/daily-investment-brief)"
)
HEADLINES_PER_GROUP = 4
REQUEST_TIMEOUT = 20

GROUPS = [
    {
        "id": "bitcoin",
        "title": "Bitcoin",
        "kicker": "Crypto",
        "blurb": "U.S. dollar spot price.",
        "symbols": [
            {"symbol": "BTC-USD", "label": "Bitcoin", "note": "Spot"},
        ],
    },
    {
        "id": "bitcoin-equities",
        "title": "Bitcoin-linked equities",
        "kicker": "Equities",
        "blurb": "Strategy, Strive, and Twenty One Capital.",
        "symbols": [
            {"symbol": "MSTR", "label": "Strategy", "note": "Bitcoin treasury"},
            {"symbol": "ASST", "label": "Strive", "note": "Bitcoin treasury"},
            {"symbol": "XXI", "label": "Twenty One Capital", "note": "Bitcoin treasury"},
        ],
    },
    {
        "id": "space-defense",
        "title": "Space & defense",
        "kicker": "Equities",
        "blurb": "SpaceX, AST SpaceMobile, and Merlin.",
        "symbols": [
            {
                "symbol": "SPCX",
                "label": "SpaceX",
                "note": "Space Exploration Technologies",
            },
            {"symbol": "ASTS", "label": "AST SpaceMobile", "note": "Satellite connectivity"},
            {"symbol": "MRLN", "label": "Merlin", "note": "Autonomous flight"},
        ],
    },
]

SOURCE_NAMES = {
    "finance.yahoo.com": "Yahoo Finance",
    "yahoo.com": "Yahoo",
    "investopedia.com": "Investopedia",
    "247wallst.com": "24/7 Wall St.",
    "reuters.com": "Reuters",
    "cnbc.com": "CNBC",
    "bloomberg.com": "Bloomberg",
    "coindesk.com": "CoinDesk",
    "theblock.co": "The Block",
    "barrons.com": "Barron's",
    "marketwatch.com": "MarketWatch",
    "wsj.com": "WSJ",
    "ft.com": "Financial Times",
    "benzinga.com": "Benzinga",
    "seekingalpha.com": "Seeking Alpha",
    "fool.com": "Motley Fool",
    "decrypt.co": "Decrypt",
    "cointelegraph.com": "Cointelegraph",
    "cryptoprowl.com": "CryptoProwl",
    "stocktwits.com": "Stocktwits",
}

BITCOIN_TERMS = ("bitcoin", "btc", "crypto")
NAME_TERMS = {
    "BTC-USD": ("bitcoin", "btc"),
    "MSTR": ("mstr", "strategy", "microstrategy"),
    "ASST": ("asst", "strive"),
    "XXI": ("xxi", "twenty one"),
    "SPCX": ("spcx", "spacex"),
    "ASTS": ("asts", "ast spacemobile", "spacemobile"),
    "MRLN": ("mrln", "merlin"),
}
TRACKING_PARAMS = {"tsrc", "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content"}


class FetchError(Exception):
    pass


def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise FetchError(str(last_error)) from last_error


def chart_url(symbol: str) -> str:
    query = urllib.parse.urlencode({"range": "5d", "interval": "1d"})
    return (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(symbol)}?{query}"
    )


def rss_url(symbol: str) -> str:
    query = urllib.parse.urlencode({"s": symbol, "region": "US", "lang": "en-US"})
    return f"https://feeds.finance.yahoo.com/rss/2.0/headline?{query}"


def round_num(value: float, places: int = 4) -> float:
    return round(float(value), places)


def round_pct(value: float) -> float:
    quantized = Decimal(f"{value:.6f}").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(quantized)


def session_label(meta: dict, now: float) -> str:
    """Label the print we actually store.

    Equity rows use the regular-session price, including while pre-market or
    after-hours trading is open, so those rows stay marked as the regular close.
    """
    if meta.get("instrumentType") == "CRYPTOCURRENCY":
        return "24-hour"
    period = meta.get("currentTradingPeriod") or {}
    window = period.get("regular") or {}
    start = window.get("start")
    end = window.get("end")
    if start is not None and end is not None and start <= now < end:
        return "Regular session"
    return "Regular close"


def parse_quote(spec: dict, payload: dict, now: float) -> dict:
    result = (payload.get("chart") or {}).get("result") or [None]
    chart = result[0]
    error = (payload.get("chart") or {}).get("error")
    if not chart:
        description = (error or {}).get("description") or "No chart returned"
        raise FetchError(description)

    meta = chart.get("meta") or {}
    price = meta.get("regularMarketPrice")
    if price is None:
        raise FetchError("Missing regular market price")

    change_percent = meta.get("regularMarketChangePercent")
    previous_close = None
    change = None
    if change_percent is not None and (1 + change_percent / 100) != 0:
        previous_close = price / (1 + change_percent / 100)
        change = price - previous_close

    quote_block = ((chart.get("indicators") or {}).get("quote") or [{}])[0]
    closes = [value for value in (quote_block.get("close") or []) if value is not None]
    five_session = None
    if closes and closes[0]:
        five_session = (price / closes[0] - 1) * 100

    as_of = meta.get("regularMarketTime")
    as_of_iso = None
    if isinstance(as_of, (int, float)):
        as_of_iso = datetime.fromtimestamp(as_of, timezone.utc).isoformat()

    return {
        "symbol": spec["symbol"],
        "label": spec["label"],
        "note": spec["note"],
        "official_name": meta.get("longName") or meta.get("shortName") or spec["label"],
        "currency": meta.get("currency") or "USD",
        "price": round_num(price),
        "change": round_num(change) if change is not None else None,
        "change_percent": round_pct(change_percent) if change_percent is not None else None,
        "previous_close": round_num(previous_close) if previous_close is not None else None,
        "day_high": round_num(meta["regularMarketDayHigh"]) if meta.get("regularMarketDayHigh") is not None else None,
        "day_low": round_num(meta["regularMarketDayLow"]) if meta.get("regularMarketDayLow") is not None else None,
        "volume": meta.get("regularMarketVolume"),
        "five_session_change_percent": round_pct(five_session) if five_session is not None else None,
        "closes": [round_num(value) for value in closes],
        "session": session_label(meta, now),
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName"),
        "as_of": as_of_iso,
        "timezone": meta.get("exchangeTimezoneName") or "America/New_York",
    }


def failed_quote(spec: dict, message: str) -> dict:
    return {
        "symbol": spec["symbol"],
        "label": spec["label"],
        "note": spec["note"],
        "official_name": spec["label"],
        "error": message,
        "currency": "USD",
        "price": None,
        "change": None,
        "change_percent": None,
        "previous_close": None,
        "day_high": None,
        "day_low": None,
        "volume": None,
        "five_session_change_percent": None,
        "closes": [],
        "session": None,
        "exchange": None,
        "as_of": None,
        "timezone": "America/New_York",
    }


def load_quote(spec: dict, now: float) -> dict:
    raw = fetch_bytes(chart_url(spec["symbol"]))
    payload = json.loads(raw.decode("utf-8"))
    return parse_quote(spec, payload, now)


def strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", text).strip()


def truncate(value: str, limit: int = 180) -> str:
    text = strip_tags(value)
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(".,;:")
    return cut + "..."


def clean_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qsl(parts.query, keep_blank_values=False)
    kept = [
        (key, item)
        for key, item in query
        if key.lower().lstrip(".") not in TRACKING_PARAMS
    ]
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(kept), "")
    )


def source_from_url(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")
    if host in SOURCE_NAMES:
        return SOURCE_NAMES[host]
    for domain, name in SOURCE_NAMES.items():
        if host.endswith("." + domain) or host == domain:
            return name
    stem = host.split(".")[0]
    return stem.replace("-", " ").title() or "News"


def parse_rss(xml_bytes: bytes, symbol: str) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    items = []
    for item in root.findall("./channel/item"):
        title = strip_tags(item.findtext("title") or "")
        link = (item.findtext("link") or "").strip()
        if not title or not link.startswith(("http://", "https://")):
            continue
        published = item.findtext("pubDate") or ""
        published_iso = None
        if published:
            try:
                published_iso = parsedate_to_datetime(published).astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError, IndexError):
                published_iso = None
        items.append(
            {
                "title": title,
                "url": clean_url(link),
                "source": source_from_url(link),
                "published": published_iso,
                "summary": truncate(item.findtext("description") or ""),
                "symbol": symbol,
            }
        )
    return items


def title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def story_text(story: dict) -> str:
    return f"{story['title']} {story['summary']}".lower()


def mentions_symbol(story: dict, symbol: str) -> bool:
    terms = NAME_TERMS.get(symbol, (symbol.lower(),))
    text = story_text(story)
    return any(term in text for term in terms)


def relevant_story(story: dict, symbol: str) -> bool:
    if symbol != "BTC-USD":
        return True
    text = story_text(story)
    return any(term in text for term in BITCOIN_TERMS)


def select_headlines(by_symbol: dict[str, list[dict]]) -> list[dict]:
    """One recent on-topic headline per symbol, then fill with the next best."""
    picked: list[dict] = []
    seen: set[str] = set()

    def take(story: dict) -> bool:
        key = title_key(story["title"])
        if not key or key in seen:
            return False
        seen.add(key)
        picked.append(story)
        return True

    for symbol, stories in by_symbol.items():
        named = [story for story in stories if mentions_symbol(story, symbol)]
        for story in named or stories:
            if take(story):
                break

    rest = [story for stories in by_symbol.values() for story in stories]
    rest.sort(
        key=lambda story: (
            mentions_symbol(story, story["symbol"]),
            story.get("published") or "",
        ),
        reverse=True,
    )
    for story in rest:
        if len(picked) >= HEADLINES_PER_GROUP:
            break
        take(story)
    picked.sort(key=lambda story: story.get("published") or "", reverse=True)
    return picked[:HEADLINES_PER_GROUP]


def load_headlines(symbols: list[str]) -> list[dict]:
    by_symbol: dict[str, list[dict]] = {}
    for symbol in symbols:
        try:
            raw = fetch_bytes(rss_url(symbol))
            stories = [
                story for story in parse_rss(raw, symbol)
                if relevant_story(story, symbol)
            ]
        except (FetchError, ET.ParseError, json.JSONDecodeError) as exc:
            print(f"Headlines unavailable for {symbol}: {exc}", file=sys.stderr)
            continue
        stories.sort(key=lambda story: story.get("published") or "", reverse=True)
        by_symbol[symbol] = stories
    return select_headlines(by_symbol)


def signed_pct(value: float) -> str:
    if abs(value) < 0.005:
        return "0.00%"
    sign = "−" if value < 0 else "+"
    return f"{sign}{abs(value):.2f}%"


def format_price(value: float) -> str:
    if abs(value) >= 10000:
        return f"${value:,.0f}"
    return f"${value:,.2f}"


def bucket(pct: float) -> str:
    if pct > 0.05:
        return "up"
    if pct < -0.05:
        return "down"
    return "flat"


def verb_for(quotes: list[dict]) -> str:
    sessions = {quote.get("session") for quote in quotes}
    if sessions == {"Regular session"} or sessions == {"Pre-market"}:
        return "trading"
    if sessions == {"24-hour"}:
        return "trading"
    return "closed"


def range_sentence(quote: dict) -> str:
    low = quote.get("day_low")
    high = quote.get("day_high")
    if low is None or high is None:
        return ""
    return f"The session ranged from {format_price(low)} to {format_price(high)}."


def five_sentence(quote: dict, subject: str) -> str:
    move = quote.get("five_session_change_percent")
    if move is None:
        return ""
    if abs(move) < 0.05:
        return f"Across the last five sessions, {subject} is about flat."
    direction = "higher" if move > 0 else "lower"
    return (
        f"Across the last five sessions, {subject} is "
        f"{abs(move):.2f}% {direction}."
    )


def single_analysis(quote: dict) -> str:
    if quote.get("error") or quote.get("price") is None or quote.get("change_percent") is None:
        return f"{quote['label']} ({quote['symbol']}) did not return a quote."
    price = format_price(quote["price"])
    move = signed_pct(quote["change_percent"])
    session = quote.get("session")
    if session == "24-hour":
        lead = f"{quote['label']} is at {price}, {move} from the prior daily close."
    elif session == "Regular session":
        lead = f"{quote['label']} is trading at {price}, {move} on the session."
    elif session == "Pre-market":
        lead = f"{quote['label']} is indicated at {price}, {move} versus the prior close."
    else:
        lead = f"{quote['label']} closed at {price}, {move} on the session."
    parts = [lead, five_sentence(quote, quote["label"]), range_sentence(quote)]
    return " ".join(part for part in parts if part)


COUNT_WORDS = {1: "One", 2: "Two", 3: "Three"}


def count_label(count: int) -> str:
    return COUNT_WORDS.get(count, str(count)).lower()


def name_move(count: int, past: bool, direction: str) -> str:
    noun = "name" if count == 1 else "names"
    if direction == "flat":
        verb = ("was" if count == 1 else "were") if past else ("is" if count == 1 else "are")
        return f"{count_label(count)} {noun} {verb} little changed"
    if past:
        action = "closed higher" if direction == "up" else "closed lower"
        return f"{count_label(count)} {noun} {action}"
    verb = "is" if count == 1 else "are"
    word = "higher" if direction == "up" else "lower"
    return f"{count_label(count)} {noun} {verb} {word}"


def breadth_clause(quotes: list[dict], past: bool) -> str:
    counts = {"up": 0, "down": 0, "flat": 0}
    for quote in quotes:
        counts[bucket(quote["change_percent"])] += 1
    if counts["up"] == len(quotes):
        action = "closed higher" if past else "are higher"
        return f"All {count_label(len(quotes))} names {action}."
    if counts["down"] == len(quotes):
        action = "closed lower" if past else "are lower"
        return f"All {count_label(len(quotes))} names {action}."
    fragments = [
        name_move(counts[direction], past, direction)
        for direction in ("up", "down", "flat")
        if counts[direction]
    ]
    if not fragments:
        return "No session moves were available."
    return _join_fragments(fragments) + "."


def _join_fragments(fragments: list[str]) -> str:
    parts = list(fragments)
    if parts:
        parts[0] = parts[0][:1].upper() + parts[0][1:]
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return f"{parts[0]}, {parts[1]}, and {parts[2]}"


def group_analysis(quotes: list[dict]) -> str:
    usable = [
        quote for quote in quotes
        if quote.get("price") is not None and quote.get("change_percent") is not None
    ]
    missing = [quote for quote in quotes if quote not in usable]
    if not usable:
        names = ", ".join(quote["symbol"] for quote in quotes)
        return f"Quotes were unavailable for {names}."
    if len(quotes) == 1 and not missing:
        return single_analysis(usable[0])

    past = verb_for(usable) == "closed"
    parts = [breadth_clause(usable, past)]
    leader = max(usable, key=lambda quote: quote["change_percent"])
    laggard = min(usable, key=lambda quote: quote["change_percent"])
    if leader["symbol"] != laggard["symbol"]:
        lead_pct = leader["change_percent"]
        lag_pct = laggard["change_percent"]
        lead = f"{leader['label']} ({leader['symbol']})"
        lag = f"{laggard['label']} ({laggard['symbol']})"
        if lead_pct > 0.05 and lag_pct > 0.05:
            parts.append(
                f"{lead} leads at {signed_pct(lead_pct)}; "
                f"{lag} is the smallest gain at {signed_pct(lag_pct)}."
            )
        elif lead_pct < -0.05 and lag_pct < -0.05:
            parts.append(
                f"{lag} is down the most at {signed_pct(lag_pct)}; "
                f"{lead} held up best at {signed_pct(lead_pct)}."
            )
        else:
            parts.append(
                f"{lead} leads at {signed_pct(lead_pct)}; "
                f"{lag} lags at {signed_pct(lag_pct)}."
            )
    average = sum(quote["change_percent"] for quote in usable) / len(usable)
    parts.append(f"The average session move is {signed_pct(average)}.")
    five_bits = []
    for quote in usable:
        move = quote.get("five_session_change_percent")
        if move is not None:
            five_bits.append(f"{quote['symbol']} {signed_pct(move)}")
    if five_bits:
        parts.append("Five-session moves: " + ", ".join(five_bits) + ".")
    if missing:
        names = ", ".join(quote["symbol"] for quote in missing)
        parts.append(f"No quote for {names}.")
    return " ".join(parts)


def build_brief(now: datetime | None = None) -> dict:
    moment = now or datetime.now(timezone.utc)
    now_ts = moment.timestamp()
    groups = []
    warnings = []
    for spec in GROUPS:
        quotes = []
        for symbol_spec in spec["symbols"]:
            try:
                quotes.append(load_quote(symbol_spec, now_ts))
            except (FetchError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                message = str(exc)
                print(f"Quote failed for {symbol_spec['symbol']}: {message}", file=sys.stderr)
                warnings.append(f"{symbol_spec['symbol']}: {message}")
                quotes.append(failed_quote(symbol_spec, message))
        headlines = load_headlines([item["symbol"] for item in spec["symbols"]])
        groups.append(
            {
                "id": spec["id"],
                "title": spec["title"],
                "kicker": spec["kicker"],
                "blurb": spec["blurb"],
                "analysis": group_analysis(quotes),
                "quotes": quotes,
                "headlines": headlines,
            }
        )
    payload = {
        "generated_at": moment.isoformat(),
        "source": "Yahoo Finance",
        "disclaimer": (
            "Delayed market data for information only. Not investment advice."
        ),
        "groups": groups,
    }
    if warnings:
        payload["warnings"] = warnings
    return payload


def write_brief(payload: dict, path: Path = OUTPUT_PATH) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def print_summary(payload: dict) -> None:
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)}")
    for group in payload["groups"]:
        print(group["title"])
        for quote in group["quotes"]:
            if quote.get("price") is None:
                print(f"  {quote['symbol']}: unavailable")
                continue
            move = quote.get("change_percent")
            move_text = signed_pct(move) if move is not None else "n/a"
            print(f"  {quote['symbol']}: {format_price(quote['price'])} ({move_text})")
        print(f"  headlines: {len(group['headlines'])}")


def central_stamp(generated_at: str | None) -> str:
    if not generated_at:
        return "this morning"
    try:
        moment = datetime.fromisoformat(generated_at)
    except ValueError:
        return "this morning"
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(CENTRAL)
    hour = local.strftime("%I").lstrip("0") or "12"
    clock = f"{hour}:{local.strftime('%M')} {local.strftime('%p').lower()}"
    zone = local.tzname() or "CT"
    return f"{local.strftime('%A, %B')} {local.day}, {clock} {zone}"


def format_notice(payload: dict) -> str:
    lines = [
        (
            f"{NOTICE_MENTION} The Daily Investment Brief is ready "
            f"({central_stamp(payload.get('generated_at'))})."
        ),
        "",
    ]
    for group in payload.get("groups") or []:
        for quote in group.get("quotes") or []:
            label = quote.get("label") or quote.get("symbol")
            symbol = quote.get("symbol")
            if quote.get("price") is None or quote.get("change_percent") is None:
                lines.append(f"- {label} ({symbol}): unavailable")
                continue
            lines.append(
                f"- {label} ({symbol}): {format_price(quote['price'])} "
                f"({signed_pct(quote['change_percent'])})"
            )
    lines.extend(
        [
            "",
            PAGES_URL,
            "",
            payload.get("disclaimer")
            or "Delayed market data for information only. Not investment advice.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def write_notice(path: Path) -> int:
    if not OUTPUT_PATH.exists():
        print("brief-data.json is missing. Run a refresh first.", file=sys.stderr)
        return 1
    payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    path.write_text(format_notice(payload), encoding="utf-8")
    print(f"Wrote {path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh the daily investment brief.")
    parser.add_argument(
        "--notice-body",
        type=Path,
        help="Write a GitHub notice from the saved brief-data.json and exit.",
    )
    args = parser.parse_args()
    if args.notice_body is not None:
        return write_notice(args.notice_body)

    payload = build_brief()
    priced = [
        quote
        for group in payload["groups"]
        for quote in group["quotes"]
        if quote.get("price") is not None
    ]
    if not priced:
        print("No quotes were retrieved.", file=sys.stderr)
        return 1
    write_brief(payload)
    print_summary(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
