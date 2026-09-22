"""Run with `python server.py`, then visit http://localhost:8888."""

import asyncio
import json
import logging
from pathlib import Path
import secrets
import signal
import time

from dotenv import load_dotenv
from tornado.httpserver import HTTPServer
from tornado.web import Application, HTTPError, RequestHandler, StaticFileHandler

from fashiongen.config import Settings
from fashiongen.fixtures import demo_results
from fashiongen.images import decode_image, normalize_image
from fashiongen.model import generate_image, setup_stable_diffusion
from fashiongen.services import ServiceError, search_google_lens, upload_image_to_imgbb

ROOT = Path(__file__).resolve().parent
LOGGER = logging.getLogger("fashiongen")


class BaseHandler(RequestHandler):
    @property
    def config(self):
        return self.application.settings["config"]

    def set_default_headers(self):
        self.set_header("X-Content-Type-Options", "nosniff")
        self.set_header("Referrer-Policy", "no-referrer")
        self.set_header("Cache-Control", "no-store")
        self.set_header("Content-Security-Policy", (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data: blob: https: http:; connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        ))

    def read_json(self) -> dict:
        if self.request.headers.get("Content-Type", "").split(";")[0] != "application/json":
            raise HTTPError(415, reason="Send JSON with Content-Type: application/json.")
        try:
            body = json.loads(self.request.body)
        except (ValueError, UnicodeDecodeError) as exc:
            raise HTTPError(400, reason="Request body must contain valid JSON.") from exc
        if not isinstance(body, dict):
            raise HTTPError(400, reason="Request body must be a JSON object.")
        return body

    def write_error(self, status_code, **kwargs):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        reason = self._reason if status_code < 500 else "The server could not complete this request."
        if "exc_info" in kwargs and isinstance(kwargs["exc_info"][1], HTTPError):
            reason = kwargs["exc_info"][1].reason or reason
        self.finish({"error": reason})


class HomeHandler(BaseHandler):
    async def get(self):
        _ = self.xsrf_token
        self.set_header("Content-Type", "text/html; charset=UTF-8")
        self.finish((ROOT / "static" / "index.html").read_text())


class HealthHandler(BaseHandler):
    def get(self):
        self.write({
            "status": "ok", "generation_mode": self.config.generation_mode,
            "search_mode": self.config.search_mode, "model": self.config.model_id,
            "model_ready": self.application.settings["pipeline"] is not None,
            "max_upload_bytes": self.config.max_upload_bytes,
            "upload_expiration_seconds": self.config.imgbb_expiration,
        })


class TextToImageHandler(BaseHandler):
    async def post(self):
        data = self.read_json()
        prompt = data.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 1500:
            raise HTTPError(400, reason="Enter a description between 1 and 1,500 characters.")
        seed = data.get("seed", secrets.randbelow(2**32))
        if type(seed) is not int or not 0 <= seed < 2**32:
            raise HTTPError(400, reason="Seed must be an integer between 0 and 4,294,967,295.")
        lock = self.application.settings["generation_lock"]
        if lock.locked():
            self.set_header("Retry-After", "20")
            raise HTTPError(429, reason="Another image is being generated. Please try again shortly.")
        start = time.perf_counter()
        async with lock:
            if self.config.generation_mode == "demo":
                image = "/static/assets/demo-sneaker.svg"
            else:
                pipeline = self.application.settings["pipeline"]
                if pipeline is None:
                    raise HTTPError(503, reason="The image model is not loaded. Restart the server after checking setup.")
                try:
                    image = await asyncio.to_thread(generate_image, pipeline, prompt.strip(), self.config, seed)
                except Exception as exc:
                    LOGGER.error("Generation failed (%s).", type(exc).__name__)
                    raise HTTPError(503, reason="Image generation failed. Check GPU memory and model setup, then retry.") from exc
        self.write({"image_url": image, "mode": self.config.generation_mode,
                    "seed": seed, "elapsed_seconds": round(time.perf_counter() - start, 3)})


class ImageSearchHandler(BaseHandler):
    async def post(self):
        start = time.perf_counter()
        limit = self.config.max_upload_bytes
        try:
            if self.request.headers.get("Content-Type", "").startswith("multipart/form-data"):
                files = self.request.files.get("image", [])
                if len(files) != 1:
                    raise HTTPError(400, reason="Upload exactly one image using the image field.")
                image = await asyncio.to_thread(normalize_image, files[0]["body"], limit)
            else:
                image = await asyncio.to_thread(decode_image, self.read_json().get("image"), limit)
        except ValueError as exc:
            raise HTTPError(400, reason=str(exc)) from exc
        if self.config.search_mode == "demo":
            results = demo_results()
        else:
            try:
                image_url = await upload_image_to_imgbb(image, self.config)
                results = await search_google_lens(image_url, self.config)
            except ServiceError as exc:
                raise HTTPError(exc.status, reason=str(exc)) from exc
        self.write({"results": results, "total": len(results), "mode": self.config.search_mode,
                    "elapsed_seconds": round(time.perf_counter() - start, 3)})


class NotFoundHandler(BaseHandler):
    def prepare(self):
        raise HTTPError(404, reason="This endpoint does not exist.")


def make_app(config=None, pipeline=None):
    config = config or Settings.from_env()
    config.validate()
    return Application([
        (r"/", HomeHandler),
        (r"/api/health", HealthHandler),
        (r"/api/text-to-image", TextToImageHandler),
        (r"/api/image-search", ImageSearchHandler),
        (r"/static/(.*)", StaticFileHandler, {"path": ROOT / "static"}),
    ], config=config, pipeline=pipeline, generation_lock=asyncio.Lock(),
        xsrf_cookies=True, xsrf_cookie_kwargs={"samesite": "Strict"},
        default_handler_class=NotFoundHandler, debug=False)


async def main():
    load_dotenv(ROOT / ".env")
    config = Settings.from_env()
    pipeline = None
    if config.generation_mode == "live":
        LOGGER.info("Preloading Stable Diffusion 3.5 Medium before starting the server…")
        pipeline = await asyncio.to_thread(setup_stable_diffusion, config)
    app = make_app(config, pipeline)
    # Includes base64 and multipart overhead; decoded image size is checked separately.
    server = HTTPServer(app, max_body_size=15 * 1024 * 1024, idle_connection_timeout=300)
    server.listen(config.port, address=config.host)
    LOGGER.info("FashionGen running at http://%s:%s (generation=%s, search=%s)",
                config.host, config.port, config.generation_mode, config.search_mode)
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stopped.set)
        except NotImplementedError:
            pass  # Windows falls back to KeyboardInterrupt.
    await stopped.wait()
    server.stop()
    await server.close_all_connections()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except (ValueError, RuntimeError) as exc:
        LOGGER.error("Startup failed: %s", exc)
        raise SystemExit(1)
