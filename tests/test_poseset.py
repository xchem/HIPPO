"""PoseSet tests (SQLite tier).

Regression: ``PoseSet.__getitem__`` for a slice passed the ``slice`` object
straight to ``filter(pk__in=key)`` instead of positionally slicing the members
(e.g. ``poseset[1:10]`` errored).
"""

import pytest

pytestmark = pytest.mark.sqlite


@pytest.fixture
def poseset(animal, make_compound):
    """A PoseSet of 20 minimal poses.

    Uses a compound dedicated to this test so it doesn't perturb the pose counts
    of compounds used by other tests sharing the session database.
    """
    from designdb.models import PoseModel
    from designdb.sets.pose import PoseSet

    compound = make_compound("c1ccc(F)cc1")  # fluorobenzene
    target = animal.target

    poses = [
        PoseModel.objects.create(
            compound=compound, target=target, pose_alias=f"slice-{i}"
        )
        for i in range(20)
    ]
    return PoseSet(PoseModel.objects.filter(pk__in=[p.pk for p in poses]))


def test_poseset_slice_returns_positional_subset(poseset):
    from designdb.sets.pose import PoseSet

    sliced = poseset[1:10]

    assert isinstance(sliced, PoseSet)
    assert len(sliced) == 9
    # a slice selects members by position, not by pk
    assert list(sliced.ids) == list(poseset.ids)[1:10]


def test_poseset_slice_full_and_out_of_range(poseset):
    assert len(poseset[:]) == 20
    assert len(poseset[100:200]) == 0


def test_poseset_slice_after_evaluation(poseset):
    """Slicing must work even after the underlying queryset was evaluated."""
    from designdb.sets.pose import PoseSet

    list(poseset)  # force-evaluate the underlying queryset

    sliced = poseset[1:10]

    assert isinstance(sliced, PoseSet)
    assert len(sliced) == 9
    assert list(sliced.ids) == list(poseset.ids)[1:10]


def test_poseset_int_indexing_is_positional(poseset):
    """pset[i] selects the i-th member by position (not by pk)."""
    from designdb.components.pose import Pose

    ids = list(poseset.ids)

    first = poseset[0]
    assert isinstance(first, Pose)
    assert first.id == ids[0]

    assert poseset[1].id == ids[1]  # second pose, by position
    assert poseset[-1].id == ids[-1]  # negative indexing -> last pose


def test_poseset_int_index_out_of_range_raises(poseset):
    with pytest.raises(IndexError):
        poseset[len(poseset)]


def test_poseset_best_placed_pose_returns_pose(poseset):
    """best_placed_pose yields a Pose component (like iteration/indexing)."""
    from designdb.components.pose import Pose

    assert isinstance(poseset.best_placed_pose, Pose)


@pytest.fixture
def scored_poseset(animal, make_compound):
    """Three poses with scores from two scoring methods (one unversioned) and a
    pose method; the first pose duplicates a score in its metadata, as load_sdf
    does. The last pose has no scores and no pose method.
    """
    from designdb.models import (
        PoseMethodJunctionModel,
        PoseMethodModel,
        PoseModel,
        ScoreValueModel,
        ScoringMethodModel,
    )
    from designdb.sets.pose import PoseSet
    from rdkit import Chem
    from rdkit.Chem import AllChem

    compound = make_compound("c1ccc(Cl)cc1")  # chlorobenzene
    mol = Chem.AddHs(Chem.MolFromSmiles("c1ccc(Cl)cc1"))
    AllChem.EmbedMolecule(mol, randomSeed=42)

    poses = [
        PoseModel.objects.create(
            compound=compound,
            target=animal.target,
            pose_alias=f"export-{i}",
            pose_mol=mol,
            pose_metadata={"export_vina": 99.0, "note": "kept"} if i == 0 else {},
        )
        for i in range(3)
    ]

    # get_or_create: the session database is shared between tests and the
    # method tables are unique on (name, version)
    vina, _ = ScoringMethodModel.objects.get_or_create(
        method_name="export_vina", method_version="1.2.5"
    )
    cnn, _ = ScoringMethodModel.objects.get_or_create(
        method_name="export_cnn", method_version=None
    )
    pose_method, _ = PoseMethodModel.objects.get_or_create(
        pose_method_name="export_dock", pose_method_version="2.0"
    )

    ScoreValueModel.objects.bulk_create(
        [
            ScoreValueModel(
                pose=poses[0], compound=compound, scoring_method=vina, score={"score": -7.1}
            ),
            ScoreValueModel(
                pose=poses[0], compound=compound, scoring_method=cnn, score={"score": 0.83}
            ),
            ScoreValueModel(
                pose=poses[1], compound=compound, scoring_method=vina, score={"score": -6.4}
            ),
        ]
    )
    PoseMethodJunctionModel.objects.bulk_create(
        [PoseMethodJunctionModel(pose=p, pose_method=pose_method) for p in poses[:2]]
    )

    return PoseSet(PoseModel.objects.filter(pk__in=[p.pk for p in poses])), poses


def test_get_df_scores_from_score_table(scored_poseset):
    pset, poses = scored_poseset

    df = pset.get_df(metadata=True)

    assert "energy_score" not in df.columns
    assert "distance_score" not in df.columns

    assert df.loc[poses[0].pk, "export_vina (1.2.5)"] == pytest.approx(-7.1)
    assert df.loc[poses[1].pk, "export_vina (1.2.5)"] == pytest.approx(-6.4)
    assert df.loc[poses[0].pk, "export_cnn"] == pytest.approx(0.83)
    assert df["export_cnn"].isna()[poses[1].pk]
    assert df["export_vina (1.2.5)"].isna()[poses[2].pk]

    assert df.loc[poses[0].pk, "pose_method_name"] == "export_dock"
    assert df.loc[poses[0].pk, "pose_method_version"] == "2.0"
    assert df["pose_method_name"].isna()[poses[2].pk]

    # score duplicated in metadata is dropped, other metadata stays
    assert "export_vina" not in df.columns
    assert df.loc[poses[0].pk, "note"] == "kept"


def test_get_df_scoring_methods_filter_and_opt_out(scored_poseset):
    pset, _ = scored_poseset

    df = pset.get_df(scoring_methods=[("export_vina", "1.2.5")])
    assert "export_vina (1.2.5)" in df.columns
    assert "export_cnn" not in df.columns

    df = pset.get_df(scores=False, pose_method=False)
    assert "export_vina (1.2.5)" not in df.columns
    assert "export_cnn" not in df.columns
    assert "pose_method_name" not in df.columns


def test_write_sdf_includes_scores_and_pose_method(scored_poseset, tmp_path):
    from rdkit.Chem import PandasTools

    pset, poses = scored_poseset
    out = tmp_path / "export.sdf"

    pset.write_sdf(str(out))

    sdf = PandasTools.LoadSDF(str(out)).set_index("ID")
    first = sdf.loc[poses[0].pose_alias]
    assert float(first["export_vina (1.2.5)"]) == pytest.approx(-7.1)
    assert float(first["export_cnn"]) == pytest.approx(0.83)
    assert first["pose_method_name"] == "export_dock"
    assert first["pose_method_version"] == "2.0"


def test_to_fragalysis_ignores_stale_hippo_ids_in_metadata(scored_poseset, tmp_path):
    """A pose re-loaded from an earlier export carries that export's
    'HIPPO Pose ID' in its metadata; it must not become a second ID column."""
    from designdb.models import InspirationModel, PoseModel
    from designdb.sets.pose import PoseSet
    from rdkit.Chem import PandasTools

    _, poses = scored_poseset
    reference, pose = poses[2], poses[0]

    pose.pose_reference = reference.pk
    pose.pose_metadata = {"HIPPO Pose ID": 317.0, "export_vina": 99.0}
    pose.save()
    InspirationModel.objects.create(original_pose=reference, derivative_pose=pose)

    out = tmp_path / "fragalysis.sdf"
    PoseSet(PoseModel.objects.filter(pk=pose.pk)).to_fragalysis(
        str(out),
        method="test",
        submitter_name="test",
        submitter_email="test@example.com",
        submitter_institution="test",
    )

    sdf = PandasTools.LoadSDF(str(out))
    record = sdf[sdf["ID"] == pose.pose_alias].iloc[0]
    assert int(record["HIPPO Pose ID"]) == pose.pk
    assert float(record["export_vina (1.2.5)"]) == pytest.approx(-7.1)
    assert "export_vina" not in sdf.columns


def test_metadata_from_record_skips_hippo_ids():
    from designdb.services.ingestion import metadata_from_record

    metadata = metadata_from_record(
        {"HIPPO Pose ID": "317", "HIPPO Compound ID": "12", "note": "kept"},
        ignore_fields=[],
        convert_floats=False,
    )

    assert metadata == {"note": "kept"}


### many-to-many columns (inspirations, tags, subsite tags)


@pytest.fixture
def tagged_poseset(animal, make_compound):
    """Two poses with two inspirations each, on a dedicated target. The first
    pose has no tags or subsites; the second has three pose tags, two subsites
    and a compound with two compound tags in this target (and one more in
    another target, which must not show up).

    Several many-to-many relations per pose: aggregating them over joins in one
    query multiplied their rows (``[None, None]`` tags for an untagged pose with
    two inspirations).
    """
    from designdb.models import (
        CompoundTagJunctionModel,
        CompoundTagModel,
        InspirationModel,
        PoseModel,
        PoseTagJunctionModel,
        PoseTagModel,
        SubsiteModel,
        SubsiteTagModel,
        TargetModel,
    )
    from designdb.sets.pose import PoseSet
    from rdkit import Chem
    from rdkit.Chem import AllChem

    target, other_target = (
        TargetModel.objects.create(
            target_name=f"m2m-test-{TargetModel.objects.count()}",
            project=animal.target.project,
        )
        for _ in range(2)
    )
    compound = make_compound("c1ccc(C#N)cc1")  # benzonitrile
    mol = Chem.AddHs(Chem.MolFromSmiles("c1ccc(C#N)cc1"))
    AllChem.EmbedMolecule(mol, randomSeed=42)

    def pose(alias):
        return PoseModel.objects.create(
            compound=compound, target=target, pose_alias=alias, pose_mol=mol
        )

    hits = [pose(f"m2m-hit-{i}") for i in range(4)]
    untagged, tagged = pose("m2m-untagged"), pose("m2m-tagged")

    InspirationModel.objects.bulk_create(
        [
            InspirationModel(original_pose=hits[0], derivative_pose=untagged),
            InspirationModel(original_pose=hits[1], derivative_pose=untagged),
            InspirationModel(original_pose=hits[2], derivative_pose=tagged),
            InspirationModel(original_pose=hits[3], derivative_pose=tagged),
        ]
    )

    pose_tags = [
        PoseTagModel.objects.get_or_create(pose_tag_name=f"m2m-pose-{c}")[0]
        for c in "cab"
    ]
    PoseTagJunctionModel.objects.bulk_create(
        [PoseTagJunctionModel(pose=tagged, pose_tag=t) for t in pose_tags]
    )

    subsites = [
        SubsiteModel.objects.create(target=target, subsite_name=f"m2m-site-{c}")
        for c in "ba"
    ]
    SubsiteTagModel.objects.bulk_create(
        [SubsiteTagModel(pose=tagged, subsite=s) for s in subsites]
    )

    compound_tags = [
        CompoundTagModel.objects.get_or_create(compound_tag_name=f"m2m-cmpd-{c}")[0]
        for c in "yxz"
    ]
    CompoundTagJunctionModel.objects.bulk_create(
        [
            CompoundTagJunctionModel(compound=compound, target=target, compound_tag=t)
            for t in compound_tags[:2]
        ]
        + [
            CompoundTagJunctionModel(
                compound=compound, target=other_target, compound_tag=compound_tags[2]
            )
        ]
    )

    pset = PoseSet(PoseModel.objects.filter(pk__in=[untagged.pk, tagged.pk]))
    return pset, hits, untagged, tagged


M2M_FLAGS = dict(
    inspiration_ids=True,
    inspiration_aliases=True,
    pose_tags=True,
    compound_tags=True,
    subsite_tags=True,
)


def test_get_df_m2m_columns_are_not_multiplied(tagged_poseset):
    pset, hits, untagged, tagged = tagged_poseset

    df = pset.get_df(**M2M_FLAGS)

    assert df.loc[tagged.pk, "inspiration_ids"] == [hits[2].pk, hits[3].pk]
    assert df.loc[tagged.pk, "inspiration_aliases"] == ["m2m-hit-2", "m2m-hit-3"]
    assert df.loc[tagged.pk, "pose_tags"] == ["m2m-pose-a", "m2m-pose-b", "m2m-pose-c"]
    assert df.loc[tagged.pk, "subsite_tags"] == ["m2m-site-a", "m2m-site-b"]
    # compound tags of this pose's target only
    assert df.loc[tagged.pk, "compound_tags"] == ["m2m-cmpd-x", "m2m-cmpd-y"]


def test_get_df_m2m_columns_empty_lists(tagged_poseset):
    pset, hits, untagged, _ = tagged_poseset

    df = pset.get_df(**M2M_FLAGS)

    assert df.loc[untagged.pk, "inspiration_ids"] == [hits[0].pk, hits[1].pk]
    assert df.loc[untagged.pk, "pose_tags"] == []
    assert df.loc[untagged.pk, "subsite_tags"] == []
    # compound tags belong to the compound, shared by both poses
    assert df.loc[untagged.pk, "compound_tags"] == ["m2m-cmpd-x", "m2m-cmpd-y"]


def test_get_df_derivative_ids(tagged_poseset):
    from designdb.models import PoseModel
    from designdb.sets.pose import PoseSet

    _, hits, untagged, tagged = tagged_poseset

    df = PoseSet(PoseModel.objects.filter(pk__in=[h.pk for h in hits])).get_df(
        derivative_ids=True
    )

    assert df.loc[hits[0].pk, "derivative_ids"] == [untagged.pk]
    assert df.loc[hits[3].pk, "derivative_ids"] == [tagged.pk]
    # derivatives, not inspirations: the hits have none of the latter
    df = PoseSet(PoseModel.objects.filter(pk=untagged.pk)).get_df(derivative_ids=True)
    assert df.loc[untagged.pk, "derivative_ids"] == []


def test_get_df_expand_tags(tagged_poseset):
    pset, _, untagged, tagged = tagged_poseset

    df = pset.get_df(pose_tags=True, expand_tags=True)

    assert "pose_tags" not in df.columns
    assert df.loc[tagged.pk, "m2m-pose-a"]
    assert not df.loc[untagged.pk, "m2m-pose-a"]


def test_get_df_tags_is_deprecated_alias_for_pose_tags(tagged_poseset):
    pset, _, _, tagged = tagged_poseset

    df = pset.get_df(tags=True)

    assert df.loc[tagged.pk, "pose_tags"] == ["m2m-pose-a", "m2m-pose-b", "m2m-pose-c"]


def test_get_df_subsites_is_deprecated_alias_for_subsite_tags(tagged_poseset):
    pset, _, _, tagged = tagged_poseset

    df = pset.get_df(subsites=True)

    assert df.loc[tagged.pk, "subsite_tags"] == ["m2m-site-a", "m2m-site-b"]


def test_get_df_m2m_columns_on_sliced_set(tagged_poseset):
    """PoseSet[:n] slices the queryset; the m2m lookups subquery it."""
    pset, _, _, _ = tagged_poseset

    df = pset[:1].get_df(**M2M_FLAGS)

    assert len(df) == 1


def test_write_sdf_m2m_fields(tagged_poseset, tmp_path):
    from rdkit.Chem import PandasTools

    pset, hits, _, _ = tagged_poseset
    out = tmp_path / "m2m.sdf"

    pset.write_sdf(str(out), **M2M_FLAGS)

    sdf = PandasTools.LoadSDF(str(out)).set_index("ID")
    tagged = sdf.loc["m2m-tagged"]
    assert tagged["inspiration_ids"] == f"{hits[2].pk},{hits[3].pk}"
    assert tagged["inspiration_aliases"] == "m2m-hit-2,m2m-hit-3"
    assert tagged["pose_tags"] == "m2m-pose-a,m2m-pose-b,m2m-pose-c"
    assert tagged["compound_tags"] == "m2m-cmpd-x,m2m-cmpd-y"
    assert tagged["subsite_tags"] == "m2m-site-a,m2m-site-b"

    untagged = sdf.loc["m2m-untagged"]
    assert untagged["pose_tags"] == ""
    assert untagged["subsite_tags"] == ""


def test_write_sdf_omits_m2m_fields_by_default(tagged_poseset, tmp_path):
    from rdkit.Chem import PandasTools

    pset, _, _, _ = tagged_poseset
    out = tmp_path / "default.sdf"

    pset.write_sdf(str(out))

    sdf = PandasTools.LoadSDF(str(out))
    for field in ("pose_tags", "compound_tags", "subsite_tags", "tags"):
        assert field not in sdf.columns


### write_sdf name_col


@pytest.mark.parametrize("name_col", ["alias", "name", "id", "longcode", "inchikey"])
def test_write_sdf_name_col(scored_poseset, tmp_path, name_col):
    """Every ``name_col`` mode names the records; ``id`` is the DataFrame index
    and ``longcode`` a pose metadata key (missing on the other poses)."""
    from designdb.models import PoseModel
    from rdkit.Chem import PandasTools

    pset, poses = scored_poseset
    poses[0].pose_metadata = {"longcode": "LC-0"}
    poses[0].save()
    PoseModel.objects.filter(pk__in=[p.pk for p in poses]).update(
        pose_inchikey="INCHIKEY-TEST"
    )
    out = tmp_path / f"{name_col}.sdf"

    pset.write_sdf(str(out), name_col=name_col)

    sdf = PandasTools.LoadSDF(str(out))
    expected = {
        "alias": [p.pose_alias for p in poses],
        "name": [p.pose_alias for p in poses],
        "id": [str(p.pk) for p in poses],
        "longcode": ["LC-0", "None", "None"],
        "inchikey": ["INCHIKEY-TEST"] * 3,
    }[name_col]
    assert sorted(sdf["ID"]) == sorted(expected)
    assert "_Name" not in sdf.columns


### to_fragalysis


FRAGALYSIS_ARGS = dict(
    method="test",
    submitter_name="test",
    submitter_email="test@example.com",
    submitter_institution="test",
)


def set_reference(pose, reference):
    pose.pose_reference = reference.pk
    pose.save()


def fragalysis_records(path):
    """The SDF records of a Fragalysis upload by name, without the header"""
    from rdkit.Chem import PandasTools

    sdf = PandasTools.LoadSDF(str(path)).set_index("ID")
    return sdf.drop(index="ver_1.2"), sdf.loc["ver_1.2"]


def test_to_fragalysis_ref_mols_tags_and_compound_tags(tagged_poseset, tmp_path):
    pset, hits, untagged, tagged = tagged_poseset
    set_reference(untagged, hits[0])
    set_reference(tagged, hits[0])
    out = tmp_path / "fragalysis.sdf"

    pset.to_fragalysis(str(out), compound_tags=True, **FRAGALYSIS_ARGS)

    records, header = fragalysis_records(out)
    assert records.loc["m2m-tagged", "ref_mols"] == "m2m-hit-2,m2m-hit-3"
    assert records.loc["m2m-untagged", "ref_mols"] == "m2m-hit-0,m2m-hit-1"
    assert records.loc["m2m-tagged", "tags"] == "m2m-pose-a,m2m-pose-b,m2m-pose-c"
    assert records.loc["m2m-untagged", "tags"] == ""
    assert records.loc["m2m-tagged", "compound tags"] == "m2m-cmpd-x,m2m-cmpd-y"
    assert records.loc["m2m-tagged", "subsite tags"] == "m2m-site-a,m2m-site-b"
    # every field is described in the header
    assert header["compound tags"] == "compound tags"
    assert header["ref_mols"] == "fragment inspirations"


def test_to_fragalysis_ref_mols_falls_back_to_self(tagged_poseset, tmp_path):
    from designdb.models import PoseModel
    from designdb.sets.pose import PoseSet

    _, hits, _, tagged = tagged_poseset
    set_reference(hits[1], hits[0])
    set_reference(tagged, hits[0])
    out = tmp_path / "fragalysis.sdf"

    PoseSet(PoseModel.objects.filter(pk__in=[hits[1].pk, tagged.pk])).to_fragalysis(
        str(out), skip_no_inspirations=False, **FRAGALYSIS_ARGS
    )

    records, _ = fragalysis_records(out)
    assert records.loc["m2m-hit-1", "ref_mols"] == "m2m-hit-1"
    assert records.loc["m2m-tagged", "ref_mols"] == "m2m-hit-2,m2m-hit-3"


def test_to_fragalysis_skip_filters_combine(tagged_poseset, tmp_path):
    """Only poses with both a reference and inspirations are exported."""
    from designdb.models import PoseModel
    from designdb.sets.pose import PoseSet

    _, hits, untagged, tagged = tagged_poseset
    set_reference(hits[1], hits[0])  # reference, no inspirations
    set_reference(tagged, hits[0])  # reference and inspirations
    # untagged: inspirations, no reference
    out = tmp_path / "fragalysis.sdf"

    PoseSet(
        PoseModel.objects.filter(pk__in=[hits[1].pk, untagged.pk, tagged.pk])
    ).to_fragalysis(str(out), **FRAGALYSIS_ARGS)

    records, _ = fragalysis_records(out)
    assert list(records.index) == ["m2m-tagged"]


def test_to_fragalysis_tags_is_deprecated_alias(tagged_poseset, tmp_path):
    pset, hits, untagged, tagged = tagged_poseset
    set_reference(untagged, hits[0])
    set_reference(tagged, hits[0])
    out = tmp_path / "fragalysis.sdf"

    pset.to_fragalysis(str(out), tags=False, **FRAGALYSIS_ARGS)

    records, header = fragalysis_records(out)
    assert "tags" not in records.columns
    assert "compound tags" not in records.columns


def test_to_fragalysis_generate_pdbs_matches_rows_to_poses(
    tagged_poseset, tmp_path, monkeypatch
):
    """Each generated PDB belongs to its own row's pose, also when the set holds
    a pose (here the first one) that is skipped for having no reference.

    ``Pose.complex_system`` is not ported yet; a stub writes the pose alias.
    """
    from pathlib import Path
    from zipfile import ZipFile

    from designdb.components.pose import Pose

    class StubSystem:
        def __init__(self, alias):
            self.alias = alias

        def write(self, path, verbosity=0):
            Path(path).write_text(self.alias)

    monkeypatch.setattr(
        Pose,
        "complex_system",
        property(lambda self: StubSystem(self.pose_alias)),
        raising=False,
    )

    pset, hits, untagged, tagged = tagged_poseset
    assert list(pset.ids) == [untagged.pk, tagged.pk]
    set_reference(tagged, hits[0])  # untagged has no reference
    out = tmp_path / "fragalysis.sdf"

    pset.to_fragalysis(str(out), generate_pdbs=True, **FRAGALYSIS_ARGS)

    records, _ = fragalysis_records(out)
    pdb_name = records.loc["m2m-tagged", "ref_pdb"]
    with ZipFile(tmp_path / "fragalysis_pdbs.zip") as z:
        assert z.namelist() == [pdb_name]
        assert z.read(pdb_name).decode() == "m2m-tagged"


def test_to_fragalysis_keeps_poses_without_reference(tagged_poseset, tmp_path):
    """skip_no_reference=False: a pose without reference (NaN reference_id in
    the DataFrame) is exported with an empty protein reference."""
    pset, hits, untagged, tagged = tagged_poseset
    set_reference(tagged, hits[0])
    out = tmp_path / "fragalysis.sdf"

    pset.to_fragalysis(str(out), skip_no_reference=False, **FRAGALYSIS_ARGS)

    records, _ = fragalysis_records(out)
    assert records.loc["m2m-tagged", "ref_pdb"] == "m2m-hit-0"
    assert records.loc["m2m-untagged", "ref_pdb"] == "None"
