# -*- coding: utf-8 -*-

from django.db import models

from cread.base.models import CReadSubCategory


class MapTemplate(models.Model):

    name = models.CharField(max_length=32, unique=True)
    description = models.TextField(default='', null=False, blank=False)

    subcategories = models.ManyToManyField(CReadSubCategory, related_name="cread_maptemplate_subcat")

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ("name",)
        db_table = 'cread_maptemplate'
        verbose_name = "Map Template"
        verbose_name_plural = "Map Templates"

