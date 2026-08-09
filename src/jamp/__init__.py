from importlib.metadata import PackageNotFoundError, version


def get_version():
    """Return installed distribution version, or unknown in an uninstalled checkout."""
    try:
        return version("jam-build")
    except PackageNotFoundError:
        return "unknown"


__version__ = get_version()

# make this callable as script
from jamp.build import main_cli as main_cli
