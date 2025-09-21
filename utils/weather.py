import requests
from config.loguru_config import logger

logger = logger.bind(name="Weather", type="Utils")

class WeatherUtils:
    """Utility class containing shared weather functionality"""

    @staticmethod
    def get_weather_emoji(weather_code):
        """Map Met.no API weather codes to emojis"""
        weather_emojis = {
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
        return weather_emojis.get(weather_code.lower(), "🌡️")

    @staticmethod
    def get_weather_description(weather_code):
        """Get a human-readable weather description from weather code"""
        weather_descriptions = {
            "clearsky_day": "Clear sky",
            "clearsky_night": "Clear night",
            "fair_day": "Fair weather",
            "fair_night": "Fair night",
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
        return weather_descriptions.get(weather_code.lower(), "Unknown conditions")

    @staticmethod
    def get_coordinates(session=None):
        """Get coordinates using IP-based geolocation"""
        if session is None:
            session = requests.Session()

        try:
            response = session.get("https://ip-api.com/json/", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data['status'] == 'success':
                    lat = data.get('lat')
                    lon = data.get('lon')
                    city = data.get('city', 'Unknown')
                    country = data.get('country', 'Unknown')
                    city_name = f"{city}, {country}"
                    logger.info(f"Auto-detected location: {city_name} ({lat}, {lon})")
                    return lat, lon, city_name
                else:
                    logger.warning(f"Geolocation failed: {data.get('message', 'Unknown error')}")
            else:
                logger.warning(f"Geolocation service returned status code: {response.status_code}")
        except Exception as e:
            logger.error(f"Error fetching coordinates: {e}")

        # Fallback coordinates (New York)
        lat, lon = 40.7128, -74.0060
        city_name = "Unknown Location"
        logger.debug(f"Using fallback coordinates: {lat}, {lon}")
        return lat, lon, city_name

    @staticmethod
    def get_met_api_url(lat, lon):
        """Get the Met.no API URL for given coordinates"""
        return f'https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={lat}&lon={lon}&altitude=90'

    @staticmethod
    def get_user_agent(app_name="weather-app"):
        """Get a proper User-Agent string for API requests"""
        return f'{app_name}/1.0'