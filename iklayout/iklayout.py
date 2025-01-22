from typing import Callable, TypedDict
from klayout import lay
import asyncio
from klayout import db
from io import BytesIO
from matplotlib.backend_bases import KeyEvent, MouseEvent
from matplotlib.transforms import Bbox
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.image import AxesImage
import matplotlib.patches as patches
from matplotlib.widgets import Button, CheckButtons
from .throttle import throttle
from matplotlib.patches import FancyBboxPatch


from os import PathLike


class CellInfo(TypedDict):
    name: str
    id: int
    bbox: db.Box
    is_top: bool


class IKlayout:
    layout_view: lay.LayoutView
    fig: plt.Figure
    ax: plt.Axes
    img: AxesImage
    info_box: patches.Rectangle | None = None
    info_text: plt.Text | None = None
    dimensions = (800, 600)
    zoom_in_btn: Button = None
    zoom_out_btn: Button = None
    reset_zoom_btn: Button = None
    ruler_toggle_btn: Button = None
    ruler_mode_active = False
    clear_ruler_btn: Button = None
    button_areas: list[Bbox] = []
    shift_pressed = False

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
        self.img.set_data(self._get_image_array())
        self.fig.canvas.draw()

    def show(self):
        self.fig, self.ax = plt.subplots(
            figsize=(self.dimensions[0] / 100, self.dimensions[1] / 100)
        )
        self.img = self.ax.imshow(self._get_image_array())
        self.ax.axis('off')
        self.ax.set_position([0, 0, 1, 1])

        self.fig.canvas.toolbar_visible = False
        self.fig.canvas.header_visible = False
        self.fig.canvas.footer_visible = False
        self.fig.canvas.resizable = False
        self.fig.canvas.capture_scroll = True

        plt.subplots_adjust(
            left=0, right=1, top=1, bottom=0, wspace=0, hspace=0,
        )
        plt.tight_layout(pad=0)
        self.ax.set_aspect('auto', 'box')

        self.fig.canvas.mpl_connect('button_press_event', self.on_mouse_press)
        self.fig.canvas.mpl_connect(
            'button_release_event', self.on_mouse_release
        )
        self.fig.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.fig.canvas.mpl_connect('figure_enter_event', self.on_mouse_enter)
        self.fig.canvas.mpl_connect('figure_leave_event', self.on_mouse_leave)
        self.fig.canvas.mpl_connect('scroll_event', self.on_scroll)
        self.fig.canvas.mpl_connect('key_press_event', self.on_key_down)
        self.fig.canvas.mpl_connect('key_release_event', self.on_key_up)

        self._draw_zoom_buttons()
        self._draw_ruler_button()
        self._update_button_areas()

        plt.show()

    def _update_button_areas(self) -> list[Bbox]:
        self.button_areas = [
            self.reset_zoom_btn.ax.bbox,
            self.ruler_toggle_btn.ax.bbox,
            self.clear_ruler_btn.ax.bbox,
        ]

    def _is_event_in_button_area(self, event: MouseEvent):
        for area in self.button_areas:
            if area.contains(event.x, event.y):
                return True
        return False

    def handle_mouse_event(
            self,
            function: Callable[[int, bool, db.DPoint, int], None],
            event: MouseEvent
    ):
        if self._is_event_in_button_area(event):
            return

        point = db.Point(event.xdata, event.ydata)
        button = lay.ButtonState.LeftButton

        if self.shift_pressed:
            button += lay.ButtonState.ShiftKey

        function(point, button)

    @throttle(0.1)
    def on_scroll(self, event: MouseEvent):
        if event.button == 'up':
            self.layout_view.zoom_in()
        elif event.button == 'down':
            self.layout_view.zoom_out()

    def on_mouse_press(self, event: MouseEvent):
        if event.dblclick:
            return
        else:
            self.handle_mouse_event(
                self.layout_view.send_mouse_press_event, event
            )

    def _on_selection_changed(self, event: MouseEvent):
        selected_cell = self._get_selected_cell()

        if selected_cell and not self.ruler_mode_active:
            point = (event.xdata, event.ydata)
            self._draw_cell_info(selected_cell, point)
        else:
            self._remove_info_box()

    def on_mouse_release(self, event: MouseEvent):
        self.handle_mouse_event(
            self.layout_view.send_mouse_release_event,
            event
        )

        if (not self.ruler_mode_active
                and not self._is_event_in_button_area(event)):
            self._on_selection_changed(event)

    def _remove_info_box(self):
        if not self.info_box:
            return
        self.info_box.remove()
        self.text.remove()
        self.info_box = None

    def on_mouse_move(self, event: MouseEvent):
        self.handle_mouse_event(self.layout_view.send_mouse_move_event, event)

    def on_mouse_enter(self, event: MouseEvent):
        self.layout_view.send_enter_event()

    def on_mouse_leave(self, event: MouseEvent):
        self.layout_view.send_leave_event()

    def on_key_down(self, event: KeyEvent):
        if event.key == 'shift':
            self.shift_pressed = True

    def on_key_up(self, event: KeyEvent):
        if event.key == 'shift':
            self.shift_pressed = False

    def _draw_cell_info(self, cell: CellInfo, point):
        self._remove_info_box()

        text = f"{cell['name']}"
        fontsize = 8
        box_height = 30

        temp_text = self.ax.text(
            0, 0, text, fontsize=fontsize, va='center', ha='center'
        )
        renderer = self.fig.canvas.get_renderer()
        bbox = temp_text.get_window_extent(renderer)
        temp_text.remove()

        display_to_data_ratio = (
            self.ax.transData.inverted().transform((1, 0))[0] 
            - self.ax.transData.inverted().transform((0, 0))[0]
        )
        box_width = (bbox.width * display_to_data_ratio) + 20

        box_x, box_y = point
        offset = 15
        box_x += offset
        box_y += offset

        # Ensure the box does not collide with the edges of the plot
        if box_x + box_width > self.ax.get_xlim()[1]:
            box_x -= (box_width + 20)
        if box_y + box_height > self.ax.get_ylim()[0]:
            box_y -= (box_height + 20)

        self.info_box = FancyBboxPatch(
            (box_x, box_y), box_width, box_height,
            boxstyle="round,pad=0.5,rounding_size=0.3",
            linewidth=2,
            edgecolor='#4CAF50',
            facecolor='#6EB700',
            alpha=0.9,
            mutation_scale=10
        )
        self.ax.add_patch(self.info_box)

        self.text = self.ax.text(
            box_x + box_width / 2,
            box_y + box_height / 2,
            text,
            color='white',
            fontsize=fontsize,
            ha='center',
            va='center',
            fontweight='bold'
        )

    def reset_zoom(self, *args):
        self.layout_view.zoom_fit()

    def _draw_zoom_buttons(self):
        reset_zoom = self.fig.add_axes([0.9, 0.93, 0.08, 0.05])
        self.reset_zoom_btn = Button(
            reset_zoom, 'Reset',
            color='#6EB700', hovercolor='#4CAF50'
        )
        self.reset_zoom_btn.label.set_fontsize(10)
        self.reset_zoom_btn.label.set_color('white')
        self.reset_zoom_btn.label.set_fontweight(500)
        self.reset_zoom_btn.on_clicked(self.reset_zoom)

    def _draw_ruler_button(self):
        if "ruler" not in self.layout_view.mode_names():
            return

        ruler_toggle = self.fig.add_axes([0.02, 0.93, 0.08, 0.05])
        self.ruler_toggle_btn = CheckButtons(
            ruler_toggle,
            ['Ruler'],
            [self.ruler_mode_active],
        )

        self.ruler_toggle_btn.on_clicked(self.toggle_ruler)

        clear_ruler = self.fig.add_axes([0.12, 0.93, 0.08, 0.05])
        self.clear_ruler_btn = Button(
            clear_ruler, 'Clear',
            color='white',
        )
        self.clear_ruler_btn.label.set_fontsize(10)
        self.clear_ruler_btn.label.set_fontweight(500)
        self.clear_ruler_btn.on_clicked(self.clear_rulers)

    def clear_rulers(self, *args):
        self.layout_view.clear_annotations()

    def toggle_ruler(self, label):
        if self.ruler_mode_active:
            self.layout_view.switch_mode("select")
            self.ruler_mode_active = False
        else:
            self.layout_view.switch_mode("ruler")
            self.ruler_mode_active = True
            self._remove_info_box()
            self.layout_view.clear_selection()
        self._update_ruler_button()

    def _update_ruler_button(self):
        pass

    def _get_selected_cell(self) -> CellInfo | None:
        all_cells = self.get_all_cells()
        selected_cell = None

        # Iterate through the selected objects
        for obj in self.layout_view.each_object_selected():
            # Get the instance path of the selected object
            cell_index = obj.cell_index()
            for cell in all_cells:
                if cell["id"] == cell_index:
                    selected_cell = cell
                    break

        return selected_cell

    def get_all_cells(self) -> list[CellInfo]:
        layout = self.layout_view.active_cellview().layout()
        top_cells = layout.top_cells()

        cells = []

        def get_children(cell: db.Cell):
            if not cell.child_cells():
                return []
            iter = cell.each_child_cell()
            for child_idx in iter:
                child = layout.cell(child_idx)
                cells.append(
                    {
                        "name": child.name,
                        "id": child.cell_index(),
                        "bbox": child.bbox(),
                        "is_top": False
                    }
                )
                get_children(child)

        for top_cell in top_cells:
            cells.append(
                {
                    "name": top_cell.name,
                    "id": top_cell.cell_index(),
                    "bbox": top_cell.bbox(),
                    "is_top": True,
                }
            )
            get_children(top_cell),

        return cells
