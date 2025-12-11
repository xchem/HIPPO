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
        debug: bool = True,
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

        if batch_size:

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
        batch_size: int = 5_000,
        tag_compound_id_regex: list[tuple[str, str]] | None = None,
        # tag_name_map: "Callable" = None,
        # rename_tag_compound_shortcodes: bool = True
    ) -> dict:
        """Migrate records from a SQLite :class:`.Database` to this :class:`.PostgresDatabase`

        :param source: path to source sqlite database
        :param batch_size: SQL insertion batch size
        :param tag_compound_id_regex: Provide regex to identify compound ID's to replace in tag names, defaults to `[(r"^C([0-9]+)", "C{new_compound_id}")]`

        The default tag_compound_id_regex means that tags such as "C123 85 percent analogues" are replaced with "C234 85 percent analogues",
        where 123 is the compound ID in the source database, and 234 in the destination.

        """

        import re
        import pandas as pd
        from json import dump
        from rdkit.Chem import Mol
        from datetime import datetime

        from .animal import HIPPO

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
                (r"^C([0-9]+)", "C{new_compound_id}"),
            ]

        mrich.var("tag_compound_id_regex", tag_compound_id_regex)

        source = HIPPO("source", source_path)

        ### helper functions

        def executemany(table, sql, payload):

            n = self.count(table)
            mrich.var(f"destination: #{table}s", n)

            result = self.executemany(sql, payload, batch_size=batch_size)

            if d := self.count(table) - n:
                mrich.success("Inserted", d, f"new {table}s")
            else:
                mrich.warning("Inserted", d, f"new {table}s")

            return result

        def dump_json(data, file):
            mrich.writing(file)
            dump(data, open(file, "wt"))

        def dump_xlsx(data, file):
            mrich.writing(file)

            meta = []
            for key, value in data.items():
                if not isinstance(value, dict):
                    meta.append(dict(key=key, value=value))

            meta_df = pd.DataFrame(meta).set_index("key")

            source = meta_df.loc["source", "value"]
            destination = meta_df.loc["destination", "value"]

            sheets = {}
            for key, value in data.items():
                if isinstance(value, dict):

                    df = pd.DataFrame(
                        [{source: k, destination: v} for k, v in value.items()]
                    )
                    sheets[key] = df.set_index(source)

            with pd.ExcelWriter(file) as writer:

                meta_df.to_excel(writer, sheet_name="meta")

                for name, df in sheets.items():
                    df.to_excel(writer, sheet_name=name, index=True)

        try:

            migration_data = {
                "source": str(source_path.resolve()),
                "destination": self.path,
                "time": str(datetime.now()),
            }

            ### compounds

            # source data
            compound_records = source.db.select(
                table="compound",
                query="compound_id, compound_inchikey, compound_smiles, compound_alias",
                multiple=True,
            )

            mrich.var("source: #compounds", len(compound_records))

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
                hippo.mol_from_smiles(%(smiles)s), 
                %(alias)s
            )
            ON CONFLICT DO NOTHING;
            """

            # format the data
            compound_dicts = [
                dict(inchikey=b, smiles=c, alias=d) for a, b, c, d in compound_records
            ]

            # do the insertion
            # executemany("compound", sql, compound_dicts)

            # map to the destination records
            destination_inchikey_map = self.get_compound_inchikey_id_dict(
                inchikeys=[b for a, b, c, d in compound_records]
            )

            compound_id_map = {
                a: destination_inchikey_map.get(b) for a, b, c, d in compound_records
            }

            migration_data["compound_id_map"] = compound_id_map

            ### scaffolds

            # source data
            scaffold_records = source.db.select(
                table="scaffold",
                query="scaffold_base, scaffold_superstructure",
                multiple=True,
            )

            # map to new IDs
            scaffold_records = [
                (compound_id_map[a], compound_id_map[b]) for a, b in scaffold_records
            ]

            mrich.var("source: #scaffolds", len(scaffold_records))

            # insert new data

            sql = """
            INSERT INTO hippo.scaffold(scaffold_base, scaffold_superstructure)
            VALUES(%s, %s)
            ON CONFLICT DO NOTHING;
            """

            # executemany("scaffold", sql, scaffold_records)

            ### targets

            # source data
            target_records = source.db.select(
                table="target", query="target_id, target_name", multiple=True
            )

            # do the insertion
            for i, name in target_records:
                self.insert_target(name=name, warn_duplicate=False)

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

            migration_data["target_id_map"] = target_id_map

            ### poses

            pose_fields = [
                "pose_id",
                "pose_inchikey",
                "pose_alias",
                "pose_smiles",
                "pose_path",
                "pose_compound",
                "pose_target",
                # "CASE WHEN pose_mol IS NOT NULL THEN mol_to_binary_mol(pose_mol) ELSE pose_mol END",
                "pose_mol",
                "pose_fingerprint",
                "pose_energy_score",
                "pose_distance_score",
                "pose_inspiration_score",
                "pose_metadata",
            ]

            # source data
            pose_records = source.db.select(
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
                hippo.mol_from_pkl(%(mol)s),
                %(fingerprint)s,
                %(energy_score)s,
                %(distance_score)s,
                %(inspiration_score)s,
                %(metadata)s
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
                    mol=Mol(mol).ToBinary() if mol else None,
                    fingerprint=fingerprint,
                    energy_score=energy_score,
                    distance_score=distance_score,
                    inspiration_score=inspiration_score,
                    metadata=metadata,
                )
                for (
                    i,
                    inchikey,
                    alias,
                    smiles,
                    path,
                    compound_id,
                    target_id,
                    mol,
                    fingerprint,
                    energy_score,
                    distance_score,
                    inspiration_score,
                    metadata,
                ) in pose_records
            ]

            mrich.var("source: #poses", len(pose_dicts))

            # do the insertion
            # executemany("pose", sql, pose_dicts)

            # map to the destination records
            destination_pose_path_map = self.get_pose_path_id_dict()

            # return destination_pose_path_map

            pose_id_map = {
                p["id"]: destination_pose_path_map[p["path"]] for p in pose_dicts
            }

            migration_data["pose_id_map"] = pose_id_map

            ### pose references

            # source data
            reference_records = source.db.select(
                table="pose",
                query="pose_id, pose_reference",
                multiple=True,
            )

            # map to new IDs
            reference_dicts = [
                dict(pose=pose_id_map[a], reference=pose_id_map[b])
                for a, b in reference_records
                if b
            ]

            mrich.var("source: #references", len(reference_dicts))

            # insert new data

            sql = """
            UPDATE hippo.pose
            SET pose_reference = %(reference)s
            WHERE pose_id = %(pose)s;
            """

            # self.executemany(sql, reference_dicts, batch_size=batch_size)

            ### inspirations

            # source data
            inspiration_records = source.db.select(
                table="inspiration",
                query="inspiration_original, inspiration_derivative",
                multiple=True,
            )

            # map to new IDs
            inspiration_dicts = [
                dict(original=pose_id_map[a], derivative=pose_id_map[b])
                for a, b in inspiration_records
                if b
            ]

            mrich.var("source: #inspirations", len(inspiration_dicts))

            # insert new data

            sql = """
            INSERT INTO hippo.inspiration(
                inspiration_original, 
                inspiration_derivative
            )
            VALUES (
                %(original)s,
                %(derivative)s
            )
            ON CONFLICT DO NOTHING;
            """

            # executemany("inspiration", sql, inspiration_dicts)

            ### tags

            # unique tag names

            tag_names = source.db.select(
                table="tag", query="DISTINCT tag_name", multiple=True
            )

            tag_names = sorted([t for t, in tag_names])

            # rename tags based on regex

            tag_name_map = {}
            for tag in tag_names:
                for pattern, template in tag_compound_id_regex:

                    match = re.match(pattern, tag)

                    if not match:
                        continue

                    groups = match.groups()

                    assert (
                        len(groups) == 1
                    ), f"tag_compound_id_regex replacement not supported with multiple groups, {pattern=}"

                    groups = [g for g in groups]

                    compound_id = int(groups[0])
                    new_compound_id = compound_id_map[compound_id]

                    replacement = template.format(new_compound_id=new_compound_id)

                    new_tag = re.sub(pattern, replacement, tag)

                    tag_name_map[tag] = new_tag

                    break

            # source data
            tag_records = source.db.select(
                table="tag",
                query="tag_name, tag_compound, tag_pose",
                multiple=True,
            )

            mrich.var("source: #tags", len(tag_records))

            if tag_name_map:
                mrich.warning("renamed", len(tag_name_map), "tags")

            # insertion query
            sql = """
            INSERT INTO hippo.tag(
                tag_name, 
                tag_compound, 
                tag_pose
            )
            VALUES(
                %(name)s, 
                %(compound)s, 
                %(pose)s
            )
            ON CONFLICT DO NOTHING;
            """

            # format the data
            tag_dicts = [
                dict(
                    name=tag_name_map.get(a, a),
                    compound=compound_id_map[b] if b else None,
                    pose=pose_id_map[c] if c else None,
                )
                for a, b, c in tag_records
            ]

            # add unchanged tags
            for tag in tag_names:
                if tag not in tag_name_map:
                    tag_name_map[tag] = tag

            migration_data["tag_name_map"] = tag_name_map

            # do the insertion
            # executemany("tag", sql, tag_dicts)

            ### reactions & reactants

            def get_reaction_id_reaction_dict_map(db, compound_id_map=None):

                # reactions
                reaction_records = db.select(
                    table="reaction",
                    query="reaction_id, reaction_type, reaction_product, reaction_product_yield",
                    multiple=True,
                )

                reaction_id_reaction_dict_map = {
                    i: dict(
                        id=i,
                        type=t,
                        product=(
                            compound_id_map[product_id]
                            if compound_id_map
                            else product_id
                        ),
                        product_yield=product_yield,
                    )
                    for i, t, product_id, product_yield in reaction_records
                }

                # reactants
                reactant_records = db.select(
                    table="reactant",
                    query="reactant_amount, reactant_reaction, reactant_compound",
                    multiple=True,
                )

                # combine
                for amount, reaction_id, compound_id in reactant_records:
                    compound_id = (
                        compound_id_map[compound_id] if compound_id_map else compound_id
                    )

                    reaction_id_reaction_dict_map[reaction_id].setdefault(
                        "reactants", set()
                    )
                    reaction_id_reaction_dict_map[reaction_id]["reactants"].add(
                        (compound_id, amount)
                    )

                    reaction_id_reaction_dict_map[reaction_id].setdefault(
                        "reactant_ids", set()
                    )
                    reaction_id_reaction_dict_map[reaction_id]["reactant_ids"].add(
                        compound_id
                    )

                return reaction_id_reaction_dict_map, reactant_records

            # get source reaction data
            source_reaction_dicts, reactant_records = get_reaction_id_reaction_dict_map(
                source.db, compound_id_map
            )
            mrich.var("source: #reactions", len(source_reaction_dicts))

            # get destination reaction data
            destination_reaction_dicts, _ = get_reaction_id_reaction_dict_map(self)
            mrich.var("destination: #reactions", len(destination_reaction_dicts))

            # create keyed lookups

            source_reaction_lookup = {
                (d["product"], d["type"], tuple(sorted(list(d["reactant_ids"])))): d[
                    "id"
                ]
                for d in source_reaction_dicts.values()
            }

            destination_reaction_lookup = {
                (d["product"], d["type"], tuple(sorted(list(d["reactant_ids"])))): d[
                    "id"
                ]
                for d in destination_reaction_dicts.values()
            }

            # work out which source reactions are not in the destination and create a map for existing reactions

            reaction_id_map = {}
            new_reaction_dicts = []

            for key, reaction_id in list(source_reaction_lookup.items()):

                if key in destination_reaction_lookup:
                    # EXISTING REACTION
                    reaction_id_map[reaction_id] = destination_reaction_lookup[key]

                else:

                    # NEW REACTION
                    new_reaction_dicts.append(source_reaction_dicts[reaction_id])

            mrich.var("existing #reactions:", len(reaction_id_map))
            mrich.var("new #reactions:", len(new_reaction_dicts))

            # reaction insertion query
            sql = """
            INSERT INTO hippo.reaction(
                reaction_type, 
                reaction_product, 
                reaction_product_yield
            )
            VALUES(
                %(type)s,
                %(product)s,
                %(product_yield)s
            )
            ON CONFLICT DO NOTHING
            RETURNING reaction_id;
            """

            # massage the data
            reaction_dicts = [
                dict(
                    type=d["type"],
                    product=d["product"],
                    product_yield=d["product_yield"],
                )
                for d in new_reaction_dicts
            ]

            # do the insertion
            inserted_reaction_ids = executemany("reaction", sql, reaction_dicts)

            if inserted_reaction_ids:
                inserted_reaction_ids = [i for i, in inserted_reaction_ids]
            else:
                inserted_reaction_ids = []

            # add to the map
            for reaction_dict, new_reaction_id in zip(
                new_reaction_dicts, inserted_reaction_ids
            ):
                reaction_id = reaction_dict["id"]
                reaction_id_map[reaction_id] = new_reaction_id

            migration_data["reaction_id_map"] = reaction_id_map

            # reactant insertion query
            sql = """
            INSERT INTO hippo.reactant(
                reactant_amount, 
                reactant_reaction, 
                reactant_compound
            )
            VALUES(
                %(amount)s,
                %(reaction)s,
                %(compound)s
            )
            ON CONFLICT DO NOTHING;
            """

            reactant_dicts = [
                dict(
                    amount=amount,
                    reaction=reaction_id_map[reaction_id],
                    compound=compound_id_map[compound_id],
                )
                for amount, reaction_id, compound_id in reactant_records
            ]

            mrich.var("source: #reactants", len(reactant_dicts))

            # do the insertion
            # executemany("reactant", sql, reactant_dicts)

            ### quotes

            ### features

            ### interactions

            ### subsites

            ### subsite_tags

            ### routes (skip?)

            ### components (skip?)

            raise NotImplementedError

            mrich.success(
                "Migration staged. Please review and db.commit() or db.rollback() the changes"
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

            # raise

        dump_json(migration_data, json_file_name)
        dump_xlsx(migration_data, xlsx_file_name)

        return migration_data

    ### MAINTENANCE

    def _drop_schema(self) -> None:
        """Empty the Database schema entirely and recreate it"""

        self.execute(f"DROP SCHEMA IF EXISTS {self.SQL_SCHEMA} CASCADE;")
        self.commit()

    def _drop_tables(self) -> None:
        """Delete all HIPPO tables"""

        for table in self.TABLES:
            self.execute(f"DROP TABLE IF EXISTS {table};")

        self.commit()

    ### DUNDERS

    def __str__(self):
        """Unformatted string representation"""
        return f"Database @ {self.path}"
