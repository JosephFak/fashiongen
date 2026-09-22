import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

from tornado.httpclient import HTTPClientError

from fashiongen.config import Settings
from fashiongen.services import ServiceError, search_google_lens, upload_image_to_imgbb


def client_response(payload, status=200):
    return SimpleNamespace(fetch=AsyncMock(return_value=SimpleNamespace(code=status, body=json.dumps(payload).encode())))


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = Settings(imgbb_api_key="imgbb-test-key", serpapi_api_key="serp-test-key")

    async def test_imgbb_upload_contract(self):
        client = client_response({"success": True, "data": {"url": "https://i.ibb.co/demo/image.jpg"}})
        self.assertEqual(await upload_image_to_imgbb(b"image-data", self.config, client), "https://i.ibb.co/demo/image.jpg")
        request = client.fetch.call_args.args[0]
        self.assertEqual(request.method, "POST")
        data = parse_qs(request.body.decode())
        self.assertEqual(data["expiration"], ["600"])
        self.assertEqual(data["image"], ["aW1hZ2UtZGF0YQ=="])
        self.assertNotIn("imgbb-test-key", request.url)

    async def test_lens_contract_and_results(self):
        client = client_response({"visual_matches": [{"title": "Shoe", "link": "https://shop.test/shoe"}]})
        results = await search_google_lens("https://i.ibb.co/demo/image.jpg", self.config, client)
        self.assertEqual(results[0]["title"], "Shoe")
        query = parse_qs(urlsplit(client.fetch.call_args.args[0].url).query)
        self.assertEqual(query["engine"], ["google_lens"])
        self.assertEqual(query["type"], ["visual_matches"])
        self.assertEqual(query["url"], ["https://i.ibb.co/demo/image.jpg"])

    async def test_upstream_failure_never_turns_into_demo_results(self):
        client = client_response({"error": "Failure containing serp-test-key"})
        with self.assertRaises(ServiceError) as raised:
            await search_google_lens("https://i.ibb.co/demo/image.jpg", self.config, client)
        self.assertNotIn("serp-test-key", str(raised.exception))

    async def test_empty_search_is_valid(self):
        self.assertEqual(await search_google_lens("https://i.ibb.co/demo/image.jpg", self.config, client_response({})), [])

    async def test_http_rate_limit_has_actionable_error(self):
        with self.assertRaises(ServiceError) as raised:
            await upload_image_to_imgbb(b"image-data", self.config, client_response({}, 429))
        self.assertEqual(raised.exception.status, 503)
        self.assertIn("quota", str(raised.exception))

    async def test_invalid_provider_payload_is_rejected(self):
        for payload in [[], {"success": False}, {"success": True, "data": {"url": "javascript:alert(1)"}}]:
            with self.subTest(payload=payload), self.assertRaises(ServiceError):
                await upload_image_to_imgbb(b"data", self.config, client_response(payload))

    async def test_timeout_does_not_leak_request_url(self):
        client = SimpleNamespace(fetch=AsyncMock(side_effect=HTTPClientError(599, "secret-api-key")))
        with self.assertRaises(ServiceError) as raised:
            await search_google_lens("https://i.ibb.co/demo/image.jpg", self.config, client)
        self.assertEqual(raised.exception.status, 504)
        self.assertNotIn("secret-api-key", str(raised.exception))
