import asyncio
import base64
from dataclasses import replace
from http.cookies import SimpleCookie
import json
from unittest.mock import AsyncMock, patch

from tornado.httpclient import HTTPRequest
from tornado.testing import AsyncHTTPTestCase, gen_test

from fashiongen.config import Settings
from fashiongen.services import ServiceError
from server import make_app
from tests.test_images import png_image


class APITests(AsyncHTTPTestCase):
    def get_app(self):
        return make_app(Settings())

    def setUp(self):
        super().setUp()
        response = self.fetch("/")
        cookie = SimpleCookie()
        cookie.load(response.headers["Set-Cookie"])
        self.headers = {"Content-Type": "application/json", "Cookie": f"_xsrf={cookie['_xsrf'].value}",
                        "X-XSRFToken": cookie["_xsrf"].value}
        self.image = "data:image/png;base64," + base64.b64encode(png_image()).decode()

    def post(self, path, data):
        return self.fetch(path, method="POST", headers=self.headers, body=json.dumps(data))

    def test_home_and_config(self):
        self.assertIn(b"Fashion Search Platform", self.fetch("/").body)
        data = json.loads(self.fetch("/api/health").body)
        self.assertEqual(data["generation_mode"], "demo")
        self.assertNotIn("api_key", json.dumps(data))

    def test_generate_then_search(self):
        response = self.post("/api/text-to-image", {"prompt": "White sneakers with blue logos", "seed": 12})
        self.assertEqual(response.code, 200)
        data = json.loads(response.body)
        self.assertEqual(data["mode"], "demo")
        self.assertEqual(data["seed"], 12)
        self.assertEqual(self.fetch(data["image_url"]).code, 200)
        search = self.post("/api/image-search", {"image": self.image})
        self.assertEqual(search.code, 200)
        self.assertEqual(json.loads(search.body)["total"], 14)

    def test_invalid_prompts_and_seeds(self):
        for body in [{}, {"prompt": " "}, {"prompt": 15}, {"prompt": "x" * 1501}, {"prompt": "shoe", "seed": True}, {"prompt": "shoe", "seed": -1}]:
            with self.subTest(body=str(body)[:80]):
                self.assertEqual(self.post("/api/text-to-image", body).code, 400)

    def test_bad_json_and_missing_csrf(self):
        response = self.fetch("/api/text-to-image", method="POST", body="{bad", headers=self.headers)
        self.assertEqual(response.code, 400)
        response = self.fetch("/api/text-to-image", method="POST", body='{"prompt":"shoe"}', headers={"Content-Type": "application/json"})
        self.assertEqual(response.code, 403)

    def test_invalid_uploaded_image(self):
        response = self.post("/api/image-search", {"image": "not-an-image"})
        self.assertEqual(response.code, 400)

    def test_multipart_upload(self):
        boundary = "FashionGenTestBoundary"
        payload = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"shoe.png\"\r\nContent-Type: image/png\r\n\r\n".encode()
                   + png_image() + f"\r\n--{boundary}--\r\n".encode())
        response = self.fetch("/api/image-search", method="POST", body=payload,
                              headers={**self.headers, "Content-Type": f"multipart/form-data; boundary={boundary}"})
        self.assertEqual(response.code, 200)

    def test_live_search_executes_pipeline(self):
        self._app.settings["config"] = replace(Settings(), search_mode="live", imgbb_api_key="fake", serpapi_api_key="fake")
        with patch("server.upload_image_to_imgbb", AsyncMock(return_value="https://i.ibb.co/test/image.jpg")) as upload, \
             patch("server.search_google_lens", AsyncMock(return_value=[])) as search:
            response = self.post("/api/image-search", {"image": self.image})
        self.assertEqual(response.code, 200)
        self.assertEqual(json.loads(response.body)["mode"], "live")
        self.assertEqual(json.loads(response.body)["results"], [])
        upload.assert_awaited_once()
        self.assertEqual(search.call_args.args[0], "https://i.ibb.co/test/image.jpg")

    def test_live_search_error_is_explicit(self):
        self._app.settings["config"] = replace(Settings(), search_mode="live", imgbb_api_key="fake", serpapi_api_key="fake")
        with patch("server.upload_image_to_imgbb", AsyncMock(side_effect=ServiceError("ImgBB unavailable."))):
            response = self.post("/api/image-search", {"image": self.image})
        self.assertEqual(response.code, 502)
        self.assertEqual(json.loads(response.body)["error"], "ImgBB unavailable.")

    @gen_test
    async def test_generation_does_not_block_health_and_rejects_duplicate_jobs(self):
        self._app.settings["config"] = replace(Settings(), generation_mode="live")
        self._app.settings["pipeline"] = object()
        started, released = asyncio.Event(), asyncio.Event()

        async def generate(*args):
            started.set()
            await released.wait()
            return self.image

        def request():
            return HTTPRequest(self.get_url("/api/text-to-image"), method="POST", headers=self.headers,
                               body=json.dumps({"prompt": "blue sneakers"}))

        with patch("server.asyncio.to_thread", side_effect=generate):
            first = self.http_client.fetch(request())
            await asyncio.wait_for(started.wait(), timeout=1)
            try:
                health = await self.http_client.fetch(self.get_url("/api/health"))
                self.assertEqual(health.code, 200)
                second = await self.http_client.fetch(request(), raise_error=False)
                self.assertEqual(second.code, 429)
            finally:
                released.set()
            self.assertEqual((await first).code, 200)
