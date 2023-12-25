import abc
import math
from typing import Literal, TypeVar, Final, overload, NamedTuple, get_args

import numpy as np
from numpy.typing import NDArray

from chmap.util.atlas_brain import BrainGlobeAtlas
from chmap.util.utils import all_int, align_arr

__all__ = ['SLICE', 'SliceView', 'SlicePlane']

SLICE = Literal['coronal', 'sagittal', 'transverse']
T = TypeVar('T')

XY = tuple[int, int]
PXY = tuple[int, int, int]  # (plane, x, y)
COOR = tuple[int, int, int]  # (ap, dv, ml)


class SliceView(metaclass=abc.ABCMeta):
    """Atlas brain slice view. Here provide three kinds of view ('coronal', 'sagittal', 'transverse').
    """

    name: Final[SLICE]
    """view"""

    resolution: Final[int]
    """um/pixel"""

    reference: Final[NDArray[np.uint]]
    """reference brain volume with shape (AP, DV, ML)"""

    grid_x: Final[NDArray[np.int_]]
    grid_y: Final[NDArray[np.int_]]

    def __new__(cls, brain: BrainGlobeAtlas, name: SLICE, reference: NDArray[np.uint] = None):
        if name == 'coronal':
            return object.__new__(CoronalView)
        elif name == 'sagittal':
            return object.__new__(SagittalView)
        elif name == 'transverse':
            return object.__new__(TransverseView)
        else:
            raise ValueError()

    def __init__(self, brain: BrainGlobeAtlas, name: SLICE, reference: NDArray[np.uint] = None):
        """

        :param name: view
        :param reference: reference brain volume with shape (AP, DL, ML)
        :param resolution: um/pixel
        """
        if reference is not None:
            if reference.shape != brain.reference.shape:
                raise RuntimeError()
        else:
            reference = brain.reference

        self.name = name
        self.reference = reference
        self.resolution = int(brain.resolution[get_args(SLICE).index(name)])
        self.grid_y, self.grid_x = np.mgrid[0:self.height, 0:self.width]

    def __str__(self):
        return f'SliceView[{self.name}]'

    __repr__ = __str__

    @property
    def n_ap(self) -> int:
        """Number of slices in AP axis"""
        return self.reference.shape[0]

    @property
    def n_dv(self) -> int:
        """Number of slices in DV axis"""
        return self.reference.shape[1]

    @property
    def n_ml(self) -> int:
        """Number of slices in ML axis"""
        return self.reference.shape[2]

    @property
    @abc.abstractmethod
    def n_plane(self) -> int:
        """Number of plane (pixel) in this view"""
        pass

    @property
    @abc.abstractmethod
    def width(self) -> int:
        """width (pixel) in this view"""
        pass

    @property
    @abc.abstractmethod
    def height(self) -> int:
        """height (pixel) in this view"""
        pass

    @property
    def width_um(self) -> float:
        """width (um) in this view"""
        return self.width * self.resolution

    @property
    def height_um(self) -> float:
        """height (um) in this view"""
        return self.height * self.resolution

    @property
    @abc.abstractmethod
    def project_index(self) -> tuple[int, int, int]:
        """index order of (ap, dv, ml).

        :return: (p, x, y)
        """
        pass

    def plane(self, o: int | tuple[int, int, int] | NDArray[np.int_], image: NDArray[np.uint] = None) -> NDArray[np.uint]:
        """Get brain image on plane *o*.

        :param o: plane, tuple (plane, dh, dv) or Array[plane:int, H, W]
        :param image: brain volume with shape (AP, DL, ML)
        :return: brain slice image with shape (height, width)
        """
        match o:
            case o if all_int(o):
                o = np.full_like((self.height, self.width), o)
            case (plane, dh, dv) if all_int(plane, dh, dv):
                o = plane + self.offset(dh, dv)
            case _ if isinstance(o, np.ndarray):
                if o.shape != (self.height, self.width):
                    raise RuntimeError(f'shape mismatch : {o.shape} != {(self.height, self.width)}')
            case _:
                raise TypeError(repr(o))

        if image is not None:
            if image.shape != self.reference.shape:
                raise RuntimeError('shape of brain volume mismatch')
        else:
            image = self.reference

        o = np.clip(o, 0, self.n_plane - 1)
        return image[self.coor_on(o, (self.grid_x, self.grid_y))]

    @overload
    def coor_on(self, plane: int, o: XY) -> COOR:
        pass

    @overload
    def coor_on(self, plane: int | NDArray[np.int_], o: tuple[NDArray[np.int_], NDArray[np.int_]]) -> tuple[NDArray[np.int_], NDArray[np.int_], NDArray[np.int_]]:
        pass

    @overload
    def coor_on(self, plane: int | NDArray[np.int_], o: NDArray[np.int_]) -> NDArray[np.int_]:
        pass

    def coor_on(self, plane, o):
        """map slice point (x, y) at plane *plane* back to volume point (ap, dv, ml).

        :param plane: plane number of array
        :param o: tuple of (x, y) or Array[int, N, (x, y)]
        :return: (ap, dv, ml) or Array[int, N, (ap, dv, ml)]
        """
        pidx, xidx, yidx = self.project_index
        match o:
            case (x, y) if all_int(plane, x, y):
                ret = [0, 0, 0]
                ret[pidx] = plane
                ret[xidx] = x
                ret[yidx] = y
                return tuple(ret)
            case (x, y):
                plane, x, y = align_arr(plane, x, y)
                ret = [0, 0, 0]
                ret[pidx] = plane
                ret[xidx] = x
                ret[yidx] = y
                return tuple(ret)
            case _ if isinstance(o, np.ndarray):
                ret = np.zeros((len(o), 3), dtype=int)
                ret[:, pidx] = plane
                ret[:, xidx] = o[:, 0]
                ret[:, yidx] = o[:, 1]
                return ret
            case _:
                raise TypeError()

    @overload
    def project(self, t: COOR) -> PXY:
        pass

    @overload
    def project(self, t: NDArray[np.int_]) -> NDArray[np.int_]:
        pass

    def project(self, t):
        """project volume point (ap, dv, ml) onto slice point (plane, x, y)

        :param t:  (ap, dv, ml) or Array[int, [N,], (ap, dv, ml)].
        :return: (plane, x, y) or Array[int, [N,], (plane, x, y)]
        """
        p, x, y = self.project_index
        match t:
            case (ap, dv, ml) if all_int(ap, dv, ml):
                return int(t[p]), int(t[x]), int(t[y])
            case _ if isinstance(t, np.ndarray):
                match t.ndim:
                    case 1:
                        return t[((p, x, y),)]
                    case 2:
                        return t[:, (p, x, y)]
                    case _:
                        raise ValueError(f'wrong dimension : {t.ndim}')
            case _:
                raise TypeError(repr(t))

    def offset(self, h: int, v: int) -> NDArray[np.int_]:
        """plane index offset according to horizontal difference *h* and vertical difference *v*.

        :param h: horizontal plane diff to the center. right side positive.
        :param v: vertical plane diff to the center. bottom side positive.
        :return: Array[int, H, W] array
        """
        x_frame = np.round(np.linspace(-h, h, self.width)).astype(int)
        y_frame = np.round(np.linspace(-v, v, self.height)).astype(int)
        return np.add.outer(y_frame, x_frame)

    def angle_offset(self, a: tuple[float, float, float]) -> tuple[int, int]:
        """plane index offset according to angle difference *a*.

        :param a: radian rotation of (ap, dv, ml)-axis.
        :return: tuple of (dw, dh)
        """
        raise RuntimeError()

    def plane_at(self, c: int | COOR | NDArray[np.int_], um=False) -> 'SlicePlane':
        """

        :param c: plane index (int) or volume point (ap, dv, ml)
        :param um: does the unit of the values used in *c* are um?
        :return: correspond slice view.
        """
        match c:
            case c if all_int(c):
                if um:
                    c = int(c / self.resolution)
                plane = int(c)
                coor = int(self.width // 2), int(self.height // 2)
            case (ap, dv, ml):
                c = np.array(c)
                if um:
                    c = np.round(c / self.resolution).astype(int)
                plane, *coor = self.project(tuple(c))
            case _ if isinstance(c, np.ndarray):
                if um:
                    c = np.round(c / self.resolution).astype(int)
                plane, *coor = self.project(tuple(c))
            case _:
                raise TypeError()

        return SlicePlane(plane, coor[0], coor[1], 0, 0, self)


class CoronalView(SliceView):

    @property
    def n_plane(self) -> int:
        return self.n_ap

    @property
    def width(self) -> int:
        return self.n_ml

    @property
    def height(self) -> int:
        return self.n_dv

    @property
    def project_index(self) -> tuple[int, int, int]:
        return 0, 2, 1  # p=AP, x=ML, y=DV

    def angle_offset(self, a: tuple[float, float, float]) -> tuple[int, int]:
        ry = a[1]
        rz = a[2]
        dw = int(-self.width * math.tan(ry) / 2)  # ml
        dh = int(self.height * math.tan(rz) / 2)  # dv
        return dw, dh


class SagittalView(SliceView):
    @property
    def n_plane(self) -> int:
        return self.n_ml

    @property
    def width(self) -> int:
        return self.n_ap

    @property
    def height(self) -> int:
        return self.n_dv

    @property
    def project_index(self) -> tuple[int, int, int]:
        return 2, 0, 1  # p=ML, x=AP, y=DV

    def angle_offset(self, a: tuple[float, float, float]) -> tuple[int, int]:
        rx = a[0]
        ry = a[1]
        dw = int(-self.width * math.tan(ry) / 2)  # ap
        dh = int(self.height * math.tan(rx) / 2)  # dv
        return dw, dh


class TransverseView(SliceView):
    @property
    def n_plane(self) -> int:
        return self.n_dv

    @property
    def width(self) -> int:
        return self.n_ml

    @property
    def height(self) -> int:
        return self.n_ap

    @property
    def project_index(self) -> tuple[int, int, int]:
        return 1, 2, 0  # p=DV, x=ML, y=AP

    def angle_offset(self, a: tuple[float, float, float]) -> tuple[int, int]:
        rx = a[0]
        ry = a[1]
        dw = int(-self.width * math.tan(ry) / 2)  # ml
        dh = int(self.height * math.tan(rx) / 2)  # ap
        return dw, dh


class SlicePlane(NamedTuple):
    """Just a wrapper of SliceView that keep the information of volume point (ap, dv, ml) and rotate (dw, dh)."""

    plane: int  # anchor frame
    ax: int  # anchor x
    ay: int  # anchor y
    dw: int
    dh: int
    slice: SliceView

    @property
    def slice_name(self) -> str:
        return self.slice.name

    @property
    def resolution(self) -> int:
        return self.slice.resolution

    @property
    def width(self) -> float:
        return self.slice.width_um

    @property
    def height(self) -> float:
        return self.slice.height_um

    @property
    def image(self) -> NDArray[np.uint]:
        return self.slice.plane(self.plane_offset)

    def image_of(self, image: NDArray[np.uint]) -> NDArray[np.uint]:
        return self.slice.plane(self.plane_offset, image)

    @property
    def plane_offset(self) -> NDArray[np.int_]:
        offset = self.slice.offset(self.dw, self.dh)
        return self.plane + offset - offset[self.ay, self.ax]

    @overload
    def plane_idx_at(self, x: int, y: int) -> int:
        pass

    @overload
    def plane_idx_at(self, x: NDArray[np.int_], y: NDArray[np.int_]) -> NDArray[np.int_]:
        pass

    def plane_idx_at(self, x, y):
        return self.plane_offset[y, x]

    @overload
    def coor_on(self, o: XY = None) -> COOR:
        pass

    @overload
    def coor_on(self, o: tuple[NDArray[np.int_], NDArray[np.int_]]) -> tuple[NDArray[np.int_], NDArray[np.int_], NDArray[np.int_]]:
        pass

    @overload
    def coor_on(self, o: NDArray[np.int_]) -> NDArray[np.int_]:
        pass

    def coor_on(self, o=None):
        """

        :param o: tuple (x,y) or Array[int, [N,], (x, y)] position
        :return:
        """
        if o is None:
            return self.slice.coor_on(self.plane_idx_at(self.ax, self.ay), (self.ax, self.ay))
        elif isinstance(o, tuple):
            return self.slice.coor_on(self.plane_idx_at(o[0], o[1]), o)
        else:
            return self.slice.coor_on(self.plane_idx_at(o[:, 0], o[:, 1]), o)

    def with_anchor(self, x: int, y: int) -> 'SlicePlane':
        plane = self.plane_idx_at(x, y)
        return self._replace(plane=plane, ax=x, ay=y)

    def with_offset(self, dw: int, dh: int) -> 'SlicePlane':
        return self._replace(dw=dw, dh=dh)

    def with_rotate(self, a: tuple[float, float]) -> 'SlicePlane':
        """plane index offset according to angle difference *a*.

        :param a: (vertical, horizontal)-axis radian rotation.
        :return: tuple of (dw, dh)
        """
        rx, ry = a
        dw = int(-self.width * math.tan(rx) / 2)
        dh = int(self.height * math.tan(ry) / 2)
        return self.with_offset(dw, dh)