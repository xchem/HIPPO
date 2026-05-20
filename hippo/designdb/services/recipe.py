import mrich
from designdb.models import CompoundModel, ReactionModel
from designdb.sets.compound import IngredientSet
from designdb.sets.reaction import ReactionSet


class RecipeService:

    @staticmethod
    def from_reaction(
        reaction,
        amount=1,
        *,
        debug: bool = False,
        pick_cheapest: bool = True,
        permitted_reactions: 'ReactionSet | None' = None,
        quoted_only: bool = False,
        supplier: None | str = None,
        unavailable_reaction: str = 'error',
        reaction_checking_cache: dict[int, bool] = None,
        reaction_reactant_cache: dict[int, bool] = None,
        inner: bool = False,
        get_ingredient_quotes: bool = True,
    ) -> 'Recipe | list[Recipe]':
        """Create a Recipe from a ReactionModel and its upstream dependencies."""

        from designdb.components.recipe import Recipe

        assert isinstance(reaction, ReactionModel)

        if debug:
            mrich.debug(
                f'RecipeService.from_reaction(R{reaction.id}, {amount=}, {pick_cheapest=})'
            )
            mrich.debug(f'{reaction.product.id=}')
            mrich.debug(f'{reaction.reactants.ids=}')

        if permitted_reactions:
            assert reaction in permitted_reactions

        recipe = Recipe(
            products=IngredientSet(
                [
                    reaction.product.as_ingredient(
                        amount=amount, get_quote=get_ingredient_quotes
                    )
                ],
            ),
            reactants=IngredientSet([], supplier=supplier),
            intermediates=IngredientSet([]),
            reactions=ReactionSet([reaction.id], sort=False),
        )

        recipes = [recipe]

        if quoted_only or supplier:
            if debug:
                mrich.debug(f'Checking reactant_availability: {reaction=}')
            if reaction_checking_cache and reaction.id in reaction_checking_cache:
                ok = reaction_checking_cache[reaction.id]
                print('reaction_checking_cache used')
            else:
                ok = reaction.check_reactant_availability(supplier=supplier)
                # print('cache not used')
                if reaction_checking_cache is not None:
                    reaction_checking_cache[reaction.id] = ok
            if not ok:
                if unavailable_reaction == 'error':
                    mrich.error(f'Reactants not available for {reaction=}')
                if pick_cheapest:
                    return None
                else:
                    return []

        def get_reactant_amount_pairs(reaction: 'ReactionModel') -> list[tuple[int, float]]:
            """Get pairs of reactant ID and float amounts"""
            if reaction_reactant_cache and reaction.id in reaction_reactant_cache:
                print('reaction_reactant_cache used')
                return reaction_reactant_cache[reaction.id]
            else:
                pairs = reaction.get_reactant_amount_pairs(compound_object=False)
                if reaction_reactant_cache is not None:
                    reaction_reactant_cache[reaction.id] = pairs
                return pairs

        if debug:
            mrich.debug(f'get_reactant_amount_pairs({reaction.id})')
        pairs = get_reactant_amount_pairs(reaction)

        for reactant, reactant_amount in pairs:
            reactant = CompoundModel.objects.get(pk=reactant)

            if debug:
                mrich.debug(f'{reactant.id=}, {reactant_amount=}')

            # scale amount
            reactant_amount *= amount
            reactant_amount /= reaction.product_yield

            inner_reactions = reactant.get_reactions(
                none='quiet', permitted_reactions=permitted_reactions
            )

            if inner_reactions:
                if debug:
                    if len(inner_reactions) == 1:
                        mrich.debug('ReactantModel has ONE inner reaction')
                    else:
                        mrich.warning(f'{reactant=} has MULTIPLE inner reactions')

                new_recipes = []

                inner_recipes = []
                for reaction in inner_reactions:
                    reaction_recipes = RecipeService.from_reaction(
                        reaction=reaction,
                        amount=reactant_amount,
                        debug=debug,
                        pick_cheapest=False,
                        quoted_only=quoted_only,
                        supplier=supplier,
                        unavailable_reaction=unavailable_reaction,
                        reaction_checking_cache=reaction_checking_cache,
                        reaction_reactant_cache=reaction_reactant_cache,
                        inner=True,
                    )
                    inner_recipes += reaction_recipes

                for recipe in recipes:
                    for inner_recipe in inner_recipes:
                        combined_recipe = recipe.copy()

                        combined_recipe.reactants += inner_recipe.reactants
                        combined_recipe.intermediates += inner_recipe.intermediates
                        combined_recipe.reactions += inner_recipe.reactions
                        combined_recipe.intermediates.add(
                            reactant.as_ingredient(reactant_amount, supplier=supplier)
                        )

                        new_recipes.append(combined_recipe)

                recipes = new_recipes

            else:
                ingredient = reactant.as_ingredient(reactant_amount, supplier=supplier)
                for recipe in recipes:
                    recipe.reactants.add(ingredient)

        # reverse ReactionSet's
        if not inner:
            for recipe in recipes:
                recipe.reactions.reverse()

        if pick_cheapest:
            if debug:
                mrich.debug('Picking cheapest')
            priced = [r for r in recipes if r.get_price(supplier=supplier)]
            # priced = [r for r in recipes if r.price]
            if not priced:
                mrich.error("0 recipes with prices, can't choose cheapest")
                return recipes
            sorted_recipes = sorted(
                priced, key=lambda r: r.get_price(supplier=supplier)
            )

            if debug:
                for recipe in recipes:
                    mrich.debug(f'{recipe}, {recipe.price}')

            return sorted_recipes[0]

        return recipes

    @staticmethod
    def from_reactions(
        reactions: 'ReactionSet',
        amount: float = 1,
        pick_cheapest: bool = True,
        permitted_reactions: 'ReactionSet | None' = None,
        final_products_only: bool = True,
        return_products: bool = False,
        supplier: str | None = None,
        use_routes: bool = False,
        debug: bool = False,
        **kwargs,
    ) -> 'Recipe | list[Recipe]':
        """Create a Recipe from a ReactionSet and its upstream dependencies."""

        from designdb.components.recipe import Recipe
        from designdb.sets.compound import CompoundSet

        assert isinstance(reactions, ReactionSet)

        if debug:
            mrich.debug('RecipeService.from_reactions()')
            mrich.var('reactions', reactions)
            mrich.var('amount', amount)
            mrich.var('final_products_only', final_products_only)
            mrich.var('permitted_reactions', permitted_reactions)

        # get all the products
        products = reactions.products

        if debug:
            mrich.var('products', products)

        if final_products_only:
            if debug:
                mrich.var('products.str_ids', products.str_ids)

            # TODO: port to Django ORM — reactions.db.execute() is the old API
            raise NotImplementedError(
                'final_products_only branch not yet ported to Django ORM'
            )

        recipe = Recipe.from_compounds(
            compounds=products,
            amount=amount,
            permitted_reactions=reactions,
            pick_cheapest=pick_cheapest,
            supplier=supplier,
            use_routes=use_routes,
            **kwargs,
        )

        return recipe
