import calendar
import subprocess
from datetime import datetime, timedelta

import gi
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.label import Label

import modules.icons as icons

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Gio

from config.loguru_config import logger

logger = logger.bind(name="Calendar", type="Module")

class Calendar(Gtk.Box):
    def __init__(self, view_mode="month"):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8, name="calendar")
        self.view_mode = view_mode
        self.first_weekday = 0  # Default: Monday, will be updated async

        self.set_halign(Gtk.Align.CENTER)
        self.set_hexpand(False)

        self.current_day_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        if self.view_mode == "month":
            self.current_shown_date = self.current_day_date.replace(day=1)
            self.current_year = self.current_shown_date.year
            self.current_month = self.current_shown_date.month
            self.current_day = self.current_day_date.day # Just to highlight in create_month_view
            self.previous_key = (self.current_year, self.current_month)
        elif self.view_mode == "week":
            # the current_shown_date is the first day (according to locale) of the current week
            days_to_subtract = (self.current_day_date.weekday() - self.first_weekday + 7) % 7
            self.current_shown_date = self.current_day_date - timedelta(days=days_to_subtract)
            self.current_year = self.current_shown_date.year # For the header
            self.current_month = self.current_shown_date.month # For the header
            iso_year, iso_week, _ = self.current_shown_date.isocalendar()
            self.previous_key = (iso_year, iso_week)
            self.set_halign(Gtk.Align.FILL)
            self.set_hexpand(True)
            self.set_valign(Gtk.Align.CENTER)
            self.set_vexpand(False)
        
        self.cache_threshold = 3 # Threshold for keeping views cached

        self.month_views = {} # Repurposed for weekday views too

        self.prev_button = Gtk.Button( # Generic button name
            name="prev-month-button", 
            child=Label(name="month-button-label", markup=icons.chevron_left) # CSS can be generic
        )
        self.prev_button.connect("clicked", self.on_prev_clicked)

        self.month_label = Gtk.Label(name="month-label") # The name is historical, but shows month/year

        self.next_button = Gtk.Button( # Generic button name
            name="next-month-button",
            child=Label(name="month-button-label", markup=icons.chevron_right) # CSS can be generic
        )
        self.next_button.connect("clicked", self.on_next_clicked)

        self.header = CenterBox(
            spacing=4,
            name="header",
            start_children=[self.prev_button],
            center_children=[self.month_label],
            end_children=[self.next_button],
        )

        self.add(self.header)

        self.weekday_row = Gtk.Box(spacing=4, name="weekday-row")
        self.pack_start(self.weekday_row, False, False, 0)

        self.stack = Gtk.Stack(name="calendar-stack")
        self.stack.set_transition_duration(250)
        self.pack_start(self.stack, True, True, 0)

        self.update_header() # Call before update_calendar so that the first header is correct
        self.update_calendar()
        self.setup_periodic_update()
        self.setup_dbus_listeners()

        # Initialize locale settings asynchronously
        GLib.Thread.new("calendar-locale", self._init_locale_settings_thread, None)

    def _init_locale_settings_thread(self, user_data):
        """Background thread to initialize locale settings without blocking UI."""
        try:
            origin_date_str = subprocess.check_output(["locale", "week-1stday"], text=True).strip()
            first_weekday_val = int(subprocess.check_output(["locale", "first_weekday"], text=True).strip())
            
            origin_date = datetime.fromisoformat(origin_date_str)
            # This logic calculates the day of the week (0-6, Monday=0) that is considered the first
            # based on the combined locale settings of week-1stday and first_weekday.
            date_of_first_day_of_week_config = origin_date + timedelta(days=first_weekday_val - 1)
            new_first_weekday = date_of_first_day_of_week_config.weekday() # Monday=0, ..., Sunday=6
            
            # Update the first_weekday on the main thread and refresh calendar if needed
            GLib.idle_add(self._update_first_weekday, new_first_weekday)
        except Exception as e:
            logger.error(f"Unable to get locale first weekday: {e}")
            # Keep default value (0 = Monday)
    
    def _update_first_weekday(self, new_first_weekday):
        """Update first weekday setting and refresh calendar if changed."""
        if self.first_weekday != new_first_weekday:
            self.first_weekday = new_first_weekday
            # Clear cache and refresh the calendar with new locale settings
            self.month_views.clear()
            # Remove all current stack children to force regeneration
            for child in self.stack.get_children():
                self.stack.remove(child)
            # Update header (which includes weekday labels) and calendar
            self.update_header()
            self.update_calendar()
        return False  # Don't repeat this idle callback

    def setup_periodic_update(self):
        # Check for date changes every second
        GLib.timeout_add(1000, self.check_date_change)

    def setup_dbus_listeners(self):
        # Listen for system suspend/resume events
        bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        bus.signal_subscribe(
            None,  # sender
            'org.freedesktop.login1.Manager',  # interface
            'PrepareForSleep',  # signal
            '/org/freedesktop/login1',  # path
            None,  # arg0
            Gio.DBusSignalFlags.NONE,
            self.on_suspend_resume,  # callback
            None  # user_data
        )

    def check_date_change(self):
        now = datetime.now()
        current_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if current_date != self.current_day_date:
            self.on_midnight()
        return True  # Continue the timer

    def on_suspend_resume(self):
        # Check date when resuming from suspend
        self.check_date_change()

    def on_midnight(self):
        now = datetime.now()
        self.current_day_date = now.replace(hour=0, minute=0, second=0, microsecond=0)

        key_to_remove_for_today_highlight = None
        if self.view_mode == "month":
            # Update the base date for the month view if necessary (although it usually doesn't change at midnight)
            self.current_shown_date = self.current_day_date.replace(day=1)
            self.current_year = self.current_shown_date.year
            self.current_month = self.current_shown_date.month
            self.current_day = self.current_day_date.day # Update the current day
            key_to_remove_for_today_highlight = (self.current_year, self.current_month)
        elif self.view_mode == "week":
            days_to_subtract = (self.current_day_date.weekday() - self.first_weekday + 7) % 7
            self.current_shown_date = self.current_day_date - timedelta(days=days_to_subtract)
            self.current_year = self.current_shown_date.year # For the header
            self.current_month = self.current_shown_date.month # For the header
            iso_year, iso_week, _ = self.current_shown_date.isocalendar()
            key_to_remove_for_today_highlight = (iso_year, iso_week)

        # Delete the current view from the cache to force a refresh with the new "today" highlighted
        if key_to_remove_for_today_highlight and key_to_remove_for_today_highlight in self.month_views:
            widget = self.month_views.pop(key_to_remove_for_today_highlight)
            self.stack.remove(widget)
            # If the deleted view was the current one, previous_key might be outdated
            # but update_calendar will correct this when setting up the new view.

        self.update_calendar() # This will regenerate the view if it was deleted and update the highlighting.
        return False # Important so that the timeout does not repeat automatically

    def update_header(self):
        # self.current_shown_date is the first day of the month (month mode) or the first day of the week (week mode)
        # The header always shows the month and year of self.current_shown_date
        self.month_label.set_text(self.current_shown_date.strftime("%B %Y").capitalize())

        for child in self.weekday_row.get_children():
            self.weekday_row.remove(child)
        
        day_initials = self.get_weekday_initials()
        for day_initial in day_initials:
            label = Gtk.Label(label=day_initial.upper(), name="weekday-label")
            self.weekday_row.pack_start(label, True, True, 0)
        self.weekday_row.show_all()

    def update_calendar(self):
        new_key = None
        child_name = "" # Renaming child_name_prefix
        view_widget = None

        if self.view_mode == "month":
            new_key = (self.current_year, self.current_month)
            child_name = f"{self.current_year}_{self.current_month}"
            if new_key not in self.month_views:
                view_widget = self.create_month_view(self.current_year, self.current_month)
        elif self.view_mode == "week":
            iso_year, iso_week, _ = self.current_shown_date.isocalendar()
            new_key = (iso_year, iso_week)
            child_name = f"{iso_year}_w{iso_week}"
            if new_key not in self.month_views:
                # Pass self.current_shown_date directly to create_week_view
                view_widget = self.create_week_view(self.current_shown_date)
        
        if new_key is None: return

        if new_key > self.previous_key:
            self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)
        elif new_key < self.previous_key:
            self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_RIGHT)
        # else: no transition if key is the same (e.g. on_midnight for same month/week)

        self.previous_key = new_key

        if view_widget: # If a new view was created
            self.month_views[new_key] = view_widget
            self.stack.add_titled(view_widget, child_name, child_name)
        
        self.stack.set_visible_child_name(child_name)
        # The header is updated BEFORE calling update_calendar in __init__ and on_clicked,
        # and also on_midnight if necessary.
        # However, if the view changes (e.g., from January to February), the header should reflect this.
        self.update_header() # Ensure the header is synchronized with the current view
        self.stack.show_all()

        self.prune_cache()

    def prune_cache(self):
        def get_key_index(key_tuple):
            year, num = key_tuple # num is month or week_number
            if self.view_mode == "month": # Assuming the key is (year, month)
                return year * 12 + (num - 1)
            else: # Assuming the key is (iso_year, iso_week)
                return year * 53 + num # Use 53 to cover years with 53 ISO weeks
                
        current_index = get_key_index(self.previous_key) # previous_key is the key of the current view
        keys_to_remove = []
        for key_iter in self.month_views:
            if abs(get_key_index(key_iter) - current_index) > self.cache_threshold:
                keys_to_remove.append(key_iter)
        for key_to_remove in keys_to_remove:
            widget = self.month_views.pop(key_to_remove)
            self.stack.remove(widget)

    def create_month_view(self, year, month):
        grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=False, name="calendar-grid")
        cal = calendar.Calendar(firstweekday=self.first_weekday)
        month_days = cal.monthdayscalendar(year, month)

        while len(month_days) < 6: # Ensure 6 rows for visual consistency
            month_days.append([0] * 7) # [0] represents an empty day

        for row, week in enumerate(month_days):
            for col, day_num in enumerate(week):
                day_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, name="day-box")
                top_spacer = Gtk.Box(hexpand=True, vexpand=True)
                middle_box = Gtk.Box(hexpand=True, vexpand=True)
                bottom_spacer = Gtk.Box(hexpand=True, vexpand=True)

                if day_num == 0:
                    label = Label(name="day-empty", markup=icons.dot)
                else:
                    label = Gtk.Label(label=str(day_num), name="day-label")
                    day_date_obj = datetime(year, month, day_num)
                    if day_date_obj == self.current_day_date:
                        label.get_style_context().add_class("current-day")
                
                middle_box.pack_start(Gtk.Box(hexpand=True, vexpand=True), True, True, 0)
                middle_box.pack_start(label, False, False, 0)
                middle_box.pack_start(Gtk.Box(hexpand=True, vexpand=True), True, True, 0)

                day_box.pack_start(top_spacer, True, True, 0)
                day_box.pack_start(middle_box, True, True, 0)
                day_box.pack_start(bottom_spacer, True, True, 0)
                grid.attach(day_box, col, row, 1, 1)
        grid.show_all()
        return grid

    def create_week_view(self, first_day_of_week_to_display):
        grid = Gtk.Grid(column_homogeneous=True, row_homogeneous=False, name="calendar-grid-week-view") # Could have different style
        
        # The reference month for dimming is the month from first_day_of_week_to_display
        # that is self.current_shown_date, and its month is self.current_month (updated in nav)
        reference_month_for_dimming = first_day_of_week_to_display.month

        for col in range(7):
            current_day_in_loop = first_day_of_week_to_display + timedelta(days=col)
            
            day_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, name="day-box") # Reuse day-box style
            top_spacer = Gtk.Box(hexpand=True, vexpand=True)
            middle_box = Gtk.Box(hexpand=True, vexpand=True)
            bottom_spacer = Gtk.Box(hexpand=True, vexpand=True)

            label = Gtk.Label(label=str(current_day_in_loop.day), name="day-label")

            if current_day_in_loop == self.current_day_date:
                label.get_style_context().add_class("current-day")
            
            if current_day_in_loop.month != reference_month_for_dimming:
                 label.get_style_context().add_class("dim-label") # Need CSS: .dim-label { opacity: 0.5; } or similar

            middle_box.pack_start(Gtk.Box(hexpand=True, vexpand=True), True, True, 0)
            middle_box.pack_start(label, False, False, 0)
            middle_box.pack_start(Gtk.Box(hexpand=True, vexpand=True), True, True, 0)

            day_box.pack_start(top_spacer, True, True, 0)
            day_box.pack_start(middle_box, True, True, 0)
            day_box.pack_start(bottom_spacer, True, True, 0)
            
            grid.attach(day_box, col, 0, 1, 1) # Every day in row 0
        
        # To maintain a similar height to the monthly view, empty rows could be added.
        # This is optional and depends on the desired layout.
        # for r_idx in range(1, 6): # Add 5 empty rows
        # empty_row_placeholder = Gtk.Box(name="day-empty-placeholder", hexpand=True, vxpand=True, height_request=20) # Adjust height
        # grid.attach(empty_row_placeholder, 0, r_idx, 7, 1) # Spans all 7 columns

        grid.show_all()
        return grid

    def get_weekday_initials(self):
        # Generates the initials of the days of the week starting with self.first_weekday
        # datetime(2025, 1, 1) is Monday. Its weekday() is 0.
        # If self.first_weekday is 0 (Monday), we want the first day to be Monday.
        # i=0: datetime(2025, 1, 1 + 0) -> Monday
        # If self.first_weekday is 6 (Sunday), we want the first day to be Sunday.
        # i=0: datetime(2025, 1, 1 + 6) -> Sunday
        # This logic is correct.
        return [(datetime(2025, 1, 1) + timedelta(days=(self.first_weekday + i) % 7)).strftime("%a")[:1] for i in range(7)]


    def on_prev_clicked(self, widget):
        if self.view_mode == "month":
            current_month_val = self.current_shown_date.month
            current_year_val = self.current_shown_date.year
            if current_month_val == 1:
                self.current_shown_date = self.current_shown_date.replace(year=current_year_val - 1, month=12)
            else:
                self.current_shown_date = self.current_shown_date.replace(month=current_month_val - 1)
            self.current_year = self.current_shown_date.year
            self.current_month = self.current_shown_date.month
        elif self.view_mode == "week":
            self.current_shown_date -= timedelta(days=7)
            self.current_year = self.current_shown_date.year # Update for the header
            self.current_month = self.current_shown_date.month # Update for header and dimming
        
        # self.update_header() # It is called within update_calendar
        self.update_calendar()

    def on_next_clicked(self, widget):
        if self.view_mode == "month":
            current_month_val = self.current_shown_date.month
            current_year_val = self.current_shown_date.year
            if current_month_val == 12:
                self.current_shown_date = self.current_shown_date.replace(year=current_year_val + 1, month=1)
            else:
                self.current_shown_date = self.current_shown_date.replace(month=current_month_val + 1)
            self.current_year = self.current_shown_date.year
            self.current_month = self.current_shown_date.month
        elif self.view_mode == "week":
            self.current_shown_date += timedelta(days=7)
            self.current_year = self.current_shown_date.year # Update for the header
            self.current_month = self.current_shown_date.month # Update for header and dimming

        # self.update_header() # It is called within update_calendar
        self.update_calendar()
