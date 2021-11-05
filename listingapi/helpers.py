from datetime import datetime
from operator import itemgetter

from django.core.cache import cache

CACHE_KEY_PREFIX = "listings"
CACHE_LISTINGS_EXPIRE = 600  # 10 minutes
MAXIMUM_PRICE_FILTER = 50000
MAX_MAXIMUM_PRICE = 1500000


def get_listings(
    min_price,
    max_price,
    guests,
    bathrooms,
    bedrooms,
    beds,
    checkin,
    checkout,
    filters,
    amenity_filters,
    market,
    building,
    complex,
    sort,
    bounds,
    enable_test_markets,
):
    # to avoid circular dependency with stay.py
    from .models import Property
    from .serializers import ListingSerializer

    if max_price >= MAXIMUM_PRICE_FILTER:
        max_price = MAX_MAXIMUM_PRICE

    date_range = DateRange(checkin, checkout)

    cache_key = f"{CACHE_KEY_PREFIX}_{market}_{building}_{complex}{checkin.strftime('%Y-%m-%d')}_{checkout.strftime('%Y-%m-%d')}"
    listings_filtered_by_market_and_date = cache.get(cache_key)
    if not listings_filtered_by_market_and_date:
        properties = Property.objects.with_bed_bath_annotations().listings(
            blocked_dates_query=date_range.blocked_dates(),
            avg_price_query=date_range.average_price(),
            num_nights=date_range.num_nights(),
            market=market,
            building=building,
            complex=complex,
            min_price=0,
            max_price=MAX_MAXIMUM_PRICE,
            guests=0,
            bathrooms=0,
            bedrooms=0,
            beds=0,
            kwargs_filters={},
            amenity_filter_codes=[],
            sort=None,
        )

        # Unless we have the query param, we need to remove all test market properties
        if not enable_test_markets:
            properties = properties.production()

        serializer = ListingSerializer(
            properties, many=True, context={"checkin": checkin, "checkout": checkout},
        )

        listings_filtered_by_market_and_date = serializer.data
        cache.set(
            cache_key, listings_filtered_by_market_and_date, CACHE_LISTINGS_EXPIRE
        )

    listings = [
        listing
        for listing in listings_filtered_by_market_and_date
        if not _filter(
            listing,
            min_price,
            max_price,
            bedrooms,
            beds,
            bathrooms,
            guests,
            amenity_filters,
            filters,
        )
    ]
    count = len(
        listings
    )  # get count of results when everything is filtered but before filtering by coords

    if bounds:
        listings = [
            listing for listing in listings if not _filter_by_coords(listing, bounds)
        ]

    in_bounds_count = len(listings)

    if sort:
        reverse_sort = sort.startswith("-")
        sort_property = sort.split("-")[-1]
        listings.sort(key=lambda l: l.get(sort_property), reverse=reverse_sort)

    return listings, count, in_bounds_count


def invalidate_listings_cache(market_pk, checkin, checkout):
    invalidate_range = DateRange(checkin, checkout)
    cache_keys = cache.keys(f"{CACHE_KEY_PREFIX}_{market_pk}_*")
    for key in cache_keys:
        try:
            *other, checkin, checkout = key.split("_")
            key_range = DateRange(
                datetime.strptime(checkin, "%Y-%m-%d").date(),
                datetime.strptime(checkout, "%Y-%m-%d").date(),
            )
            # invalidate cache for keys which overlap with this stay
            if key_range.is_overlapping(invalidate_range):
                cache.delete(key)
        except:
            pass


def _filter(
    listing,
    min_price,
    max_price,
    bedrooms,
    beds,
    bathrooms,
    guests,
    amenity_filters,
    filters,
):
    price = listing["price"]
    if not min_price <= price <= max_price:
        return True
    if (
        float(listing["num_bedrooms"]) < bedrooms
        or float(listing["num_beds"]) < beds
        or float(listing["num_bathrooms"]) < bathrooms
        or float(listing["occupancy"]) < guests
    ):
        return True

    listing_amenities = listing["amenities"]
    for amenity in amenity_filters:
        if amenity not in listing_amenities:
            return True

    if (
        filters.get("property_type__in", None)
        and listing["property_type"] not in filters["property_type__in"]
    ):
        return True

    if filters.get("wheelchair_friendly", False):
        return True

    return False


def _filter_by_coords(listing, bounds):
    coords = listing["address"]["coords"]
    return not (
        bounds["west"] <= coords["lng"] <= bounds["east"]
        and bounds["south"] <= coords["lat"] <= bounds["north"]
    )


class DateRange:
    def __init__(self, checkin, checkout):
        self.checkin = checkin
        self.checkout = checkout

    def num_nights(self):
        return (self.checkout - self.checkin).days

    def property_dates(self):
        # to avoid circular dependency with stay.py
        from .models import PropertyDate

        return PropertyDate.objects.outer_ref_property_pk().between(
            self.checkin, self.checkout
        )

    def blocked_dates(self):
        return self.property_dates().blocked_dates(self.checkin, self.checkout)

    def average_price(self):
        return self.property_dates().average_price()

    def is_overlapping(self, other):
        return (self.checkin >= other.checkin and self.checkin <= other.checkout) or (
            self.checkout >= other.checkin and self.checkout <= other.checkout
        )
