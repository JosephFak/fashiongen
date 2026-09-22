"""Normalize Lens results and promote above-average image resolution."""

from urllib.parse import urlsplit


def safe_http_url(value) -> str:
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        return ""
    try:
        parts = urlsplit(value)
        if parts.scheme in {"https", "http"} and parts.hostname and not parts.username and not parts.password:
            return value
    except ValueError:
        pass
    return ""


def positive_dimension(value) -> int:
    try:
        value = int(value)
        return value if 0 < value <= 100_000 else 0
    except (TypeError, ValueError, OverflowError):
        return 0


def rank_results(matches: list) -> list[dict]:
    results, seen = [], set()
    for item in matches[:200]:
        if not isinstance(item, dict):
            continue
        link = safe_http_url(item.get("link"))
        if not link or link in seen:
            continue
        seen.add(link)
        width, height = positive_dimension(item.get("image_width")), positive_dimension(item.get("image_height"))
        if not (width and height):
            width = positive_dimension(item.get("thumbnail_width"))
            height = positive_dimension(item.get("thumbnail_height"))
        price = item.get("price")
        results.append({
            "title": str(item.get("title") or "Untitled fashion result"),
            "source": str(item.get("source") or urlsplit(link).hostname),
            "link": link,
            "thumbnail": safe_http_url(item.get("thumbnail")) or safe_http_url(item.get("image")),
            "price": str(price.get("value") or "") if isinstance(price, dict) else "",
            "width": width, "height": height, "resolution": width * height,
        })
    known = [item["resolution"] for item in results if item["resolution"] > 0]
    average = sum(known) / len(known) if known else 0
    for item in results:
        item["premium"] = item["resolution"] > average if average else False
    return sorted(results, key=lambda item: -item["resolution"])
