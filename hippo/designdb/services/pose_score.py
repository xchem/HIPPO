import logging
import re

# from mypackage.services.compound import CompoundService
# from rdkit.Chem import inchi
from designdb.models import PoseModel, ScoreValueModel, ScoringMethodModel
from designdb.services.method import MethodService
from designdb.utils import safe_batch_size

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


class ScoreService:
    def __init__(self, scoring_method_list: list[str] | None = None):
        self._scoring_method_list = scoring_method_list
        # self._score_map = {}
        self._scoring_method_cache = {}

        # unused, but I imagine this could take various arguments,
        # like include or exclude list

        # if self._scoring_method_list:
        #     for m in self._scoring_method_list:
        #         sm, _ = ScoringMethodModel.objects.get_or_create(
        #             method_name=m,
        #         )
        #         self._score_map[sm.method_name] = sm

    @staticmethod
    def resolve_score_method_map(
        score_cols: list[str] | None,
        scoring_methods: list[tuple[str, str]] | None,
    ) -> dict[str, ScoringMethodModel]:
        """Build the SDF-column to scoring-method mapping used during ingestion.

        Pairs each score column with the registered method that produced it. The
        per-method lookup is delegated to
        :meth:`MethodService.resolve_scoring_method`; this owns only the
        column-to-method association, which is a scoring concern.

        :param score_cols: SDF column names holding score values
        :param scoring_methods: ``(name, version)`` pairs, positionally aligned
            with ``score_cols``
        :returns: mapping of column name to scoring method; empty if either
            argument is empty
        :raises ValueError: if the two arguments differ in length, or a method is
            not registered
        """
        if not (score_cols and scoring_methods):
            return {}

        if len(score_cols) != len(scoring_methods):
            raise ValueError('score_cols and scoring_methods must be the same length')

        return {
            col: MethodService.resolve_scoring_method(name, version)
            for col, (name, version) in zip(score_cols, scoring_methods, strict=True)
        }

    def add_scores_from_record(
        self,
        *,
        pose: PoseModel,
        record: dict[str, str | float],
        score_method_map: dict[str, ScoringMethodModel] | None = None,
    ):
        if score_method_map:
            scores = {col: record[col] for col in score_method_map if col in record}
        else:
            # FIXME: this because don't know how to select
            scores = {k: v for k, v in record.items() if k.lower().find('score') >= 0}

        for col_or_method_name, score_value in scores.items():
            if score_method_map:
                method = score_method_map[col_or_method_name]
            else:
                try:
                    method = self.scoring_methods[col_or_method_name]
                except KeyError:
                    method, _ = ScoringMethodModel.objects.get_or_create(
                        method_name=col_or_method_name,
                    )

            score = ScoreValueModel(
                pose=pose,
                compound=pose.compound,
                scoring_method=method,
                score={'score': score_value},
            )
            score.save()

    def add_scores_from_records_batch(
        self,
        *,
        pairs: list[tuple[PoseModel, dict[str, str | float]]],
        score_method_map: dict[str, ScoringMethodModel] | None = None,
        batch_size: int | None = None,
    ) -> int:
        """Bulk counterpart of :meth:`add_scores_from_record`.

        The per-record version calls ``score.save()`` once per score, so a file with
        two score columns costs two round trips per molecule. This collects every
        score across the batch and writes them in one statement.

        .. note::
           Uses ``update_conflicts`` rather than a plain insert, so re-loading an SDF
           updates existing scores instead of raising. The per-record version calls
           ``.save()`` on a fresh object, which issues an INSERT and violates
           ``pk_score_values`` if that (pose, compound, method) score already exists
           -- meaning re-ingesting a scored SDF currently fails. Treating it as an
           upsert is the deliberate difference, and matches how :meth:`create`
           overwrites pose metadata on re-load.

        :param pairs: ``(pose, record)`` tuples to extract scores from
        :param score_method_map: optional column to scoring-method mapping; when
            omitted, columns whose name contains "score" are used, as in the
            per-record version
        :param batch_size: rows per INSERT statement; ``None`` picks the safe
            per-model maximum. See :func:`safe_batch_size`.
        :returns: number of score rows written
        """
        objects = []
        # (pose, method) pairs already staged, so a record cannot contribute two
        # values for the same score - bulk_create cannot resolve a conflict against
        # a row inside its own batch
        staged: set[tuple[int, int]] = set()

        for pose, record in pairs:
            if score_method_map:
                scores = {col: record[col] for col in score_method_map if col in record}
            else:
                # FIXME: this because don't know how to select
                scores = {
                    k: v for k, v in record.items() if k.lower().find('score') >= 0
                }

            for col_or_method_name, score_value in scores.items():
                if score_method_map:
                    method = score_method_map[col_or_method_name]
                else:
                    try:
                        method = self.scoring_methods[col_or_method_name]
                    except KeyError:
                        method, _ = ScoringMethodModel.objects.get_or_create(
                            method_name=col_or_method_name,
                        )
                        # cache it so the batch does not re-query per record
                        self._scoring_method_cache[col_or_method_name] = method

                key = (pose.pk, method.pk)
                if key in staged:
                    continue
                staged.add(key)

                objects.append(
                    ScoreValueModel(
                        pose=pose,
                        compound_id=pose.compound_id,
                        scoring_method=method,
                        score={'score': score_value},
                    )
                )

        if not objects:
            return 0

        ScoreValueModel.objects.bulk_create(
            objects,
            update_conflicts=True,
            unique_fields=['pose', 'compound', 'scoring_method'],
            update_fields=['score'],
            batch_size=safe_batch_size(
                ScoreValueModel, objs=objects, requested=batch_size
            ),
        )
        return len(objects)

    # def bulk_scores(poses: list[pose], record: dict[str, str | float]):
    #     # potentially lots of scores, can do bulk insertion all at once
    #     pass

    @property
    def scoring_methods(self) -> dict[str, ScoringMethodModel]:
        return self._scoring_method_cache
