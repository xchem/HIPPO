import json

import mcol
import mrich

from designdb.models import Component, Reaction, Route

from .recipe import Recipe


# name conflict with route model. Trying to get rid of this entirely
class RouteObj(Recipe):
    """A recipe with a single product, that is stored in the database"""

    def __init__(
        self,
        *,
        route_id: int,
        product: 'IngredientSet',
        reactants: 'IngredientSet',
        intermediates: 'IngredientSet',
        reactions: 'ReactionSet',
    ) -> None:
        """Route initialisation"""

        # avoiding circular imports
        from designdb.sets.compound import IngredientSet
        from designdb.sets.reaction import ReactionSet

        # check typing
        assert isinstance(product, IngredientSet)
        assert isinstance(reactants, IngredientSet)
        assert isinstance(intermediates, IngredientSet)
        assert isinstance(reactions, ReactionSet)

        assert len(product) == 1
        assert isinstance(route_id, int)
        assert route_id

        self._id = route_id
        self._products = product
        self._product_id = product.ids[0]
        self._reactants = reactants
        self._intermediates = intermediates
        self._reactions = reactions

    ### FACTORIES

    @classmethod
    def from_json(cls, path: 'str | Path', data: dict = None) -> 'Route':
        """Load a serialised route from a JSON file

        :param db: database to link
        :param path: path to JSON
        :param data: serialised data (Default value = None)

        """

        # avoiding circular imports
        from designdb.sets.compound import IngredientSet
        from designdb.sets.reaction import ReactionSet

        if data is None:
            data = json.load(open(path))

        self = cls.__new__(cls)

        self._id = data['id']

        self._product_id = data['product_id']
        self._products = IngredientSet.from_compounds(
            compounds=None, ids=[self._product_id]
        )  # IngredientSet

        self._reactants = IngredientSet.from_json(
            path=None,
            data=data['reactants']['data'],
            supplier=data['reactants']['supplier'],
        )
        self._intermediates = IngredientSet.from_json(
            path=None,
            data=data['intermediates']['data'],
            supplier=data['intermediates']['supplier'],
        )
        self._reactions = ReactionSet(
            Reaction.objects.filter(pk__in=data['reactions']['indices'])
        )  # ReactionSet

        return self

    @classmethod
    def get_route(
        cls,
        *,
        id: int,
        debug: bool = False,
    ) -> 'RouteObj':
        """Fetch a :class:`.Route` object stored in the :class:`.Database`.

        :param id: the ID of the :class:`.Route` to be retrieved
        :param debug: increase verbosity for debugging, defaults to False
        :returns: :class:`.Route` object

        """

        # avoiding circular dependencies
        from designdb.sets.compound import CompoundSet, IngredientSet
        from designdb.sets.reaction import ReactionSet

        # multiples??
        route = Route.objects.get(pk=id)

        if debug:
            mrich.var('product_id', route.product_compound)

        qs = Component.objects.filter(route=route).order_by('id')

        reaction_ids = []
        reactant_ids = []
        reactant_amounts = []
        intermediate_ids = []
        intermediate_amounts = []

        # for ref, c_type, amount in triples:
        for k in qs:
            ref = k.component_ref
            c_type = k.component_type
            amount = k.component_amount
            match c_type:
                case 1:
                    reaction_ids.append(ref)
                case 2:
                    reactant_ids.append(ref)
                    reactant_amounts.append(amount)
                case 3:
                    intermediate_ids.append(ref)
                    intermediate_amounts.append(amount)
                case _:
                    raise ValueError(f'Unknown component type {c_type}')

        if debug:
            mrich.var('pairs', qs)

        products = CompoundSet([route.pk])
        reactants = CompoundSet(reactant_ids)
        intermediates = CompoundSet(intermediate_ids)

        products = IngredientSet.from_compounds(compounds=products, amount=1)
        reactants = IngredientSet.from_compounds(
            compounds=reactants, amount=reactant_amounts
        )
        intermediates = IngredientSet.from_compounds(
            compounds=intermediates, amount=intermediate_amounts
        )

        reactions = ReactionSet(reaction_ids)

        recipe = RouteObj(
            route_id=id,
            product=products,
            reactants=reactants,
            intermediates=intermediates,
            reactions=reactions,
        )

        if debug:
            mrich.var('recipe', recipe)

        return recipe

    ### PROPERTIES

    @property
    def product(self) -> 'Ingredient':
        """Product ingredient"""
        return self._products[0]

    @property
    def product_compound(self) -> 'Compound':
        """Product compound"""
        return self.product.compound

    @property
    def id(self) -> int:
        """Route ID"""
        return self._id

    @property
    def price(self) -> 'Price':
        """Get the price of the reactants"""
        return self.reactants.price

    ### METHODS

    def get_dict(self) -> dict:
        """Serialisable dictionary"""
        data = {}

        data['id'] = self.id
        data['product_id'] = self.product.id
        data['reactants'] = self.reactants.get_dict()
        data['intermediates'] = self.intermediates.get_dict()
        data['reactions'] = self.reactions.get_dict()

        return data

    ### DUNDERS

    def __str__(self) -> str:
        """Unformatted string representation"""
        return f'Route #{self.id}: {self.product_compound}'

    def __repr__(self) -> str:
        """ANSI Formatted string representation"""
        return f'{mcol.bold}{mcol.underline}{self}{mcol.unbold}{mcol.ununderline}'

    def __rich__(self) -> str:
        """Rich Formatted string representation"""
        return f'[bold underline]{self}'
