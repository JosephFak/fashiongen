# Implementation notes

## Mapping to the supplied demo

| Demo feature | Implementation |
| --- | --- |
| HTML and JavaScript frontend | `static/index.html`, `static/app.js`, `static/styles.css` |
| Python Tornado server | `server.py`, port 8888 |
| Text prompt → generated image | `POST /api/text-to-image` |
| Generated image or manual upload → reverse search | `POST /api/image-search` |
| Stable Diffusion 3.5 Medium | `setup_stable_diffusion()` in `fashiongen/model.py` |
| 4-bit quantization | Diffusers NF4 configuration for the SD3 transformer |
| Preload before web server startup | Model setup completes before `server.listen()` |
| Public image hosting | `upload_image_to_imgbb()` with expiration |
| Google Lens via SerpAPI | `search_google_lens()` with `type=visual_matches` |
| Stubbed search for the presentation | Independent `SEARCH_MODE=demo` with fixed shoe results |
| Image timer | Measured frontend timer and backend elapsed seconds |
| “Premium” results displayed first | Above-average known image resolution, sorted descending |
| Titles no longer clipped after three lines | Wrapping card headings without line clamping |
| Previous and Next | Six-item client pagination, including first/last boundaries |
| “View item” link | Provider item URL in live mode; clearly labeled general web search in demo mode |

## Faithfulness and deliberate limits

The transcript explains functionality and technology, but does not provide original source files, layout measurements, fonts, colors, screenshots, or the original fixed result data. The frontend styling, SVG sample, and fixture dataset are therefore new work. The initial port is interpreted as `8888`, Tornado's commonly used development port; `PORT` is configurable.

The original demo generated real AI images and stubbed only search. Select **live generation + demo search** to reproduce that arrangement. The default **demo + demo** profile additionally allows a fresh clone to run on an ordinary laptop without downloading model weights.

No authentication, saved collections, shopping cart, checkout, claimed originality score, or persistent account history is added. There are no hardcoded credentials or model weights. Product titles from live providers are rendered as text, not HTML.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `GENERATION_MODE` | `demo` | `demo` or `live` |
| `SEARCH_MODE` | `demo` | `demo` or `live` |
| `HOST` | `127.0.0.1` | Listening interface |
| `PORT` | `8888` | HTTP port |
| `HF_TOKEN` | empty | Hugging Face read token; existing local authentication may also work |
| `MODEL_DEVICE` | `auto` | `cuda`, `mps`, `cpu`, or automatic selection |
| `QUANTIZE_4BIT` | `true` | NF4 transformer quantization; this project supports it on CUDA |
| `CPU_OFFLOAD` | `true` | Offload model components when using CUDA |
| `INFERENCE_STEPS` | `40` | 1–100 denoising steps |
| `IMAGE_SIZE` | `1024` | Square size, 512–1536 in multiples of 64 |
| `IMGBB_API_KEY` | empty | ImgBB credential, required for live search |
| `SERPAPI_API_KEY` | empty | SerpAPI credential, required for live search |
| `IMGBB_EXPIRATION` | `600` | Hosted-image lifetime requested from ImgBB, in seconds |

The API's seed is optional; the UI chooses a random seed per generation. Reproducibility still depends on hardware and software versions.

## Runtime and data flow

The model pipeline is shared in one Python process. GPU inference runs in a worker thread under a generation lock; a second generation receives 429. HTTP search calls use Tornado's nonblocking HTTP client. Image parsing/resizing also runs outside the event loop.

Uploaded images are checked by Pillow, EXIF orientation is applied, transparency is flattened on white, and metadata is discarded. Images are reduced to a maximum of 1600 pixels on either side for search. There is no server-side fetch of user-provided URLs. Secrets exist only in the local environment and outgoing provider requests.

XSRF protection and same-origin frontend requests are enabled. The default listener and Docker published port are local-only. This is a local project, not a fully operated multi-user service; a public deployment needs authentication and cost/rate controls before it can safely expose generation and paid search.

## Upstream documentation checked

The model setup follows the official SD3.5 Medium Diffusers/NF4 example. SerpAPI's current documentation includes a newer direct-upload option, but the implementation retains ImgBB to match the narrated pipeline. Quantization primarily reduces memory requirements; performance is hardware-dependent. The exact model path and supported API fields are linked in the README.
