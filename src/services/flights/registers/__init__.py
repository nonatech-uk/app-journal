"""Aircraft register lookup dispatcher."""

from .base import RegisterData
from . import uk_ginfo, ie_iaa, ch_bazl, us_faa, airframes_org


def lookup(
    registration: str,
    register_path: str | None = None,
    airframes_user: str = "",
    airframes_password: str = "",
) -> RegisterData | None:
    """Route to the correct country register based on registration prefix.

    Falls back to airframes.org for countries without a dedicated register module.
    """
    reg = registration.upper()
    if reg.startswith("G-"):
        return uk_ginfo.lookup(reg)
    elif reg.startswith("EI-"):
        kwargs = {}
        if register_path:
            kwargs["register_path"] = register_path
        return ie_iaa.lookup(reg, **kwargs)
    elif reg.startswith("HB-"):
        return ch_bazl.lookup(reg)
    elif reg.startswith("N") and len(reg) >= 2 and reg[1:2].isdigit():
        return us_faa.lookup(reg)
    elif airframes_user and airframes_password:
        return airframes_org.lookup(reg, username=airframes_user, password=airframes_password)
    return None
