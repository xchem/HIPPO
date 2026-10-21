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
