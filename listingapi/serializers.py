from datetime import datetime, timedelta

from django.db.models import Q
from rest_framework import serializers

from .models import Property, PropertyDate, Address

class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = (
            "pk",
            "street",
            "city",
            "state",
            "country",
            "zipcode",
            "coords",
            "city_model",
        )

    coords = serializers.SerializerMethodField()
    city_model = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    street = serializers.SerializerMethodField()

    def get_coords(self, obj):
        return {"lat": obj.coords.y, "lng": obj.coords.x}

    def get_city(self, obj):
        return obj.city.name

    def get_street(self, obj):
        prop = self.context.get("property", None)
        if not prop:
            return obj.street
        else:
            return prop.street

class ListingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = (
            "pk",
            "address",
            "external_platform_listing_name",
            "amenities",
            "blocked_dates",
            "check_in_dates",
            "check_out_dates",
            "description",
            "name",
            "num_bathrooms",
            "num_bedrooms",
            "num_beds",
            "occupancy",
            "price",
            "property_type",
            "property_type",
            "blocked_dates",
            "wheelchair_friendly",
            "amenities",
            "description",
            "property_type",
            "stairs_required",
            "max_booking_date",
            "market",
            "is_new",
            "num_bookings",
            "min_stay_length",
            "original_price",
        )

    num_bedrooms = serializers.IntegerField()
    num_beds = serializers.IntegerField()
    num_bathrooms = serializers.DecimalField(max_digits=3, decimal_places=1)
    amenities = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    blocked_dates = serializers.SerializerMethodField()
    check_in_dates = serializers.SerializerMethodField()
    check_out_dates = serializers.SerializerMethodField()
    wheelchair_friendly = serializers.SerializerMethodField()
    external_platform_listing_name = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()
    is_new = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()
    num_reviews = serializers.SerializerMethodField()
    num_bookings = serializers.SerializerMethodField()
    original_price = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()

    @staticmethod
    def setup_eager_loading(queryset):
        queryset = queryset.select_related("building__address__city__market")
        queryset = queryset.prefetch_related(
            "booking__airbnb_reviews", "listing_photos"
        )
        return queryset

    def get_is_new(self, obj):
        if not obj.activation_completed_date:
            return False

        today = datetime.today().date()
        one_month_ago = today - timedelta(days=30)

        return obj.activation_completed_date > one_month_ago

    def get_num_bookings(self, obj):
        return obj.usages.bookings().count()


    def get_address(self, obj):
        return AddressSerializer(obj.address, context={"property": obj}).data

    def get_amenities(self, obj):
        return obj.amenity_codes("WANDERJAUNT")

    def get_description(self, obj):
        return obj.description

    def get_blocked_dates(self, obj):
        return [date.date.strftime("%Y-%m-%d") for date in self._blocked_dates(obj)]

    def get_external_platform_listing_name(self, obj):
        return obj.external_platform_listing_name.replace(" by WanderJaunt", "")

    def get_wheelchair_friendly(self, obj):
        return not obj.stairs_required

    def get_price(self, obj):
        avg_price = (self._property_dates(obj).average_price())[0]["avg_price"]
        nightly_service_fee = (
            avg_price + self._cleaning_fee_per_night(obj)
        ) * self._service_fee(obj)

        return int(avg_price + nightly_service_fee)

    def get_check_in_dates(self, obj):
        return [
            date.date.strftime("%Y-%m-%d")
            for date in self._check_in_property_dates(obj)
        ]

    def get_check_out_dates(self, obj):
        return [
            date.date.strftime("%Y-%m-%d")
            for date in self._check_out_property_dates(obj)
        ]

    def _num_nights(self):
        return (self.context.get("checkout") - self.context.get("checkin")).days

    def _property_dates(self, obj):
        return (
            PropertyDate.objects.between(
                self.context.get("checkin"), self.context.get("checkout")
            )
            .filter(property=obj)
            .order_by()
        )

    def _check_in_property_dates(self, obj):
        return (PropertyDate.objects.filter(property=obj).check_in_dates()).order_by()

    def _check_out_property_dates(self, obj):
        return (PropertyDate.objects.filter(property=obj).check_out_dates()).order_by()

    def _blocked_dates(self, obj):
        return (
            PropertyDate.objects.filter(property=obj)
            .filter(Q(date__gte=datetime.now()))
            .filter(Q(is_block=True))
            .filter(Q(is_available=True))
        )

    def _cleaning_fee_per_night(self, obj):
        price = int(100 * obj.cleaning_fee) or 12000
        return float(price / self._num_nights())

    def _service_fee(self, obj):
        return float(obj.market.service_fee / 100)
