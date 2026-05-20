import mrich
import pandas as pd
from designdb.models import CataloguePriceCompoundJunctionModel, CataloguePriceModel, CompoundModel
from django.db.models import Exists, OuterRef, Q


class IngredientService:

    @staticmethod
    def get_quotes(
        compound: CompoundModel,
        min_amount: float | None = None,
        supplier: str | None = None,
        max_lead_time: float | None = None,
        none: str = 'quiet',
        pick_cheapest: bool = False,
        df: bool = False,
    ):
        qs = CataloguePriceModel.objects.annotate(
            has_compound=Exists(
                CataloguePriceCompoundJunctionModel.objects.filter(
                    compound=compound,
                    catalogue_price=OuterRef('pk'),
                ),
            ),
        ).filter(
            has_compound=True,
        )

        if supplier:
            if isinstance(supplier, str):
                qs = qs.filter(supplier=supplier)
            else:
                qs = qs.filter(supplier__in=supplier)

        if not qs.exists():
            return None

        if max_lead_time:
            qs = qs.filter(lead_time__lte=max_lead_time)

        if min_amount:
            qs = qs.filter(amount__gte=min_amount)

            if not qs.exists():
                mrich.debug(
                    f'No quote available for C{compound.pk} with amount >= {min_amount} mg. Estimating price...'
                )

        if pick_cheapest:
            return qs.order_by('price').first()

        if df:
            return pd.DataFrame(qs.values()).drop(columns='compound')

        return qs

    @staticmethod
    def get_cheapest_quote_id(
        compound: CompoundModel,
        min_amount: float | None = None,
        supplier: str | None = None,
        max_lead_time: float | None = None,
    ) -> int | None:
        query = Q(compound=compound)

        if supplier:
            query &= Q(quote_supplier=supplier)

        if min_amount:
            query &= Q(quote_amount__gte=min_amount)

        if max_lead_time:
            query &= Q(quote_lead_time__lte=max_lead_time)

        return CataloguePriceModel.objects.filter(query).order_by('quote_price').first()
