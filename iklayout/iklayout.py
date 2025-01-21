from typing import Callable
from klayout import lay
from gdsfactory import Component
import asyncio
from klayout import db
import matplotlib.pyplot as plt
from io import BytesIO
import plotly.express as px
import numpy as np
from PIL import Image
from plotly.graph_objects import Figure


class IKlayout:
    layout_view: lay.LayoutView
    ax: plt.Axes
    img: Figure

    def __init__(self, c: Component):
        self.layout_view = lay.LayoutView()
        p = c.write_gds()
        self.layout_view.load_layout(p.absolute())
        self.layout_view.max_hier()
        self.layout_view.zoom_fit()
        self.layout_view.add_missing_layers()

        self.show()

        asyncio.create_task(self.timer())

    async def timer(self):
        self.layout_view.on_image_updated_event = self.refresh
        while(True):
            self.layout_view.timer()
            await asyncio.sleep(0.01)


    def refresh(self):
        self.layout_view.resize(800, 600)
        pixel_buffer = self.layout_view.get_screenshot_pixels()
        png_data = pixel_buffer.to_png_data()
        array = np.array(Image.open(BytesIO(png_data)))
        self.img.update_layout(images=[dict(z=array)])

    def show(self):
        self.layout_view.resize(800, 600)
        pixel_buffer = self.layout_view.get_screenshot_pixels()
        png_data = pixel_buffer.to_png_data()


        array = np.array(Image.open(BytesIO(png_data)))

        self.img = px.imshow(array, width=800, height=600)
        self.img.show()

        # self.fig = fig
        # self.ax = ax

        # # Remove margins and display the image
        # ax.imshow(img_array)
        # ax.axis("off")  # Hide axes
        # ax.set_position([0, 0, 1, 1])  # Set axes to occupy the full figure space

        # plt.subplots_adjust(
        #     left=0, right=1, top=1, bottom=0, wspace=0, hspace=0
        # )  # Remove any padding
        # plt.tight_layout(pad=0)  # Ensure no space is wasted

        # fig.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        # fig.canvas.mpl_connect('button_release_event', self.on_mouse_release)
        # fig.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        # fig.canvas.mpl_connect('figure_enter_event', self.on_mouse_enter)
        # fig.canvas.mpl_connect('figure_leave_event', self.on_mouse_leave)

        # fig = px.imshow(img_rgb)
        # fig.show()
        
        # self.img = self.ax.imshow(img_array)

    def handle_mouse_event(self, function: Callable[[int, bool, db.DPoint, int], None], event):
        function(db.Point(event.xdata, event.ydata), lay.ButtonState.LeftButton)

    def on_mouse_press(self, event):
        if event.dblclick:
            self.handle_mouse_event(self.layout_view.send_mouse_double_clicked_event, event)
        else:
            self.handle_mouse_event(self.layout_view.send_mouse_press_event, event)

    def on_mouse_release(self, event):
        self.handle_mouse_event(self.layout_view.send_mouse_release_event, event)

    def on_mouse_move(self, event):
        self.handle_mouse_event(self.layout_view.send_mouse_move_event, event)
    
    def on_mouse_enter(self, event):
        self.layout_view.send_enter_event()
    
    def on_mouse_leave(self, event):
        self.layout_view.send_leave_event()


    def get_selected_cell(self):
        selected_cells_paths = self.layout_view.selected
        return self.layout_view.cell(selected_cells_paths[0])

