import gi
import requests
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.label import Label
from gi.repository import Gdk, GLib

from utils.weather import WeatherUtils

gi.require_version("Gdk", "3.0")
from config.loguru_config import logger
import modules.icons as icons

logger = logger.bind(name="Weather", type="Module")


def on_button_enter(widget, _):
    window = widget.get_window()
    if window:
        window.set_cursor(Gdk.Cursor.new_from_name(widget.get_display(), "hand2"))

def on_button_leave(widget, _):
    window = widget.get_window()
    if window:
        window.set_cursor(None)

def get_location_label(session: requests.Session) -> str:
    try:
        lat, lon, city = WeatherUtils.get_coordinates(session)
        return city or "Unknown Location"
    except Exception as e:
        logger.warning(f"Location lookup failed: {e}")
        return "Unknown Location"

class Weather(Box):
    def __init__(self, **kwargs) -> None:
        super().__init__(name="weather", orientation="h", spacing=8, **kwargs)

        self.label = Label(name="weather-label", markup=icons.loader)
        self.button = Button(
            name="weather-button",
            child=self.label,
            on_clicked=self.on_weather_clicked,
            tooltip_text="Click to open weather dashboard"
        )

        self.button.connect("enter_notify_event", on_button_enter)
        self.button.connect("leave_notify_event", on_button_leave)

        self.lat: float | None = None
        self.lon: float | None = None
        self.notch = None
        self.has_weather_data = False
        self.session = requests.Session()

        self.add(self.button)
        self.show_all()

        # Refresh every 10 minutes
        GLib.timeout_add_seconds(600, self.fetch_weather)
        self.fetch_weather()

    def set_notch(self, notch) -> None:
        self.notch = notch

    def on_weather_clicked(self, _btn) -> None:
        if self.notch:
            self.notch.open_notch("weather")

    # --- data fetching ---

    def _ensure_coordinates(self) -> bool:
        self.lat, self.lon, _ = WeatherUtils.get_coordinates(self.session)
        return self.lat is not None and self.lon is not None

    def fetch_weather(self) -> bool:
        GLib.Thread.new("weather-fetch", self._fetch_weather_thread)
        return True

    def _fetch_weather_thread(self):
        # Get coordinates automatically
        if not self.get_coordinates():
            self.has_weather_data = False
            GLib.idle_add(self.label.set_markup, f"{icons.cloud_off} Location Error")
            return

        url = WeatherUtils.get_met_api_url(self.lat, self.lon)
        try:
            response = self.session.get(url, headers={"User-Agent": WeatherUtils.get_user_agent()}, timeout=8)
            if response.status_code == 200:
                data = response.json()["properties"]["timeseries"][0]["data"]
                temp = data["instant"]["details"]["air_temperature"]
                # prefer next_1_hours, fallback to next_6_hours
                code = (data.get("next_1_hours") or data.get("next_6_hours") or {}).get("summary", {}).get("symbol_code")
                emoji = WeatherUtils.get_weather_emoji(code or "")
                GLib.idle_add(self.label.set_label, f"{emoji} {int(round(temp))}°C")
                self.has_weather_data = True
            else:
                logger.warning(f"met.no error {r.status_code}: {r.text[:120]}")
                self.has_weather_data = False
                GLib.idle_add(self.label.set_markup, f"{icons.cloud_off} Unavailable")
        except Exception as e:
            self.has_weather_data = False
            logger.warning(f"Error fetching weather: {e}")
            GLib.idle_add(self.label.set_markup, f"{icons.cloud_off} Error")