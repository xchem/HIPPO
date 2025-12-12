"""PostgreSQL database wrapper class using psycopg3"""

import mcol
import mrich

import psycopg
from pathlib import Path

from .db import Database
from .tools import strip_sql


class PostgresDatabase(Database):
    """Wrapper to connect to a HIPPO Postgres database.

    .. attention::

            :class:`.PostGresDatabase` objects should not be created directly. Instead use the methods in :class:`.HIPPO` to interact with data in the database. See :doc:`getting_started` and :doc:`insert_elaborations`.

    """

    TABLES = [
        "subsite",
        "subsite_tag",
        "scaffold",
        "compound",
        "pose",
        "inspiration",
        "reaction",
        "reactant",
        "tag",
        "quote",
        "route",
        "component",
        "feature",
        "interaction",
        "target",
    ]

    SQL_STRING_PLACEHOLDER = "%s"
    SQL_PK_DATATYPE = "SERIAL"
    SQL_SCHEMA = "hippo"
    SQL_SCHEMA_PREFIX = f"{SQL_SCHEMA}."

    ERROR_UNIQUE_VIOLATION = psycopg.errors.UniqueViolation

    SQL_CREATE_TABLE_COMPOUND = """CREATE TABLE hippo.compound(
        compound_id SERIAL PRIMARY KEY,
        compound_inchikey TEXT,
        compound_alias TEXT,
        compound_smiles TEXT,
        compound_base INTEGER,
        compound_mol hippo.MOL,
        compound_pattern_bfp bit(2048),
        compound_morgan_bfp bit(2048),
        compound_metadata TEXT,
        FOREIGN KEY (compound_base) REFERENCES hippo.compound(compound_id),
        CONSTRAINT UC_compound_inchikey UNIQUE (compound_inchikey),
        CONSTRAINT UC_compound_alias UNIQUE (compound_alias),
        CONSTRAINT UC_compound_smiles UNIQUE (compound_smiles)
    );
    """

    SQL_CREATE_TABLE_POSE = """CREATE TABLE hippo.pose(
        pose_id SERIAL PRIMARY KEY,
        pose_inchikey TEXT,
        pose_alias TEXT,
        pose_smiles TEXT,
        pose_reference INTEGER,
        pose_path TEXT,
        pose_compound INTEGER,
        pose_target INTEGER,
        pose_mol hippo.MOL,
        pose_fingerprint INTEGER,
        pose_energy_score REAL,
        pose_distance_score REAL,
        pose_inspiration_score REAL,
        pose_metadata TEXT,
        FOREIGN KEY (pose_compound) REFERENCES hippo.compound(compound_id),
        CONSTRAINT UC_pose_alias UNIQUE (pose_alias),
        CONSTRAINT UC_pose_path UNIQUE (pose_path)
    );
    """

    SQL_INSERT_COMPOUND = """
    INSERT INTO hippo.compound(
        compound_inchikey, 
        compound_smiles, 
        compound_mol, 
        compound_alias
    )
    VALUES(
        %(inchikey)s, 
        %(smiles)s, 
        hippo.mol_from_smiles(%(smiles)s), 
        %(alias)s
    )
    RETURNING compound_id;
    """

    SQL_BULK_INSERT_INTERACTIONS = """
    INSERT INTO hippo.interaction(
        interaction_feature, 
        interaction_pose, 
        interaction_type, 
        interaction_family, 
        interaction_atom_ids, 
        interaction_prot_coord, 
        interaction_lig_coord, 
        interaction_distance, 
        interaction_angle, 
        interaction_energy
    )
    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT ON CONSTRAINT UC_interaction DO NOTHING
    """

    POSE_FIELDS = [
        "pose_id",
        "pose_inchikey",
        "pose_alias",
        "pose_smiles",
        "pose_reference",
        "pose_path",
        "pose_compound",
        "pose_target",
        "hippo.mol_to_pkl(pose_mol)",
        "pose_fingerprint",
        "pose_energy_score",
        "pose_distance_score",
        "pose_inspiration_score",
    ]

    COMPOUND_PROPERTY_FUNCTIONS = {
        "num_heavy_atoms": "hippo.mol_numheavyatoms",
        "formula": ("hippo.mol_formula", ", false, false"),
        "num_rings": "hippo.mol_numrings",
        "molecular_weight": "hippo.mol_amw",
    }

    def __init__(
        self,
        animal: "HIPPO",
        username: str,
        password: str,
        host: str = "localhost",
        port: int = 5432,
        dbname: str = "hippo",
        update_legacy: bool = False,
        auto_compute_bfps: bool = False,
        create_blank: bool = True,
        check_legacy: bool = False,
        create_indexes: bool = True,
        update_indexes: bool = False,
        debug: bool = True,
    ) -> None:
        """PostgresDatabase initialisation"""

        assert isinstance(username, str)
        assert isinstance(password, str)
        assert isinstance(port, int)

        if debug:
            mrich.debug("hippo.PostgresDatabase.__init__()")

        self._username = username
        self._password = password
        self._port = port
        self._host = host

        self._connection = None
        self._cursor = None
        self._animal = animal
        self._auto_compute_bfps = auto_compute_bfps
        self._engine = "psycopg"
        self._dbname = dbname

        if debug:
            mrich.debug(f"PostgresDatabase.username = {self.username}")
            mrich.debug(f"PostgresDatabase.password = {self.password}")
            mrich.debug(f"PostgresDatabase.host = {self.host}")
            mrich.debug(f"PostgresDatabase.port = {self.port}")

        self.connect()

        if not self.table_names:

            if create_blank:
                self.create_schema()
                self.create_blank_db()
            else:
                mrich.error("Database is empty!", self.path)
                raise ValueError(
                    "Database is empty! Check connection or run with create_blank=True"
                )

        if check_legacy:
            self.check_schema(update=update_legacy)

        if create_indexes:
            self.create_indexes(update=update_indexes, debug=debug)

    ### PROPERTIES

    @property
    def path(self) -> None:
        """PostgresDatabase path"""
        # raise NotImplementedError("PostgresDatabase has no path")
        return f"postgresql://{self.username}@{self.host}:{self.port}"

    @property
    def username(self) -> str:
        """PostgresDatabase username"""
        return self._username

    @property
    def dbname(self) -> str:
        """PostgresDatabase dbname"""
        return self._dbname

    @property
    def password(self) -> str:
        """PostgresDatabase password"""
        return self._password

    @property
    def host(self) -> str:
        """PostgresDatabase host"""
        return self._host

    @property
    def port(self) -> int:
        """PostgresDatabase port"""
        return self._port

    @property
    def table_names(self) -> list[str]:
        """List of all the table names in the database"""
        results = self.execute(
            f"""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = '{self.SQL_SCHEMA}'
            AND table_type = 'BASE TABLE';
        """
        ).fetchall()
        return [n for n, in results]

    def index_names(self) -> list[str]:
        """Get the index names"""

        cursor = self.execute(
            f"""
        SELECT indexname
        FROM pg_indexes
        WHERE schemaname = '{self.SQL_SCHEMA}';
        """
        )

        return [n for n, in cursor]

    @property
    def total_changes(self) -> int:
        """Return the current transaction ID as a proxy of sqlite's total_changes."""
        cursor = self.execute("SELECT txid_current()")
        return cursor.fetchone()[0]

    ### GENERAL SQL

    def connect(self, debug: bool = True) -> None:
        """Connect to the database"""

        if debug:
            mrich.debug("hippo.PostgresDatabase.connect()")

        conn = None

        try:
            conn = psycopg.connect(
                user=self.username,
                host=self.host,
                password=self.password,
                port=self.port,
                dbname=self.dbname,
            )

            with conn.cursor() as c:
                c.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM pg_type t
                        JOIN pg_namespace n ON n.oid = t.typnamespace
                        WHERE t.typname = 'mol'
                    );
                """
                )
                (exists,) = c.fetchone()

            if not exists:
                raise ValueError(
                    "'mol' datatype not defined, is the rdkit postgres cartridge installed correctly?"
                )

            conn.execute("SET client_encoding TO 'UTF8'")

        except Exception as e:
            mrich.error("Could not connect to", self.path)
            mrich.error(e)
            raise

        self._connection = conn
        self._cursor = conn.cursor()

    def execute(
        self,
        sql,
        payload=None,
        *,
        debug: bool = False,
        time: bool = False,
    ):
        """Execute arbitrary SQL with retry if database is locked."""
        if debug:
            mrich.debug(sql)

        if time:
            import re
            from time import perf_counter

            start = perf_counter()

        try:
            if payload:
                records = self.cursor.execute(sql, payload)
            else:
                records = self.cursor.execute(sql)
        except Exception as e:
            # mrich.error(e)
            # mrich.print(strip_sql(sql))
            self.rollback()
            raise

        if time:
            mrich.debug(f"{perf_counter()-start:.2}s: ", strip_sql(sql))

        return records

    def executemany(
        self,
        sql,
        payload=None,
        *,
        debug: bool = False,
        time: bool = False,
        batch_size: int = None,
    ):
        """Execute arbitrary SQL with retry if database is locked."""

        returning = "RETURNING" in sql

        if debug:
            from .tools import strip_sql

            mrich.debug(strip_sql(sql))
            mrich.debug("len(payload):", len(payload))
            mrich.debug(f"{returning=}")

        if time:
            import re
            from time import perf_counter

            start = perf_counter()

        if batch_size and batch_size < len(payload):

            from itertools import batched, chain

            batches = list(batched(payload, batch_size))

            n = len(batches)

            results = []
            for i, batch in enumerate(mrich.track(batches, prefix="batch execution")):
                mrich.set_progress_field("i", i)
                mrich.set_progress_field("n", n)

                self.cursor.executemany(sql, batch, returning=returning)

                if returning:
                    result = [self.cursor.fetchone() for _ in self.cursor.results()]

                    if result:
                        results.append(result)

            else:
                mrich.set_progress_field("i", n)

            if results:
                records = list(chain.from_iterable(results))
            else:
                records = None

        else:

            self.cursor.executemany(sql, payload, returning=returning)

            if returning:
                records = [self.cursor.fetchone() for _ in self.cursor.results()]
            else:
                records = None

        if time:
            sql = re.sub(r"\s+", " ", sql).strip()
            mrich.debug(f"{perf_counter()-start:.2}s: ", sql)

        return records

    def rollback(self) -> None:
        """rollback (not relevant for sqlite)"""
        self.connection.rollback()
        self.connection.execute("SET client_encoding TO 'UTF8'")

    def sql_return_id_str(self, key: str) -> str:
        """Add this to SQL queries to return the entry primary key"""
        return f"RETURNING {key}_id"

    def get_lastrowid(self) -> int:
        """Get ID of last inserted row"""
        return self.cursor.fetchone()[0]

    def column_names(self, table: str) -> list[str]:
        """Get the column names of the given table"""

        sql = f"""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'hippo'
        AND table_name = '{table}'
        ORDER BY ordinal_position;
        """

        return [n for n, in self.execute(sql).fetchall()]

    ### CREATE TABLES

    def create_schema(self) -> None:
        """Create postgres schema if it does not exist"""

        sql = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.schemata
            WHERE schema_name = %s
        );
        """

        c = self.execute(sql, (self.SQL_SCHEMA,))

        exists = c.fetchone()[0]

        if exists:
            return None

        self.execute("CREATE SCHEMA IF NOT EXISTS hippo;")
        self.commit()

    def create_table_pattern_bfp(self) -> None:
        """Create the pattern_bfp table"""
        mrich.warning(
            "HIPPO.PostgresDatabase.create_table_pattern_bfp(): NotImplemented"
        )

        return

        mrich.debug("HIPPO.PostgresDatabase.create_table_pattern_bfp()")

        sql = """
        CREATE VIRTUAL TABLE compound_pattern_bfp 
        USING rdtree(compound_id, fp bits(2048))
        """

        self.execute(sql)

    ### GETTERS

    def get_compound_mol(
        self,
        compound_id: int,
    ) -> "Chem.Mol":
        """Get the rdkit.Chem.Mol for a given :class:`.Compound`"""

        from rdkit.Chem import Mol

        (bytestr,) = self.select_where(
            query="hippo.mol_to_pkl(compound_mol)",
            table="compound",
            key="id",
            value=compound_id,
        )

        return Mol(bytestr)

    ### SINGLE UPDATES

    def update_pose_mol(self, pose_id: int, mol: "Chem.Mol") -> None:
        """Update the molecule stored for a specific pose"""

        from rdkit.Chem import MolToMolBlock

        sql = f"""
        UPDATE hippo.pose
        SET pose_mol = hippo.mol_from_pkl(%s)
        WHERE pose_id = %s;
        """

        self.execute(sql, (mol.ToBinary(), pose_id))
        self.commit()

    ### BULK CALCULATIONS

    def calculate_all_scaffolds(self) -> None:
        raise NotImplementedError

    def calculate_all_murcko_scaffolds(self) -> None:
        raise NotImplementedError

    ### MIGRATIONS

    def migrate_sqlite(
        self,
        source: str | Path,
        *,
        reactions: bool = True,
        scaffolds: bool = True,
        features: bool = True,
        interactions: bool = True,
        subsites: bool = True,
        quotes: bool = True,
        batch_size: int = 5_000,
        tag_compound_id_regex: list[tuple[str, str]] | None = None,
        # pose_path_compound_id_regex: list[tuple[str, str]] | None = None,
        # pose_path_pose_id_regex: list[tuple[str, str]] | None = None,
        # overwrite_quotes: bool = True,
    ) -> None:
        """Migrate records from a SQLite :class:`.Database` to this :class:`.PostgresDatabase`

        :param source: path to source sqlite database
        :param batch_size: SQL insertion batch size
        :param tag_compound_id_regex: Provide regex to identify compound ID's to replace in tag names, defaults to `[(r"^C([0-9]+)", "C{new_compound_id}")]`

        The default tag_compound_id_regex means that tags such as "C123 85 percent analogues" are replaced with "C234 85 percent analogues",
        where 123 is the compound ID in the source database, and 234 in the destination.

        """

        from datetime import datetime

        from .animal import HIPPO
        from .migration import (
            migrate_compounds,
            migrate_scaffolds,
            migrate_targets,
            migrate_poses,
            migrate_pose_references,
            migrate_inspirations,
            migrate_tags,
            migrate_reactions_and_reactants,
            migrate_features,
            migrate_interactions,
            migrate_subsites,
            migrate_quotes,
            dump_xlsx,
            dump_json,
        )

        mrich.var("source", source)
        mrich.var("batch_size", batch_size)

        source_path = Path(source).resolve()
        assert source_path.exists()

        json_file_name = f"{source_path.name.removesuffix('.sqlite')}_migration.json"
        xlsx_file_name = f"{source_path.name.removesuffix('.sqlite')}_migration.xlsx"
        mrich.var("json_file_name", json_file_name)
        mrich.var("xlsx_file_name", xlsx_file_name)

        if not tag_compound_id_regex:
            tag_compound_id_regex = [
                (r"^C([0-9]+).*$", "C{new_compound_id}"),
            ]
        mrich.var("tag_compound_id_regex", tag_compound_id_regex)

        ### THIS DEV WAS NOT COMPLETED

        # if not pose_path_compound_id_regex:
        #     pose_path_compound_id_regex = [
        #         (r"\/.*\/C([0-9]+)-P[0-9]+\.fake\.mol$", "C{new_compound_id}"),
        #     ]
        # mrich.var("pose_path_compound_id_regex", pose_path_compound_id_regex)

        # if not pose_path_pose_id_regex:
        #     pose_path_pose_id_regex = [
        #         (r"\/.*\/C[0-9]+-P([0-9]+)\.fake\.mol$", "P{new_pose_id}"),
        #         (r"\/.*\/[A-Z]{14}-[A-Z]{10}-[A-Z]-P([0-9]+)-P[0-9]+-P[0-9]+-[0-9]{6}.fake.mol$", "P{new_pose_id}"),
        #         (r"\/.*\/[A-Z]{14}-[A-Z]{10}-[A-Z]-P[0-9]+-P([0-9]+)-P[0-9]+-[0-9]{6}.fake.mol$", "P{new_pose_id}"),
        #         (r"\/.*\/[A-Z]{14}-[A-Z]{10}-[A-Z]-P[0-9]+-P[0-9]+-P([0-9]+)-[0-9]{6}.fake.mol$", "P{new_pose_id}"),
        #     ]
        # mrich.var("pose_path_pose_id_regex", pose_path_pose_id_regex)

        source = HIPPO("source", source_path)

        ### helper functions

        try:

            migration_data = {
                "source": str(source_path.resolve()),
                "destination": self.path,
                "time": str(datetime.now()),
                "tag_compound_id_regex": tag_compound_id_regex,
                # "pose_path_compound_id_regex": pose_path_compound_id_regex,
                # "pose_path_pose_id_regex": pose_path_pose_id_regex,
            }

            ### compounds

            migration_data = migrate_compounds(
                source=source.db,
                destination=self,
                migration_data=migration_data,
                batch_size=batch_size,
                # execute=False,
            )

            ### scaffolds

            if scaffolds:

                migration_data = migrate_scaffolds(
                    source=source.db,
                    destination=self,
                    migration_data=migration_data,
                    batch_size=batch_size,
                    # execute=False,
                )

            ### targets

            migration_data = migrate_targets(
                source=source.db,
                destination=self,
                migration_data=migration_data,
                batch_size=batch_size,
                # execute=False,
            )

            ### poses

            migration_data = migrate_poses(
                source=source.db,
                destination=self,
                migration_data=migration_data,
                batch_size=batch_size,
                # execute=False,
            )

            ### pose references

            migration_data = migrate_pose_references(
                source=source.db,
                destination=self,
                migration_data=migration_data,
                batch_size=batch_size,
                # execute=False,
            )

            ### inspirations

            migration_data = migrate_inspirations(
                source=source.db,
                destination=self,
                migration_data=migration_data,
                batch_size=batch_size,
                # execute=False,
            )

            ### tags

            migration_data = migrate_tags(
                source=source.db,
                destination=self,
                migration_data=migration_data,
                batch_size=batch_size,
                # execute=False,
            )

            ### reactions & reactants

            if reactions:

                migration_data = migrate_reactions_and_reactants(
                    source=source.db,
                    destination=self,
                    migration_data=migration_data,
                    batch_size=batch_size,
                )

            ### features

            if features or interactions:

                migration_data = migrate_features(
                    source=source.db,
                    destination=self,
                    migration_data=migration_data,
                    batch_size=batch_size,
                    # execute=False,
                )

            ### interactions

            if interactions:

                migration_data = migrate_interactions(
                    source=source.db,
                    destination=self,
                    migration_data=migration_data,
                    batch_size=batch_size,
                    # execute=False,
                )

            ### subsites

            if subsites:

                migration_data = migrate_subsites(
                    source=source.db,
                    destination=self,
                    migration_data=migration_data,
                    batch_size=batch_size,
                    # execute=False,
                )

            ### quotes

            if quotes:

                migration_data = migrate_quotes(
                    source=source.db,
                    destination=self,
                    migration_data=migration_data,
                    batch_size=batch_size,
                    # execute=False,
                )

        except Exception as e:
            self.rollback()

            mrich.error(e)

            json_file_name = (
                f"{source.db.path.name.removesuffix('.sqlite')}_migration_partial.json"
            )
            xlsx_file_name = (
                f"{source.db.path.name.removesuffix('.sqlite')}_migration_partial.xlsx"
            )

            dump_json(migration_data, json_file_name)
            dump_xlsx(migration_data, xlsx_file_name)

            raise

        dump_json(migration_data, json_file_name)
        dump_xlsx(migration_data, xlsx_file_name)

        mrich.success(
            "Migration staged. Please review and db.commit() or db.rollback() the changes"
        )

    ### MAINTENANCE

    def _drop_schema(self) -> None:
        """Empty the Database schema entirely and recreate it"""

        self.execute(f"DROP SCHEMA IF EXISTS {self.SQL_SCHEMA} CASCADE;")
        self.commit()

    def _drop_tables(self) -> None:
        """Delete all HIPPO tables and restart sequences"""

        for table in self.TABLES:
            self.execute(f"DROP TABLE IF EXISTS {self.SQL_SCHEMA}.{table} CASCADE;")

        # sql = f"""
        # DO $$
        # DECLARE
        #     seq RECORD;
        # BEGIN
        #     FOR seq IN
        #         SELECT sequence_schema, sequence_name
        #         FROM information_schema.sequences
        #         WHERE sequence_schema = '{self.SQL_SCHEMA}'
        #     LOOP
        #         EXECUTE format(
        #             'ALTER SEQUENCE %I.%I RESTART WITH 1;',
        #             seq.sequence_schema,
        #             seq.sequence_name
        #         );
        #     END LOOP;
        # END $$;
        # """

        # self.execute(sql)

        self.commit()

    ### DUNDERS

    def __str__(self):
        """Unformatted string representation"""
        return f"Database @ {self.path}"
