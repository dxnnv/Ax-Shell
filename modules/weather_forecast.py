import gi
import requests
from datetime import datetime, timedelta
from gi.repository import GLib

from fabric.widgets.label import Label
from fabric.widgets.box import Box

gi.require_version("GLib", "2.0")
import modules.icons as icons
from utils.weather import WeatherUtils

def get_weather_emoji(weather_code):
    return WeatherUtils.get_weather_emoji(weather_code)

def get_day_name(date):
    """Get day name for the date"""
    today = datetime.now().date()
    if date == today:
        return "Today"
    elif date == today + timedelta(days=1):
        return "Tomorrow"
    else:
        return date.strftime("%A")


def get_time_period_name(hour, is_today=False, current_hour=0):
    """Get the closest time period based on hour"""
    # If it's today and after 18:00, use hourly periods
    if is_today and current_hour >= 18:
        return f"{hour:02d}:00"

    # Map to the closest specific time period for regular periods
    if hour < 3:
        return "00:00"
    elif hour < 9:
        return "06:00"
    elif hour < 15:
        return "12:00"
    elif hour < 21:
        return "18:00"
    else:
        return "00:00"


def create_time_period_widget(period_name, temp, emoji):
    """Create a widget for a specific time period"""
    period_box = Box(
        name=f"forecast-period-{period_name.lower()}",
        orientation="v",
        spacing=4,
        h_align="center"
    )

    # Time period label
    period_label = Label(
        name="forecast-period-name",
        markup=f"<span size='small'>{period_name}</span>",
        h_align="center"
    )

    # Weather emoji
    emoji_label = Label(
        name="forecast-period-emoji",
        markup=f"<span size='large'>{emoji}</span>",
        h_align="center"
    )

    # Temperature
    temp_label = Label(
        name="forecast-period-temp",
        markup=f"<span size='small' weight='bold'>{temp}°</span>",
        h_align="center"
    )

    period_box.add(period_label)
    period_box.add(emoji_label)
    period_box.add(temp_label)

    return period_box


def create_day_forecast(date, periods_data):
    """Create a forecast widget for a single day with detailed time periods"""
    day_name = get_day_name(date)

    # Main day container
    day_box = Box(
        name="forecast-day",
        orientation="v",
        spacing=8,
        h_expand=True
    )

    # Day name header
    day_header = Label(
        name="forecast-day-name",
        markup=f"<span size='medium' weight='bold'>{day_name}</span>",
        h_align="center"
    )

    # Time periods container
    periods_box = Box(
        name="forecast-periods",
        orientation="h",
        spacing=16,
        h_align="center",
        h_expand=True
    )

    # Add time period widgets based on available data
    for period_name in sorted(periods_data.keys()):
        period_data = periods_data[period_name]
        period_widget = create_time_period_widget(
            period_name,
            period_data['temp'],
            period_data['emoji']
        )
        periods_box.add(period_widget)

    day_box.add(day_header)
    day_box.add(periods_box)

    return day_box


def _get_weather_description(weather_code):
    """Get a human-readable weather description from weather code"""
    return WeatherUtils.get_weather_description(weather_code)


class WeatherForecast(Box):
    def __init__(self, **kwargs) -> None:
        super().__init__(name="weather-forecast", orientation="v", spacing=16, **kwargs)
        self.session = requests.Session()
        self.lat = None
        self.lon = None
        self.city_name = "Unknown Location"
        self.current_weather_emoji = icons.radar

        # Title
        self.title = Label(
            name="weather-forecast-title",
            markup=f"<span size='large' weight='bold'>{self.city_name}</span>",
            h_align="center"
        )
        self.add(self.title)

        # Current weather section
        self.current_weather_container = Box(
            name="current-weather-container",
            orientation="v",
            spacing=8,
            h_align="center",
            visible=False
        )

        self.current_weather_main = Box(
            name="current-weather-main",
            orientation="h",
            spacing=16,
            h_align="center"
        )

        self.current_temp_label = Label(
            name="current-temperature",
            markup="<span size='xx-large' weight='bold'>--°C</span>",
            h_align="center"
        )

        self.current_emoji_label = Label(
            name="current-weather-emoji",
            markup="<span size='xx-large'>🌡️</span>",
            h_align="center"
        )

        self.current_weather_main.add(self.current_emoji_label)
        self.current_weather_main.add(self.current_temp_label)

        self.current_weather_details = Label(
            name="current-weather-details",
            markup="<span size='medium'>Current conditions</span>",
            h_align="center"
        )

        self.current_weather_container.add(self.current_weather_main)
        self.current_weather_container.add(self.current_weather_details)

        self.add(self.current_weather_container)

        # Initially hide the current weather section
        self.current_weather_container.set_visible(False)

        # Loading indicator
        self.loading_label = Label(
            name="weather-loading",
            markup=f"{icons.loader} Loading weather data...",
            h_align="center"
        )
        self.add(self.loading_label)

        # Container for forecast days
        self.forecast_container = Box(
            name="forecast-container",
            orientation="h",
            spacing=12,
            visible=False,
            h_expand=True,
            h_align="center"
        )
        self.add(self.forecast_container)

        # Error label
        self.error_label = Label(
            name="weather-error",
            markup=f"{icons.cloud_off} Unable to load weather data",
            h_align="center",
            visible=False
        )
        self.add(self.error_label)

        self.show_all()
        self.fetch_weather_forecast()

        # Update every 10 minutes
        GLib.timeout_add_seconds(600, self.fetch_weather_forecast)

    def get_coordinates(self):
        """Get coordinates using IP-based geolocation"""
        self.lat, self.lon, self.city_name = WeatherUtils.get_coordinates(self.session)
        return self.lat is not None and self.lon is not None

    def _update_title(self):
        """Update the title with the city name"""
        self.title.set_markup(f"<span size='large' weight='bold'>{self.city_name}</span>")
        return GLib.SOURCE_REMOVE

    def _update_current_weather(self, temperature, emoji, description):
        """Update the current weather display"""
        # Update temperature with decimal
        self.current_temp_label.set_markup(f"<span size='xx-large' weight='bold'>{temperature:.1f}°C</span>")
        self.current_emoji_label.set_markup(f"<span size='xx-large'>{emoji}</span>") # Update emoji
        self.current_weather_details.set_markup(f"<span size='medium'>{description}</span>") # Update description
        self.current_weather_container.set_visible(True) # Show the current weather container

        return GLib.SOURCE_REMOVE

    def fetch_weather_forecast(self):
        """Start the weather fetch in a separate thread"""
        GLib.Thread.new("weather-forecast-fetch", self._fetch_weather_forecast_thread)
        return True

    def _fetch_weather_forecast_thread(self):
        """Fetch weather data from Met.no API"""
        # Get coordinates automatically
        if not self.get_coordinates():
            GLib.idle_add(self._show_error)
            return
        url = WeatherUtils.get_met_api_url(self.lat, self.lon)

        try:
            response = self.session.get(url,
                headers={'User-Agent': WeatherUtils.get_user_agent()},
                timeout=8
            )
            if response.status_code == 200:
                data = response.json()
                timeseries = data["properties"]["timeseries"]

                # Get current weather data
                current_temp = None
                current_weather_code = None
                current_weather_description = ""

                if timeseries:
                    current_data = timeseries[0]["data"]

                    # Get current temperature
                    if "instant" in current_data and "details" in current_data["instant"]:
                        current_temp = current_data["instant"]["details"].get("air_temperature")

                    # Get current weather code and emoji
                    if "next_1_hours" in current_data and "summary" in current_data["next_1_hours"]:
                        current_weather_code = current_data["next_1_hours"]["summary"].get("symbol_code")
                        if current_weather_code:
                            self.current_weather_emoji = WeatherUtils.get_weather_emoji(current_weather_code)
                            current_weather_description = WeatherUtils.get_weather_description(current_weather_code)
                    elif "next_6_hours" in current_data and "summary" in current_data["next_6_hours"]:
                        current_weather_code = current_data["next_6_hours"]["summary"].get("symbol_code")
                        if current_weather_code:
                            self.current_weather_emoji = WeatherUtils.get_weather_emoji(current_weather_code)
                            current_weather_description = WeatherUtils.get_weather_description(current_weather_code)

                # Update the current weather UI
                if current_temp is not None and current_weather_code:
                    GLib.idle_add(self._update_current_weather, current_temp, self.current_weather_emoji,
                                  current_weather_description)

                # Update title with current weather emoji
                GLib.idle_add(self._update_title)

                # Group data by date and time periods
                daily_data = {}
                now = datetime.now()
                today = now.date()
                current_hour = now.hour

                # Determine periods for today based on current time
                if current_hour >= 18:
                    # After 18:00, show next 4 hours (excluding 00:00)
                    today_periods = []
                    for i in range(4):
                        next_hour = current_hour + 1 + i
                        if next_hour <= 23:  # Don't show 00:00 (24:00)
                            today_periods.append(f"{next_hour:02d}:00")
                else:
                    # Before 18:00, use regular periods
                    today_periods = ['00:00', '06:00', '12:00', '18:00']

                for entry in timeseries:
                    time_str = entry["time"]
                    time_obj = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    date = time_obj.date()
                    hour = time_obj.hour

                    # Process today and the next 2 days (3 days total)
                    days_diff = (date - today).days
                    if days_diff < 0 or days_diff > 2:
                        continue

                    is_today = (days_diff == 0)

                    # Initialize daily data structure
                    if date not in daily_data:
                        if is_today:
                            # Use dynamic periods for today
                            daily_data[date] = {period: {'temps': [], 'codes': []} for period in today_periods}
                        else:
                            # Use regular periods for future days
                            daily_data[date] = {
                                '00:00': {'temps': [], 'codes': []},
                                '06:00': {'temps': [], 'codes': []},
                                '12:00': {'temps': [], 'codes': []},
                                '18:00': {'temps': [], 'codes': []}
                            }

                    # Determine time period
                    period = get_time_period_name(hour, is_today, current_hour)

                    # For today, only process periods we're interested in
                    if is_today and period not in today_periods:
                        continue

                    # For today with regular periods, only show future time periods
                    if is_today and current_hour < 18:
                        period_hour_map = {'00:00': 0, '06:00': 6, '12:00': 12, '18:00': 18}
                        if period in period_hour_map and period_hour_map[period] < current_hour:
                            continue

                    # Skip if this period doesn't exist in our data structure
                    if period not in daily_data[date]:
                        continue

                    # Extract temperature
                    if "instant" in entry["data"] and "details" in entry["data"]["instant"]:
                        temp = entry["data"]["instant"]["details"].get("air_temperature")
                        if temp is not None:
                            daily_data[date][period]['temps'].append(int(temp))

                    # Extract weather code
                    weather_code = None
                    if "next_6_hours" in entry["data"] and "summary" in entry["data"]["next_6_hours"]:
                        weather_code = entry["data"]["next_6_hours"]["summary"].get("symbol_code")
                    elif "next_1_hours" in entry["data"] and "summary" in entry["data"]["next_1_hours"]:
                        weather_code = entry["data"]["next_1_hours"]["summary"].get("symbol_code")

                    if weather_code:
                        daily_data[date][period]['codes'].append(weather_code)

                # Process daily data and create widgets
                forecast_widgets = []
                for date in sorted(daily_data.keys()):
                    day_data = daily_data[date]
                    periods_data = {}

                    # Determine which periods to process for this date
                    is_today_date = (date == today)
                    periods_to_process = today_periods if is_today_date else ['00:00', '06:00', '12:00', '18:00']

                    for period in periods_to_process:
                        if period in day_data:
                            period_info = day_data[period]

                            if period_info['temps'] and period_info['codes']:
                                # Use average temperature for the period
                                avg_temp = int(sum(period_info['temps']) / len(period_info['temps']))

                                # Use the most common weather code for the period
                                most_common_code = max(set(period_info['codes']),
                                                       key=period_info['codes'].count)

                                emoji = WeatherUtils.get_weather_emoji(most_common_code)

                                periods_data[period] = {
                                    'temp': avg_temp,
                                    'emoji': emoji
                                }
                            elif period_info['temps']:
                                # Have temperature but no weather code
                                avg_temp = int(sum(period_info['temps']) / len(period_info['temps']))
                                periods_data[period] = {
                                    'temp': avg_temp,
                                    'emoji': "🌡️"
                                }

                    if periods_data:  # Only create the widget if we have data
                        day_widget = create_day_forecast(date, periods_data)
                        forecast_widgets.append(day_widget)

                # Update UI in the main thread
                GLib.idle_add(self._update_forecast_ui, forecast_widgets)

            else:
                GLib.idle_add(self._show_error)

        except Exception as e:
            print(f"Error fetching weather forecast: {e}")
            GLib.idle_add(self._show_error)

    def _update_forecast_ui(self, forecast_widgets):
        """Update the UI with forecast data"""
        # Clear existing forecast
        for child in self.forecast_container.get_children():
            self.forecast_container.remove(child)

        # Add new forecast widgets
        for widget in forecast_widgets:
            self.forecast_container.add(widget)

        # Show/hide appropriate elements
        self.loading_label.set_visible(False)
        self.error_label.set_visible(False)
        self.forecast_container.set_visible(True)
        self.forecast_container.show_all()

        return GLib.SOURCE_REMOVE

    def _show_error(self):
        """Show error message"""
        self.loading_label.set_visible(False)
        self.current_weather_container.set_visible(False)
        self.forecast_container.set_visible(False)
        self.error_label.set_visible(True)

        return GLib.SOURCE_REMOVE