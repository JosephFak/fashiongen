import os
import unittest
from unittest.mock import patch

from fashiongen.config import Settings


class ConfigurationTests(unittest.TestCase):
    def test_default_mode_requires_no_keys(self):
        with patch.dict(os.environ, {}, clear=True):
            config = Settings.from_env()
        self.assertEqual(config.generation_mode, "demo")
        self.assertEqual(config.host, "127.0.0.1")

    def test_live_search_fails_fast_without_keys(self):
        with patch.dict(os.environ, {"SEARCH_MODE": "live"}, clear=True), self.assertRaises(ValueError):
            Settings.from_env()

    def test_invalid_settings_fail_fast(self):
        for env in [{"PORT": "oops"}, {"PORT": "0"}, {"IMAGE_SIZE": "1000"}, {"QUANTIZE_4BIT": "yes"}, {"SEARCH_MODE": "unknown"}]:
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True), self.assertRaises(ValueError):
                Settings.from_env()

    def test_secrets_are_excluded_from_repr(self):
        config = Settings(imgbb_api_key="secret-imgbb", serpapi_api_key="secret-serp", hf_token="secret-hf")
        self.assertNotIn("secret-", repr(config))
