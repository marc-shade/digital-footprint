import pytest
from pathlib import Path
from digital_footprint.db import Database
from digital_footprint.config import Config


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    config = Config(db_path=db_path, brokers_dir=Path(__file__).parent.parent / "digital_footprint" / "brokers")
    db = Database(config)
    db.initialize()
    yield db
    db.close()
