"""Pose tags from Fragalysis metadata.csv tag columns (SQLite tier).

Fragalysis names tag columns ``[<category>] <tag name>``. Only the ``Data type``,
``Site``, ``Library`` and ``DMTA cycle`` categories become pose tags, under the
bare tag name; every other category is ignored.
"""

import pytest

pytestmark = pytest.mark.sqlite

COLUMNS = [
    "Code",
    "Long code",
    "Pose",
    "[Data type] Fragment screen",
    "[Site] my site tag",
    "[Library] DSI poised",
    "[DMTA cycle] Cycle01",
    "[Other] upload_1 2026-11-16",
    "[Release] Unreleased",
    "[User defined] my wonderful tag",
    "[Pose] Cycle02",
    "[Compound] Product",
    "Main status",
]


def write_metadata(path, rows):
    import pandas as pd

    pd.DataFrame(rows, columns=COLUMNS).to_csv(path, index=False)
    return path


def row(code, **truthy):
    """A metadata row; tag columns are False unless named in ``truthy``."""
    values = {c: False for c in COLUMNS if c.startswith("[")}
    values.update(truthy)
    values.update({"Code": code, "Long code": f"T-{code}", "Pose": code})
    values["Main status"] = "Good"
    return values


@pytest.fixture
def registered_tags(animal):
    from designdb.models import PoseTagModel

    names = ["Fragment screen", "my site tag", "DSI poised", "Cycle01"]
    return {
        name: PoseTagModel.objects.get_or_create(pose_tag_name=name)[0]
        for name in names
    }


def test_parse_tag_column(animal):  # animal puts designdb on the path
    from designdb.utils_frag import parse_tag_column

    assert parse_tag_column("[Site] my site tag") == ("Site", "my site tag")
    assert parse_tag_column(" [DMTA cycle]  Cycle01 ") == ("DMTA cycle", "Cycle01")
    assert parse_tag_column("Main status") is None
    assert parse_tag_column("CanonSites alias") is None


def test_only_imported_categories_are_curated(tmp_path, registered_tags):
    from designdb.services.pose import PoseTagService

    csv = write_metadata(tmp_path / "metadata.csv", [row("A")])
    tagger = PoseTagService(csv)

    assert tagger._curated_tag_cols == {
        "[Data type] Fragment screen": "Fragment screen",
        "[Site] my site tag": "my site tag",
        "[Library] DSI poised": "DSI poised",
        "[DMTA cycle] Cycle01": "Cycle01",
    }


def test_ignored_categories_do_not_need_registering(tmp_path, registered_tags):
    """Regression: an unregistered '[Other]' tag true everywhere broke add_hits."""
    from designdb.services.pose import PoseTagService

    truthy = {
        "[Other] upload_1 2026-11-16": True,
        "[Release] Unreleased": True,
        "[User defined] my wonderful tag": True,
        "[Pose] Cycle02": True,
        "[Compound] Product": True,
    }
    csv = write_metadata(tmp_path / "metadata.csv", [row("A", **truthy)])

    tags, _ = PoseTagService(csv).tags_and_meta(code="A", longcode="T-A")

    assert tags == []


def test_imported_tags_resolve_to_bare_names(tmp_path, registered_tags):
    from designdb.services.pose import PoseTagService

    csv = write_metadata(
        tmp_path / "metadata.csv",
        [
            row("A", **{"[Site] my site tag": True, "[DMTA cycle] Cycle01": True}),
            row("B", **{"[Library] DSI poised": True}),
        ],
    )
    tagger = PoseTagService(csv)

    tags_a, meta_a = tagger.tags_and_meta(code="A", longcode="T-A")
    tags_b, _ = tagger.tags_and_meta(code="B", longcode="T-B")

    assert {t.pose_tag_name for t in tags_a} == {"my site tag", "Cycle01"}
    assert {t.pose_tag_name for t in tags_b} == {"DSI poised"}
    assert meta_a["fragalysis_longcode"] == "T-A"


def test_unregistered_imported_tag_raises(tmp_path, animal):
    from designdb.models import PoseTagModel
    from designdb.services.pose import PoseTagService
    from designdb.utils import MissingTagError

    csv = write_metadata(
        tmp_path / "metadata.csv", [row("A", **{"[Site] my site tag": True})]
    )

    # the session-scoped db may hold it from another test
    PoseTagModel.objects.filter(pose_tag_name="my site tag").delete()

    with pytest.raises(MissingTagError, match="my site tag"):
        PoseTagService(csv)
