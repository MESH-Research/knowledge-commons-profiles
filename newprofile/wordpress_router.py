"""
A router to control all database operations on models in the WordPress DB
"""


class ReadWriteRouter:
    """
    A router to control all database operations on models in the WordPress
    DB
    """

    def db_for_read(self, model, **hints):
        """
        Controls which database should be used for read operations for a given
        model.
        """
        return (
            "wordpress_dev"
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
        """
        return db == "default"
