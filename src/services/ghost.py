"""Ghost Admin API client for publishing memoirs to blog.mees.st."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from base64 import b64encode, urlsafe_b64encode

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
    ) -> dict:
        """Create a Ghost post. Returns the post object."""
        # Wrap HTML in a mobiledoc HTML card (Ghost's native format)
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
            post["custom_excerpt"] = custom_excerpt

        resp = httpx.post(
            f"{self.api_url}/posts/",
            json={"posts": [post]},
            headers={**self._headers(), "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["posts"][0]

    def update_post(self, post_id: str, **fields) -> dict:
        """Update a Ghost post. Must include updated_at for conflict detection."""
        # First fetch the current post to get updated_at
        resp = httpx.get(
            f"{self.api_url}/posts/{post_id}/",
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        current = resp.json()["posts"][0]

        update: dict = {"updated_at": current["updated_at"]}

        for key in ("title", "status", "visibility", "featured",
                     "slug", "feature_image", "custom_excerpt"):
            if key in fields:
                update[key] = fields[key]

        # Convert HTML to lexical format for updates (Ghost 5.x+ uses lexical)
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
            f"{self.api_url}/posts/{post_id}/",
            json={"posts": [update]},
            headers={**self._headers(), "Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code != 200:
            log.error("Ghost update %s failed (%d): %s", post_id, resp.status_code, resp.text[:500])
        resp.raise_for_status()
        return resp.json()["posts"][0]

    def delete_post(self, post_id: str) -> None:
        """Delete a Ghost post."""
        resp = httpx.delete(
            f"{self.api_url}/posts/{post_id}/",
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
