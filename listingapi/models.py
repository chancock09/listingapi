from django.db import models

class Property(models.Model):
    short_name = models.CharField(max_length=30)

class PropertyDate(models.Model):
    is_block = models.BooleanField()
    is_available = models.BooleanField()
    price = models.IntegerField()

class Market(models.Model):
    short_name = models.CharField(max_length=30)

class BookingPlatform(models.Model):
    name = models.CharField(max_length=32, unique=True)
    commission_bps = models.IntegerField(default=0)
    service_fee_bps = models.IntegerField(default=0)

class Address(models.Model):
    line_one = models.TextField()
    line_two = models.TextField(blank=True)
    city = models.TextField()
    zip_code = models.TextField()
