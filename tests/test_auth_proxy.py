from __future__ import annotations

import gzip
import subprocess
import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.auth import _proxy_url, proxy_router


REAL_ASYNC_CLIENT = httpx.AsyncClient


class ClerkProxyTests(unittest.TestCase):
    def setUp(self) -> None:
        _proxy_url.cache_clear()
        app = FastAPI()
        app.include_router(proxy_router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        _proxy_url.cache_clear()

    @staticmethod
    def _client_factory(handler):
        transport = httpx.MockTransport(handler)

        def factory(*args, **kwargs):
            kwargs["transport"] = transport
            return REAL_ASYNC_CLIENT(*args, **kwargs)

        return factory

    def test_browser_compression_request_relays_parseable_uncompressed_javascript(self) -> None:
        javascript = b"globalThis.Clerk = { loaded: true };\n"

        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.headers["accept-encoding"], "identity")
            self.assertEqual(request.headers["clerk-proxy-url"], "https://studio.example/api/__clerk")
            self.assertEqual(request.headers["clerk-secret-key"], "test-secret")
            return httpx.Response(
                200,
                content=gzip.compress(javascript),
                headers={
                    "Content-Type": "application/javascript; charset=utf-8",
                    "Content-Encoding": "gzip",
                    "Content-Length": str(len(gzip.compress(javascript))),
                    "Cache-Control": "public, max-age=60",
                },
            )

        with (
            patch.dict("os.environ", {"CLERK_SECRET_KEY": "test-secret"}),
            patch("server.auth.httpx.AsyncClient", self._client_factory(handler)),
        ):
            response = self.client.get(
                "/api/__clerk/npm/@clerk/clerk-js/dist/clerk.browser.js",
                headers={
                    "Accept-Encoding": "gzip, deflate, br, zstd",
                    "X-Forwarded-Host": "studio.example",
                    "X-Forwarded-Proto": "https",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, javascript)
        self.assertNotIn("content-encoding", response.headers)
        self.assertEqual(response.headers["cache-control"], "public, max-age=60")
        subprocess.run(
            ["node", "--check", "-"],
            input=response.content,
            check=True,
            capture_output=True,
        )

    def test_redirect_status_and_safe_response_headers_are_preserved(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                302,
                headers={
                    "Location": "/npm/@clerk/clerk-js@latest/dist/clerk.browser.js",
                    "Cache-Control": "no-cache",
                    "Content-Encoding": "br",
                    "Transfer-Encoding": "chunked",
                    "Connection": "keep-alive",
                },
            )

        with (
            patch.dict("os.environ", {"CLERK_SECRET_KEY": "test-secret"}),
            patch("server.auth.httpx.AsyncClient", self._client_factory(handler)),
        ):
            response = self.client.get(
                "/api/__clerk/npm/@clerk/clerk-js",
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.headers["location"],
            "/npm/@clerk/clerk-js@latest/dist/clerk.browser.js",
        )
        self.assertEqual(response.headers["cache-control"], "no-cache")
        self.assertNotIn("content-encoding", response.headers)
        self.assertNotIn("transfer-encoding", response.headers)
        self.assertNotIn("connection", response.headers)


if __name__ == "__main__":
    unittest.main()