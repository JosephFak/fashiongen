"""Stable Diffusion 3.5 Medium on Replicate; credentials stay on the server."""

import asyncio
import base64
import json
import re
import time
from urllib.parse import urlsplit

from tornado.httpclient import AsyncHTTPClient, HTTPClientError, HTTPRequest

from .images import normalize_image
from .services import ServiceError, fetch_json

API = "https://api.replicate.com/v1"
MODEL = "stability-ai/stable-diffusion-3.5-medium"


async def generate_hosted_image(prompt, settings, seed, client=None):
    client = client or AsyncHTTPClient()
    headers = {"Authorization": f"Bearer {settings.replicate_api_token}"}
    # Do not retry creation: a lost response might still have started a paid job.
    prediction = await fetch_json(HTTPRequest(
        f"{API}/models/{MODEL}/predictions", method="POST",
        headers={**headers, "Content-Type": "application/json", "Prefer": "wait=10", "Cancel-After": "180s"},
        body=json.dumps({"input": {"prompt": prompt, "seed": seed, "cfg": 4.5,
                                   "aspect_ratio": "1:1", "output_format": "png"}}),
        connect_timeout=10, request_timeout=25, follow_redirects=False,
    ), "Image generation", client)
    deadline = time.monotonic() + 180
    while prediction.get("status") in {"starting", "processing"}:
        prediction_id = prediction.get("id")
        if not isinstance(prediction_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", prediction_id):
            raise ServiceError("Image generation returned an invalid job identifier.")
        if time.monotonic() >= deadline:
            raise ServiceError("Image generation timed out. Please try again later.", 504)
        await asyncio.sleep(1)
        # Construct the URL ourselves; never forward a token to a response-supplied URL.
        prediction = await fetch_json(HTTPRequest(
            f"{API}/predictions/{prediction_id}", headers=headers,
            connect_timeout=10, request_timeout=15, follow_redirects=False,
        ), "Image generation", client)
    if prediction.get("status") != "succeeded":
        raise ServiceError("The image could not be generated. Try another description or check the provider account.", 503)
    output = prediction.get("output")
    if not isinstance(output, str):
        raise ServiceError("Image generation did not return an image.")
    try:
        url = urlsplit(output)
    except ValueError as exc:
        raise ServiceError("Image generation returned an unexpected image location.") from exc
    if (url.scheme != "https" or not url.hostname
            or not (url.hostname == "replicate.delivery" or url.hostname.endswith(".replicate.delivery"))
            or url.username or url.password or url.netloc.lower() != url.hostname.lower()):
        raise ServiceError("Image generation returned an unexpected image location.")

    chunks = []
    downloaded = 0

    def collect(chunk):
        nonlocal downloaded
        downloaded += len(chunk)
        if downloaded > settings.max_upload_bytes:
            raise ServiceError("The generated image exceeded the size limit.")
        chunks.append(chunk)

    try:
        response = await client.fetch(HTTPRequest(
            output, headers=headers, streaming_callback=collect,
            connect_timeout=10, request_timeout=30, follow_redirects=False,
        ), raise_error=False)
    except (HTTPClientError, OSError) as exc:
        raise ServiceError("The generated image could not be downloaded.", 504) from exc
    if response.code != 200:
        raise ServiceError("The generated image could not be downloaded.")
    try:
        image = await asyncio.to_thread(normalize_image, b"".join(chunks), settings.max_upload_bytes)
    except ValueError as exc:
        raise ServiceError("Image generation returned an unreadable image.") from exc
    # Browser receives image bytes, never the provider token or a credentialed URL.
    return "data:image/jpeg;base64," + base64.b64encode(image).decode("ascii")
