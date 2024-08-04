from django.db import models

from apps.account.models import User
from apps.inventory.models import Product
from core.models import CoreModel


class StatusType(models.TextChoices):
    UNKNOWN = 'UNKNOWN', 'Unknown'
    PENDING = 'PENDING', 'Pending'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    COMPLETED = 'COMPLETED', 'Completed'


# Create your models here.
class Order(CoreModel):
    user: User = models.ForeignKey(to=User, null=False, blank=False, on_delete=models.CASCADE, related_name='orders')
    location = models.CharField(max_length=512, null=True, blank=True)
    status = models.CharField(max_length=20, choices=StatusType.choices, default=StatusType.UNKNOWN)

    def __str__(self):
        return self.user.username

    class Meta:
        verbose_name_plural = 'Orders'


class OrderItem(CoreModel):
    order: Order = models.ForeignKey(to=Order, null=False, blank=False, on_delete=models.CASCADE, related_name='items')
    quantity = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    product = models.ForeignKey(to=Product, null=False, blank=False, on_delete=models.CASCADE,
                                related_name='order_items')

    def __str__(self):
        return f"{self.order} - {self.product.name}"

    class Meta:
        verbose_name_plural = 'Order Items'
