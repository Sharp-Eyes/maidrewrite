import databases
import ormar
import sqlalchemy

from .. import constants

database = databases.Database(constants.DBConfig.URL)
metadata = sqlalchemy.MetaData()


class BaseMeta(ormar.ModelMeta):
    metadata = metadata
    database = database
