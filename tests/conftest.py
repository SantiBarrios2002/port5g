import warnings
import pytest
from port5g.config import load_config


@pytest.fixture(scope="session")
def cfg():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return load_config(warn=False)
