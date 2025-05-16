"""
Pagination for the REST API
"""

from rest_framework.pagination import CursorPagination
from rest_framework.response import Response

from knowledge_commons_profiles.rest_api.utils import build_metadata


class ProfileCursorPagination(CursorPagination):
    def __init__(self, *args, **kwargs):
        super().__init__()

    page_size = 20
    ordering = "id"
    cursor_query_param = "cursor"

    def get_paginated_response(self, data):
        has_full_access = bool(self.request.auth)
        # build_metadata returns a dict like {'has_full_access': True, …}
        meta = build_metadata(has_full_access)
        # add the DRF cursor links
        meta.update(
            {
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
            }
        )
        return Response({"data": data, **meta})
