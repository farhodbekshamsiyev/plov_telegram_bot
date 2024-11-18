from django.db import models

from apps.account.models import User
from apps.inventory.models import Product
from core.models import CoreModel


class StatusType(models.TextChoices):
    UNKNOWN = 'UNKNOWN', 'Unknown'
    PENDING = 'PENDING', 'Pending'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    CHECKED_OUT = 'CHECKED_OUT', 'Checked Out'
    COMPLETED = 'COMPLETED', 'Completed'


# Create your models here.
class Order(CoreModel):
    user: User = models.ForeignKey(to=User, null=False, blank=False, on_delete=models.CASCADE, related_name='orders')
    location = models.CharField(max_length=512, null=True, blank=True)
    status = models.CharField(max_length=20, choices=StatusType.choices, default=StatusType.UNKNOWN)
    delivery_date = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.user.username

    class Meta:
        verbose_name_plural = 'Orders'


class OrderItem(CoreModel):
    order: Order = models.ForeignKey(to=Order, null=False, blank=False, on_delete=models.CASCADE, related_name='items')
    quantity = models.IntegerField(null=True, blank=True)
    product = models.ForeignKey(to=Product, null=False, blank=False, on_delete=models.CASCADE,
                                related_name='order_items')

    def __str__(self):
        return f"{self.order} - {self.product.name}"

    class Meta:
        verbose_name_plural = 'Order Items'


class PredefinedLocations(CoreModel):
    location_name = models.CharField(max_length=512, null=True, blank=True)
    location_description = models.CharField(max_length=512, null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location_code = models.CharField(max_length=4, null=True, blank=True)

    def __str__(self):
        return self.location_name

    class Meta:
        verbose_name_plural = 'Predefined Locations'
