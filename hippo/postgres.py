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
        compound_mol MOL,
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
        pose_mol MOL,
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
        -- compound_pattern_bfp, 
        -- compound_morgan_bfp, 
        compound_alias
    )
    VALUES(
        %(inchikey)s, 
        %(smiles)s, 
        mol_from_smiles(%(smiles)s), 
        -- mol_pattern_bfp(mol_from_smiles(%(smiles)s), 2048), 
        -- mol_morgan_bfp(mol_from_smiles(%(smiles)s), 2, 2048), 
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
        "mol_to_pkl(pose_mol)",
        "pose_fingerprint",
        "pose_energy_score",
        "pose_distance_score",
        "pose_inspiration_score",
    ]

    COMPOUND_PROPERTY_FUNCTIONS = {
        "num_heavy_atoms": "mol_numheavyatoms",
        "formula": "mol_formula",
        "num_rings": "mol_numrings",
        "molecular_weight": "mol_amw",
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
                self.execute("CREATE SCHEMA IF NOT EXISTS hippo;")
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
        return f"postgresql://{self.username}:{self.password}@{self.host}:{self.port}"

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
            mrich.error(e)
            mrich.print(strip_sql(sql))
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
    ):
        """Execute arbitrary SQL with retry if database is locked."""
        if debug:
            from .tools import strip_sql

            mrich.debug(strip_sql(sql))

        if time:
            import re
            from time import perf_counter

            start = perf_counter()

        records = self.cursor.executemany(sql, payload)

        if time:
            sql = re.sub(r"\s+", " ", sql).strip()
            mrich.debug(f"{perf_counter()-start:.2}s: ", sql)

        return records

    def rollback(self) -> None:
        """rollback (not relevant for sqlite)"""
        self.connection.rollback()

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
            query="mol_to_pkl(compound_mol)",
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
        SET pose_mol = mol_from_pkl(%s)
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

    def migrate(
        cls,
        source: Path,
        batch_size: int = 10000,
    ) -> None:
        """Migrate records from a SQLite :class:`.Database` to this :class:`.PostgresDatabase`"""

        raise NotImplementedError

        from .animal import HIPPO

        source_path = Path(source)

        assert source_path.exists()

        source = HIPPO("source", source)

        ### compounds

        # source data
        compound_records = source.select(
            table="compound",
            query="compound_id, compound_inchikey, compound_smiles, compound_alias",
            multiple=True,
        )

        # insertion query
        sql = """
        INSERT INTO hippo.compound(
            compound_inchikey, 
            compound_smiles, 
            compound_mol, 
            compound_alias
        )
        VALUES(
            %(inchikey)s, 
            %(smiles)s, 
            mol_from_smiles(%(smiles)s), 
            %(alias)s
        )
        ON CONFLICT DO NOTHING;
        """

        # format the data
        new_compound_records = [
            dict(inchikey=b, smiles=c, alias=d) for a, b, c, d in compound_records
        ]

        # do the insertion
        self.execute(sql, new_compound_records)

        # map to the destination records
        destination_inchikey_map = self.get_compound_inchikey_id_dict(
            inchikeys=[b for a, b, c, d in compound_records]
        )
        compound_id_map = {
            a: destination_inchikey_map[b] for a, b, c, d in compound_records
        }

        ### scaffolds

        # source data
        scaffold_records = source.select(
            table="scaffold",
            query="scaffold_base, scaffold_superstructure",
            multiple=True,
        )

        # map to new IDs
        scaffold_records = [
            (compound_id_map[a], compound_id_map[b]) for a, b in scaffold_records
        ]

        # insert new data

        sql = """
        INSERT INTO hippo.scaffold(scaffold_base, scaffold_superstructure)
        VALUES(%s, %s)
        ON CONFLICT DO NOTHING;
        """

        self.execute(sql, scaffold_records)

        ### targets

        # source data
        target_records = source.select(
            table="target", query="target_id, target_name", multiple=True
        )

        # do the insertion
        for i, name in target_records:
            self.insert_target(name, warn_duplicate=False)

        # map to the destination records
        destination_target_name_map = {
            name: i
            for i, name in self.select(
                table="target", query="target_id, target_name", multiple=True
            )
        }
        target_id_map = {
            i: destination_target_name_map[name] for i, name in target_records
        }

        ### poses

        pose_fields = [
            "pose_id",
            "pose_inchikey",
            "pose_alias",
            "pose_smiles",
            "pose_path",
            "pose_compound",
            "pose_target",
            "mol_to_pkl(pose_mol)",
            "pose_fingerprint",
            "pose_energy_score",
            "pose_distance_score",
            "pose_inspiration_score",
            "pose_metadata",
        ]

        # source data
        pose_records = source.select(
            table="pose", query=", ".join(pose_fields), multiple=True
        )

        # insertion query
        sql = """
        INSERT INTO hippo.pose(
            pose_inchikey,
            pose_alias,
            pose_smiles,
            pose_path,
            pose_compound,
            pose_target,
            pose_mol,
            pose_fingerprint,
            pose_energy_score,
            pose_distance_score,
            pose_inspiration_score,
            pose_metadata
        )
        VALUES(
            %(inchikey)s,
            %(alias)s,
            %(smiles)s,
            %(path)s,
            %(compound)s,
            %(target)s,
            mol_frok_pkl(%(mol)s),
            %(fingerprint)s,
            %(energy_score)s,
            %(distance_score)s,
            %(inspiration_score)s,
            %(metadata)s,
        )
        ON CONFLICT DO NOTHING;
        """

        # massage the data
        pose_dicts = [
            dict(
                id=i,
                inchikey=inchikey,
                alias=alias,
                smiles=smiles,
                path=path,
                compound=compound_id_map[compound_id],
                target=target_id_map[target_id],
                mol=mol,
                fingerprint=fingerprint,
                energy_score=energy_score,
                distance_score=distance_score,
                inspiration_score=inspiration_score,
                metadata=metadata,
            )
            for i, inchikey, alias, smiles, path, compound_id, target_id, mol, fingerprint, energy_score, distance_score, inspiration_score, metadata in pose_records
        ]

        # do the insertion
        self.execute(sql, [p[1:] for p in pose_records])

        # map to the destination records
        destination_pose_path_map = self.get_pose_path_id_dict()
        pose_id_map = {p[0]: destination_pose_path_map[p[5]] for p in pose_records}

        ### pose references

        ### inspirations

        ### tags

        ### reactions

        ### quotes

        ### reactants

        ### routes

        ### components

        ### features

        ### interactions

        ### subsites

        ### subsite_tags

    ### MAINTENANCE

    def _clear_schema(self) -> None:
        """Empty the Database schema entirely and recreate it"""

        self.execute(
            f"""
            DROP SCHEMA IF EXISTS {self.SQL_SCHEMA} CASCADE;
            CREATE SCHEMA {self.SQL_SCHEMA};
        """
        )

        self.commit()

    ### DUNDERS

    def __str__(self):
        """Unformatted string representation"""
        return f"Database @ {self.path}"
