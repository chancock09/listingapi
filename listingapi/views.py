import datetime

from django.utils.dateparse import parse_datetime
from django.core.paginator import Paginator
from django.db.models import OuterRef
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .helpers import get_listings
from .models import Market, Property
from .serializers import ListingSerializer

LISTINGS_PER_PAGE = 20

class ListingViewSet(viewsets.ViewSet):
    """
    Guest-facing wrapper for Property.
    """

    permission_classes = (AllowAny,)

    def list(self, request):
        """
        `query_params` values:
            checkin: YYYY-MM-DD
            checkout: YYYY-MM-DD
            min_price: number
            max_price: number
            guests: number
            beds: number,
            bathrooms: number
            bedrooms: number
            sort: string
            page: number
        """
        query = request.query_params
        bedrooms = int(query.get("bedrooms", 0))
        # If the guest sets their min # of bedrooms to 1, we'd like to still
        # expose our "0 bedroom" / studio units
        if bedrooms == 1:
            bedrooms = 0
        beds = int(query.get("beds", 0))
        bathrooms = int(query.get("bathrooms", 0))
        guests = int(query.get("guests", 0))
        market = int(query.get("market", 0))
        building = int(query.get("building", 0))
        complex = int(query.get("complex", 0))
        page_number = int(query.get("page", 1))
        min_price = int(query.get("min_price", 0)) * 100
        max_price = int(query.get("max_price", 500)) * 100
        sort = query.get("sort")

        listings, total_count, in_bounds_count = get_listings(
            min_price,
            max_price,
            guests,
            bathrooms,
            bedrooms,
            beds,
            self._checkin(),
            self._checkout(),
            self._kwargs_filters(query),
            self._amenity_filters(query),
            market,
            building,
            complex,
            sort,
            self._parse_bounds(query.get("bounds", None)),
            request.GET.get("enable_test_markets"),
        )

        paginator = Paginator(listings, LISTINGS_PER_PAGE)
        page_number = min(page_number, paginator.num_pages)
        response = {
            "total_count": total_count,
            "in_bounds_count": in_bounds_count,
            "result": paginator.page(page_number).object_list,
        }

        return Response(response)

    def retrieve(self, request, pk=None):
        properties = (
            Property.objects.active_on_wanderjaunt().with_bed_bath_annotations()
        )
        property = get_object_or_404(properties, pk=pk)
        serializer = ListingSerializer(
            property, context={"checkin": self._checkin(), "checkout": self._checkout()}
        )
        return Response(serializer.data)

    def _kwargs_filters(self, query):
        kwargs_filters = {}

        townhouse = query.get("townhouse")
        apartment = query.get("apartment")
        house = query.get("house")
        container = query.get("container")

        if (
            townhouse == "true"
            or apartment == "true"
            or house == "true"
            or container == "true"
        ):
            prop_types = []
            if townhouse == "true":
                prop_types.append("townhouse")
            if apartment == "true":
                prop_types.append("apartment")
            if house == "true":
                prop_types.append("house")
            if container == "true":
                prop_types.append("container")
            kwargs_filters["property_type__in"] = prop_types

        wheelchair_friendly = query.get("wheelchair_friendly")
        if wheelchair_friendly == "true":
            kwargs_filters["wheelchair_friendly"] = True

        return kwargs_filters

    def _amenity_filters(self, query):
        amenity_filter_codes = []
        street_parking = query.get("street_parking")
        if street_parking == "true":
            amenity_filter_codes.append("FREE_STREET_PARKING")
        garage_parking = query.get("garage_parking")
        if garage_parking == "true":
            amenity_filter_codes.append("GARAGE_PARKING")
        gym = query.get("gym")
        if gym == "true":
            amenity_filter_codes.append("GYM")
        pool = query.get("pool")
        if pool == "true":
            amenity_filter_codes.append("POOL")
        hottub = query.get("hot_tub")
        if hottub == "true":
            amenity_filter_codes.append("HOT_TUB")
        washer_dryer = query.get("washer_dryer")
        if washer_dryer == "true":
            amenity_filter_codes.append("WASHER_DRYER")
        dishwasher = query.get("dishwasher")
        if dishwasher == "true":
            amenity_filter_codes.append("DISHWASHER")
        return amenity_filter_codes

    def _checkin(self):
        return (
            parse_datetime(self.request.query_params["checkin"])
            if self.request.query_params.get("checkin")
            else datetime.date.today() + datetime.timedelta(days=7)
        )

    def _checkout(self):
        return (
            parse_datetime(self.request.query_params["checkout"])
            if self.request.query_params.get("checkout")
            and self.request.query_params["checkout"] != "Invalid date"
            else self._checkin() + datetime.timedelta(days=7)
        )

    def _service_fee(self):
        return Market.objects.filter(property=OuterRef("pk")).values("service_fee")

    def _parse_bounds(self, bounds_string):
        try:
            splits = bounds_string.split(",")
            return {
                "north": float(splits[0]),
                "east": float(splits[1]),
                "south": float(splits[2]),
                "west": float(splits[3]),
            }
        except:
            return None
