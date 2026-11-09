"""Host validation and lifecycle privacy for the reusable client."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('public_pzp_client', Path(__file__).parents[1] / 'custom_components/pzp_web/client.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)


class PublicClientTests(unittest.TestCase):
    def test_host_normalization(self):
        for raw, expected in [(' PUMP.Local ', 'pump.local'), ('192.0.2.10:80', '192.0.2.10'),
                              ('pump:008080', None), ('pump:8080', 'pump:8080')]:
            with self.subTest(raw=raw):
                if expected is None:
                    with self.assertRaises(ValueError): client.normalize_host(raw)
                else:
                    self.assertEqual(client.normalize_host(raw), expected)

    def test_unsafe_or_invalid_authorities_rejected_before_connecting(self):
        for host in ['http://pump', 'pump/path', 'user:password@pump', 'pump?token=x',
                     'pump#x', 'pump:0', 'pump:65536', 'pump..local', '-pump', None]:
            with self.subTest(host=host), patch.object(client.PzpClient, '_request') as request:
                with self.assertRaises(ValueError): client.PzpClient(host, 'synthetic', 'test-only')
                request.assert_not_called()

    def test_constructor_never_contacts_device_or_writes(self):
        with patch.object(client.PzpClient, '_request') as request:
            first = client.PzpClient('pump-one.local', 'synthetic', 'test-only')
            second = client.PzpClient('pump-two.local', 'synthetic', 'test-only')
            request.assert_not_called()
            self.assertIsNot(first.cookies, second.cookies)
            self.assertIsNot(first._admin_tokens, second._admin_tokens)
            self.assertEqual(first.host, 'pump-one.local')

    def test_same_origin_redirect_only(self):
        handler = client.LocalRedirects('pump.local')
        for destination in ['http://other.local/', 'https://pump.local/', 'http://pump.local:8080/']:
            with self.subTest(destination=destination), self.assertRaises(client.PzpError):
                handler.redirect_request(None, None, 302, '', {}, destination)
