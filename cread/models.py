# -*- coding: utf-8 -*-

from django.db import models
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _

from geonode.base.models import ResourceBase, TopicCategory
from geonode.layers.models import Layer


class CReadCategory(models.Model):

    related_help_text = _('TopicCategory associated to this category')

    identifier = models.CharField(max_length=8, unique=True, null=False, blank=False)
    name = models.CharField(max_length=32, unique=True)
    description = models.TextField(default='')

    relatedtopic = models.ForeignKey(TopicCategory, null=False, help_text=related_help_text)

    class Meta:
        ordering = ("identifier",)


class CReadSubCategory(models.Model):

    issue_help_text = _('Main category this issue belongs to')

    identifier = models.CharField(max_length=8, unique=True, null=False, blank=False)
    name = models.CharField(max_length=32)
    description = models.TextField(default='')

    category = models.ForeignKey(CReadCategory, null=False, blank=False, limit_choices_to=Q(is_choice=True),
                                 help_text=issue_help_text)

    class Meta:
        ordering = ("identifier",)


class Mosaic(models.Model):

    layer = models.ForeignKey(Layer, blank=False, null=False)


class MosaicDimension(models.Model):

    allowed_formats = (
        ('DIM_year', 'yyyy'),
        ('DIM_year_month', 'yyyy-mm'),
        ('DIM_full_date', 'yyyy-mm-dd'),
        ('DIM_fulle_timestamp', 'yyyy-mm-ddThh:MM:ss')
    )

    allowed_types = (
        ('TYPE_time', 'Time'),
        ('TYPE_elev', 'Elevation')
    )

    def __init__(self):
        super(MosaicDimension, self).__init__()

    layer = models.ForeignKey(Mosaic, blank=False, null=False)

    dimtype = models.CharField(max_length=8, null=False, blank=False, choices=allowed_types)  # 'date' 'elev'
    dimformat = models.CharField(max_length=16, choices=allowed_formats)


