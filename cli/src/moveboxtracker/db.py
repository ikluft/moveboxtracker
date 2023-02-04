"""
database (model layer) routines for moveboxtracker
"""

from pathlib import Path
from sqlalchemy import create_engine
from xdg import BaseDirectory

# globals
data_home = BaseDirectory.xdg_data_home

class DBMovingBox():
    """moving box database access"""

    def __init__(self, filename):
        filepath = Path(f"{data_home}/{filename}")
        self.engine = create_engine("sqlite+pysqlite://" + str(filepath))
        # TODO
