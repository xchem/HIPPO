"""Tag resolution tests (SQLite tier).

The tag vocabulary (``compound_tags`` / ``pose_tags``) is maintained outside
HIPPO, through a pathway that bypasses this library. Ingestion therefore
*resolves* tag names against existing rows and never creates them; the
``add_tag`` helpers still create, for test instances, but warn and can be
switched off via ``designdb.settings.ALLOW_TAG_CREATION``.
"""

import pytest

pytestmark = pytest.mark.sqlite


def queryset_for(compound):
    """A one-member queryset, for wrapping a compound in a CompoundSet."""
    from designdb.models import CompoundModel

    return CompoundModel.objects.filter(pk=compound.pk)


def compound_tags_of(compound, target):
    from designdb.models import CompoundTagJunctionModel

    return set(
        CompoundTagJunctionModel.objects.filter(
            compound=compound, target=target
        ).values_list("compound_tag__compound_tag_name", flat=True)
    )


@pytest.fixture
def compound_tag(animal):
    """An existing compound-tag vocabulary row."""
    from designdb.models import CompoundTagModel

    tag, _ = CompoundTagModel.objects.get_or_create(compound_tag_name="res-known-cmpd")
    return tag


@pytest.fixture
def pose_tag(animal):
    """An existing pose-tag vocabulary row."""
    from designdb.models import PoseTagModel

    tag, _ = PoseTagModel.objects.get_or_create(pose_tag_name="res-known-pose")
    return tag


### resolve_tags


def test_resolve_tags_returns_existing_rows(compound_tag, pose_tag):
    from designdb.services.compound import CompoundTagService
    from designdb.services.pose import PoseTagService

    assert CompoundTagService.resolve_tags(["res-known-cmpd"]) == [compound_tag]
    assert PoseTagService.resolve_tags(["res-known-pose"]) == [pose_tag]


def test_resolve_tags_returns_a_list_not_a_lazy_queryset(compound_tag):
    """ingest_sdf iterates the result once per chunk; a queryset would re-query."""
    from designdb.services.compound import CompoundTagService

    assert isinstance(CompoundTagService.resolve_tags(["res-known-cmpd"]), list)


def test_resolve_tags_strips_whitespace(compound_tag):
    """Regression: rows were created stripped but selected unstripped."""
    from designdb.services.compound import CompoundTagService

    assert CompoundTagService.resolve_tags([" res-known-cmpd "]) == [compound_tag]


def test_resolve_tags_ignores_blanks_and_duplicates(compound_tag):
    from designdb.services.compound import CompoundTagService

    assert CompoundTagService.resolve_tags([]) == []
    assert CompoundTagService.resolve_tags(["", "  ", None]) == []
    assert CompoundTagService.resolve_tags(
        ["res-known-cmpd", "res-known-cmpd"]
    ) == [compound_tag]


def test_resolve_tags_rejects_none():
    from designdb.services.compound import CompoundTagService

    with pytest.raises(ValueError):
        CompoundTagService.resolve_tags(None)


def test_resolve_tags_raises_naming_every_missing_tag(compound_tag):
    from designdb.services.compound import CompoundTagService
    from designdb.utils import MissingTagError

    with pytest.raises(MissingTagError) as exc:
        CompoundTagService.resolve_tags(
            ["res-known-cmpd", "res-absent-a", "res-absent-b"]
        )

    message = str(exc.value)
    assert "res-absent-a" in message
    assert "res-absent-b" in message
    # the tag that does exist is not part of the complaint
    assert "res-known-cmpd" not in message


def test_resolve_tags_creates_nothing(animal):
    from designdb.models import CompoundTagModel
    from designdb.services.compound import CompoundTagService
    from designdb.utils import MissingTagError

    before = CompoundTagModel.objects.count()

    with pytest.raises(MissingTagError):
        CompoundTagService.resolve_tags(["res-never-created"])

    assert CompoundTagModel.objects.count() == before
    assert not CompoundTagModel.objects.filter(
        compound_tag_name="res-never-created"
    ).exists()


def test_resolve_tags_is_a_value_error():
    """MissingTagError subclasses ValueError, matching MethodService."""
    from designdb.utils import MissingTagError

    assert issubclass(MissingTagError, ValueError)


### ingestion


def test_load_sdf_rejects_unknown_tag_before_touching_the_file(animal, tmp_path):
    """Tags resolve before any file IO, so a bad tag beats a missing SDF."""
    from designdb.models import CompoundModel, PoseModel
    from designdb.utils import MissingTagError

    compounds_before = CompoundModel.objects.count()
    poses_before = PoseModel.objects.count()

    with pytest.raises(MissingTagError):
        animal.load_sdf(
            path=tmp_path / "does-not-exist.sdf",
            compound_tags=["res-absent-ingest"],
        )

    assert CompoundModel.objects.count() == compounds_before
    assert PoseModel.objects.count() == poses_before


### add_tag


def test_compoundset_add_tag_creates_with_a_warning(animal, make_compound):
    from designdb.models import CompoundTagModel
    from designdb.sets.compound import CompoundSet

    compound = make_compound("c1ccc(Cl)cc1")  # chlorobenzene
    cset = CompoundSet(queryset_for(compound))

    cset.add_tag("res-debug-created", target=animal.target)

    assert CompoundTagModel.objects.filter(
        compound_tag_name="res-debug-created"
    ).exists()
    assert "res-debug-created" in compound_tags_of(compound, animal.target)


def test_compoundset_add_tag_blocked_when_creation_disabled(animal, make_compound):
    from unittest.mock import patch

    from designdb.models import CompoundTagModel
    from designdb.sets.compound import CompoundSet
    from designdb.utils import MissingTagError

    compound = make_compound("c1ccc(Br)cc1")  # bromobenzene
    cset = CompoundSet(queryset_for(compound))

    with patch("designdb.settings.ALLOW_TAG_CREATION", False):
        with pytest.raises(MissingTagError):
            cset.add_tag("res-blocked", target=animal.target)

    assert not CompoundTagModel.objects.filter(
        compound_tag_name="res-blocked"
    ).exists()


def test_compound_add_tag_blocked_when_creation_disabled(animal, make_compound):
    from unittest.mock import patch

    from designdb.components.compound import Compound
    from designdb.models import CompoundTagModel
    from designdb.utils import MissingTagError

    compound = Compound(make_compound("c1ccc(I)cc1"))  # iodobenzene

    with patch("designdb.settings.ALLOW_TAG_CREATION", False):
        with pytest.raises(MissingTagError):
            compound.add_tag("res-blocked-component", target=animal.target)

    assert not CompoundTagModel.objects.filter(
        compound_tag_name="res-blocked-component"
    ).exists()


def test_poseset_add_tag_accepts_an_existing_tag(animal, make_compound, pose_tag):
    """Regression: a bare PoseTagModel(...).save() hit the uc_pose_tag constraint."""
    from designdb.models import PoseModel
    from designdb.sets.pose import PoseSet

    compound = make_compound("c1ccc(C)cc1")  # toluene
    pose = PoseModel.objects.create(
        compound=compound, target=animal.target, pose_alias="res-tag-pose"
    )
    pset = PoseSet(PoseModel.objects.filter(pk=pose.pk))

    pset.add_tag(pose_tag.pose_tag_name)  # must not raise IntegrityError

    assert pose_tag.pose_tag_name in {t.pose_tag_name for t in pose.tags.all()}
