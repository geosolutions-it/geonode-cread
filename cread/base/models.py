# -*- coding: utf-8 -*-

from django.db import models
from django.utils.translation import ugettext_lazy as _

from geonode.base.models import ResourceBase, TopicCategory


class CReadCategory(models.Model):

    identifier = models.CharField(max_length=8, unique=True, null=False, blank=False)
    name = models.CharField(max_length=32, unique=True)
    description = models.TextField(default='')

    class Meta:
        ordering = ("identifier",)
        db_table = 'cread_category'


class CReadSubCategory(models.Model):

    issue_help_text = _('Main category this issue belongs to')
    related_help_text = _('TopicCategory associated to this category')

    identifier = models.CharField(max_length=8, unique=True, null=False, blank=False)
    name = models.CharField(max_length=32)
    description = models.TextField(default='')

    category = models.ForeignKey(CReadCategory, null=False, blank=False, help_text=issue_help_text)

    relatedtopic = models.ForeignKey(TopicCategory, null=False, help_text=related_help_text)

    class Meta:
        ordering = ("identifier",)
        db_table = 'cread_subcategory'


class CReadResource(models.Model):
    """
    For C-READ we need to add some more info the resource (i.e. Layer, Map, Document).
    In order not to change the original model, we're creating a new class that
    will reference the original resource.
    """

    resource = models.ForeignKey(ResourceBase, null=False, blank=False, unique=True)
    category = models.ForeignKey(CReadCategory, null=False, blank=False)
    subcategory = models.ForeignKey(CReadSubCategory, null=False, blank=False)

    class Meta:
        db_table = 'cread_resource'
