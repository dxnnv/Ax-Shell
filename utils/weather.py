import os
import requests
from typing import Tuple, Optional
from config.loguru_config import logger

logger = logger.bind(name="Weather", type="Utils")

_MET_NO_CONTACT = os.getenv("AX_SHELL_CONTACT", "github.com/dxnnv/Ax-Shell")
_APP_UA = os.getenv("AX_SHELL_UA", f"Ax-Shell/0.1 (+{_MET_NO_CONTACT})")

class WeatherUtils:
    """Shared weather helpers: geolocation, UA, emoji/description mapping."""

    @staticmethod
    def get_weather_emoji(weather_code: str) -> str:
        code = (weather_code or "").lower()
        mapping = {
            "clearsky_day": "☀️",
            "clearsky_night": "🌙",
            "fair_day": "🌤️",
            "fair_night": "🌤️",
            "partlycloudy_day": "⛅",
            "partlycloudy_night": "☁️",
            "cloudy": "☁️",
            "rainshowers_day": "🌦️",
            "rainshowers_night": "🌧️",
            "rain": "🌧️",
            "thunder": "⛈️",
            "sleet": "🌨️",
            "snow": "❄️",
            "fog": "🌫️",
            "lightrain": "🌦️",
            "heavyrain": "🌧️",
            "lightsleet": "🌨️",
            "heavysleet": "🌨️",
            "lightsnow": "🌨️",
            "heavysnow": "❄️",
            "lightrainshowers_day": "🌦️",
            "heavyrainshowers_day": "🌧️",
            "lightrainshowers_night": "🌧️",
            "heavyrainshowers_night": "🌧️"
        }
        return mapping.get(code, "🌡️")

    @staticmethod
    def get_weather_description(weather_code: str) -> str:
        code = (weather_code or "").lower()
        mapping = {
            "clearsky_day": "Clear sky",
            "clearsky_night": "Clear night",
            "fair_day": "Fair",
            "fair_night": "Fair",
            "partlycloudy_day": "Partly cloudy",
            "partlycloudy_night": "Partly cloudy",
            "cloudy": "Cloudy",
            "rainshowers_day": "Rain showers",
            "rainshowers_night": "Rain showers",
            "rain": "Rain",
            "thunder": "Thunderstorm",
            "sleet": "Sleet",
            "snow": "Snow",
            "fog": "Fog",
            "lightrain": "Light rain",
            "heavyrain": "Heavy rain",
            "lightsleet": "Light sleet",
            "heavysleet": "Heavy sleet",
            "lightsnow": "Light snow",
            "heavysnow": "Heavy snow",
            "lightrainshowers_day": "Light rain showers",
            "heavyrainshowers_day": "Heavy rain showers",
            "lightrainshowers_night": "Light rain showers",
            "heavyrainshowers_night": "Heavy rain showers"
        }
        return mapping.get(code, "Unknown conditions")

    @staticmethod
    def _try_ip_provider(session: requests.Session) -> Optional[Tuple[float, float, str]]:
        """Try providers in order; return (lat, lon, city) or None."""
        headers = {"User-Agent": _APP_UA}
        # 1) ipapi.co: anonymous, generous limits
        try:
            r = session.get("https://ipapi.co/json/", headers=headers, timeout=5)
            if r.ok:
                j = r.json()
                lat, lon = float(j["latitude"]), float(j["longitude"])
                city = j.get("city") or "Unknown Location"
                return lat, lon, city
            logger.debug(f"ipapi.co failed: {r.status_code} {r.text[:120]}")
        except Exception as e:
            logger.debug(f"ipapi.co error: {e}")
        return None

    @staticmethod
    def get_coordinates(session: Optional[requests.Session] = None) -> Tuple[float, float, str]:
        """Get coordinates using env/config first, then IP-based geolookup with fallbacks."""
        sess = session or requests.Session()

        # Manual override via env
        env_lat = os.getenv("AX_SHELL_LAT")
        env_lon = os.getenv("AX_SHELL_LON")
        env_city = os.getenv("AX_SHELL_CITY")
        if env_lat and env_lon:
            try:
                lat, lon = float(env_lat), float(env_lon)
                city = env_city or "Custom Location"
                logger.debug(f"Using env coordinates: {lat}, {lon} ({city})")
                return lat, lon, city
            except Exception:
                pass

        # IP providers
        found = WeatherUtils._try_ip_provider(sess)
        if found:
            return found

        # Fallback coordinates (New York)
        lat, lon = 40.7128, -74.0060
        city = "Unknown Location"
        logger.debug(f"Using fallback coordinates: {lat}, {lon}")
        return lat, lon, city

    @staticmethod
    def get_met_api_url(lat: float, lon: float) -> str:
        return f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat}&lon={lon}"

    @staticmethod
    def get_user_agent(_app_name: str = "Ax-Shell") -> str:
        return _APP_UA