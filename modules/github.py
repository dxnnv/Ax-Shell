import os
import time
import json
import requests
from datetime import datetime, timedelta, timezone

from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.label import Label
from gi.repository import GLib
from config.loguru_config import logger

logger = logger.bind(name="GitHub", type="Module")

_GQL = "https://api.github.com/graphql"

_Q = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    url
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""

def _now_utc():
    return datetime.now(timezone.utc)

class GitHub(Box):
    def __init__(self, **kwargs) -> None:
        super().__init__(name="github", orientation="h", spacing=6, **kwargs)
        self._sess = requests.Session()
        self._username = os.getenv("GITHUB_USERNAME")
        self._token = os.getenv("GITHUB_PAT")
        self._profile_url = f"https://github.com/{self._username}" if self._username else "https://github.com"

        self.label = Label(name="github-label", markup=" loading…")
        self.button = Button(name="github-button", child=self.label,
                             on_clicked=self._open_profile)
        self.add(self.button)
        self.show_all()

        if not self._username or not self._token:
            logger.info("GitHub module disabled (missing GITHUB_USERNAME or GITHUB_PAT).")
            self.set_visible(False)
            return

        self._refresh()
        GLib.timeout_add_seconds(1800, self._refresh)  # every 30 minutes

    def _open_profile(self, _btn):
        os.system(f"xdg-open '{self._profile_url}' &")

    def _refresh(self) -> bool:
        GLib.Thread.new("github-refresh", self._refresh_thread)
        return True

    def _refresh_thread(self):
        try:
            now = _now_utc()
            week_ago = now - timedelta(days=7)
            variables = {
                "login": self._username,
                "from": week_ago.isoformat(),
                "to": now.isoformat(),
            }
            headers = {"Authorization": f"Bearer {self._token}"}
            r = self._sess.post(_GQL, json={"query": _Q, "variables": variables}, headers=headers, timeout=8)
            if r.status_code != 200:
                raise RuntimeError(f"GitHub GraphQL {r.status_code}: {r.text[:120]}")
            j = r.json()
            cal = j["data"]["user"]["contributionsCollection"]["contributionCalendar"]
            total = cal.get("totalContributions", 0)
            # Compute today's contributions if present
            today = _now_utc().date().isoformat()
            today_count = 0
            for w in cal.get("weeks", []):
                for d in w.get("contributionDays", []):
                    if d["date"] == today:
                        today_count = d["contributionCount"]
                        break
            text = f" {total} last 7d • {today_count} today"
            GLib.idle_add(self.label.set_label, text)
            GLib.idle_add(self.set_visible, True)
        except Exception as e:
            logger.warning(f"GitHub module error: {e}")
            GLib.idle_add(self.label.set_label, " error")
            GLib.idle_add(self.set_visible, False)