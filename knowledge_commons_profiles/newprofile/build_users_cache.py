"""
A set of models for user profiles
"""

import csv
import logging
from typing import TYPE_CHECKING

# pylint: disable=too-few-public-methods,no-member, too-many-ancestors
from django.db.models import OuterRef
from django.db.models import Subquery

from knowledge_commons_profiles.newprofile.models import RORLookup
from knowledge_commons_profiles.newprofile.models import RORRecord
from knowledge_commons_profiles.newprofile.models import WpBpActivity
from knowledge_commons_profiles.newprofile.models import WpProfileData
from knowledge_commons_profiles.newprofile.models import WpUser

if TYPE_CHECKING:
    from _typeshed import SupportsWrite
    from django.db.models.query import QuerySet

logger = logging.getLogger(__name__)


@staticmethod
def get_user_data(
    output_stream: "SupportsWrite[str] | None" = None, limit: int = -1
) -> "QuerySet[WpUser]":
    """
    :param output_stream: if given, write CSV rows here
    :param limit: max number of users, or -1 for all
    :return: list of dicts (if no output_stream), else None
    """

    # 1) build the annotated base queryset (only two correlated subqueries)
    institution_sq = (
        WpProfileData.objects.filter(
            user_id=OuterRef("pk"),
            field__name="Institutional or Other Affiliation",
        )
        .order_by()
        .values("value")[:1]
    )
    latest_sq = (
        WpBpActivity.objects.filter(user_id=OuterRef("pk"))
        .order_by("-date_recorded")
        .values("date_recorded")[:1]
    )

    qs = WpUser.objects.annotate(
        institution=Subquery(institution_sq),
        latest_activity=Subquery(latest_sq),
    )
    if limit != -1:
        qs = qs[:limit]

    # 2) pull out exactly the columns we need into Python dicts
    users = list(
        qs.values(
            "id",
            "display_name",
            "user_login",
            "user_email",
            "institution",
            "latest_activity",
            "user_registered",
        )
    )

    # 3) bulk load all RORLookup rows in one shot (other DB)
    distinct_insts = {u["institution"] for u in users if u["institution"]}
    lookups = RORLookup.objects.filter(text__in=distinct_insts)
    lookup_by_text = {rl.text: rl for rl in lookups}

    # 4) bulk-load all RORRecord rows you'll need
    ror_ids = {rl.ror.id for rl in lookup_by_text.values() if rl.ror}
    records = RORRecord.objects.in_bulk(ror_ids)

    for u in users:
        inst = u["institution"]
        rl = lookup_by_text.get(inst)
        rec = records.get(rl.ror.id) if (rl and rl.ror) else None

        u["ror"] = rl.ror if rl else None
        u["ror_record"] = rec if rec else None
        u["canonical_institution_name"] = (
            rec.institution_name if rec and rec.institution_name else inst
        )
        u["user_registered"] = u["user_registered"]

        if "user_registered" not in u:
            u["user_registered"] = None

    logger.info("Got WordPress users (%s)", len(users))

    fieldnames: list[str] = [
        "id",
        "display_name",
        "user_login",
        "user_email",
        "institution",
        "date_registered",
        "latest_activity",
    ]

    if output_stream:
        writer: csv.DictWriter = csv.DictWriter(
            output_stream,
            fieldnames=fieldnames,
            quotechar='"',
            quoting=csv.QUOTE_ALL,
            lineterminator="\n",
        )
        writer.writeheader()

        wp_user: WpUser

        for wp_user in users:
            output_object: dict = {
                "id": wp_user.id,
                "display_name": wp_user.display_name,
                "user_login": wp_user.user_login,
                "user_email": wp_user.user_email,
                "institution": wp_user.institution,
                "date_registered": wp_user.user_registered,
                "latest_activity": (
                    wp_user.latest_activity
                    if wp_user.latest_activity
                    else None
                ),
            }

            writer.writerow(output_object)

    return users
