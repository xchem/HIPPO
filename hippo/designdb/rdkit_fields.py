"""
RDKit PostgreSQL cartridge field types, vendored from django-rdkit.

Only the ``mol`` column type is reproduced here, since that is all HIPPO uses
(``Pose.pose_mol``). ``RxnField``, ``BfpField`` and ``SfpField`` — and their
``tanimoto``/``dice``/``ne``/``*fp`` lookups — are deliberately omitted; add
them back from upstream if reaction or fingerprint columns are ever needed.

Vendored because django-rdkit is not published on PyPI: it is only installable
from git, and PyPI rejects distributions that declare direct-URL dependencies,
so depending on it made ``pip install xchem-hippo`` unsatisfiable.

Upstream: https://github.com/rdkit/django-rdkit (django_rdkit/models/fields.py)

Copyright (c) 2015, Riccardo Vianello
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

from enum import Enum

from django import forms
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db.models import (
    Field,
    FloatField,
    Func,
    IntegerField,
    Lookup,
    Transform,
    Value,
)
from django.utils.translation import gettext_lazy as _
from rdkit.Chem import AllChem as Chem

__all__ = ['MolField']


class MolSerialization(Enum):
    BINARY = 'BINARY'
    TEXT = 'TEXT'


try:
    MOL_SERIALIZATION = MolSerialization(
        getattr(settings, 'DJANGO_RDKIT_MOL_SERIALIZATION', 'BINARY')
    )
except ValueError:
    raise ImproperlyConfigured(
        'An invalid DJANGO_RDKIT_MOL_SERIALIZATION value was found in the '
        f'settings. Supported values are {[v.value for v in MolSerialization]}'
    ) from None


class MolFieldPklMixin:
    def get_placeholder(self, value, compiler, connection):
        # define if/how the value assigned to this field is
        # to be wrapped into an insertion query
        if hasattr(value, 'as_sql'):
            return '%s'
        else:
            return 'mol_from_pkl(%s)'

    def select_format(self, compiler, sql, params):
        # format to use when the corresponding column appears
        # in select clauses.
        return f'mol_to_pkl({sql})', params

    def from_db_value(self, value, expression, connection):
        # convert the value returned by the database driver
        # into the desired Python data type
        if value is None:
            return value
        return Chem.Mol(bytes(value))

    def get_prep_value(self, value):
        # convert from Python to the value to be used in queries
        if isinstance(value, str):
            value = self.text_to_mol(value)
        if isinstance(value, Chem.Mol):
            value = memoryview(value.ToBinary())
        return value


class MolFieldSmilesMixin:
    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return Chem.MolFromSmiles(value)

    def get_prep_value(self, value):
        if isinstance(value, str):
            value = self.text_to_mol(value)
        if isinstance(value, Chem.Mol):
            value = Chem.MolToSmiles(value)
        return value


MolFieldSerializationMixin = {
    MolSerialization.BINARY: MolFieldPklMixin,
    MolSerialization.TEXT: MolFieldSmilesMixin,
}[MOL_SERIALIZATION]


class MolField(MolFieldSerializationMixin, Field):
    description = _('Molecule')

    def db_type(self, connection):
        # return the database column data type for this field
        return 'mol'

    def to_python(self, value):
        # convert the input value into the expected Python data
        # types (called during input cleanup and prior to field
        # validation)
        if value is None or isinstance(value, Chem.Mol):
            return value
        elif isinstance(value, str):
            return self.text_to_mol(value)
        elif isinstance(value, (bytes, bytearray, memoryview)):
            return Chem.Mol(bytes(value))
        else:
            raise ValidationError('Invalid input for a Mol instance')

    @staticmethod
    def text_to_mol(value):
        value = str(value)
        mol = (
            Chem.MolFromSmiles(value)
            or Chem.MolFromMolBlock(value)
            or Chem.inchi.MolFromInchi(value)
        )
        if mol is None:
            raise ValidationError('Invalid input for a Mol instance')
        return mol

    def get_prep_lookup(self, lookup_type, value):
        """Perform preliminary non-db specific lookup checks and conversions"""
        supported_lookup_types = [
            'hassubstruct',
            'issubstruct',
            'exact',
            'isnull',
        ] + [T.lookup_name for T in MOL_DESCRIPTOR_TRANSFORMS]
        if lookup_type in supported_lookup_types:
            return value
        raise TypeError(f'Field has invalid lookup: {lookup_type}')

    def formfield(self, **kwargs):
        # Use TextField as default input form to accommodate line breaks
        # needed for molBlocks
        defaults = {
            'form_class': forms.CharField,
            'strip': False,
            'widget': forms.Textarea,
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)


###################################################################
# MolField lookup operations, substruct and exact searches


class MolLookupMixin:
    def get_prep_lookup(self):
        if self.rhs_is_direct_value():
            if isinstance(self.rhs, Chem.Mol):
                if MOL_SERIALIZATION == MolSerialization.BINARY:
                    self.rhs = self.rhs.ToBinary()
                    self.rhs = Func(self.rhs, function='mol_from_pkl')
                elif MOL_SERIALIZATION == MolSerialization.TEXT:
                    self.rhs = Value(Chem.MolToSmiles(self.rhs))
                else:
                    # this should never happen, because MOL_SERIALIZATION
                    # is validated at import time
                    raise NotImplementedError
            else:
                self.rhs = Value(self.rhs)
        return super().get_prep_lookup()


class HasMolSubstruct(MolLookupMixin, Lookup):
    lookup_name = 'hassubstruct'
    prepare_rhs = True

    def as_sql(self, qn, connection):
        lhs, lhs_params = self.process_lhs(qn, connection)
        rhs, rhs_params = self.process_rhs(qn, connection)
        params = lhs_params + rhs_params
        return f'{lhs} @> {rhs}', params


class IsMolSubstruct(MolLookupMixin, Lookup):
    lookup_name = 'issubstruct'
    prepare_rhs = True

    def as_sql(self, qn, connection):
        lhs, lhs_params = self.process_lhs(qn, connection)
        rhs, rhs_params = self.process_rhs(qn, connection)
        params = lhs_params + rhs_params
        return f'{lhs} <@ {rhs}', params


class SameStructure(MolLookupMixin, Lookup):
    lookup_name = 'exact'
    prepare_rhs = True

    def as_sql(self, qn, connection):
        lhs, lhs_params = self.process_lhs(qn, connection)
        rhs, rhs_params = self.process_rhs(qn, connection)
        params = lhs_params + rhs_params
        return f'{lhs} @= {rhs}', params


MolField.register_lookup(HasMolSubstruct)
MolField.register_lookup(IsMolSubstruct)
MolField.register_lookup(SameStructure)


##########################################
# MolField transforms and descriptors


def make_descriptor_mixin(name, prefix, field):
    return type(
        str(f'{name.upper()}_Mixin'),
        (object,),
        {
            'descriptor_name': name,
            'function': f'{prefix}_{name}',
            'default_output_field': field,
        },
    )


class DescriptorTransform(Transform):
    def as_sql(self, qn, connection):
        lhs, params = qn.compile(self.lhs)
        return f'{self.function}({lhs})', params


MOL_DESCRIPTORS = [
    ('hba', IntegerField),
    ('hbd', IntegerField),
    ('numatoms', IntegerField),
    ('numheavyatoms', IntegerField),
    ('numrotatablebonds', IntegerField),
    ('numheteroatoms', IntegerField),
    ('numrings', IntegerField),
    ('numaromaticrings', IntegerField),
    ('numaliphaticrings', IntegerField),
    ('numsaturatedrings', IntegerField),
    ('numaromaticheterocycles', IntegerField),
    ('numaliphaticheterocycles', IntegerField),
    ('numsaturatedheterocycles', IntegerField),
    ('numaromaticcarbocycles', IntegerField),
    ('numaliphaticcarbocycles', IntegerField),
    ('numsaturatedcarbocycles', IntegerField),
    ('amw', FloatField),
    ('logp', FloatField),
    ('tpsa', FloatField),
    ('fractioncsp3', FloatField),
    ('chi0v', FloatField),
    ('chi1v', FloatField),
    ('chi2v', FloatField),
    ('chi3v', FloatField),
    ('chi4v', FloatField),
    ('chi0n', FloatField),
    ('chi1n', FloatField),
    ('chi2n', FloatField),
    ('chi3n', FloatField),
    ('chi4n', FloatField),
    ('kappa1', FloatField),
    ('kappa2', FloatField),
    ('kappa3', FloatField),
    ('murckoscaffold', MolField),
]


MOL_DESCRIPTOR_MIXINS = [
    make_descriptor_mixin(descriptor, 'mol', field_class())
    for descriptor, field_class in MOL_DESCRIPTORS
]


MOL_DESCRIPTOR_TRANSFORMS = [
    type(
        str(f'{mixin.descriptor_name.upper()}_Transform'),
        (
            mixin,
            DescriptorTransform,
        ),
        {
            'lookup_name': mixin.descriptor_name,
            'output_field': mixin.default_output_field,
        },
    )
    for mixin in MOL_DESCRIPTOR_MIXINS
]


for descriptor_transform in MOL_DESCRIPTOR_TRANSFORMS:
    MolField.register_lookup(descriptor_transform)
