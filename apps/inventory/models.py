from django.db import models

from core.models import CoreModel


class MeasureType(models.TextChoices):
    PORTION = 'Portion', 'ptn',
    KILOGRAM = 'Kilogram', 'kg',
    MILLILITER = 'Milliliter', 'ml',


# Create your models here.
class Category(CoreModel):
    name = models.CharField(max_length=64, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Categories'


class Product(CoreModel):
    name = models.CharField(max_length=64, null=True, blank=True)
    type = models.CharField(max_length=20, choices=MeasureType.choices, default=MeasureType.KILOGRAM)
    price = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    category = models.ManyToManyField(to=Category, blank=False)
    image = models.ImageField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = 'Products'
