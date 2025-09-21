import gi
import requests
from fabric.widgets.button import Button
from fabric.widgets.label import Label
from gi.repository import Gdk, GLib

from utils.weather import WeatherUtils

gi.require_version("Gdk", "3.0")
from config.loguru_config import logger
import modules.icons as icons

logger = logger.bind(name="Weather", type="Module")


def on_button_enter(button, _):
    # Implement hover effects when the button is entered
    window = button.get_window()
    if window:
        window.set_cursor(Gdk.Cursor.new_from_name(button.get_display(), "hand2"))


def on_button_leave(button, _):
    # Implement hover effects when the button is left
    window = button.get_window()
    if window:
        window.set_cursor(None)


def get_weather_emoji(weather_code):
    return WeatherUtils.get_weather_emoji(weather_code)


def get_location():
    try:
        response = requests.get("https://ipinfo.io/json")
        if response.status_code == 200:
            data = response.json()
            return data.get("city", "")
        else:
            logger.error("Error getting location from ipinfo.")
    except Exception as e:
        logger.error(f"Error getting location: {e}")
    return ""


class Weather(Button):
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

        self.lat = None
        self.lon = None

        self.add(self.button)
        self.show_all()
        self.enabled = True
        self.session = requests.Session()
        self.notch = None
        GLib.timeout_add_seconds(600, self.fetch_weather)
        self.fetch_weather()

    def on_weather_clicked(self, _):
        if self.notch:
            self.notch.open_notch("weather")

    def set_notch(self, notch):
        self.notch = notch

    def get_coordinates(self):
        """Get coordinates using IP-based geolocation"""
        self.lat, self.lon, _ = WeatherUtils.get_coordinates(self.session)
        return self.lat is not None and self.lon is not None

    def set_visible(self, visible):
        """Override to track external visibility setting"""
        self.enabled = visible
        value = True if visible and hasattr(self, 'has_weather_data') and self.has_weather_data else visible
        super().set_visible(value)

    def fetch_weather(self):
        GLib.Thread.new("weather-fetch", self._fetch_weather_thread)
        return True

    def _fetch_weather_thread(self):
        # Get coordinates automatically
        if not self.get_coordinates():
            self.has_weather_data = False
            GLib.idle_add(self.label.set_markup, f"{icons.cloud_off} Location Error")
            GLib.idle_add(super().set_visible, False)
            return

        url = WeatherUtils.get_met_api_url(self.lat, self.lon)
        try:
            response = requests.get(url, headers={'User-Agent': WeatherUtils.get_user_agent('weather-app')})
            if response.status_code == 200:
                data = response.json()["properties"]["timeseries"][0]["data"]
                temp = data["instant"]["details"]["air_temperature"]
                weather_code = data["next_1_hours"]["summary"]["symbol_code"]
                logger.debug(f"Weather code: {weather_code}")
                emoji = get_weather_emoji(weather_code)
                GLib.idle_add(self.label.set_label, f"{emoji} {temp}°C")
                self.has_weather_data = True
            else:
                self.has_weather_data = False
                GLib.idle_add(self.label.set_markup, f"{icons.cloud_off} Unavailable")
                GLib.idle_add(super().set_visible, False)
        except Exception as e:
            self.has_weather_data = False
            logger.warning(f"Error fetching weather: {e}")
            GLib.idle_add(self.label.set_markup, f"{icons.cloud_off} Error")
            GLib.idle_add(super().set_visible, False)
