import constants
import databases
import ormar
import sqlalchemy

database = databases.Database(constants.DBConfig.URL)
metadata = sqlalchemy.MetaData()


class BaseMeta(ormar.ModelMeta):
    metadata = metadata
    database = database
