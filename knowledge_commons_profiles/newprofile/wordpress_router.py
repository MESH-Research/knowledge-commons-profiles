"""
A router to control all database operations on models in the WordPress DB
"""


# pylint: disable=unused-argument
class ReadWriteRouter:
    """
    A router to control all database operations on models in the WordPress
    DB
    """

    db_name = "wordpress_dev"

    def db_for_read(self, model, **hints):
        """
        Controls which database should be used for read operations for a given
        model.
        """
        return (
            self.db_name
            if model.__name__.lower().startswith("wp")
            else "default"
        )

    def db_for_write(self, model, **hints):
        """
        Controls which database should be used for writes for a given model.
        """
        return None if model.__name__.lower().startswith("wp") else "default"

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Controls if a model should be allowed to migrate on the given database.

        The WordPress database is an external, read-only MySQL instance:
        nothing may migrate onto it. This also keeps system checks (which
        consult the router since Django 6.1 connects during MySQL field
        validation) from touching its connection.
        """
        if db == self.db_name:
            return False
        return not model_name.lower().startswith("wp") if model_name else True
