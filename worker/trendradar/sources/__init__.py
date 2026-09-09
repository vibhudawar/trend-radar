"""Select the DataSource by config.DATA_SOURCE (live ScrapeCreators vs cached fixture)."""
from ..config import DATA_SOURCE
from . import scrapecreators


def get_source():
    if DATA_SOURCE == "fixture":
        from . import fixture
        return fixture
    return scrapecreators
