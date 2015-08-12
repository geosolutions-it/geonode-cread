# -*- coding: utf-8 -*-

import os
import sys
import logging
import shutil
import traceback

from django.contrib.auth.decorators import login_required
from django.template import RequestContext
from django.utils.translation import ugettext as _
from django.http import Http404
from django.http import HttpResponse
from django.template import loader
from django.core.exceptions import PermissionDenied

from geonode.base.forms import CategoryForm
from geonode.base.models import TopicCategory

from geonode.maps.models import Map
from geonode.maps.views import _resolve_map
from geonode.maps.views import _PERMISSION_MSG_METADATA, _PERMISSION_MSG_VIEW
from geonode.maps.views import map_detail

from cread.base.models import CReadResource, CReadCategory, CReadSubCategory
from cread.base.forms import CReadSubCategoryForm, CReadBaseInfoForm
from cread.layers.forms import CReadLayerForm


@login_required
def publish(request, mapid, template=None):
    return _change_published_status(request, mapid, True)


@login_required
def unpublish(request, mapid, template=None):
    return _change_published_status(request, mapid, False)


def _change_published_status(request, mapid, published):

    # let's restrict auth to superuser only
    if not request.user.is_superuser:
        return HttpResponse("Not allowed", status=403)

    # search for the resource
    xmap = None
    try:
        xmap = _resolve_map(
            request,
            mapid,
            'base.view_resourcebase',
            _PERMISSION_MSG_VIEW)

    except Http404:
        return HttpResponse(
            loader.render_to_string(
                '404.html', RequestContext(
                    request, {
                        })), status=404)

    except PermissionDenied:
        return HttpResponse(
            loader.render_to_string(
                '401.html', RequestContext(
                    request, {
                        'error_message': _("You are not allowed to view this map.")})), status=403)

    if xmap is None:
        return HttpResponse(
            'An unknown error has occured.',
            mimetype="text/plain",
            status=401
        )

    Map.objects.filter(id=mapid).update(is_published=published)

    return map_detail(request, mapid)
