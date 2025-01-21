from typing import Callable
from klayout import lay
import asyncio
from klayout import db
from io import BytesIO
import numpy as np
from PIL import Image
import plotly.graph_objects as go
from plotly.callbacks import Points, InputDeviceState

from os import PathLike


class IKlayout:
    layout_view: lay.LayoutView
    fig: go.FigureWidget
    trace: go.Figure
    img: go.Image
    dimensions = (800, 600)

    def __init__(self, gds_file: PathLike):
        self.layout_view = lay.LayoutView()
        self.layout_view.load_layout(gds_file)
        self.layout_view.max_hier()
        self.layout_view.zoom_fit()
        self.layout_view.add_missing_layers()
        self.layout_view.resize(self.dimensions[0], self.dimensions[1])

        asyncio.create_task(self.timer())

    async def timer(self):
        self.layout_view.on_image_updated_event = self.refresh
        while (True):
            self.layout_view.timer()
            await asyncio.sleep(0.01)

    def _get_image_array(self):
        pixel_buffer = self.layout_view.get_screenshot_pixels()
        png_data = pixel_buffer.to_png_data()
        return np.array(Image.open(BytesIO(png_data)))

    def refresh(self):
        print("refresh")
        self.fig.update(
            {
                'data': [go.Image(
                    z=self._get_image_array(),
                )]
            }
        )

    def show(self):
        self.fig = go.FigureWidget(
            go.Image(
                z=self._get_image_array(),
            )
        )
        self.fig.update_layout(
            margin=dict(l=0, r=0, b=0, t=0, pad=0),
            autosize=True,
            width=self.dimensions[0],
            height=self.dimensions[1],
            xaxis_visible=False,
            yaxis_visible=False,
        )

        img: go.Image = self.fig.data[0]

        img.on_click(self.on_mouse_click)
        return self.fig

    @property
    def image(self) -> go.Image:
        return self.fig.data[0]

    def handle_mouse_event(
        self,
        function: Callable[[int, bool, db.DPoint, int], None],
        trace,
        points: Points,
        state: InputDeviceState
    ):
        function(
            db.Point(points.xs[0], points.ys[0]), lay.ButtonState.LeftButton
        )

    def on_mouse_click(self, *args, **kwargs):
        self.handle_mouse_event(
                self.layout_view.send_mouse_press_event, *args, **kwargs
            )
        self.handle_mouse_event(
                self.layout_view.send_mouse_release_event, *args, **kwargs
            )

    def on_mouse_release(self, *args, **kwargs):
        print("clicked")
        self.handle_mouse_event(
            self.layout_view.send_mouse_release_event, *args, **kwargs
        )

    def on_mouse_move(self, *args, **kwargs):
        self.handle_mouse_event(
            self.layout_view.send_mouse_move_event, *args, **kwargs
        )

    def on_mouse_enter(self, *args, **kwargs):
        self.layout_view.send_enter_event()

    def on_mouse_leave(self, *args, **kwargs):
        self.layout_view.send_leave_event()

    def get_selected_cell(self):
        selected_cells_paths = self.layout_view.selected
        return self.layout_view.cell(selected_cells_paths[0])
