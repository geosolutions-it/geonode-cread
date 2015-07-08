# -*- coding: utf-8 -*-

import json
import time
import logging

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count

from tastypie.constants import ALL
from tastypie.serializers import Serializer
from guardian.shortcuts import get_objects_for_user

from geonode.base.models import ResourceBase

from geonode.api.api import TypeFilteredResource, CountJSONSerializer

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
        resource_name = 'cread_categories'
        allowed_methods = ['get']
        filtering = {
            'identifier': ALL,
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


class CReadResourceResource(TypeFilteredResource):
    """Category api"""

    def serialize(self, request, data, format, options={}):

        return super(CReadResourceResource, self).serialize(request, data, format, options)

    class Meta:
        queryset = CReadResource.objects.all()
        resource_name = 'cread_resources'
        allowed_methods = ['get']
        filtering = {
            'identifier': ALL,
        }
        #serializer = CReadResourceSerializer()

