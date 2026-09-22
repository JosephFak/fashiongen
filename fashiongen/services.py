"""Asynchronous adapters for the demo's ImgBB → SerpAPI pipeline."""

import base64
import json
from urllib.parse import urlencode

from tornado.httpclient import AsyncHTTPClient, HTTPClientError, HTTPRequest

from .results import rank_results, safe_http_url


class ServiceError(Exception):
    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.status = status


async def fetch_json(request: HTTPRequest, provider: str, client=None) -> dict:
    client = client or AsyncHTTPClient()
    try:
        response = await client.fetch(request, raise_error=False)
    except (HTTPClientError, OSError) as exc:
        # Exception text can include a URL containing credentials. Never expose it.
        raise ServiceError(f"{provider} could not be reached. Please try again.", 504) from exc
    if response.code == 599:
        raise ServiceError(f"{provider} timed out. Please try again.", 504)
    if response.code == 429:
        raise ServiceError(f"{provider} rate limit reached. Check your account quota or try later.", 503)
    if response.code >= 400:
        raise ServiceError(f"{provider} returned HTTP {response.code}. Check its API key and account status.")
    try:
        data = json.loads(response.body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ServiceError(f"{provider} returned an unreadable response.") from exc
    if not isinstance(data, dict):
        raise ServiceError(f"{provider} returned an unexpected response.")
    return data


async def upload_image_to_imgbb(image: bytes, settings, client=None) -> str:
    request = HTTPRequest(
        "https://api.imgbb.com/1/upload", method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=urlencode({"key": settings.imgbb_api_key,
                        "image": base64.b64encode(image).decode("ascii"),
                        "expiration": settings.imgbb_expiration}),
        connect_timeout=10, request_timeout=45, follow_redirects=False,
    )
    response = await fetch_json(request, "ImgBB", client)
    data = response.get("data")
    url = safe_http_url(data.get("url")) if isinstance(data, dict) else ""
    if response.get("success") is not True or not url:
        raise ServiceError("ImgBB did not return a usable image URL. Check your account and retry.")
    return url


async def search_google_lens(image_url: str, settings, client=None) -> list[dict]:
    if not safe_http_url(image_url):
        raise ServiceError("The image host returned an invalid URL.")
    parameters = urlencode({
        "engine": "google_lens", "type": "visual_matches", "url": image_url,
        "api_key": settings.serpapi_api_key, "hl": "en", "safe": "active",
    })
    response = await fetch_json(HTTPRequest(
        f"https://serpapi.com/search.json?{parameters}",
        connect_timeout=10, request_timeout=60, follow_redirects=False,
    ), "SerpAPI", client)
    if response.get("error"):
        raise ServiceError("SerpAPI could not complete the Lens search. Check its dashboard and retry.")
    matches = response.get("visual_matches", [])
    if not isinstance(matches, list):
        raise ServiceError("SerpAPI returned an unexpected visual-matches format.")
    return rank_results(matches)
