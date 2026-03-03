"""Functions to perform the SQLite -> PostgreSQL migration, called by :meth:`.PostgresDatabase.migrate_sqlite`"""

import mrich


def migrate_compounds(
    *,
    source: "Database",
    destination: "PostgresDatabase",
    migration_data: dict,
    batch_size: int,
    execute: bool = True,
) -> dict:
    """migrate compounds"""

    # source data
    compound_records = source.select(
        table="compound",
        query="compound_id, compound_inchikey, compound_smiles",
        multiple=True,
    )

    mrich.var("source: #compounds", len(compound_records))

    if not compound_records:
        return migration_data

    # insertion query
    sql = """
    INSERT INTO hippo.compound(
        compound_inchikey, 
        compound_smiles, 
        compound_mol
    )
    VALUES(
        %(inchikey)s, 
        %(smiles)s, 
        hippo.mol_from_smiles(%(smiles)s)
    )
    ON CONFLICT DO NOTHING;
    """

    # format the data
    compound_dicts = [
        dict(smiles=smiles, inchikey=inchikey)
        for i, inchikey, smiles in compound_records
    ]

    # do the insertion
    if execute:
        executemany(destination, "compound", sql, compound_dicts, batch_size)

    # map to the destination records
    destination_inchikey_map = destination.get_compound_inchikey_id_dict(
        inchikeys=[inchikey for i, inchikey, smiles in compound_records]
    )

    compound_id_map = {
        i: destination_inchikey_map[inchikey]
        for i, inchikey, smiles in compound_records
    }

    migration_data["compound_id_map"] = compound_id_map

    return migration_data


def migrate_scaffolds(
    *,
    source: "Database",
    destination: "PostgresDatabase",
    migration_data: dict,
    batch_size: int,
    execute: bool = True,
) -> dict:
    """migrate scaffolds"""

    # source data
    scaffold_records = source.select(
        table="scaffold",
        query="scaffold_base, scaffold_superstructure",
        multiple=True,
    )

    if not scaffold_records:
        return migration_data

    # map to new IDs
    scaffold_records = [
        (
            migration_data["compound_id_map"][base_id],
            migration_data["compound_id_map"][superstructure_id],
        )
        for (base_id, superstructure_id) in scaffold_records
    ]

    mrich.var("source: #scaffolds", len(scaffold_records))

    # insert new data

    sql = """
    INSERT INTO hippo.scaffold(scaffold_base, scaffold_superstructure)
    VALUES(%s, %s)
    ON CONFLICT DO NOTHING;
    """

    if execute:
        executemany(destination, "scaffold", sql, scaffold_records, batch_size)

    return migration_data


def migrate_targets(
    *,
    source: "Database",
    destination: "PostgresDatabase",
    migration_data: dict,
    batch_size: int,
    execute: bool = True,
) -> dict:
    """migrate targets"""

    # source data
    target_records = source.select(
        table="target", query="target_id, target_name", multiple=True
    )

    if not target_records:
        return migration_data

    # do the insertion
    for i, name in target_records:
        destination.insert_target(name=name, warn_duplicate=False)

    # map to the destination records
    destination_target_name_map = {
        name: i
        for i, name in destination.select(
            table="target", query="target_id, target_name", multiple=True
        )
    }

    target_id_map = {i: destination_target_name_map[name] for i, name in target_records}

    migration_data["target_id_map"] = target_id_map

    return migration_data


def migrate_poses(
    *,
    source: "Database",
    destination: "PostgresDatabase",
    migration_data: dict,
    batch_size: int,
    execute: bool = True,
) -> dict:
    """migrate poses"""

    from rdkit.Chem import Mol

    pose_fields = [
        "pose_id",
        "pose_inchikey",
        "pose_alias",
        "pose_smiles",
        "pose_path",
        "pose_compound",
        "pose_target",
        "pose_mol",
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

    if not pose_records:
        return migration_data

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
            compound=migration_data["compound_id_map"][compound_id],
            target=migration_data["target_id_map"][target_id],
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

    ### THIS DEVELOPMENT WAS NOT COMPLETED,
    ### TO IMPLEMENT WOULD REQUIRE FIRST INSERTING ALL
    ### UPSTREAM REFERENCES AND INSPIRATIONS SO THEIR IDS
    ### ARE IN THE POSE_ID_MAP
    # pose_dicts = rename_pose_paths(pose_dicts, migration_data)

    # do the insertion
    if execute:
        executemany(destination, "pose", sql, pose_dicts, batch_size)

    # map to the destination records
    destination_pose_path_map = destination.get_pose_path_id_dict()

    # return destination_pose_path_map

    pose_id_map = {p["id"]: destination_pose_path_map[p["path"]] for p in pose_dicts}

    migration_data["pose_id_map"] = pose_id_map

    return migration_data


def migrate_pose_references(
    *,
    source: "Database",
    destination: "PostgresDatabase",
    migration_data: dict,
    batch_size: int,
    execute: bool = True,
) -> dict:
    """migrate pose references"""

    # source data
    reference_records = source.select(
        table="pose",
        query="pose_id, pose_reference",
        multiple=True,
    )

    if not reference_records:
        return migration_data

    # map to new IDs
    reference_dicts = [
        dict(
            pose=migration_data["pose_id_map"][pose_id],
            reference=migration_data["pose_id_map"][reference_id],
        )
        for pose_id, reference_id in reference_records
        if reference_id
    ]

    mrich.var("source: #references", len(reference_dicts))

    # insert new data

    sql = """
    UPDATE hippo.pose
    SET pose_reference = %(reference)s
    WHERE pose_id = %(pose)s;
    """

    if execute:
        destination.executemany(sql, reference_dicts, batch_size=batch_size)

    return migration_data


def migrate_inspirations(
    *,
    source: "Database",
    destination: "PostgresDatabase",
    migration_data: dict,
    batch_size: int,
    execute: bool = True,
) -> dict:
    """migrate inspirations"""

    # source data
    inspiration_records = source.select(
        table="inspiration",
        query="inspiration_original, inspiration_derivative",
        multiple=True,
    )

    if not inspiration_records:
        return migration_data

    # map to new IDs
    inspiration_dicts = [
        dict(
            original=migration_data["pose_id_map"][a],
            derivative=migration_data["pose_id_map"][b],
        )
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

    if execute:
        executemany(destination, "inspiration", sql, inspiration_dicts, batch_size)

    return migration_data


def migrate_tags(
    *,
    source: "Database",
    destination: "PostgresDatabase",
    migration_data: dict,
    batch_size: int,
    execute: bool = True,
) -> dict:
    """migrate reactions and reactants"""

    import re

    # unique tag names

    tag_names = source.select(table="tag", query="DISTINCT tag_name", multiple=True)

    tag_names = sorted([t for t, in tag_names])

    if not tag_names:
        return migration_data

    # rename tags based on regex

    tag_name_map = {}
    for tag in tag_names:
        for pattern, template in migration_data["tag_compound_id_regex"]:

            match = re.match(pattern, tag)

            if not match:
                continue

            groups = match.groups()

            assert (
                len(groups) == 1
            ), f"tag_compound_id_regex replacement not supported with multiple groups, {pattern=}"

            groups = [g for g in groups]

            compound_id = int(groups[0])
            new_compound_id = migration_data["compound_id_map"][compound_id]

            replacement = template.format(new_compound_id=new_compound_id)

            new_tag = re.sub(pattern, replacement, tag)

            if new_tag != tag:
                tag_name_map[tag] = new_tag

            break

    # source data
    tag_records = source.select(
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
            name=tag_name_map.get(name, name),
            compound=(
                migration_data["compound_id_map"][compound_id] if compound_id else None
            ),
            pose=migration_data["pose_id_map"][pose_id] if pose_id else None,
        )
        for name, compound_id, pose_id in tag_records
    ]

    # add unchanged tags
    for tag in tag_names:
        if tag not in tag_name_map:
            tag_name_map[tag] = tag

    migration_data["tag_name_map"] = tag_name_map

    # do the insertion
    if execute:
        executemany(destination, "tag", sql, tag_dicts, batch_size)

    return migration_data


def migrate_reactions_and_reactants(
    *,
    source: "Database",
    destination: "PostgresDatabase",
    migration_data: dict,
    batch_size: int,
) -> dict:
    """migrate inspirations"""

    # get source reaction data
    source_reaction_dicts, reactant_records = get_reaction_id_reaction_dict_map(
        source, migration_data["compound_id_map"]
    )
    mrich.var("source: #reactions", len(source_reaction_dicts))

    if not source_reaction_dicts:
        return migration_data

    # get destination reaction data
    destination_reaction_dicts, _ = get_reaction_id_reaction_dict_map(destination)
    mrich.var("destination: #reactions", len(destination_reaction_dicts))

    # create keyed lookups

    source_reaction_lookup = {
        (
            d["product"],
            d["type"],
            tuple(sorted(list(d["reactant_ids"]))),
        ): d["id"]
        for d in source_reaction_dicts.values()
    }

    destination_reaction_lookup = {
        (
            d["product"],
            d["type"],
            tuple(sorted(list(d["reactant_ids"]))),
        ): d["id"]
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
    inserted_reaction_ids = executemany(
        destination, "reaction", sql, reaction_dicts, batch_size
    )

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
            compound=migration_data["compound_id_map"][compound_id],
        )
        for amount, reaction_id, compound_id in reactant_records
    ]

    mrich.var("source: #reactants", len(reactant_dicts))

    # do the insertion
    executemany(destination, "reactant", sql, reactant_dicts, batch_size)

    return migration_data


def migrate_features(
    *,
    source: "Database",
    destination: "PostgresDatabase",
    migration_data: dict,
    batch_size: int,
    execute: bool = True,
) -> dict:
    """migrate features"""

    # source data
    feature_records = source.select(
        table="feature",
        query="feature_id, feature_family, feature_target, feature_chain_name, feature_residue_name, feature_residue_number, feature_atom_names",
        multiple=True,
    )

    mrich.var("source: #features", len(feature_records))

    if not feature_records:
        return migration_data

    # insertion query
    sql = """
    INSERT INTO hippo.feature(
        feature_family,
        feature_target,
        feature_chain_name,
        feature_residue_name,
        feature_residue_number,
        feature_atom_names
    )
    VALUES(
       %(family)s,
       %(target)s,
       %(chain_name)s,
       %(residue_name)s,
       %(residue_number)s,
       %(atom_names)s
    )
    ON CONFLICT DO NOTHING;
    """

    # format the data
    feature_dicts = [
        dict(
            family=family,
            target=migration_data["target_id_map"][target_id],
            chain_name=chain_name,
            residue_name=residue_name,
            residue_number=residue_number,
            atom_names=atom_names,
        )
        for (
            i,
            family,
            target_id,
            chain_name,
            residue_name,
            residue_number,
            atom_names,
        ) in feature_records
    ]

    # do the insertion
    if execute:
        executemany(destination, "feature", sql, feature_dicts, batch_size)

    # get destination values
    feature_map = {
        (
            family,
            target_id,
            chain_name,
            residue_name,
            residue_number,
            atom_names,
        ): i
        for (
            i,
            family,
            target_id,
            chain_name,
            residue_name,
            residue_number,
            atom_names,
        ) in destination.select(
            table="feature",
            query="feature_id, feature_family, feature_target, feature_chain_name, feature_residue_name, feature_residue_number, feature_atom_names",
            multiple=True,
        )
    }

    # map to the destination records
    feature_id_map = {
        i: feature_map[
            (
                family,
                migration_data["target_id_map"][target_id],
                chain_name,
                residue_name,
                residue_number,
                atom_names,
            )
        ]
        for (
            i,
            family,
            target_id,
            chain_name,
            residue_name,
            residue_number,
            atom_names,
        ) in feature_records
    }

    migration_data["feature_id_map"] = feature_id_map

    return migration_data


def migrate_interactions(
    *,
    source: "Database",
    destination: "PostgresDatabase",
    migration_data: dict,
    batch_size: int,
    execute: bool = True,
) -> dict:
    """migrate interactions"""

    interaction_fields = [
        "interaction_id",
        "interaction_feature",
        "interaction_pose",
        "interaction_type",
        "interaction_family",
        "interaction_atom_ids",
        "interaction_prot_coord",
        "interaction_lig_coord",
        "interaction_distance",
        "interaction_angle",
        "interaction_energy",
    ]

    # source data
    interaction_records = source.select(
        table="interaction",
        query=", ".join(interaction_fields),
        multiple=True,
    )

    mrich.var("source: #interactions", len(interaction_records))

    if not interaction_records:
        return migration_data

    # insertion query
    sql = """
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
    VALUES(
        %(feature)s,
        %(pose)s,
        %(type)s,
        %(family)s,
        %(atom_ids)s,
        %(prot_coord)s,
        %(lig_coord)s,
        %(distance)s,
        %(angle)s,
        %(energy)s
    )
    ON CONFLICT DO NOTHING;
    """

    # format the data
    interaction_dicts = [
        dict(
            feature=migration_data["feature_id_map"][feature_id],
            pose=migration_data["pose_id_map"][pose_id],
            type=type,
            family=family,
            atom_ids=atom_ids,
            prot_coord=prot_coord,
            lig_coord=lig_coord,
            distance=distance,
            angle=angle,
            energy=energy,
        )
        for (
            i,
            feature_id,
            pose_id,
            type,
            family,
            atom_ids,
            prot_coord,
            lig_coord,
            distance,
            angle,
            energy,
        ) in interaction_records
    ]

    # do the insertion
    if execute:
        executemany(destination, "interaction", sql, interaction_dicts, batch_size)

    # get destination values
    interaction_map = {
        (
            feature_id,
            pose_id,
            type,
            family,
        ): i
        for (
            i,
            feature_id,
            pose_id,
            type,
            family,
            atom_ids,
            prot_coord,
            lig_coord,
            distance,
            angle,
            energy,
        ) in destination.select(
            table="interaction",
            query=", ".join(interaction_fields),
            multiple=True,
        )
    }

    # map to the destination records
    interaction_id_map = {
        i: interaction_map[
            (
                migration_data["feature_id_map"][feature_id],
                migration_data["pose_id_map"][pose_id],
                type,
                family,
            )
        ]
        for (
            i,
            feature_id,
            pose_id,
            type,
            family,
            atom_ids,
            prot_coord,
            lig_coord,
            distance,
            angle,
            energy,
        ) in interaction_records
    }

    migration_data["interaction_id_map"] = interaction_id_map

    return migration_data


def migrate_subsites(
    *,
    source: "Database",
    destination: "PostgresDatabase",
    migration_data: dict,
    batch_size: int,
    execute: bool = True,
) -> dict:
    """migrate subsites and subsite_tags"""

    # source data
    subsite_records = source.select(
        table="subsite",
        query="subsite_id, subsite_target, subsite_name, subsite_metadata",
        multiple=True,
    )

    mrich.var("source: #subsites", len(subsite_records))

    if not subsite_records:
        return migration_data

    # insertion query
    sql = """
    INSERT INTO hippo.subsite(
        subsite_target, 
        subsite_name, 
        subsite_metadata
    )
    VALUES(
        %(target)s,
        %(name)s,
        %(metadata)s
    )
    ON CONFLICT DO NOTHING;
    """

    # format the data
    subsite_dicts = [
        dict(
            target=migration_data["target_id_map"][target_id],
            name=name,
            metadata=metadata,
        )
        for i, target_id, name, metadata in subsite_records
    ]

    # do the insertion
    if execute:
        executemany(destination, "subsite", sql, subsite_dicts, batch_size)

    # map to the destination records
    subsite_map = {
        (target_id, name): i
        for i, target_id, name, metadata in destination.select(
            table="subsite",
            query="subsite_id, subsite_target, subsite_name, subsite_metadata",
            multiple=True,
        )
    }

    subsite_id_map = {
        i: subsite_map[(migration_data["target_id_map"][target_id], name)]
        for i, target_id, name, metadata in subsite_records
    }

    migration_data["subsite_id_map"] = subsite_id_map

    ### subsite_tags

    # source data
    subsite_tag_records = source.select(
        table="subsite_tag",
        query="subsite_tag_id, subsite_tag_ref, subsite_tag_pose, subsite_tag_metadata",
        multiple=True,
    )

    mrich.var("source: #subsite_tags", len(subsite_tag_records))

    # insertion query
    sql = """
    INSERT INTO hippo.subsite_tag(
        subsite_tag_ref, 
        subsite_tag_pose, 
        subsite_tag_metadata
    )
    VALUES(
        %(subsite)s,
        %(pose)s,
        %(metadata)s
    )
    ON CONFLICT DO NOTHING;
    """

    # format the data
    subsite_tag_dicts = [
        dict(
            subsite=migration_data["subsite_id_map"][subsite_id],
            pose=migration_data["pose_id_map"][pose_id],
            metadata=metadata,
        )
        for i, subsite_id, pose_id, metadata in subsite_tag_records
    ]

    # do the insertion
    if execute:
        executemany(destination, "subsite_tag", sql, subsite_tag_dicts, batch_size)

    # map to the destination records
    subsite_tag_map = {
        (subsite_id, pose_id): i
        for i, subsite_id, pose_id, metadata in destination.select(
            table="subsite_tag",
            query="subsite_tag_id, subsite_tag_ref, subsite_tag_pose, subsite_tag_metadata",
            multiple=True,
        )
    }

    subsite_tag_id_map = {
        i: subsite_tag_map[
            (
                migration_data["subsite_id_map"][subsite_id],
                migration_data["pose_id_map"][pose_id],
            )
        ]
        for i, subsite_id, pose_id, metadata in subsite_tag_records
    }

    migration_data["subsite_tag_id_map"] = subsite_tag_id_map

    return migration_data


def migrate_quotes(
    *,
    source: "Database",
    destination: "PostgresDatabase",
    migration_data: dict,
    batch_size: int,
    execute: bool = True,
) -> dict:
    """migrate quotes"""

    quote_fields = [
        "quote_id",
        "quote_smiles",
        "quote_amount",
        "quote_supplier",
        "quote_catalogue",
        "quote_entry",
        "quote_lead_time",
        "quote_price",
        "quote_currency",
        "quote_purity",
        "quote_date",
        "quote_compound",
    ]

    # source data
    quote_records = source.select(
        table="quote",
        query=", ".join(quote_fields),
        multiple=True,
    )

    mrich.var("source: #quotes", len(quote_records))

    if not quote_records:
        return migration_data

    # insertion query
    sql = """
    INSERT INTO hippo.quote(
        quote_smiles,
        quote_amount,
        quote_supplier,
        quote_catalogue,
        quote_entry,
        quote_lead_time,
        quote_price,
        quote_currency,
        quote_purity,
        quote_date,
        quote_compound
    )
    VALUES(
        %(smiles)s,
        %(amount)s,
        %(supplier)s,
        %(catalogue)s,
        %(entry)s,
        %(lead_time)s,
        %(price)s,
        %(currency)s,
        %(purity)s,
        %(date)s,
        %(compound)s
    )
    ON CONFLICT ON CONSTRAINT UC_quote
    DO UPDATE SET
        quote_smiles = EXCLUDED.quote_smiles,
        quote_amount = EXCLUDED.quote_amount,
        quote_supplier = EXCLUDED.quote_supplier,
        quote_catalogue = EXCLUDED.quote_catalogue,
        quote_entry = EXCLUDED.quote_entry,
        quote_lead_time = EXCLUDED.quote_lead_time,
        quote_price = EXCLUDED.quote_price,
        quote_currency = EXCLUDED.quote_currency,
        quote_purity = EXCLUDED.quote_purity,
        quote_date = EXCLUDED.quote_date,
        quote_compound = EXCLUDED.quote_compound
    WHERE hippo.quote.quote_date < EXCLUDED.quote_date;
    """

    # format the data
    quote_dicts = [
        dict(
            smiles=smiles,
            amount=round(amount, 3),
            supplier=supplier,
            catalogue=catalogue,
            entry=entry,
            lead_time=lead_time,
            price=price,
            currency=currency,
            purity=purity,
            date=date,
            compound=migration_data["compound_id_map"][compound_id],
        )
        for (
            i,
            smiles,
            amount,
            supplier,
            catalogue,
            entry,
            lead_time,
            price,
            currency,
            purity,
            date,
            compound_id,
        ) in quote_records
    ]

    # do the insertion
    if execute:
        executemany(destination, "quote", sql, quote_dicts, batch_size)

    # map to the destination records
    quote_map = {
        (round(amount, 3), supplier, catalogue, entry): i
        for (
            i,
            smiles,
            amount,
            supplier,
            catalogue,
            entry,
            lead_time,
            price,
            currency,
            purity,
            date,
            compound_id,
        ) in destination.select(
            table="quote",
            query=", ".join(quote_fields),
            multiple=True,
        )
    }

    quote_id_map = {
        i: quote_map[(round(amount, 3), supplier, catalogue, entry)]
        for (
            i,
            smiles,
            amount,
            supplier,
            catalogue,
            entry,
            lead_time,
            price,
            currency,
            purity,
            date,
            compound_id,
        ) in quote_records
    }

    migration_data["quote_id_map"] = quote_id_map

    return migration_data


def get_reaction_id_reaction_dict_map(
    db: "Database | PostgresDatabase", compound_id_map: dict = None
) -> (dict, list):
    """Get serialised reaction and reactant data"""

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
            product=(compound_id_map[product_id] if compound_id_map else product_id),
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
        compound_id = compound_id_map[compound_id] if compound_id_map else compound_id

        reaction_id_reaction_dict_map[reaction_id].setdefault("reactants", set())
        reaction_id_reaction_dict_map[reaction_id]["reactants"].add(
            (compound_id, amount)
        )

        reaction_id_reaction_dict_map[reaction_id].setdefault("reactant_ids", set())
        reaction_id_reaction_dict_map[reaction_id]["reactant_ids"].add(compound_id)

    return reaction_id_reaction_dict_map, reactant_records


def executemany(
    db: "PostgresDatabase", table: str, sql: str, payload: list, batch_size: int
) -> None | list:
    """Bulk execution with console logging"""

    n = db.count(table)
    mrich.var(f"destination: #{table}s", n)

    result = db.executemany(sql, payload, batch_size=batch_size)

    if d := db.count(table) - n:
        mrich.success("Inserted", d, f"new {table}s")
    else:
        mrich.warning("Inserted", d, f"new {table}s")

    return result


def rename_pose_paths(
    pose_dicts: list[dict],
    migration_data: dict,
) -> list[dict]:
    """Uses regex to rename ID's in pose paths"""

    import re

    mrich.var(
        "pose_path_compound_id_regex", migration_data["pose_path_compound_id_regex"]
    )
    mrich.var("pose_path_pose_id_regex", migration_data["pose_path_pose_id_regex"])

    # compound IDs

    pose_path_map = {}
    # pose_path_map_log = {}

    for pose_dict in pose_dicts:

        orig_path = pose_dict["path"]

        path = orig_path

        for pattern, template in migration_data["pose_path_compound_id_regex"]:

            if orig_path in pose_path_map:
                path = pose_path_map[orig_path]

            match = re.match(pattern, path)

            if not match:
                # if "fake.mol" in path:
                #     print("NO MATCH", pattern, path)
                #     raise NotImplementedError
                continue

            groups = match.groups()

            assert (
                len(groups) == 1
            ), f"pose_path_compound_id_regex replacement not supported with multiple groups, {pattern=}"

            groups = [g for g in groups]

            compound_id = int(groups[0])
            new_compound_id = migration_data["compound_id_map"][compound_id]

            replacement = template.format(new_compound_id=new_compound_id)

            new_path = re.sub(pattern, replacement, path)

            if new_path != path:
                pose_path_map[orig_path] = new_path

    raise NotImplementedError("pose_path_pose_id_regex development was not completed")

    #     for pattern, template in migration_data["pose_path_pose_id_regex"]:

    #         if orig_path in pose_path_map:
    #             path = pose_path_map[orig_path]

    #         match = re.match(pattern, path)

    #         if not match:
    #             # if "fake.mol" in path:
    #             #     print("NO MATCH", pattern, path)
    #             #     raise NotImplementedError
    #             continue

    #         groups = match.groups()

    #         assert (
    #             len(groups) == 1
    #         ), f"pose_path_pose_id_regex replacement not supported with multiple groups, {pattern=}"

    #         groups = [g for g in groups]

    #         pose_id = int(groups[0])
    #         new_pose_id = migration_data["pose_id_map"][pose_id]

    #         replacement = template.format(new_pose_id=new_pose_id)

    #         new_path = re.sub(pattern, replacement, path)

    #         if new_path != path:
    #             pose_path_map[orig_path] = new_path

    return pose_dicts


def dump_json(data: dict, file: str) -> None:
    """Dump migration data to JSON"""
    from json import dump

    mrich.writing(file)
    dump(data, open(file, "wt"))


def dump_xlsx(data: dict, file: str) -> None:
    """Dump migration data to Excel"""

    import pandas as pd

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

            data = [{source: k, destination: v} for k, v in value.items()]

            if len(data) > 1_000_000:
                from itertools import batched

                batches = batched(data, 1_000_000)

                for i, batch in enumerate(batches):
                    df = pd.DataFrame(batch)
                    sheets[f"{key} ({i+1})"] = df.set_index(source)

            else:
                df = pd.DataFrame(data)
                sheets[key] = df.set_index(source)

    with pd.ExcelWriter(file) as writer:

        meta_df.to_excel(writer, sheet_name="meta")

        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=True)
