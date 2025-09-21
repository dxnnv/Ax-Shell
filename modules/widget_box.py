import gi

gi.require_version("Gtk", "3.0")
from fabric.widgets.box import Box
from fabric.widgets.stack import Stack

import config.data as data
from modules.buttons import Buttons
from modules.cal import Calendar
from modules.controls import ControlSliders
from modules.metrics import Metrics
from modules.notifications import NotificationHistory
from modules.player import Player


class Widgets(Box):
    def __init__(self, **kwargs):
        super().__init__(
            name="dash-widgets",
            h_align="fill",
            v_align="fill",
            h_expand=True,
            v_expand=True,
            visible=True,
            all_visible=True,
        )

        vertical_layout = False
        if data.PANEL_THEME == "Panel" and (
            data.BAR_POSITION in ["Left", "Right"]
            or data.PANEL_POSITION in ["Start", "End"]
        ):
            vertical_layout = True

        calendar_view_mode = "week" if vertical_layout else "month"

        self.calendar = Calendar(view_mode=calendar_view_mode)

        self.notch = kwargs["notch"]

        self.buttons = Buttons(widgets=self)

        self.box_1 = Box(
            name="box-1",
            h_expand=True,
            v_expand=True,
        )

        self.box_2 = Box(
            name="box-2",
            h_expand=True,
            v_expand=True,
        )

        self.box_3 = Box(
            name="box-3",
            v_expand=True,
        )

        self.controls = ControlSliders()

        self.player = Player()

        self.metrics = Metrics()

        self.notification_history = NotificationHistory()

        self.applet_stack = Stack(
            h_expand=True,
            v_expand=True,
            transition_type="slide-left-right",
            children=[
                self.notification_history
            ],
        )

        self.applet_stack_box = Box(
            name="applet-stack",
            h_expand=True,
            v_expand=True,
            h_align="fill",
            children=[
                self.applet_stack,
            ],
        )

        if not vertical_layout:
            self.children_1 = [
                Box(
                    name="container-sub-1",
                    h_expand=True,
                    v_expand=True,
                    spacing=8,
                    children=[
                        self.calendar,
                        self.applet_stack_box,
                    ],
                ),
                self.metrics,
            ]
        else:
            self.children_1 = [
                self.applet_stack_box,
                self.calendar,  # Weekly view when vertical
                self.player,
            ]

        self.container_1 = Box(
            name="container-1",
            h_expand=True,
            v_expand=True,
            orientation="h" if not vertical_layout else "v",
            spacing=8,
            children=self.children_1,
        )

        self.container_2 = Box(
            name="container-2",
            h_expand=True,
            v_expand=True,
            orientation="v",
            spacing=8,
            children=[
                self.buttons,
                self.controls,
                self.container_1,
            ],
        )

        if not vertical_layout:
            self.children_3 = [
                self.player,
                self.container_2,
            ]
        else:  # vertical_layout
            self.children_3 = [
                self.container_2,
            ]

        self.container_3 = Box(
            name="container-3",
            h_expand=True,
            v_expand=True,
            orientation="h",
            spacing=8,
            children=self.children_3,
        )

        self.add(self.container_3)

    def show_notif(self):
        self.applet_stack.set_visible_child(self.notification_history)