"""Ghost Admin API client for publishing memoirs to blog.mees.st."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from base64 import urlsafe_b64encode

import httpx

log = logging.getLogger(__name__)


class GhostClient:
    """Ghost Admin API client with JWT authentication."""

    def __init__(self, api_url: str, admin_key: str):
        self.api_url = api_url.rstrip("/")
        key_id, secret_hex = admin_key.split(":")
        self.key_id = key_id
        self.secret = bytes.fromhex(secret_hex)

    def _make_jwt(self) -> str:
        """Create a short-lived JWT for Ghost Admin API."""
        now = int(time.time())
        header = {"alg": "HS256", "typ": "JWT", "kid": self.key_id}
        payload = {"iat": now, "exp": now + 300, "aud": "/admin/"}

        def b64(data: dict) -> str:
            return urlsafe_b64encode(json.dumps(data, separators=(",", ":")).encode()).rstrip(b"=").decode()

        segments = f"{b64(header)}.{b64(payload)}"
        sig = urlsafe_b64encode(
            hmac.new(self.secret, segments.encode(), hashlib.sha256).digest()
        ).rstrip(b"=").decode()
        return f"{segments}.{sig}"

    def _headers(self) -> dict:
        return {"Authorization": f"Ghost {self._make_jwt()}"}

    def _resource(self, is_page: bool) -> str:
        """Return 'pages' or 'posts' depending on content type."""
        return "pages" if is_page else "posts"

    def create_post(
        self,
        title: str,
        html: str,
        slug: str | None = None,
        status: str = "published",
        visibility: str = "members",
        tags: list[str] | None = None,
        featured: bool = False,
        feature_image: str | None = None,
        custom_excerpt: str | None = None,
        is_page: bool = False,
    ) -> dict:
        """Create a Ghost post or page. Returns the post/page object."""
        mobiledoc = json.dumps({
            "version": "0.3.1",
            "atoms": [],
            "cards": [["html", {"html": html}]],
            "markups": [],
            "sections": [[10, 0]],
        })

        post: dict = {
            "title": title,
            "mobiledoc": mobiledoc,
            "status": status,
            "visibility": visibility,
            "featured": featured,
        }
        if slug:
            post["slug"] = slug
        if tags:
            post["tags"] = [{"name": t} for t in tags]
        if feature_image:
            post["feature_image"] = feature_image
        if custom_excerpt:
            post["custom_excerpt"] = custom_excerpt[:300]

        resource = self._resource(is_page)
        resp = httpx.post(
            f"{self.api_url}/{resource}/",
            json={resource: [post]},
            headers={**self._headers(), "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()[resource][0]

    def update_post(self, post_id: str, is_page: bool = False, **fields) -> dict:
        """Update a Ghost post or page."""
        resource = self._resource(is_page)
        resp = httpx.get(
            f"{self.api_url}/{resource}/{post_id}/",
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        current = resp.json()[resource][0]

        update: dict = {"updated_at": current["updated_at"]}

        for key in ("title", "status", "visibility", "featured",
                     "slug", "feature_image"):
            if key in fields:
                update[key] = fields[key]
        if "custom_excerpt" in fields:
            update["custom_excerpt"] = (fields["custom_excerpt"] or "")[:300]

        if "html" in fields:
            update["lexical"] = json.dumps({
                "root": {
                    "children": [{"type": "html", "html": fields["html"], "version": 1}],
                    "direction": None,
                    "format": "",
                    "indent": 0,
                    "type": "root",
                    "version": 1,
                },
            })

        if "tags" in fields:
            update["tags"] = [{"name": t} for t in fields["tags"]]

        resp = httpx.put(
            f"{self.api_url}/{resource}/{post_id}/",
            json={resource: [update]},
            headers={**self._headers(), "Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code != 200:
            log.error("Ghost update %s/%s failed (%d): %s", resource, post_id, resp.status_code, resp.text[:500])
        resp.raise_for_status()
        return resp.json()[resource][0]

    def delete_post(self, post_id: str, is_page: bool = False) -> None:
        """Delete a Ghost post or page."""
        resource = self._resource(is_page)
        resp = httpx.delete(
            f"{self.api_url}/{resource}/{post_id}/",
            headers=self._headers(),
            timeout=30,
        )
        # Try other resource type if 404 (post may have been converted to page or vice versa)
        if resp.status_code == 404:
            alt = self._resource(not is_page)
            resp = httpx.delete(
                f"{self.api_url}/{alt}/{post_id}/",
                headers=self._headers(),
                timeout=30,
            )
        resp.raise_for_status()

    def upload_image(self, image_bytes: bytes, filename: str) -> str:
        """Upload an image to Ghost. Returns the URL."""
        resp = httpx.post(
            f"{self.api_url}/images/upload/",
            files={"file": (filename, image_bytes, "image/jpeg")},
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["images"][0]["url"]
