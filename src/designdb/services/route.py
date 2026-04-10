# from mypackage.services.compound import CompoundService

# from rdkit.Chem import inchi
from designdb.models import Component, Route
from designdb.recipe import Recipe


class RouteService:
    @classmethod
    def create_from_recipe(
        cls,
        *,
        recipe: Recipe,
    ) -> tuple[Route, bool]:

        route, created = Route.objects.get_or_create(
            product_compound=recipe.product.compound
        )

        # are you joking?? reactants and intermediates are all of the
        # sudden components

        # reactions
        components = []
        components.extend(
            [
                Component(route=route, component_type=1, component_ref=ref.pk)
                for ref in recipe.reactions
            ],
        )

        # this part needs data from ingredient df, which I don't have
        # and is not implemented

        # reactants
        # for ref, amount in recipe.reactants.id_amount_pairs:
        #     self.insert_component(
        #         component_type=2, ref=ref, route=route_id, amount=amount, commit=False
        #     )

        components.extend(
            [
                Component(
                    route=route,
                    component_type=1,
                    component_ref=ref,
                    component_amount=amount,
                )
                for ref, amount in recipe.reactants.id_amount_pairs
            ],
        )

        # # intermediates
        # for ref, amount in recipe.intermediates.id_amount_pairs:
        #     self.insert_component(
        #         component_type=3, ref=ref, route=route_id, amount=amount, commit=False
        #     )

        components.extend(
            [
                Component(
                    route=route,
                    component_type=1,
                    component_ref=ref,
                    component_amount=amount,
                )
                for ref, amount in recipe.intermediates.id_amount_pairs
            ],
        )

        Component.objects.bulk_create(components, ignore_conflicts=True)

        return route, created

    # @property
    # def id_amount_pairs(self) -> list[tuple]:
    #     """Get a list of compound ID and amount pairs"""
    #     return [
    #         (id, amount) for id, amount in self.df[['compound_id', 'amount']].values
    #     ]
