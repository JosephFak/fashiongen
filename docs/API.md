# API guide

Base URL: `http://localhost:8888`. There are no API keys in client requests.

The home page issues a Tornado `_xsrf` cookie. POST requests must send that cookie and its corresponding `X-XSRFToken` header. The browser client handles this automatically. External scripts should first GET `/`, save the cookie, and send the token in the header. CORS is not enabled.

## `GET /api/health`

Returns readiness and public configuration:

```json
{
  "status": "ok",
  "generation_mode": "demo",
  "search_mode": "demo",
  "model": "stabilityai/stable-diffusion-3.5-medium",
  "model_ready": false,
  "max_upload_bytes": 10485760,
  "upload_expiration_seconds": 600
}
```

`model_ready` is false in demo mode because no model is loaded. In live generation mode, the server does not listen until model initialization completes.

## `POST /api/text-to-image`

Content type: `application/json`.

```json
{"prompt": "White sneakers with blue logos", "seed": 1234}
```

- `prompt`: required, nonblank string, at most 1,500 characters.
- `seed`: optional integer from 0 through 4,294,967,295; generated randomly when absent.

Response:

```json
{
  "image_url": "/static/assets/demo-sneaker.svg",
  "mode": "demo",
  "seed": 1234,
  "elapsed_seconds": 0.001
}
```

In live mode `image_url` is a `data:image/png;base64,...` URL. Times above are illustrative; the server always measures its actual elapsed time. This route **only generates**. It does not upload the image or run a search.

## `POST /api/image-search`

JSON request:

```json
{"image": "data:image/jpeg;base64,..."}
```

A raw base64 string is also accepted. Alternatively use `multipart/form-data` with one file field named `image`. Arbitrary image URLs and SVG uploads are not accepted. The bundled SVG demo is converted into a raster image in the browser before submission.

Response structure:

```json
{
  "results": [
    {
      "title": "Example result title",
      "source": "Example source",
      "link": "https://example.com/item",
      "thumbnail": "https://example.com/image.jpg",
      "price": "",
      "width": 1200,
      "height": 1200,
      "resolution": 1440000,
      "premium": false
    }
  ],
  "total": 1,
  "mode": "live",
  "elapsed_seconds": 3.24
}
```

This response is a schema example, not a real search. Demo entries also have `demo=true`.

The backend normalizes up to 200 provider entries, discards unsafe/missing links and duplicate item URLs, and sorts by descending image pixel area. Full-image dimensions are preferred; thumbnail dimensions are a fallback. Missing dimensions have resolution 0 and are not premium. The average is computed over valid known resolutions. Client pagination displays six items at a time without another paid search request.

In live mode, each search uploads normalized JPEG bytes to ImgBB, then sends the returned URL to SerpAPI. No uploaded or generated images are written to application disk. Browser state lasts until refresh; this project has no account system or persistent design history.

## Errors

Errors have a JSON `error` field with a readable message.

| Status | Meaning |
| --- | --- |
| 400 | Invalid prompt, seed, JSON, or image |
| 403 | Missing or invalid XSRF token |
| 404 | Unknown endpoint |
| 415 | Unsupported request content type |
| 429 | Another generation is already running |
| 502 | External service returned an unusable response |
| 503 | Model failure or provider rate limit |
| 504 | Provider timeout/network failure |

The HTTP server caps request bodies at 15 MB; transport-level rejection of a larger body may close the connection before a JSON response is possible. Decoded images are independently limited to 10 MB and 25 megapixels.

ImgBB requests time out after 45 seconds; Lens requests after 60 seconds. The browser uses a 120-second search timeout and a 300-second generation timeout. A browser timeout does not cancel an in-progress GPU job, so a retry may return 429 until that job finishes. Provider error text and credential-bearing request URLs are not sent to clients or included in application error logs.
