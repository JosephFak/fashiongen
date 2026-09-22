import base64
import io
import unittest

from PIL import Image

from fashiongen.images import decode_image, normalize_image


def png_image(size=(32, 24)):
    output = io.BytesIO()
    Image.new("RGBA", size, (0, 0, 255, 0)).save(output, format="PNG")
    return output.getvalue()


class ImageTests(unittest.TestCase):
    def test_transparency_flattens_to_white_and_metadata_is_removed(self):
        image = Image.open(io.BytesIO(normalize_image(png_image(), 100_000)))
        self.assertEqual(image.format, "JPEG")
        self.assertEqual(image.mode, "RGB")
        self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))
        self.assertFalse(image.getexif())

    def test_data_url_and_raw_base64_work(self):
        encoded = base64.b64encode(png_image()).decode()
        self.assertEqual(decode_image(encoded, 100_000), decode_image("data:image/png;base64," + encoded, 100_000))

    def test_large_images_are_resized(self):
        image = Image.open(io.BytesIO(normalize_image(png_image((2000, 1000)), 100_000)))
        self.assertEqual(image.size, (1600, 800))

    def test_invalid_and_oversized_payloads_are_rejected(self):
        for payload in [None, "", "%%%%", "https://example.com/a.png", "data:image/svg+xml;base64,PHN2Zy8+", "AAAA" * 100]:
            with self.subTest(payload=str(payload)[:40]), self.assertRaises(ValueError):
                decode_image(payload, 100)

    def test_deceptive_mime_type_is_not_trusted(self):
        value = "data:image/png;base64," + base64.b64encode(b"<svg></svg>").decode()
        with self.assertRaises(ValueError):
            decode_image(value, 1000)
