# views that pertain to /members/
import base64
import json
from math import ceil

from django.db.models import Q
from django.db.models import QuerySet
from django.shortcuts import render

from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.utils import get_profile_photo

PAGE_SIZE = 25


def _encode_cursor(payload: dict) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode()


def _decode_cursor(token: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(token.encode()).decode())


def _prefix_count_qs(qs, username, id_):
    """
    Count how many rows are <= the (username, id) tuple in the sort order.
    This is index-friendly with a composite index on (username, id).
    """
    return qs.filter(
        Q(username__lt=username) | (Q(username=username) & Q(id__lte=id_))
    ).count()


def _page_bounds(page_num: int):
    start = (page_num - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    return start, end


def people_by_username(request):
    if request.POST:
        username = request.POST.get("username")

        # make a Q query that searches username and name fields
        rows = Profile.objects.filter(
            Q(username__icontains=username) | Q(name__icontains=username)
        ).order_by("username", "id")

        return render(
            request,
            "newprofile/members.html",
            {
                "profiles": rows,
                "has_next": False,
                "has_prev": False,
                "next_cursor": None,
                "prev_cursor": None,
                "current_page": 1,
                "page_count": 1,
                "total_count": rows.count(),
                "page_size": PAGE_SIZE,
            },
        )

    cursor = request.GET.get("cursor")
    direction = request.GET.get("dir", "next")

    current_page = 1

    page_count, qs, total_count = fetch_member_data()

    rows = []

    has_next, has_prev, next_cursor, prev_cursor, rows = _handle_cursor(
        cursor, direction, qs, rows
    )

    current_page = _compute_current_page(current_page, qs, rows)

    return render(
        request,
        "newprofile/members.html",
        {
            "profiles": rows,
            "has_next": has_next,
            "has_prev": has_prev,
            "next_cursor": next_cursor,
            "prev_cursor": prev_cursor,
            "current_page": current_page,
            "page_count": page_count,
            "total_count": total_count,
            "page_size": PAGE_SIZE,
        },
    )


def _handle_cursor(
    cursor: str | None,
    direction: str,
    qs: QuerySet[Profile, Profile],
    rows: list[Profile],
) -> tuple[list[Profile], bool, bool, str | None, str | None]:
    if cursor:
        c = _decode_cursor(cursor)
        c_username, c_id = c["username"], c["id"]

        if direction == "prev":
            page_qs = qs.filter(
                Q(username__lt=c_username)
                | (Q(username=c_username) & Q(id__lt=c_id))
            ).order_by("-username", "-id")

            fetched = list(page_qs[: PAGE_SIZE + 1])
            if len(fetched) > PAGE_SIZE:
                rows = fetched[:PAGE_SIZE]
                has_prev = True
            else:
                rows = fetched
                has_prev = False

            rows.reverse()  # show A→Z
            # has_next is true because we came from a later cursor
            has_next = bool(rows)

        else:
            # next page (normal direction)
            page_qs = qs.filter(
                Q(username__gt=c_username)
                | (Q(username=c_username) & Q(id__gt=c_id))
            ).order_by("username", "id")

            fetched = list(page_qs[: PAGE_SIZE + 1])
            if len(fetched) > PAGE_SIZE:
                rows = fetched[:PAGE_SIZE]
                has_next = True
            else:
                rows = fetched
                has_next = False

            has_prev = bool(rows)

    else:
        # first page
        start_set = list(qs[: PAGE_SIZE + 1])
        if len(start_set) > PAGE_SIZE:
            rows = start_set[:PAGE_SIZE]
            has_next = True
        else:
            rows = start_set
            has_next = False
        has_prev = False

    # Build cursors
    if rows:
        first, last = rows[0], rows[-1]
        next_cursor = (
            _encode_cursor({"username": last.username, "id": last.id})
            if has_next
            else None
        )
        prev_cursor = (
            _encode_cursor({"username": first.username, "id": first.id})
            if has_prev
            else None
        )
    else:
        next_cursor = prev_cursor = None
    return has_next, has_prev, next_cursor, prev_cursor, rows


def fetch_member_data() -> tuple[int, QuerySet[Profile, Profile], int]:
    qs = (
        Profile.objects.filter(name__isnull=False)
        .only(
            "id",
            "name",
            "institutional_or_other_affiliation",
            "profile_image",
            "username",
        )
        .exclude(name__exact="")
        .order_by("username", "id")
    )

    # Cheap total count (uses index-only scans on Postgres if possible)
    total_count = qs.count()
    page_count = max(1, ceil(total_count / PAGE_SIZE)) if total_count else 1
    return page_count, qs, total_count


def _compute_current_page(
    current_page: int, qs: QuerySet[Profile, Profile], rows: list[Profile]
) -> int:
    # Compute current_page from the first visible row via a prefix COUNT
    # (This is O(log N) on a good composite index and avoids big OFFSETs)
    if rows:
        leading = _prefix_count_qs(qs, rows[0].username, rows[0].id)
        current_page = max(1, ceil(leading / PAGE_SIZE))
    else:
        current_page = 1

    # Attach images
    for profile in rows:
        profile.final_image = get_profile_photo(profile)
    return current_page
