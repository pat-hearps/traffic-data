from pathlib import Path
from typing import Any


class DotPath(Path):
    """To enable adding Paths as nested attributes of other Paths."""
    pass


# base DIR Path is (Dot)Path of the repository root directory
DIR: Any = DotPath(__file__).parent.parent.resolve()
"""
DIR DotPath allows object-based access to all project directories with a single import.
The use of make_dirs(DIR) anytime the file is accessed ensures no errors from trying to access
folders that do not exist when code is run on containers/virtual machines.

Usage:

from common.directory import DIR

df = pd.read_csv(DIR.DATA.RAW / "raw_filename.csv"
"""

DIR.DATA = DIR / "data"
DIR.DATA.LOGS = DIR.DATA / "logs"
DIR.DATA.TEMP = DIR.DATA / "temp"


def make_dirs(indir: DotPath) -> None:
    """Recursively make all project directories of initial DotPath object fed in
    by looping through class attributes that are also custom added DotPath objects.

    :param indir: a DotPath object with child DotPath attributes already attached."""

    custom_child_attributes = (attr_name for attr_name in dir(indir) if "_" not in attr_name)
    for attr_name in custom_child_attributes:
        attribute = getattr(indir, attr_name)
        if isinstance(attribute, DotPath) and attr_name != "parent":
            attribute.mkdir(exist_ok=True, parents=False)
            # recursive call to traverse down the attribute tree if exists
            make_dirs(attribute)


# run any time DIR is imported, even when __name__ != "__main__" to avoid any folder issues
try:
    make_dirs(DIR)
except OSError:
    print(
        "OSError encountered on DIR path creation - likely running on a read-only file system. Skipping dir creation."
    )
