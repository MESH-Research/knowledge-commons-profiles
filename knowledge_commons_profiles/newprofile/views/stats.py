import json
import logging
from http import HTTPStatus

from basicauth.decorators import basic_auth_required
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render

from knowledge_commons_profiles.newprofile.models import UserStats
from knowledge_commons_profiles.newprofile.models import WpUser

logger = logging.getLogger(__name__)


@basic_auth_required
def stats_board(request):
    """
    The stats dashboard
    """

    logger.debug("Getting stats dashboard for %s", request.user)

    stats = UserStats.objects.all().first()

    if stats is None:
        logger.warning("Stats requested before build_stats has been run")
        return HttpResponse(
            "Statistics have not been generated yet. Please try again later.",
            status=HTTPStatus.SERVICE_UNAVAILABLE,
            content_type="text/plain; charset=utf-8",
        )

    users = WpUser.get_user_data(limit=10)

    context = {
        "user_count": stats.user_count,
        "user_count_active": stats.user_count_active,
        "user_count_active_two": stats.user_count_active_two,
        "user_count_active_three": stats.user_count_active_three,
        "years": stats.years,
        "data": stats.data,
        "latlong": json.loads(stats.latlong),
        "topinsts": stats.topinsts,
        "topinstscount": stats.topinstscount,
        "emails": stats.emails,
        "emailcount": stats.emailcount,
        "country_count": stats.country_count,
        "countries": json.loads(stats.countries or "{}"),
        "users": users,
        "map_tile_url": settings.STATS_MAP_TILE_URL,
        "map_tile_attribution": settings.STATS_MAP_TILE_ATTRIBUTION,
        "map_tile_max_zoom": settings.STATS_MAP_TILE_MAX_ZOOM,
    }

    return render(request, "newprofile/dashboard.html", context)


@basic_auth_required
def stats_download(request):
    """
    The stats CSV download
    """

    logger.debug("Downloading stats for %s", request.user)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="users.csv"'

    WpUser.get_user_data(limit=-1, output_stream=response)

    return response


@basic_auth_required
def stats_table(request):
    """
    The stats table
    """

    logger.debug("Getting stats table for %s", request.user)

    users = WpUser.get_user_data(limit=-1)

    return render(
        request, "newprofile/partials/stats_table.html", {"users": users}
    )
