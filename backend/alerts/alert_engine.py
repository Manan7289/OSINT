"""backend/alerts/alert_engine.py - Geofence Watch Zones, SSE Push & Multi-Channel Alerting.

Evaluates user-defined polygon watch zones using deterministic ray-casting,
manages Server-Sent Events (SSE) queues for live browser HUD pushes,
and dispatches notifications to configured Telegram bots and Discord webhooks.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
import urllib.request
import urllib.error

from backend.collectors.sweep_delta import point_in_polygon
from backend.core.config import vault
from backend.core.database import DatabaseManager, db

logger = logging.getLogger(__name__)


class AlertEngine:
    """Evaluates geofences, streams real-time SSE updates, and dispatches webhooks."""

    def __init__(self, database: DatabaseManager = db) -> None:
        self.db = database
        self._sse_subscribers: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()

    async def subscribe_stream(self) -> AsyncGenerator[str, None]:
        """Subscribes an HTTP client to the SSE event stream."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        async with self._lock:
            self._sse_subscribers.append(queue)
        try:
            # Send initial keepalive
            yield f"event: connected\ndata: {json.dumps({'time': datetime.datetime.now(datetime.timezone.utc).isoformat()})}\n\n"
            while True:
                msg = await queue.get()
                yield msg
        finally:
            async with self._lock:
                if queue in self._sse_subscribers:
                    self._sse_subscribers.remove(queue)

    async def broadcast_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Pushes an event to all connected SSE clients."""
        payload = f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
        async with self._lock:
            for q in list(self._sse_subscribers):
                try:
                    q.put_nowait(payload)
                except asyncio.QueueFull:
                    pass

    def dispatch_alert_notifications(
        self,
        alert_title: str,
        alert_description: str,
        severity: str = "HIGH",
        channels: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """Dispatches an alert to configured external channels (Telegram, Discord)."""
        dispatched = {}
        active_channels = channels or ["SSE"]

        # 1. Telegram Bot
        if "TELEGRAM" in active_channels:
            tg_token = vault.get_secret("TELEGRAM_BOT_TOKEN") or None
            tg_chat_id = vault.get_secret("TELEGRAM_CHAT_ID") or None
            if tg_token and tg_chat_id:
                try:
                    url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
                    msg_text = f"🚨 *[LOCALOSINT v3.0 ALERT]*\n*Severity:* {severity}\n*Title:* {alert_title}\n{alert_description}"
                    body = json.dumps({"chat_id": tg_chat_id, "text": msg_text, "parse_mode": "Markdown"}).encode("utf-8")
                    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=5.0) as resp:
                        dispatched["telegram"] = resp.status == 200
                except Exception as e:
                    logger.warning(f"Telegram alert failed: {e}")
                    dispatched["telegram"] = False

        # 2. Discord Webhook
        if "DISCORD" in active_channels:
            discord_url = vault.get_secret("DISCORD_WEBHOOK_URL") or None
            if discord_url:
                try:
                    color = 0xEF4444 if severity == "CRITICAL" else 0xF59E0B
                    embed = {
                        "title": f"[{severity}] {alert_title}",
                        "description": alert_description,
                        "color": color,
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "footer": {"text": "LocalOSINT v3.0 Command Centre"},
                    }
                    body = json.dumps({"embeds": [embed]}).encode("utf-8")
                    req = urllib.request.Request(discord_url, data=body, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=5.0) as resp:
                        dispatched["discord"] = resp.status in (200, 204)
                except Exception as e:
                    logger.warning(f"Discord webhook failed: {e}")
                    dispatched["discord"] = False

        return dispatched


# Singleton
alert_engine = AlertEngine()
