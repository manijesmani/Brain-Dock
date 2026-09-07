from collections import OrderedDict
from typing import Any

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class DefaultPagination(PageNumberPagination):
    """Page-number pagination with a client-adjustable page size.

    The response is flattened into a `results` list plus a `pagination` object
    so the frontend has one predictable shape to read instead of DRF's default
    mix of top-level keys.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data: Any) -> Response:
        return Response(
            OrderedDict(
                [
                    ("results", data),
                    (
                        "pagination",
                        OrderedDict(
                            [
                                ("count", self.page.paginator.count),
                                ("page", self.page.number),
                                ("pages", self.page.paginator.num_pages),
                                ("page_size", self.get_page_size(self.request)),
                                ("next", self.get_next_link()),
                                ("previous", self.get_previous_link()),
                            ]
                        ),
                    ),
                ]
            )
        )
