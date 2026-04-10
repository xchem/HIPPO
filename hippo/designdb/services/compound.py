import logging
import re

import mrich
import rdkit
# from rdkit.Chem import inchi
from designdb.models import Compound, CompoundTag
from designdb.utils import inchikey_from_smiles, sanitise_smiles
# from mypackage.services.compound import CompoundService
from rdkit import Chem

# from .validation.compound import ValidationError, validate_compound_data

SDF_XCAv2_PATTERN = re.compile(
    r'^.*-.\d{4}_._\d*_\d_.*-.\d{4}\+.\+\d*\+\d_ligand\.sdf$'
)
SDF_XCAV3_PATTERN = re.compile(
    r'^.*-.\d{4}_._\d*_._\d_.*-.\d{4}\+.\+\d*\+.\+\d_ligand\.sdf$'
)


SDF_FRAGALYSIS_PATTERN = re.compile(r'^.*\d{4}[a-z].sdf$')
PDBID_PATTERN = re.compile(r'^[A-Za-z0-9]{4}-[a-z].sdf$')


logger = logging.getLogger(__name__)


class CompoundBatchResult:
    def __init__(self):
        self.created = []
        self.errors = []


class CompoundService:
    @classmethod
    def create(
        cls,
        *,
        mol: Chem.rdchem.Mol,
        smiles: str,
        inchikey: str,
    ) -> tuple[Compound, bool]:

        # TODO: new fields to consider, fingerprints and tautomer hashes

        # TODO and SQLITE_RELIC: inchikey is calculated by postgres in
        # trigger. But I need to calculate it here as well, for
        # queries. I feel like having two different calculation
        # methods is not ideal. Are the versions guaranteed to be the
        # same? And even if I do this in trigger, it's already here,
        # why not just insert it?

        compound, created = Compound.objects.get_or_create(
            compound_inchikey=inchikey,
            # compound_smiles=smiles,
            defaults={
                'compound_mol': mol,
                'compound_smiles': smiles,
                'rdkit_version': rdkit.__version__,
                'inchi_version': Chem.inchi.GetInchiVersion(),
            },
        )
        if not created and logger.level == logging.DEBUG:
            mrich.warning(
                f'Skipping compound {inchikey}, {smiles}, duplicate of {compound.pk}'
            )

        # there's a following block in the original code
        # I don't understand what it is trying to achieve
        # smiles and inchikey are both inserted, so compound existing
        # but not reachable by inchikey should not happen. maybe this
        # covers compounds loaded through different pathway?

        # compound_id = self.db.insert_compound(
        #     smiles=smiles,
        #     tags=tags,
        #     warn_duplicate=debug,
        #     commit=False,
        # )

        # if not compound_id:
        #     inchikey = inchikey_from_smiles(smiles)
        #     compound = self.compounds[inchikey]

        #     if not compound:
        #         mrich.error(
        #             'Compound exists in database but could not be found by inchikey'
        #         )
        #         mrich.var('smiles', smiles)
        #         mrich.var('inchikey', inchikey)
        #         mrich.var('observation_shortname', name)
        #         raise Exception

        # else:
        #     count_compound_registered += 1
        #     compound = self.compounds[compound_id]

        return compound, created

    @classmethod
    def create_from_smiles(
        cls,
        smiles_list: list[str],
    ) -> list[tuple[str, str]]:
        result = []
        for smiles in smiles_list:
            sane_smiles = sanitise_smiles(
                smiles, verbosity=logger.level == logging.DEBUG
            )
            mol = Chem.MolFromSmiles(sane_smiles)
            sane_inchikey = inchikey_from_smiles(sane_smiles)

            cls.create(
                mol=mol,
                smiles=sane_smiles,
                inchikey=sane_inchikey,
            )

            result.append((sane_inchikey, sane_smiles))

        return result


class CompoundTagService:
    @staticmethod
    def tags_from_list(tag_list: list[str]):
        assert tag_list is not None, '"None" passed as tag_list'

        CompoundTag.objects.bulk_create(
            [CompoundTag(compound_tag_name=k.strip()) for k in tag_list if k.strip()],
            ignore_conflicts=True,
        )
        tags = CompoundTag.objects.filter(compound_tag_name__in=tag_list)
        return tags
