import mcol
import mrich
import pandas as pd
from django.db.models import Exists, OuterRef, Q

from designdb.models import CataloguePrice, CataloguePriceCompoundJunction, Compound


class Ingredient:
    """An ingredient is a :class:`.Compound` with a fixed quanitity and an attached quote.

    .. image:: ../images/ingredient.png
              :width: 450
              :alt: Ingredient schema

    .. attention::

            :class:`.Ingredient` objects should not be created directly. Instead use :meth:`.Compound.as_ingredient`.
    """

    _table = 'ingredient'

    def __init__(
        self,
        compound: Compound,  # or CatalogueCompound?
        amount: float,
        quote: CataloguePrice,
        max_lead_time: float | None = None,
        supplier: str | None = None,
    ):
        """Ingredient initialisation"""

        self._compound = compound
        self._quote = quote
        self._amount = amount
        self._max_lead_time = max_lead_time
        self._supplier = supplier

    def __str__(self) -> str:
        """Plain string representation"""
        return f'{self.amount:.2f}mg of C{self._compound.id}'

    def __repr__(self) -> str:
        """ANSI Formatted string representation"""
        return f'{mcol.bold}{mcol.underline}{str(self)}{mcol.unbold}{mcol.ununderline}'

    def __rich__(self) -> str:
        """Representation for mrich"""
        return f'[bold underline]{str(self)}'

    def __eq__(self, other) -> bool:
        """Equality operator"""

        if self.compound != other.compound:
            return False

        return self.amount == other.amount

    def __getattr__(self, key: str):
        """For missing attributes try getting from associated :class:`.Compound`"""
        return getattr(self.compound, key)

    @classmethod
    def from_compound(
        cls,
        compound: Compound,
        amount: float,
        max_lead_time: float = None,
        supplier: str = None,
        get_quote: bool = True,
        quote_none: str = 'quiet',
    ) -> 'Ingredient':
        """Convert this compound into an :class:`.Ingredient` object with an associated amount (in ``mg``) and :class:`.Quote` if available.

        :param amount: Amount in ``mg``
        :param supplier: Only search for quotes with the given supplier, defaults to ``None``
        :param max_lead_time: Only search for quotes with lead times less than this (in days), defaults to ``None``
        """

        if get_quote:
            # quote = self.get_quotes(
            #     pick_cheapest=True,
            #     min_amount=amount,
            #     max_lead_time=max_lead_time,
            #     supplier=supplier,
            #     none=quote_none,
            # )

            # if not quote:
            #     quote = None

            quote = cls.get_quotes(
                compound=compound,
                pick_cheapest=True,
                min_amount=amount,
                max_lead_time=max_lead_time,
                supplier=supplier,
                none=quote_none,
            )

        else:
            quote = None

        return Ingredient(
            compound=compound,
            amount=amount,
            quote=quote,
            supplier=supplier,
            max_lead_time=max_lead_time,
        )

    @classmethod
    def get_quotes(
        cls,
        compound: Compound,
        min_amount: float | None = None,
        supplier: str | None = None,
        max_lead_time: float | None = None,
        none: str = 'quiet',
        pick_cheapest: bool = False,
        df: bool = False,
    ):
        """Get all quotes associated to this compound

        :param min_amount: Only return quotes with amounts greater than this, defaults to ``None``
        :param supplier: Only return quotes with the given supplier, defaults to ``None``
        :param max_lead_time: Only return quotes with lead times less than this (in days), defaults to ``None``
        :param none: Define the behaviour when no quotes are found. Choose `error` to raise print an error.
        :param pick_cheapest: If ``True`` only the cheapest :class:`.Quote` is returned, defaults to ``False``
        :param df: Returns a ``DataFrame`` of the quoting data, defaults to ``False``
        :returns: List of :class:`.Quote` objects, ``DataFrame``, or single :class:`.Quote`. See ``pick_cheapest`` and ``df`` parameters

        """

        qs = CataloguePrice.objects.annotate(
            has_compound=Exists(
                CataloguePriceCompoundJunction.objects.filter(
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

    ### METHODS

    def get_cheapest_quote_id(
        self,
        min_amount: float | None = None,
        supplier: str | None = None,
        max_lead_time: float | None = None,
    ) -> int | None:
        """
        Query quotes associated to this ingredient, and return the cheapest

        :param min_amount: Only return quotes with amounts greater than this, defaults to ``None``
        :param supplier: Only return quotes with the given supplier, defaults to ``None``
        :param max_lead_time: Only return quotes with lead times less than this (in days), defaults to ``None``
        :param none: Define the behaviour when no quotes are found. Choose `error` to raise print an error.
        """

        query = Q(compound=self.compound)

        if supplier:
            query &= Q(quote_supplier=supplier)

        if min_amount:
            query &= Q(quote_amount__gte=min_amount)

        if max_lead_time:
            query &= Q(quote_lead_time__lte=max_lead_time)

        return CataloguePrice.objects.filter(query).order_by('quote_price').first()

    ### PROPERTIES

    @property
    def amount(self) -> float:
        """Returns the amount (in ``mg``)"""
        return self._amount

    @property
    def id(self) -> int:
        """Returns the ID of the associated :class:`.Compound`"""
        return self._compound_id

    @property
    def compound_id(self) -> int:
        """Returns the ID of the associated :class:`.Compound`"""
        return self._compound_id

    @property
    def quote(self) -> int:
        """Returns the ID of the associated :class:`.Quote`"""
        return self._quote

    @property
    def max_lead_time(self) -> float:
        """Returns the max_lead_time (in days) from the original quote query"""
        return self._max_lead_time

    @property
    def supplier(self) -> str:
        """Returns the supplier from the original quote query"""
        return self._supplier

    @amount.setter
    def amount(self, a) -> None:
        """Set the amount and fetch updated :class:`.Quote`s"""

        quote = self.get_cheapest_quote_id(
            min_amount=a,
            max_lead_time=self._max_lead_time,
            supplier=self._supplier,
            none='quiet',
        )

        self._quote = quote

        self._amount = a

    @property
    def compound(self) -> Compound:
        """Returns the associated :class:`.Compound`"""

        # if not self._compound:
        #     self._compound = self.db.get_compound(id=self.compound_id)
        return self._compound

    @property
    def compound_price_amount_str(self) -> str:
        """String representation including :class:`.Compound`, :class:`.Price`, and amount."""
        return f'{self} ({self.amount})'

    @property
    def smiles(self) -> str:
        """Returns the SMILES of the associated :class:`.Compound`"""
        return self.compound.smiles
