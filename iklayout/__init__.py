from .iklayout import IKlayout

from os import PathLike


def show(c: PathLike):
    return IKlayout(c).show()
