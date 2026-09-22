"""Intentionally fixed sample results, mirroring the demo's stubbed search."""

from .results import rank_results


def demo_results() -> list[dict]:
    styles = [
        "White and blue low-top sneaker with contrasting leather panels",
        "Blue monogram-inspired sneaker concept on a white leather upper",
        "White leather trainer with blue heel detail and a layered rubber sole",
        "Cobalt panel low-top with white laces and contrast stitching",
        "Minimal white court sneaker with soft blue accents",
        "Blue and white runway-inspired trainer with an oversized sole",
        "White lace-up sneaker with a royal blue side panel",
        "Two-tone low-top shoe with textured leather and blue trim",
        "White leather sneaker with a blue tongue and matching heel tab",
        "Retro blue court shoe with a sculpted white midsole",
        "Clean white sneaker with cobalt geometric details",
        "Blue-accented casual trainer with a smooth leather finish",
        "White and blue sneaker study with an extended descriptive title that remains fully visible across several lines without clipping",
        "Minimal blue-panel leather sneaker design study",
    ]
    dimensions = [1200, 1600, 1400, 1000, 800, 900, 760, 720, 680, 640, 600, 560, 520, 480]
    items = rank_results([
        {"title": title, "source": "Demo collection · sample image",
         "link": f"https://www.google.com/search?q=white+blue+designer+sneakers&start={i * 10}",
         "image_width": size, "image_height": size}
        for i, (title, size) in enumerate(zip(styles, dimensions))
    ])
    for item in items:
        item["thumbnail"] = "/static/assets/demo-sneaker.svg"
        item["demo"] = True
    return items
