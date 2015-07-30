# -*- coding: utf-8 -*-

from django.contrib import admin

from cread.maptemplates.models import MapTemplate
from cread.base.models import CReadSubCategory


class RenderedItem(object):
    """
    Class used to render a nice label for the subcategory
    """

    _meta = "dummy"  # this is needed in order for the forms.Field to search for 'pk' attrib

    def __init__(self, id, label):
        self.id = id
        self.pk = id
        self.label = label

    def __str__(self):
        return self.label


class ListWrapper(object):
    """
    The widget expects a queryset, and will perform an all() call,
    so this class implements the all() function returning the whole list
    """

    def __init__(self, the_list):
        self.the_list = the_list

    def all(self):
        return self.the_list

    def filter(self, **kwargs):
        """ Used by form validity controller"""
        return CReadSubCategory.objects.all().filter(**kwargs)


class MapTemplateAdmin(admin.ModelAdmin):

    # list
    list_filter = ('subcategories',)
    search_fields = ['name']

    # form
    filter_horizontal = ['subcategories']

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """ We want to format the subcat labels as cat_name + subcat_name """
        if db_field.name == "subcategories":
            kwargs["queryset"] = ListWrapper([RenderedItem(subcat.id, "%s / %s" % (subcat.category.name, subcat.description))
                                    for subcat in CReadSubCategory.objects.all().prefetch_related('category')])
        return super(MapTemplateAdmin, self).formfield_for_manytomany(db_field, request, **kwargs)


admin.site.register(MapTemplate, MapTemplateAdmin)
