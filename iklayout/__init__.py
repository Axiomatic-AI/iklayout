from importlib.metadata import version, PackageNotFoundError
from os import PathLike
from .iklayout import IKlayout

try:
    __version__ = version("iklayout")
except PackageNotFoundError:
    __version__ = "unknown"


def show(c: PathLike):
    return IKlayout(c).show()
