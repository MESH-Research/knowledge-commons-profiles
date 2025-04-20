"""
A set of models for user profiles
"""

import csv
import logging
from typing import TYPE_CHECKING

# pylint: disable=too-few-public-methods,no-member, too-many-ancestors
from django.db.models import Case
from django.db.models import IntegerField
from django.db.models import OuterRef
from django.db.models import Subquery
from django.db.models import Value
from django.db.models import When
from django.db.models.functions import Coalesce

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
    Get user data as a CSV written to a stream or a list of dicts

    :param output_stream: stream to write to
    :param limit: number of users to get or -1 for all
    :return:
    """

    logger.info("Fetching WordPress users")

    writer: csv.DictWriter | None = None

    # first, make sure there is at least one RORLookup row
    if RORLookup.objects.all().count() == 0:
        RORLookup.objects.create(text="Test", ror=None)

    # 1) Subquery for the institution:
    institution_sq = (
        WpProfileData.objects.filter(
            user_id=OuterRef("pk"),
            field__name="Institutional or Other Affiliation",
        )
        .order_by()
        .values("value")[:1]
    )

    # 2) Subquery for the latest activity date:
    latest_activity_sq = (
        WpBpActivity.objects.filter(user_id=OuterRef("pk"))
        .order_by("-date_recorded")
        .values("date_recorded")[:1]
    )

    if limit == -1:
        users: QuerySet[WpUser] = WpUser.objects.annotate(
            institution=Subquery(institution_sq),
            latest_activity=Subquery(latest_activity_sq),
        )
    else:
        users: QuerySet[WpUser] = WpUser.objects.annotate(
            institution=Subquery(institution_sq),
            latest_activity=Subquery(latest_activity_sq),
        )[:limit]

    ror_map = {row.text: row.ror for row in RORLookup.objects.all()}

    cases = [
        When(institution=inst, then=Value(ror.id) if ror else None)
        for inst, ror in ror_map.items()
    ]

    users = users.annotate(
        ror=Coalesce(
            Case(*cases, default=Value(None), output_field=IntegerField()),
            Value(None),
        )
    )

    ror_record_ids = {u.ror for u in users if u.ror is not None}
    ror_record_map = RORRecord.objects.in_bulk(ror_record_ids)

    for u in users:
        record = ror_record_map.get(u.ror, None)

        u.canonical_institution_name = (
            record.institution_name
            if record and record.institution_name
            else u.institution
        )

        u.ror_record = record

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
