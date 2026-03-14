# from django.db.models import indexes
from django.conf import settings
from django.db import models

_MANAGE_MODELS = settings.MANAGE_MODELS


if settings.MANAGE_MODELS:
    # sqlite3, rdkit field types not available
    from django.db.models import BinaryField as BfpField

    # shouldn't this be binary as well?
    from django.db.models import TextField as MolField
else:
    from django_rdkit.models import BfpField, MolField


class BaseModel(models.Model):
    created_on = models.DateTimeField(null=True, blank=True)
    updated_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        # managed = False
        managed = _MANAGE_MODELS
        app_label = 'designdb'
        default_related_name = '%(class)ss'


class Target(BaseModel):
    id = models.BigAutoField(primary_key=True)
    external_target_id = models.BigIntegerField(null=True, blank=True)
    target_name = models.TextField()
    target_metadata = models.TextField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'targets'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'target_name',
                ],
                name='uc_target',
            ),
        ]
        indexes = [
            models.Index(fields=['target_name'], name='idx_target_name'),
            models.Index(fields=['created_on'], name='idx_target_created'),
        ]


class Compound(BaseModel):
    id = models.BigAutoField(primary_key=True)
    compound_inchikey = models.TextField(null=True, blank=True)
    compound_alias = models.TextField(null=True, blank=True)
    compound_smiles = models.TextField(null=True, blank=True)

    base_compound = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        db_column='base_compound_id',
        related_name='+',  # add if needed
    )

    # compound_mol = models.TextField(null=True, blank=True)
    # compound_pattern_bfp = models.TextField(null=True, blank=True)
    # compound_morgan_bfp = models.TextField(null=True, blank=True)
    compound_mol = MolField(null=True)
    compound_pattern_bfp = BfpField(null=True)
    compound_morgan_bfp = BfpField(null=True)

    compound_metadata = models.TextField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)
    rdkit_version = models.TextField(null=True, blank=True)
    inchi_version = models.TextField(null=True, blank=True)

    tags = models.ManyToManyField(
        'CompoundTag',
        through='CompoundTagJunction',
        related_name='compounds',
    )

    enumeration_methods = models.ManyToManyField(
        'EnumerationMethod',
        through='CompoundEnumerationMethodJunction',
        related_name='compounds',
    )

    # unlike others, this wasn't clearly defined as m2m. may not want
    # to keep it
    scaffolds = models.ManyToManyField(
        'self',
        through='Scaffold',
    )

    class Meta(BaseModel.Meta):
        db_table = 'compounds'
        constraints = [
            # I believe there were supposed to be changes to these
            models.UniqueConstraint(
                fields=[
                    'compound_alias',
                ],
                name='uc_compound_alias',
            ),
            models.UniqueConstraint(
                fields=[
                    'compound_inchikey',
                ],
                name='uc_compound_inchikey',
            ),
            models.UniqueConstraint(
                fields=[
                    'compound_smiles',
                ],
                name='uc_compound_smiles',
            ),
        ]
        indexes = [
            models.Index(fields=['base_compound'], name='idx_base_compound_id'),
            models.Index(fields=['compound_inchikey'], name='idx_compound_inchikey'),
            models.Index(fields=['compound_smiles'], name='idx_compound_smiles'),
            models.Index(fields=['created_on'], name='idx_compound_created'),
        ]


class Subsite(BaseModel):
    id = models.BigAutoField(primary_key=True)
    target = models.ForeignKey(
        Target,
        on_delete=models.RESTRICT,
        db_column='target_id',
    )

    subsite_name = models.TextField()
    subsite_metadata = models.TextField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'subsites'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'target',
                    'subsite_name',
                ],
                name='uc_subsite',
            ),
        ]
        indexes = [
            models.Index(fields=['target'], name='idx_subsite_target_id'),
            models.Index(fields=['created_on'], name='idx_subsite_created'),
        ]


class Pose(BaseModel):
    id = models.BigAutoField(primary_key=True)

    pose_inchikey = models.TextField(null=True, blank=True)
    pose_alias = models.TextField(null=True, blank=True)
    pose_smiles = models.TextField(null=True, blank=True)

    pose_reference = models.IntegerField(null=True, blank=True)
    pose_path = models.TextField(null=True, blank=True)

    compound = models.ForeignKey(
        Compound,
        on_delete=models.RESTRICT,
        db_column='compound_id',
    )

    target = models.ForeignKey(
        Target,
        on_delete=models.RESTRICT,
        db_column='target_id',
    )

    # pose_mol = models.TextField(null=True, blank=True)
    pose_mol = MolField(null=True)
    # this is integer in the db.. pretty sure this cannot be the case?
    pose_fingerprint = models.IntegerField(null=True, blank=True)

    pose_metadata = models.TextField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)

    rdkit_version = models.TextField(null=True, blank=True)
    inchi_version = models.TextField(null=True, blank=True)

    methods = models.ManyToManyField(
        'PoseMethod',
        through='PoseMethodJunction',
        related_name='poses',
    )
    tags = models.ManyToManyField(
        'PoseTag',
        through='PoseTagJunction',
        related_name='poses',
    )
    # unlike others, this wasn't clearly defined as m2m. may not want
    # to keep it
    inspirations = models.ManyToManyField(
        'self',
        through='Inspiration',
    )

    class Meta(BaseModel.Meta):
        db_table = 'poses'
        # There are no constraints here, but they need to be unique,
        # verified in code (rdkit.align_pose coords from
        # file). Investigate adding coords to db and doing the search
        # there

        # although.. would alias-target combo work?
        indexes = [
            models.Index(fields=['compound'], name='idx_pose_compound_id'),
            models.Index(fields=['target'], name='idx_pose_target_id'),
            models.Index(fields=['pose_path'], name='idx_pose_path'),
            models.Index(fields=['created_on'], name='idx_pose_created'),
        ]


class SubsiteTag(BaseModel):
    id = models.BigAutoField(primary_key=True)
    subsite = models.ForeignKey(
        Subsite,
        on_delete=models.RESTRICT,
        db_column='subsite_id',
    )
    pose = models.ForeignKey(
        Pose,
        on_delete=models.RESTRICT,
        db_column='pose_id',
    )

    subsite_tag_metadata = models.TextField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'subsite_tags'
        unique_together = ('subsite', 'pose')
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'subsite',
                    'pose',
                ],
                name='uc_subsite_tag',
            ),
        ]
        indexes = [
            models.Index(fields=['subsite'], name='idx_subsite_tag_subsite_id'),
            models.Index(fields=['pose'], name='idx_subsite_tag_pose_id'),
            models.Index(fields=['created_on'], name='idx_subsite_tag_created'),
        ]


class PoseMethod(BaseModel):
    id = models.BigAutoField(primary_key=True)
    pose_method_name = models.TextField(null=True, blank=True)
    pose_method_description = models.TextField(null=True, blank=True)
    pose_method_version = models.TextField(null=True, blank=True)
    pose_method_organization = models.TextField(null=True, blank=True)
    pose_method_link = models.TextField(null=True, blank=True)
    pose_method_note = models.TextField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'pose_methods'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'pose_method_name',
                    'pose_method_version',
                ],
                name='uc_pose_method',
                nulls_distinct=False,
            )
        ]
        indexes = [
            models.Index(fields=['pose_method_name'], name='idx_pose_method_name'),
            models.Index(fields=['created_on'], name='idx_pose_method_created'),
        ]


class PoseMethodJunction(BaseModel):
    pk = models.CompositePrimaryKey('pose_id', 'pose_method_id')
    pose = models.ForeignKey(
        'Pose',
        on_delete=models.CASCADE,
        db_column='pose_id',
    )

    pose_method = models.ForeignKey(
        'PoseMethod',
        on_delete=models.CASCADE,
        db_column='pose_method_id',
    )

    class Meta(BaseModel.Meta):
        db_table = 'has_pose_methods'
        indexes = [
            models.Index(
                fields=['pose_method'], name='idx_has_pose_methods_pose_method_id'
            ),
            models.Index(
                fields=['created_on'], name='idx_idx_has_pose_methods_created'
            ),
        ]


class PoseTag(BaseModel):
    id = models.BigAutoField(primary_key=True)
    pose_tag_name = models.TextField()
    pose_tag_description = models.TextField(null=True, blank=True)
    pose_tag_note = models.TextField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'pose_tags'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'pose_tag_name',
                ],
                name='uc_pose_tag',
            )
        ]
        indexes = [
            models.Index(fields=['created_on'], name='idx_pose_tag_created'),
        ]


class PoseTagJunction(BaseModel):
    pk = models.CompositePrimaryKey('pose_id', 'pose_tag_id')
    pose = models.ForeignKey(
        Pose,
        on_delete=models.CASCADE,
        db_column='pose_id',
    )
    pose_tag = models.ForeignKey(
        PoseTag,
        on_delete=models.CASCADE,
        db_column='pose_tag_id',
    )

    class Meta(BaseModel.Meta):
        db_table = 'has_pose_tags'
        indexes = [
            models.Index(fields=['pose_tag'], name='idx_has_pose_tag_pose_tag_id'),
            models.Index(fields=['created_on'], name='idx_has_pose_tag_created'),
        ]


# this was missing.. is this a m2m table as well? really looks like it
class Inspiration(BaseModel):
    id = models.BigAutoField(primary_key=True)
    # original behaviour described in schema was SET_NULL but I don't
    # see how that makes sense. if either original or derivative is
    # deleted, you'll have orphaned entries
    original_pose = models.ForeignKey(
        Pose,
        # on_delete=models.SET_NULL,
        on_delete=models.CASCADE,
        db_column='original_pose_id',
        related_name='+',
    )
    derivative_pose = models.ForeignKey(
        Pose,
        # on_delete=models.SET_NULL,
        on_delete=models.CASCADE,
        db_column='derivative_pose_id',
        related_name='+',
    )

    class Meta(BaseModel.Meta):
        db_table = 'inspirations'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'original_pose',
                    'derivative_pose',
                ],
                name='uc_inspiration',
            )
        ]
        indexes = [
            models.Index(
                fields=['original_pose'], name='idx_inspiration_original_pose_id'
            ),
            models.Index(
                fields=['derivative_pose'], name='idx_inspiration_derivative_pose_id'
            ),
            models.Index(fields=['created_on'], name='idx_inspiration_created'),
        ]


class Feature(BaseModel):
    id = models.BigAutoField(primary_key=True)
    feature_family = models.TextField(null=True, blank=True)
    target = models.ForeignKey(
        Target,
        on_delete=models.RESTRICT,
        db_column='target_id',
    )

    feature_chain_name = models.TextField(null=True, blank=True)
    feature_residue_name = models.TextField(null=True, blank=True)
    feature_residue_number = models.IntegerField(null=True, blank=True)
    feature_atom_name = models.TextField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'features'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'feature_family',
                    'target',
                    'feature_chain_name',
                    'feature_residue_name',
                    'feature_residue_number',
                    'feature_atom_name',
                ],
                name='uc_feature',
            )
        ]
        indexes = [
            models.Index(fields=['target'], name='idx_feature_target_id'),
            models.Index(fields=['created_on'], name='idx_feature_created'),
        ]


class Interaction(BaseModel):
    id = models.BigAutoField(primary_key=True)
    feature = models.ForeignKey(
        Feature,
        on_delete=models.RESTRICT,
        db_column='feature_id',
    )
    pose = models.ForeignKey(
        Pose,
        on_delete=models.RESTRICT,
        db_column='pose_id',
    )

    interaction_type = models.TextField()
    interaction_family = models.TextField()
    interaction_atom_id = models.TextField()

    # could these be vectors?
    interaction_prot_coord = models.TextField()
    interaction_lig_coord = models.TextField()

    interaction_distance = models.FloatField()
    interaction_angle = models.FloatField(null=True, blank=True)
    interaction_energy = models.FloatField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'interactions'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'feature',
                    'pose',
                    'interaction_type',
                    'interaction_family',
                    'interaction_atom_id',
                ],
                name='uc_interaction',
            )
        ]
        indexes = [
            models.Index(fields=['feature_id'], name='idx_interaction_feature_id'),
            models.Index(fields=['pose'], name='idx_interaction_pose_id'),
            models.Index(fields=['created_on'], name='idx_interaction_created'),
        ]


class CompoundTag(BaseModel):
    id = models.BigAutoField(primary_key=True)
    compound_tag_name = models.TextField()
    compound_tag_description = models.TextField(null=True, blank=True)
    compound_tag_note = models.TextField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'compound_tags'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'compound_tag_name',
                ],
                name='uc_compound_tag_name',
            )
        ]
        indexes = [
            models.Index(fields=['created_on'], name='idx_compound_tag_created'),
        ]


class CompoundTagJunction(BaseModel):
    pk = models.CompositePrimaryKey('compound_id', 'compound_tag_id')
    compound = models.ForeignKey(
        Compound,
        on_delete=models.CASCADE,
        db_column='compound_id',
    )
    compound_tag = models.ForeignKey(
        CompoundTag,
        on_delete=models.CASCADE,
        db_column='compound_tag_id',
    )

    class Meta(BaseModel.Meta):
        db_table = 'has_compound_tags'
        indexes = [
            models.Index(
                fields=['compound_tag'], name='idx_has_compound_tag_compound_tag_id'
            ),
            models.Index(fields=['created_on'], name='idx_has_compound_tag_created'),
        ]


class EnumerationMethod(BaseModel):
    id = models.BigAutoField(primary_key=True)
    enum_name = models.TextField(null=True, blank=True)
    enum_description = models.TextField(null=True, blank=True)
    enum_version = models.TextField(null=True, blank=True)
    enum_organization = models.TextField(null=True, blank=True)
    enum_link = models.TextField(null=True, blank=True)
    enum_note = models.TextField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'enumeration_methods'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'enum_name',
                    'enum_version',
                ],
                name='uc_enumeration_method',
                nulls_distinct=False,
            )
        ]
        indexes = [
            models.Index(fields=['enum_name'], name='idx_enumeration_method_name'),
            models.Index(fields=['created_on'], name='idx_enumeration_method_created'),
        ]


class CompoundEnumerationMethodJunction(BaseModel):
    pk = models.CompositePrimaryKey('compound_id', 'enumeration_method_id')
    compound = models.ForeignKey(
        Compound,
        on_delete=models.CASCADE,
        db_column='compound_id',
    )
    enumeration_method = models.ForeignKey(
        EnumerationMethod,
        on_delete=models.CASCADE,
        db_column='enumeration_method_id',
    )

    class Meta(BaseModel.Meta):
        db_table = 'has_enumeration_methods'
        indexes = [
            models.Index(
                fields=['enumeration_method'],
                name='idx_has_enumeration_methods_enumeration_method_id',
            ),
            models.Index(
                fields=['created_on'], name='idx_has_enumeration_methods_created'
            ),
        ]


class ScoringMethod(BaseModel):
    id = models.BigAutoField(primary_key=True)
    method_name = models.TextField(null=True, blank=True)
    method_description = models.TextField(null=True, blank=True)
    method_version = models.TextField(null=True, blank=True)
    method_organization = models.TextField(null=True, blank=True)
    method_link = models.TextField(null=True, blank=True)
    note = models.TextField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'scoring_methods'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'method_name',
                    'method_version',
                ],
                name='uc_scoring_method',
                nulls_distinct=False,
            )
        ]
        indexes = [
            models.Index(fields=['method_name'], name='idx_scoring_method_name'),
            models.Index(fields=['created_on'], name='idx_scoring_method_created'),
        ]


class ScoreValue(BaseModel):
    pk = models.CompositePrimaryKey('pose_id', 'compound_id', 'scoring_method_id')
    pose = models.ForeignKey(
        Pose,
        on_delete=models.RESTRICT,
        db_column='pose_id',
        related_name='scores',
    )

    compound = models.ForeignKey(
        Compound,
        on_delete=models.RESTRICT,
        db_column='compound_id',
        related_name='scores',
    )

    scoring_method = models.ForeignKey(
        ScoringMethod,
        on_delete=models.RESTRICT,
        db_column='scoring_method_id',
        related_name='scores',
    )

    score = models.JSONField()

    class Meta(BaseModel.Meta):
        db_table = 'score_values'
        indexes = [
            models.Index(fields=['pose'], name='idx_score_values_pose_id'),
            models.Index(fields=['compound'], name='idx_score_values_compound_id'),
            models.Index(
                fields=['scoring_method'], name='idx_score_values_scoring_method_id'
            ),
            models.Index(fields=['created_on'], name='idx_score_values_created'),
        ]


class Reaction(BaseModel):
    id = models.BigAutoField(primary_key=True)
    reaction_type = models.TextField(null=True, blank=True)
    product_compound = models.ForeignKey(
        Compound,
        on_delete=models.RESTRICT,
        db_column='product_compound_id',
    )

    reaction_product_yield = models.FloatField(null=True, blank=True)
    reaction_metadata = models.TextField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'reactions'
        indexes = [
            models.Index(
                fields=['product_compound'], name='idx_reaction_product_compound_id'
            ),
            models.Index(fields=['created_on'], name='idx_reaction_created'),
        ]


class Reactant(BaseModel):
    id = models.BigAutoField(primary_key=True)
    reactant_amount = models.FloatField(null=True, blank=True)
    reaction = models.ForeignKey(
        Reaction,
        on_delete=models.CASCADE,
        db_column='reaction_id',
    )
    compound = models.ForeignKey(
        Compound,
        on_delete=models.RESTRICT,
        db_column='compound_id',
    )

    class Meta(BaseModel.Meta):
        db_table = 'reactants'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'reaction',
                    'compound',
                ],
                name='uc_reactant',
            )
        ]
        indexes = [
            models.Index(fields=['reaction'], name='idx_reactant_reaction_id'),
            models.Index(fields=['compound'], name='idx_reactant_compound_id'),
            models.Index(fields=['created_on'], name='idx_reactant_created'),
        ]


class Quote(BaseModel):
    id = models.BigAutoField(primary_key=True)
    quote_smiles = models.TextField(null=True, blank=True)
    quote_amount = models.FloatField(null=True, blank=True)
    quote_supplier = models.TextField(null=True, blank=True)
    quote_catalogue = models.TextField(null=True, blank=True)
    quote_entry = models.TextField(null=True, blank=True)
    quote_lead_time = models.IntegerField(null=True, blank=True)
    quote_price = models.FloatField(null=True, blank=True)
    quote_currency = models.TextField(null=True, blank=True)
    quote_purity = models.FloatField(null=True, blank=True)
    quote_date = models.TextField(null=True, blank=True)
    compound = models.ForeignKey(
        Compound,
        # sql schema speciefies SET_NULL. Doesn't seem right but not sure
        null=True,
        on_delete=models.SET_NULL,
        db_column='compound_id',
    )

    class Meta(BaseModel.Meta):
        db_table = 'quotes'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'quote_amount',
                    'quote_supplier',
                    'quote_catalogue',
                    'quote_entry',
                ],
                name='uc_quote',
            )
        ]
        indexes = [
            models.Index(fields=['compound'], name='idx_quote_compound_id'),
            models.Index(fields=['created_on'], name='idx_quote_created'),
        ]


class Scaffold(BaseModel):
    id = models.BigAutoField(primary_key=True)
    # same comment as with inspiratons. original schema says SET_NULL
    # but doesn't seem right
    base_compound = models.ForeignKey(
        Compound,
        # on_delete=models.SET_NULL,
        on_delete=models.CASCADE,
        db_column='base_compound_id',
        related_name='scaffold_bases',
    )
    superstructure_compound = models.ForeignKey(
        Compound,
        # on_delete=models.SET_NULL,
        on_delete=models.CASCADE,
        db_column='superstructure_compound_id',
        related_name='scaffold_superstructures',
    )

    class Meta(BaseModel.Meta):
        db_table = 'scaffolds'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'base_compound',
                    'superstructure_compound',
                ],
                name='uc_scaffold',
            )
        ]
        indexes = [
            models.Index(
                fields=['base_compound'], name='idx_scaffold_base_compound_id'
            ),
            models.Index(
                fields=['superstructure_compound'],
                name='idx_scaffold_superstructure_compound_id',
            ),
            models.Index(fields=['created_on'], name='idx_scaffold_created'),
        ]


class Route(BaseModel):
    id = models.BigAutoField(primary_key=True)
    product_compound = models.ForeignKey(
        Compound,
        on_delete=models.RESTRICT,
        db_column='product_compound_id',
    )

    class Meta(BaseModel.Meta):
        db_table = 'routes'
        indexes = [
            models.Index(
                fields=['product_compound'], name='idx_route_product_compound_id'
            ),
            models.Index(fields=['created_on'], name='idx_route_created'),
        ]


class Component(BaseModel):
    id = models.BigAutoField(primary_key=True)
    route = models.ForeignKey(
        Route,
        on_delete=models.RESTRICT,
        db_column='route_id',
    )
    component_type = models.IntegerField(null=True, blank=True)
    component_ref = models.IntegerField(null=True, blank=True)
    component_amount = models.FloatField(null=True, blank=True)

    class Meta(BaseModel.Meta):
        db_table = 'components'
        constraints = [
            models.UniqueConstraint(
                fields=[
                    'route',
                    'component_ref',
                    'component_type',
                ],
                name='uc_component',
            )
        ]
        indexes = [
            models.Index(fields=['route'], name='idx_component_route_id'),
            models.Index(fields=['created_on'], name='idx_component_created'),
        ]


# what follows is audit tables, indexes, materialised views (none),
# views, functions and triggers. I'm not sure I need them here, will create if do.


# these functions available in db
# CREATE OR REPLACE FUNCTION designdb.mol_from_smiles(smiles TEXT) RETURNS rdkit.mol
#   LANGUAGE SQL AS $$ SELECT rdkit.mol_from_smiles(smiles::cstring); $$;

# CREATE OR REPLACE FUNCTION designdb.mol_to_smiles(m rdkit.mol) RETURNS text
#   LANGUAGE SQL AS $$ SELECT rdkit.mol_to_smiles(m); $$;

# CREATE OR REPLACE FUNCTION designdb.mol_to_inchikey(m rdkit.mol) RETURNS text
#   LANGUAGE SQL AS $$ SELECT rdkit.mol_inchikey(m); $$;
