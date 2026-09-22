# FashionGen

An AI-powered **Fashion Search Platform** for turning design descriptions into images and finding visually similar fashion items.

This is a new implementation of the behavior described in the [project demo](https://youtu.be/3J2U3lt0vt8) and its supplied transcript. It uses the same stack and pipeline: **HTML/CSS/JavaScript → Tornado → Stable Diffusion 3.5 Medium → ImgBB → SerpAPI Google Lens**. The original source, CSS, screenshots, and demo dataset were not available, so this is not a verified pixel-for-pixel or source-code copy.

The interface uses a plain white layout with standard form controls, a side-by-side image preview, and a simple results grid. It stacks vertically on mobile. The earlier screenshot in `docs/preview.png` predates this simplified layout.

## Start in under a minute

Requires Python 3.11 or newer. Demo mode needs no API keys, model download, or GPU.

Extract the project ZIP or clone this repository, then:

```bash
cd fashiongen
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python server.py
```

Open **http://localhost:8888**. On Windows, activate with `.venv\Scripts\activate` and use `copy .env.example .env`.

1. Enter a description such as “white Louis Vuitton sneakers with blue logos.”
2. Click **Generate and Search** to create the preview.
3. Click **Search for Similar Items** to run the reverse-search step.
4. Explore the cards and use **Previous / Next** to navigate.

The two buttons are intentionally separate, matching the narrated demonstration. You can also drag in a PNG, JPG, or WebP image and search it directly. No Node build or frontend framework is required.

## Demo and live modes

| `GENERATION_MODE` | `SEARCH_MODE` | Behavior |
| --- | --- | --- |
| `demo` | `demo` | Default. Fixed original sneaker illustration and 14 labeled sample results; no external API calls. |
| `live` | `demo` | Actual Stable Diffusion generation plus fixed search results, matching the demo's working model and stubbed Lens service. |
| `demo` | `live` | Run real searches on uploaded images or the fixed illustration, without loading the AI model. |
| `live` | `live` | Full generation → ImgBB → Google Lens pipeline. |

Demo search always returns the same sneaker collection, irrespective of the input. Its “View item” links open general web searches, not verified retail listings. The interface labels this explicitly. Demo generation also uses a fixed illustration; it is not AI inference. Live API failures produce actionable errors and **never silently substitute demo data**.

## Enable real reverse-image search

Create API keys at [ImgBB](https://api.imgbb.com/) and [SerpAPI](https://serpapi.com/manage-api-key), then edit your local `.env`:

```dotenv
SEARCH_MODE=live
IMGBB_API_KEY=your_imgbb_key
SERPAPI_API_KEY=your_serpapi_key
```

Restart `python server.py`. Upload an image and click **Search for Similar Items**. Requests go through the backend; API keys are never sent to the browser.

Live search normalizes the image, uploads it to ImgBB, and passes its public URL to SerpAPI using `engine=google_lens` and `type=visual_matches`. ImgBB uploads are configured to expire after 600 seconds by default. The public upload and sharing with the search provider are disclosed next to the search button. Do not submit private material unless you intend that sharing. Expiration does not control copies or retention by downstream services.

SerpAPI now also documents direct image upload. This project deliberately keeps the **ImgBB URL workflow described in the video**.

## Enable Stable Diffusion 3.5 Medium

For a public website on an ordinary web host, use the hosted option in
[Public deployment](docs/DEPLOYMENT.md): `GENERATION_MODE=live`,
`GENERATION_PROVIDER=replicate`, and a private `REPLICATE_API_TOKEN`.
It runs the same Stable Diffusion 3.5 Medium model on Replicate. The following
instructions cover the original local GPU option (`GENERATION_PROVIDER=local`).

1. Visit [the model page](https://huggingface.co/stabilityai/stable-diffusion-3.5-medium), review its terms, and obtain access using your own Hugging Face account.
2. Install a [PyTorch build for your machine](https://pytorch.org/get-started/locally/). For the default 4-bit configuration, use an NVIDIA GPU with a compatible CUDA build.
3. Install the additional dependencies:

   ```bash
   pip install -r requirements-model.txt
   ```

4. Edit `.env`:

   ```dotenv
   GENERATION_MODE=live
   HF_TOKEN=your_hugging_face_read_token
   MODEL_DEVICE=cuda
   QUANTIZE_4BIT=true
   CPU_OFFLOAD=true
   ```

5. Restart the server. It downloads/loads the model **before listening on port 8888**, so the first request does not trigger model loading.

The transformer uses NF4 4-bit quantization; other pipeline components are not all quantized. CPU offload reduces GPU memory pressure. Memory requirements and inference speed depend on hardware, precision, and image size. The demo's 20–30 seconds is not a timing guarantee, and quantization does not guarantee faster inference. Initial model loading can take considerably longer.

For Apple Silicon, `MODEL_DEVICE=mps`, `QUANTIZE_4BIT=false`, and `CPU_OFFLOAD=false` select the unquantized path. CPU inference is available with `MODEL_DEVICE=cpu` and quantization disabled. Both require substantial memory and can be slow; these hardware paths have not been exercised as part of this reconstruction. You can use uploaded-image live search on a Mac without running Stable Diffusion.

Defaults are 40 inference steps, guidance scale 4.5, 1024×1024 images, and a 256-token T5 sequence limit. Generation runs outside Tornado's event loop. One model job runs at a time; a concurrent request gets HTTP 429 instead of overloading GPU memory.

## Included behavior

- Text prompts, example prompts, and a live generation timer.
- Separate generation and visual-search controls.
- Drag-and-drop and file-picker upload, preview, clear, and download.
- Image validation, a 10 MB input limit, metadata removal, and resizing for search.
- Result title, source, thumbnail, optional price, and outbound item link.
- Full wrapping titles, with no three-line clipping.
- “Premium” results promoted according to above-average image resolution when known. This is a resolution heuristic, not a quality or similarity score.
- Six results per page, working Previous/Next boundaries, and empty-result handling.
- Responsive desktop/mobile layout, keyboard navigation, and reduced-motion support.
- Explicit loading/error states and no invented progress percentages.

Visual search can help compare existing designs. It does not prove originality.

## Repository map

```text
server.py                 Tornado routes, startup, and pipeline orchestration
fashiongen/config.py      Environment validation
fashiongen/model.py       Model preloading, NF4 setup, and inference
fashiongen/hosted_model.py Hosted SD 3.5 Medium without a local GPU
fashiongen/limits.py      Global rolling usage limits for live operations
fashiongen/services.py    ImgBB and SerpAPI HTTP adapters
fashiongen/images.py      Upload decoding and normalization
fashiongen/results.py     Result normalization and premium ranking
fashiongen/fixtures.py    Clearly labeled fixed demo search data
static/index.html         Application markup
static/styles.css         Responsive layout and visual styling
static/app.js             Frontend requests, state, timers, and pagination
static/assets/            Original SVG illustration and icons
tests/                    Backend and browser checks
docs/                     API and implementation notes
```

See [the API guide](docs/API.md) and [implementation notes](docs/IMPLEMENTATION.md) for request formats, configuration, and the mapping to the transcript.

## Tests

```bash
python -m unittest discover -s tests -v
```

The backend suite exercises upload validation, endpoint contracts, concurrent-generation behavior, premium sorting, provider errors, and mocked live integrations. It does not download models, use real API keys, or spend provider credits.

Optional browser checks (Node 20+), with the server running in `demo`/`demo` mode:

```bash
npm install
npx playwright install chromium
npm run test:e2e
```

Set `BASE_URL` if the server is elsewhere. Set `SCREENSHOT_DIR` to save browser screenshots. The application itself does not depend on Node.

## Docker

```bash
docker compose up --build
```

Open http://localhost:8888. This lightweight image supports demo generation or
hosted generation through Replicate, and either demo or live search. It does not
bundle PyTorch, CUDA, or model weights. Use the Python instructions above for
local GPU generation. The Compose port binds to localhost.

## Publish a website linked from GitHub

See [the deployment guide](docs/DEPLOYMENT.md). The repository includes
`railway.json` and `render.yaml` for hosting the complete Tornado app. Provider
keys belong in the host's private runtime variables; they never belong in
browser JavaScript or GitHub Pages assets. GitHub Pages cannot run this backend.

Public mode requires live generation and live search, so a missing integration
does not silently publish fixed demo results. Live endpoints have concurrency
and usage limits. These are per-process limits, not durable billing caps.
After deploying and testing real provider calls, put the verified HTTPS URL in
the repository's Website field. No live URL is claimed by this source code.

## Verification limits

The backend suite covers endpoint contracts, provider errors, hosted generation,
credential isolation, usage limits, secure public cookies, image validation, and
result ranking. Earlier Chromium checks covered generation, upload, search, and
pagination; they predate the simplified layout. Actual model inference, successful
live provider calls, the Docker build, and a public deployment still need
verification with connected hosting and funded provider accounts. Simulated
provider tests do not establish that those external services work.

## Reference
- [Stable Diffusion 3.5 Medium model card and quantization example](https://huggingface.co/stabilityai/stable-diffusion-3.5-medium).
- [Diffusers 0.35.1 bitsandbytes documentation](https://huggingface.co/docs/diffusers/v0.35.1/quantization/bitsandbytes).
- [Tornado asynchronous I/O](https://www.tornadoweb.org/en/stable/guide/async.html).
- [ImgBB API](https://api.imgbb.com/).
- [SerpAPI Google Lens](https://serpapi.com/google-lens-api).

The vector artwork is an original demo illustration. Model weights are not included; their use is subject to the model provider's terms.
