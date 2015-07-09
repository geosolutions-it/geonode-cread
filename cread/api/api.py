# -*- coding: utf-8 -*-

import json
import time
import logging

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count

from tastypie.constants import ALL, ALL_WITH_RELATIONS
from tastypie.resources import ModelResource
from tastypie.serializers import Serializer
from tastypie import fields

from guardian.shortcuts import get_objects_for_user

from geonode.base.models import ResourceBase

from geonode.api.api import TypeFilteredResource
from geonode.api.resourcebase_api import ResourceBaseResource, CommonMetaApi, LayerResource, DocumentResource

from cread.base.models import CReadCategory, CReadResource


logger = logging.getLogger("geonode.api")


class CatCountJSONSerializer(Serializer):
    """Custom serializer to post process the api and add counts"""

    def get_resources_counts(self, options):
        if settings.SKIP_PERMS_FILTER:
            resources = ResourceBase.objects.all()
        else:
            resources = get_objects_for_user(
                options['user'],
                'base.view_resourcebase'
            )
        if settings.RESOURCE_PUBLISHING:
            resources = resources.filter(is_published=True)

        if options['title_filter']:
            resources = resources.filter(title__icontains=options['title_filter'])

        if options['type_filter']:
            resources = resources.instance_of(options['type_filter'])

        cread_res = CReadResource.objects.filter(resource__in=resources)

        counts = list(cread_res.values(options['count_type']).annotate(count=Count(options['count_type'])))

        return dict([(c[options['count_type']], c['count']) for c in counts])

    def to_json(self, data, options=None):
        options = options or {}
        data = self.to_simple(data, options)

        # check if we're returning the whole list or just one instance
        if 'objects' in data:
            counts = self.get_resources_counts(options)
            for item in data['objects']:
                item['count'] = counts.get(item['id'], 0)

        # Add in the current time.
        data['requested_time'] = time.time()

        return json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True)


class CReadCategoryResource(TypeFilteredResource):
    """Category api"""

    def serialize(self, request, data, format, options={}):
        options['count_type'] = 'category'

        return super(CReadCategoryResource, self).serialize(request, data, format, options)

    class Meta:
        queryset = CReadCategory.objects.all()
        resource_name = 'categories'
        allowed_methods = ['get']
        filtering = {
            'identifier': ALL,
            'id': ALL_WITH_RELATIONS,
        }
        serializer = CatCountJSONSerializer()


class CReadResourceSerializer(Serializer):
    """Custom serializer to post process the resource and add some fields to it"""

    def get_resources_counts(self, options):
        if settings.SKIP_PERMS_FILTER:
            resources = ResourceBase.objects.all()
        else:
            resources = get_objects_for_user(
                options['user'],
                'base.view_resourcebase'
            )
        if settings.RESOURCE_PUBLISHING:
            resources = resources.filter(is_published=True)

        if options['title_filter']:
            resources = resources.filter(title__icontains=options['title_filter'])

        if options['type_filter']:
            resources = resources.instance_of(options['type_filter'])

        cread_res = CReadResource.objects.filter(resource__in=resources)

        counts = list(cread_res.values(options['count_type']).annotate(count=Count(options['count_type'])))

        return dict([(c[options['count_type']], c['count']) for c in counts])

    def to_json(self, data, options=None):
        options = options or {}
        data = self.to_simple(data, options)
        counts = self.get_resources_counts(options)
        for item in data['objects']:
            item['count'] = counts.get(item['id'], 0)
        # Add in the current time.
        data['requested_time'] = time.time()

        return json.dumps(data, cls=DjangoJSONEncoder, sort_keys=True)


class CReadResourceBaseResource(ResourceBaseResource):

    """
    ResourceBase api

    Adds:
    * filtering by creadcategory
    * return field containings related creadcategory and creadsubcategory
    """

    def build_filters(self, filters={}):
        orm_filters = super(CReadResourceBaseResource, self).build_filters(filters)

        if 'cread_category_id__in' in filters:
            orm_filters['creadresource__category_id__in'] = filters['cread_category_id__in']

        return orm_filters

    def dehydrate(self, bundle):
        res = CReadResource.objects.all().prefetch_related('category').prefetch_related('subcategory').get(id=bundle.obj.id)

        if res:
            bundle.data['cread_category_id'] = res.category.id
            bundle.data['cread_subcategory_id'] = res.subcategory.id
            bundle.data['cread_subcategory_name'] = res.subcategory.name
            bundle.data['cread_subcategory_description'] = res.subcategory.description

        return bundle


class CReadResourceResource(ModelResource):
    """ Association between resources and cread categories"""
    baseresource = fields.ToOneField(
        CReadResourceBaseResource,
        'resource',
        null=True,
        full=False)

    category = fields.ToOneField(
        CReadCategoryResource,
        'category',
        null=True,
        full=True)

    def serialize(self, request, data, format, options={}):

        return super(CReadResourceResource, self).serialize(request, data, format, options)

    class Meta:
        queryset = CReadResource.objects.all()
        resource_name = 'cread_resources'
        allowed_methods = ['get']
        filtering = {
            'identifier': ALL,
            'id': ALL,
            'category': ALL_WITH_RELATIONS,
        }


class CReadLayerResource(LayerResource):

    """Layer API"""

    def build_filters(self, filters={}):
        orm_filters = super(CReadLayerResource, self).build_filters(filters)

        if 'cread_category_id__in' in filters:
            orm_filters['creadresource__category_id__in'] = filters['cread_category_id__in']

        return orm_filters

    def dehydrate(self, bundle):

        bundle = super(CReadLayerResource, self).dehydrate(bundle)
        res = CReadResource.objects.all().prefetch_related('category').prefetch_related('subcategory').get(id=bundle.obj.id)

        if res:
            bundle.data['cread_category_id'] = res.category.id
            bundle.data['cread_subcategory_id'] = res.subcategory.id
            bundle.data['cread_subcategory_name'] = res.subcategory.name
            bundle.data['cread_subcategory_description'] = res.subcategory.description

        return bundle


class CReadDocumentResource(DocumentResource):

    """Docs API"""

    def build_filters(self, filters={}):
        orm_filters = super(CReadDocumentResource, self).build_filters(filters)

        if 'cread_category_id__in' in filters:
            orm_filters['creadresource__category_id__in'] = filters['cread_category_id__in']

        return orm_filters

    def dehydrate(self, bundle):

        bundle = super(CReadDocumentResource, self).dehydrate(bundle)
        res = CReadResource.objects.all().prefetch_related('category').prefetch_related('subcategory').get(id=bundle.obj.id)

        if res:
            bundle.data['cread_category_id'] = res.category.id
            bundle.data['cread_subcategory_id'] = res.subcategory.id
            bundle.data['cread_subcategory_name'] = res.subcategory.name
            bundle.data['cread_subcategory_description'] = res.subcategory.description

        return bundle
