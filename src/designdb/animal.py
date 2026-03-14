"""Main animal class for HIPPO"""

from pathlib import Path

import mrich

from .django_setup import configure_django

# can't import modules, because forces loading models before they're ready


class HIPPO:
    """The :class:`.HIPPO` `animal` class. Instantiating a :class:`.HIPPO` object will create or link a :class:`.HIPPO` :class:`.Database`.

    ::

            from hippo import HIPPO
            animal = HIPPO(project_name, db_path)

    .. attention::

            In addition to this API reference please see the tutorial pages :doc:`getting_started` and :doc:`insert_elaborations`.

    :param project_name: give this :class:`.HIPPO` a name
    :param db_path: path where the :class:`.Database` will be stored
    :param copy_from: optionally initialise this animal by copying the :class:`.Database` at this given path, defaults to None
    :returns: :class:`.HIPPO` object
    """

    def __init__(
        self,
        name: str,
        db: str | Path | dict,
        copy_from: str | Path | None = None,
        overwrite_existing: bool = False,
        update_legacy: bool = False,
    ) -> None:
        """HIPPO initialisation"""

        mrich.bold('Creating HIPPO animal')

        self._name = name

        mrich.var('name', name, color='arg')

        if isinstance(db, dict):
            ### POSTGRES
            pass
            # from .postgres import PostgresDatabase

            # self._db = PostgresDatabase(animal=self, **db)
            # configure_django(db, manage_models=False)

        else:
            ### INITIALISE SQLITE DATABASE

            # from .db import Database

            db_path = Path(db)

            mrich.var('db_path', db_path, color='file')

            # if copy_from:
            #     self._db = Database.copy_from(
            #         source=copy_from,
            #         destination=db_path,
            #         animal=self,
            #         update_legacy=update_legacy,
            #         overwrite_existing=overwrite_existing,
            #     )
            # else:
            #     self._db = Database(db_path, animal=self, update_legacy=update_legacy)

            configure_django(db_path, manage_models=True)

            from django.apps import apps
            from django.db import connection

            with connection.schema_editor() as schema_editor:
                for model in apps.get_models():
                    if model._meta.managed:
                        schema_editor.create_model(model)

        # self._compounds = CompoundTable(self.db)
        # self._poses = PoseTable(self.db)
        # self._tags = TagTable(self.db)
        # self._reactions = ReactionTable(self.db)

        # ### in memory subsets
        # self._reactants = None
        # self._products = None
        # self._intermediates = None
        # self._scaffolds = None
        # self._elabs = None

        mrich.success('Initialised animal', f'[var_name]{self}')
