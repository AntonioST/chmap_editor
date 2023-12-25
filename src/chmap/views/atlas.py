from typing import get_args, TypedDict, Final

import numpy as np
from bokeh.models import ColumnDataSource, GlyphRenderer, Select, Slider, UIElement, Toggle
from bokeh.plotting import figure as Figure
from numpy.typing import NDArray

from chmap.config import ChannelMapEditorConfig
from chmap.util.atlas_brain import BrainGlobeAtlas, get_atlas_brain
from chmap.util.atlas_slice import SlicePlane, SLICE, SliceView
from chmap.util.bokeh_util import ButtonFactory
from chmap.util.utils import is_recursive_called
from chmap.views.base import StateView, BoundView, BoundaryState

__all__ = ['AtlasBrainView', 'AtlasBrainViewState']


class AtlasBrainViewState(TypedDict):
    atlas_brain: str
    brain_slice: SLICE | None
    slice_plane: int | None
    slice_rot_w: int | None
    slice_rot_h: int | None
    image_dx: float
    image_dy: float
    image_sx: float
    image_sy: float
    image_rt: float


class AtlasBrainView(BoundView, StateView[AtlasBrainViewState]):
    brain: Final[BrainGlobeAtlas]

    data_brain: ColumnDataSource
    render_brain: GlyphRenderer

    def __init__(self, config: ChannelMapEditorConfig):
        self.brain = get_atlas_brain(config.atlas_name, config.atlas_root)

        super().__init__(config)

        self.data_brain = ColumnDataSource(data=dict(image=[], x=[], y=[], dw=[], dh=[]))

        self._brain_view: SliceView | None = None
        self._brain_slice: SlicePlane | None = None

    # ========== #
    # properties #
    # ========== #

    @property
    def visible(self) -> bool:
        try:
            return self.render_brain.visible
        except AttributeError:
            return False

    @visible.setter
    def visible(self, v: bool):
        try:
            self.render_brain.visible = v
            self.render_boundary.visible = v
        except AttributeError:
            pass

    @property
    def width(self) -> float:
        try:
            return self._brain_slice.width
        except TypeError:
            return 0

    @property
    def height(self) -> float:
        try:
            return self._brain_slice.height
        except TypeError:
            return 0

    @property
    def brain_view(self) -> SliceView:
        return self._brain_view

    @property
    def brain_slice(self) -> SlicePlane | None:
        return self._brain_slice

    # ================= #
    # render components #
    # ================= #

    def plot(self, f: Figure, palette: str = 'Greys256',
             boundary_color: str = 'black',
             boundary_desp: str = 'drag atlas brain image',
             **kwargs):
        self.render_brain = f.image(
            'image', x='x', y='y', dw='dw', dh='dh', source=self.data_brain,
            palette=palette, level="image", global_alpha=0.5, syncable=False,
        )
        super().plot(f, boundary_color=boundary_color, boundary_desp=boundary_desp, **kwargs)

    # ============= #
    # UI components #
    # ============= #

    visible_btn: Toggle
    slice_select: Select
    plane_slider: Slider
    rotate_hor_slider: Slider
    rotate_ver_slider: Slider

    def setup(self, slider_width: int = 300, rotate_steps=(-1000, 1000, 5), **kwargs) -> list[UIElement]:
        new_btn = ButtonFactory(min_width=100, width_policy='min')

        #
        slice_view_options = list(get_args(SLICE))
        self.slice_select = Select(
            title='Slice view',
            value=slice_view_options[0],
            options=slice_view_options,
            width=100
        )
        self.slice_select.on_change('value', self.on_slice_selected)

        #
        self.plane_slider = Slider(
            start=0,
            end=1,
            step=1,
            value=0,
            title='Slice Plane',
            width=slider_width,
            align='end',
        )
        self.plane_slider.on_change('value', self.on_slice_changed)

        #
        self.rotate_hor_slider = Slider(
            start=rotate_steps[0],
            end=rotate_steps[1],
            step=rotate_steps[2],
            value=0,
            title='horizontal rotation (um)',
            width=slider_width,
        )
        self.rotate_hor_slider.on_change('value', self.on_rotate_changed)

        #
        self.rotate_ver_slider = Slider(
            start=rotate_steps[0],
            end=rotate_steps[1],
            step=rotate_steps[2],
            value=0,
            title='vertical rotation (um)',
            width=slider_width,
        )
        self.rotate_ver_slider.on_change('value', self.on_rotate_changed)

        self.visible_btn = Toggle(label='Brain Atlas', active=True, min_width=150, width_policy='min')
        self.visible_btn.on_change('active', self.on_visible)

        reset_rth = new_btn('reset', self.on_reset_rotate_horizontal)
        reset_rtv = new_btn('reset', self.on_reset_rotate_vertical)

        from bokeh.layouts import row
        return [
            self.visible_btn,
            row(self.slice_select, self.plane_slider),
            row(reset_rth, self.rotate_hor_slider),
            row(reset_rtv, self.rotate_ver_slider),
            *self.setup_slider(slider_width=slider_width)
        ]

    # noinspection PyUnusedLocal
    def on_visible(self, prop: str, old: bool, active: bool):
        self.visible = active

    # noinspection PyUnusedLocal
    def on_slice_selected(self, prop: str, old: str, s: str):
        if is_recursive_called():
            return

        self.update_brain_view(s)

    # noinspection PyUnusedLocal
    def on_slice_changed(self, prop: str, old: int, s: int):
        if is_recursive_called():
            return

        if (p := self._brain_slice) is not None:
            q = p.slice.plane_at(int(s)).with_offset(p.dw, p.dh)
            self.update_brain_slice(q)

    # noinspection PyUnusedLocal
    def on_rotate_changed(self, prop: str, old: int, s: int):
        if is_recursive_called():
            return

        if (p := self._brain_slice) is not None:
            r = p.slice.resolution
            x = int(self.rotate_hor_slider.value / r)
            y = int(self.rotate_ver_slider.value / r)
            q = p.with_offset(x, y)
            self.update_brain_slice(q)

    def on_reset_rotate_horizontal(self):
        try:
            self.rotate_hor_slider.value = 0
        except AttributeError:
            pass

    def on_reset_rotate_vertical(self):
        try:
            self.rotate_ver_slider.value = 0
        except AttributeError:
            pass

    # ========= #
    # load/save #
    # ========= #

    def save_state(self) -> AtlasBrainViewState:
        boundary = self.get_boundary_state()

        return AtlasBrainViewState(
            atlas_brain=self.brain.atlas_name,
            brain_slice=None if (p := self._brain_view) is None else p.name,
            slice_plane=None if (p := self._brain_slice) is None else p.plane,
            slice_rot_w=None if p is None else p.dw,
            slice_rot_h=None if p is None else p.dh,
            image_dx=boundary['dx'],
            image_dy=boundary['dy'],
            image_sx=boundary['sx'],
            image_sy=boundary['sy'],
            image_rt=boundary['rt'],
        )

    def restore_state(self, state: AtlasBrainViewState):
        if self.brain.atlas_name != state['atlas_brain']:
            raise RuntimeError()

        self.update_brain_view(state['brain_slice'], update_image=False)

        dp = state['slice_plane']
        dw = state['slice_rot_w']
        dh = state['slice_rot_h']
        brain_slice = self.brain_view.plane_at(dp).with_offset(dw, dh)
        self.update_brain_slice(brain_slice, update_image=False)

        self.update_boundary_transform(p=(state['image_dx'], state['image_dy']), s=(state['image_sx'], state['image_sx']), rt=state['image_rt'])

    # ================ #
    # updating methods #
    # ================ #

    def update(self):
        if self.brain_view is None:
            try:
                view = self.slice_select.value
            except AttributeError:
                view = 'coronal'

            self.update_brain_view(view)
        elif (plane := self._brain_slice) is not None:
            self.update_image(plane.image)

    def update_brain_view(self, view: SLICE | SliceView, *,
                          update_image=True):
        if is_recursive_called():
            return

        if isinstance(view, str):
            view = SliceView(self.brain, view)

        self._brain_view = view

        try:
            self.slice_select.value = view.name
        except AttributeError:
            pass

        try:
            self.plane_slider.title = f'Slice Plane (1/{view.resolution} um)'
            self.plane_slider.end = view.n_plane
        except AttributeError:
            pass

        try:
            self.rotate_hor_slider.step = view.resolution
        except AttributeError:
            pass

        try:
            self.rotate_ver_slider.step = view.resolution
        except AttributeError:
            pass

        if (p := self._brain_slice) is not None:
            self._brain_slice = None  # avoid self.plane_slider.value invoke updating methods
            p = view.plane_at(p.coor_on())

            try:
                self.plane_slider.value = p.plane
            except AttributeError:
                pass
        else:
            self._brain_slice = None  # avoid self.plane_slider.value invoke updating methods
            p = view.plane_at(view.n_plane // 2)

        self.update_brain_slice(p, update_image=update_image)
        self.update_boundary_transform()

    def update_brain_slice(self, plane: int | SlicePlane | None, *,
                           update_image=True):
        if is_recursive_called():
            return

        if isinstance(plane, int):
            plane = self.brain_view.plane(plane)

        self._brain_slice = plane

        try:
            self.plane_slider.value = plane.plane
        except AttributeError:
            pass
        try:
            self.rotate_hor_slider.value = plane.dw * plane.resolution
        except AttributeError:
            pass
        try:
            self.rotate_ver_slider.value = plane.dh * plane.resolution
        except AttributeError:
            pass

        if update_image:
            if plane is None:
                self.update_image(None)
            else:
                self.update_image(plane.image)

    def _update_boundary_transform(self, state: BoundaryState):
        super()._update_boundary_transform(state)
        if (plane := self._brain_slice) is not None:
            self.update_image(plane.image)

    def update_image(self, image_data: NDArray[np.uint] | None):
        if image_data is None:
            self.render_boundary.visible = False
            self.data_brain.data = dict(image=[], dw=[], dh=[], x=[], y=[])
        else:
            self.render_boundary.visible = self.render_brain.visible
            self.data_brain.data = self.transform_image_data(np.flipud(image_data))
