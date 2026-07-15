"""CompoundSet element-type and indexing tests (SQLite tier).

CompoundSet yields ``Compound`` component objects (like PoseSet yields ``Pose``)
regardless of how it was constructed, and supports positional int/slice indexing.
"""

import pytest

pytestmark = pytest.mark.sqlite


@pytest.fixture
def compoundset(make_compound):
    """A CompoundSet of 10 distinct compounds."""
    from designdb.models import CompoundModel
    from designdb.sets.compound import CompoundSet

    smiles = ["C", "CC", "CCC", "CCCC", "CCCCC", "c1ccccc1", "CCO", "CCN", "CCCl", "CCBr"]
    ids = [make_compound(s).pk for s in smiles]
    return CompoundSet(CompoundModel.objects.filter(pk__in=ids))


def test_compoundset_from_values_list_yields_compounds(make_compound):
    """Constructing from a values_list of ids (as RouteSet.products does) yields
    Compound components, not ints or CompoundModels."""
    from designdb.components.compound import Compound
    from designdb.models import CompoundModel
    from designdb.sets.compound import CompoundSet

    ids = [make_compound(s).pk for s in ["C", "CC", "CCC"]]
    values_list = CompoundModel.objects.filter(pk__in=ids).values_list(
        "id", flat=True
    )

    cset = CompoundSet(values_list)

    assert isinstance(cset[0], Compound)
    assert all(isinstance(c, Compound) for c in cset)
    assert set(cset.ids) == set(ids)


def test_compoundset_copy_yields_compounds(compoundset):
    """copy() (built from self.ids, a values_list) must yield Compounds."""
    from designdb.components.compound import Compound

    copied = compoundset.copy()

    assert isinstance(copied[0], Compound)
    assert list(copied.ids) == list(compoundset.ids)


def test_compoundset_from_set_and_instances(make_compound):
    """A set of ids and a list of model instances both yield Compounds."""
    from designdb.components.compound import Compound
    from designdb.sets.compound import CompoundSet

    models = [make_compound(s) for s in ["C", "CC", "CCC"]]
    ids = {m.pk for m in models}

    from_set = CompoundSet(ids)  # set of ids
    from_instances = CompoundSet(models)  # list of CompoundModel instances

    assert isinstance(from_set[0], Compound)
    assert isinstance(from_instances[0], Compound)
    assert set(from_set.ids) == ids
    assert set(from_instances.ids) == ids


def test_compoundset_slice_returns_positional_subset(compoundset):
    from designdb.sets.compound import CompoundSet

    sliced = compoundset[1:5]

    assert isinstance(sliced, CompoundSet)
    assert len(sliced) == 4
    assert list(sliced.ids) == list(compoundset.ids)[1:5]


def test_compoundset_slice_full_and_out_of_range(compoundset):
    assert len(compoundset[:]) == len(compoundset)
    assert len(compoundset[100:200]) == 0


def test_compoundset_slice_after_evaluation(compoundset):
    """Slicing must work even after the underlying queryset was evaluated."""
    from designdb.sets.compound import CompoundSet

    list(compoundset)  # force-evaluate the underlying queryset (real-world usage)

    sliced = compoundset[1:5]

    assert isinstance(sliced, CompoundSet)
    assert len(sliced) == 4
    assert list(sliced.ids) == list(compoundset.ids)[1:5]


def test_compoundset_int_indexing_is_positional(compoundset):
    """cset[i] selects the i-th member (as a Compound) by position."""
    from designdb.components.compound import Compound

    ids = list(compoundset.ids)

    first = compoundset[0]
    assert isinstance(first, Compound)
    assert first.id == ids[0]
    assert first.pk == ids[0]  # Compound.pk alias

    assert compoundset[1].id == ids[1]
    assert compoundset[-1].id == ids[-1]  # negative indexing -> last compound


def test_compoundset_int_index_out_of_range_raises(compoundset):
    with pytest.raises(IndexError):
        compoundset[len(compoundset)]


def test_compoundset_add_sub_accept_compound(compoundset):
    """+/- round-trip with a Compound element (iteration/indexing yield Compound)."""
    from designdb.components.compound import Compound

    first = compoundset[0]
    assert isinstance(first, Compound)

    removed = compoundset - first
    assert first.id not in list(removed.ids)
    assert len(removed) == len(compoundset) - 1

    readded = removed + first
    assert first.id in list(readded.ids)
    assert len(readded) == len(compoundset)


def test_compoundset_contains_accepts_compound(compoundset):
    from designdb.components.compound import Compound

    first = compoundset[0]
    assert isinstance(first, Compound)
    assert first in compoundset


def test_compoundset_get_by_smiles_returns_compound(compoundset):
    """get_by_smiles yields a Compound component (matching iteration/indexing)."""
    from designdb.components.compound import Compound

    comp = compoundset.get_by_smiles("CCO")  # ethanol is in the fixture

    assert isinstance(comp, Compound)
    assert comp.smiles == "CCO"
