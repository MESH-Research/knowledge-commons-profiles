# views that pertain to /members/
import base64
import json
from math import ceil

from django.conf import settings
from django.db.models import Prefetch
from django.db.models import Q
from django.db.models import QuerySet
from django.db.models import TextField
from django.db.models.functions import Cast
from django.http import Http404
from django.shortcuts import redirect
from django.shortcuts import render

from knowledge_commons_profiles.newprofile.models import AcademicInterest
from knowledge_commons_profiles.newprofile.models import Profile
from knowledge_commons_profiles.newprofile.utils import get_profile_photo

PAGE_SIZE = 25
MAX_DISPLAY_INTERESTS = 5


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


def go_to_works(request):
    # redirect to NAV_WORKS_URL
    return redirect(settings.NAV_WORKS_URL)


def resolve_network_name(network_name: str) -> str:
    """
    Map a URL network slug to its canonical society name.

    Slugs are looked up case-insensitively in KNOWN_SOCIETY_MAPPINGS
    (e.g. "stemedplus" -> "STEMED+"). Unknown slugs are treated as
    literal network names (e.g. "up" -> "up").
    """
    return settings.KNOWN_SOCIETY_MAPPINGS.get(
        network_name.lower(), network_name
    )


def resolve_network_display_name(network: str) -> str:
    """
    Map a canonical network name to its human display name.

    Looked up case-insensitively in NETWORK_DISPLAY_NAMES; networks
    without an entry display their canonical name unchanged.
    """
    return settings.NETWORK_DISPLAY_NAMES.get(network.lower(), network)


def _has_network_membership(profile: Profile, network_lower: str) -> bool:
    """
    Check a profile's final roles for the given network, ignoring case.

    Final roles are the canonical merge of the synced is_member_of JSON
    and the manual role_overrides layer, as computed by
    get_external_memberships (the same logic as the manage-roles page).
    """
    memberships = profile.get_external_memberships()
    return any(
        value and key.lower() == network_lower
        for key, value in memberships.items()
    )


def _paginate_profile_list(
    rows_all: list[Profile], cursor: str | None, direction: str
) -> tuple[list[Profile], bool, bool, str | None, str | None, int]:
    """
    Cursor-paginate an in-memory, (username, id)-ordered profile list.

    Mirrors the cursor semantics of _handle_cursor so the members
    template's pager links work unchanged.
    """
    if cursor:
        c = _decode_cursor(cursor)
        key = (c["username"], c["id"])

        if direction == "prev":
            before = [p for p in rows_all if (p.username, p.id) < key]
            rows = before[-PAGE_SIZE:]
            has_prev = len(before) > PAGE_SIZE
            has_next = bool(rows)
        else:
            after = [p for p in rows_all if (p.username, p.id) > key]
            rows = after[:PAGE_SIZE]
            has_next = len(after) > PAGE_SIZE
            has_prev = bool(rows)
    else:
        rows = rows_all[:PAGE_SIZE]
        has_next = len(rows_all) > PAGE_SIZE
        has_prev = False

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
        leading = rows_all.index(rows[0]) + 1
        current_page = max(1, ceil(leading / PAGE_SIZE))
    else:
        next_cursor = prev_cursor = None
        current_page = 1

    return rows, has_next, has_prev, next_cursor, prev_cursor, current_page


def network_members(request, network_name):
    """
    List members whose final roles include the given network.

    The database narrows candidates with a cheap substring prefilter on
    the is_member_of JSON and the role_overrides array (no false
    negatives: a matching role must contain the network name verbatim).
    Final membership is then verified per profile via the canonical
    get_external_memberships merge, so this listing always agrees with
    the manage-roles page.
    """
    network = resolve_network_name(network_name)
    network_lower = network.lower()

    # NETWORK_DISPLAY_NAMES is the allowlist of networks we serve;
    # everything else is rejected rather than rendered as a phantom
    # empty network (the subdomain middleware applies the same gate)
    if network_lower not in settings.NETWORK_DISPLAY_NAMES:
        msg = f"Unknown network: {network_name}"
        raise Http404(msg)

    candidates = (
        Profile.objects.filter(name__isnull=False)
        .exclude(name__exact="")
        .annotate(role_overrides_text=Cast("role_overrides", TextField()))
        .filter(
            Q(is_member_of__icontains=f'"{network}"')
            | Q(role_overrides_text__icontains=network)
        )
        .prefetch_related(
            Prefetch(
                "academic_interests",
                queryset=AcademicInterest.objects.all(),
                to_attr="display_interests",
            ),
            "profileimage_set",
        )
        .order_by("username", "id")
    )

    rows_all = [
        profile
        for profile in candidates
        if _has_network_membership(profile, network_lower)
    ]

    total_count = len(rows_all)
    page_count = max(1, ceil(total_count / PAGE_SIZE))

    cursor = request.GET.get("cursor")
    direction = request.GET.get("dir", "next")

    rows, has_next, has_prev, next_cursor, prev_cursor, current_page = (
        _paginate_profile_list(rows_all, cursor, direction)
    )

    for profile in rows:
        profile.final_image = get_profile_photo(profile)

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
            "interest_filter": None,
            "max_display_interests": MAX_DISPLAY_INTERESTS,
            "network": network,
            "network_display_name": resolve_network_display_name(network),
        },
    )


def people_by_username(request):
    # on a network subdomain (NetworkSubdomainMiddleware) the members
    # directory is scoped to that network, as /network/<name>/members/
    network = getattr(request, "network", None)
    if network:
        return network_members(request, network)

    interest_filter = request.GET.get("interest")

    if request.POST:
        username = request.POST.get("username")

        # make a Q query that searches username and name fields
        rows = (
            Profile.objects.filter(
                Q(username__icontains=username) | Q(name__icontains=username)
            )
            .prefetch_related(
                Prefetch(
                    "academic_interests",
                    queryset=AcademicInterest.objects.all(),
                    to_attr="display_interests",
                ),
                "profileimage_set",
            )
            .order_by("username", "id")
        )

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
                "interest_filter": interest_filter,
                "max_display_interests": MAX_DISPLAY_INTERESTS,
            },
        )

    cursor = request.GET.get("cursor")
    direction = request.GET.get("dir", "next")

    current_page = 1

    page_count, qs, total_count = fetch_member_data(interest=interest_filter)

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
            "interest_filter": interest_filter,
            "max_display_interests": MAX_DISPLAY_INTERESTS,
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


def fetch_member_data(
    interest: str | None = None,
) -> tuple[int, QuerySet[Profile, Profile], int]:
    qs = (
        Profile.objects.filter(name__isnull=False)
        .exclude(name__exact="")
        .prefetch_related(
            Prefetch(
                "academic_interests",
                queryset=AcademicInterest.objects.all(),
                to_attr="display_interests",
            ),
            "profileimage_set",
        )
        .order_by("username", "id")
    )

    if interest:
        qs = qs.filter(academic_interests__text=interest)

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
