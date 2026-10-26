"""
Utilities for reading Knowledge Commons user data for the stats dashboard
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
    from collections.abc import Iterator

    from _typeshed import SupportsWrite
    from django.db.models.query import QuerySet

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 1000

USER_FIELDS = (
    "id",
    "display_name",
    "user_login",
    "user_email",
    "institution",
    "latest_activity",
    "user_registered",
)

CSV_FIELDNAMES: list[str] = [
    "id",
    "display_name",
    "user_login",
    "user_email",
    "institution",
    "date_registered",
    "latest_activity",
    "ror_institution",
    "ror_id",
    "country",
    "profile",
]


def _annotated_users() -> QuerySet[WpUser]:
    """
    The base user queryset with institution and latest activity annotated
    (only two correlated subqueries)
    """
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

    return WpUser.objects.annotate(
        institution=Subquery(institution_sq),
        latest_activity=Subquery(latest_sq),
    )


def _enrich_with_ror(users: list[dict]) -> list[dict]:
    """
    Attach ROR lookup data to a batch of user dicts, using one query for the
    lookups and one for the records (both on the default database)
    """
    distinct_insts = {u["institution"] for u in users if u["institution"]}

    lookups = (
        RORLookup.objects.filter(text__in=distinct_insts)
        if distinct_insts
        else []
    )
    lookup_by_text = {rl.text: rl for rl in lookups}

    ror_ids = {rl.ror.id for rl in lookup_by_text.values() if rl.ror}
    records = RORRecord.objects.in_bulk(ror_ids) if ror_ids else {}

    for u in users:
        u["profile"] = "https://hcommons.org/members/" + u["user_login"]

        inst = u["institution"]
        rl = lookup_by_text.get(inst)
        rec = records.get(rl.ror.id) if (rl and rl.ror) else None

        u["ror"] = rl.ror if rl else None
        u["ror_record"] = rec if rec else None
        u["canonical_institution_name"] = (
            rec.institution_name if rec and rec.institution_name else inst
        )
        u["country"] = rec.country if rec and rec.country else None

        if "user_registered" not in u:
            u["user_registered"] = None

    return users


def iter_user_data(
    limit: int = -1, chunk_size: int = DEFAULT_CHUNK_SIZE
) -> Iterator[dict]:
    """
    Stream annotated user dicts in bounded chunks.

    Users are paged by primary key so that each query against the WordPress
    database returns at most chunk_size rows, and the ROR lookups for each
    chunk are loaded in bulk before its users are yielded.

    :param limit: max number of users, or -1 for all
    :param chunk_size: number of users fetched per query
    """
    if chunk_size < 1:
        msg = "chunk_size must be at least 1"
        raise ValueError(msg)

    base = _annotated_users()
    last_pk = None
    remaining = None if limit == -1 else limit

    while remaining is None or remaining > 0:
        size = chunk_size if remaining is None else min(chunk_size, remaining)

        qs = base
        if last_pk is not None:
            qs = qs.filter(pk__gt=last_pk)

        batch = list(qs.order_by("pk").values(*USER_FIELDS)[:size])

        if not batch:
            return

        yield from _enrich_with_ror(batch)

        last_pk = batch[-1]["id"]
        if remaining is not None:
            remaining -= len(batch)

        if len(batch) < size:
            return


def _csv_row(wp_user: dict) -> dict:
    """
    Map a user dict onto the CSV columns
    """
    record = wp_user["ror_record"]

    return {
        "id": wp_user["id"],
        "display_name": wp_user["display_name"],
        "profile": wp_user["profile"],
        "user_login": wp_user["user_login"],
        "user_email": wp_user["user_email"],
        "institution": wp_user["institution"],
        "date_registered": wp_user["user_registered"],
        "latest_activity": (
            wp_user["latest_activity"] if wp_user["latest_activity"] else None
        ),
        "ror_institution": record.institution_name if record else None,
        "ror_id": record.ror_id if record else None,
        "country": wp_user["country"],
    }


@staticmethod
def get_user_data(
    output_stream: SupportsWrite[str] | None = None, limit: int = -1
) -> list[dict]:
    """
    :param output_stream: if given, write CSV rows here
    :param limit: max number of users, or -1 for all
    :return: list of user dicts
    """
    writer: csv.DictWriter | None = None

    if output_stream:
        writer = csv.DictWriter(
            output_stream,
            fieldnames=CSV_FIELDNAMES,
            quotechar='"',
            quoting=csv.QUOTE_ALL,
            lineterminator="\n",
        )
        writer.writeheader()

    users: list[dict] = []

    for wp_user in iter_user_data(limit=limit):
        users.append(wp_user)

        if writer:
            writer.writerow(_csv_row(wp_user))

    logger.info("Got WordPress users (%s)", len(users))

    return users
