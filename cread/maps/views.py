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
from django.conf import settings
from django.template import RequestContext
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.shortcuts import render_to_response
from django.utils.html import strip_tags

from geonode.base.forms import CategoryForm
from geonode.base.models import TopicCategory
from geonode.people.forms import ProfileForm, PocForm

from geonode.maps.models import Map
from geonode.maps.views import _resolve_map
from geonode.maps.views import _PERMISSION_MSG_METADATA, _PERMISSION_MSG_VIEW
from geonode.maps.views import map_detail

from cread.base.models import CReadResource, CReadCategory, CReadSubCategory
from cread.base.forms import CReadSubCategoryForm, CReadBaseInfoForm
from cread.maps.forms import CReadMapForm


logger = logging.getLogger("cread.maps.views")


@login_required
def map_metadata(request, mapid, template='maps/cread_map_metadata.html'):

    map_obj = _resolve_map(request, mapid, 'base.change_resourcebase_metadata', _PERMISSION_MSG_VIEW)

    cmapqs = CReadResource.objects.filter(resource=map_obj)

    if len(cmapqs) == 0:
        logger.info('cread_resource does not exist for map %r', map_obj)
        cread_resource = None
    else:
        logger.debug('cread_resource found for map %r (%d)', map_obj, len(cmapqs))
        cread_resource = cmapqs[0]

    poc = map_obj.poc
    metadata_author = map_obj.metadata_author
    topic_category = map_obj.category
    cread_subcategory = cread_resource.subcategory if cread_resource else None

    if request.method == "POST":
        baseinfo_form = CReadBaseInfoForm(request.POST, prefix="baseinfo")
        map_form = CReadMapForm(
        #map_form = MapForm(
            request.POST,
            instance=map_obj,
            prefix="resource")
        category_form = CategoryForm(
            request.POST,
            prefix="category_choice_field",
            initial=int(
                request.POST["category_choice_field"]) if "category_choice_field" in request.POST else None)
        cread_subcategory_form = CReadSubCategoryForm(
            request.POST,
            prefix="cread_subcategory_choice_field",
            initial=int(
                request.POST["cread_subcategory_choice_field"]) if "cread_subcategory_choice_field" in request.POST else None)
    else:
        baseinfo_form = CReadBaseInfoForm(
            prefix="baseinfo",
            initial={'title': map_obj.title,
                     'abstract': map_obj.abstract})
        map_form = CReadMapForm(instance=map_obj, prefix="resource")
        category_form = CategoryForm(
            prefix="category_choice_field",
            initial=topic_category.id if topic_category else None)
        cread_subcategory_form = CReadSubCategoryForm(
            prefix="cread_subcategory_choice_field",
            initial=cread_subcategory.id if cread_subcategory else None)

    if request.method == "POST" \
            and baseinfo_form.is_valid() \
            and map_form.is_valid() \
            and cread_subcategory_form.is_valid():

        new_title = strip_tags(baseinfo_form.cleaned_data['title'])
        new_abstract = strip_tags(baseinfo_form.cleaned_data['abstract'])

        new_poc = map_form.cleaned_data['poc']
        new_author = map_form.cleaned_data['metadata_author']
        new_keywords = map_form.cleaned_data['keywords']

        if new_poc is None:
            if poc is None:
                poc_form = ProfileForm(
                    request.POST,
                    prefix="poc",
                    instance=poc)
            else:
                poc_form = ProfileForm(request.POST, prefix="poc")
            if poc_form.has_changed and poc_form.is_valid():
                new_poc = poc_form.save()

        if new_author is None:
            if metadata_author is None:
                author_form = ProfileForm(request.POST, prefix="author",
                                          instance=metadata_author)
            else:
                author_form = ProfileForm(request.POST, prefix="author")
            if author_form.has_changed and author_form.is_valid():
                new_author = author_form.save()

        # CRead category
        # note: call to is_valid is needed to compute the cleaned data
        if(cread_subcategory_form.is_valid()):
            logger.info("Checking CReadLayer record %r ", cread_subcategory_form.is_valid())
            cread_subcat_id = cread_subcategory_form.cleaned_data['cread_subcategory_choice_field']
            new_creadsubcategory = CReadSubCategory.objects.get(id=cread_subcat_id)
            new_creadcategory = new_creadsubcategory.category
            logger.debug("Selected cread cat/subcat: %s : %s / %s",
                    new_creadcategory.identifier,
                    new_creadcategory.name,
                    new_creadsubcategory.identifier)

            if cread_resource:
                logger.info("Update CReadResource record")
            else:
                logger.info("Create new CReadResource record")
                cread_resource = CReadResource()
                cread_resource.resource = map_obj

            cread_resource.category = new_creadcategory
            cread_resource.subcategory = new_creadsubcategory
            cread_resource.save()
        else:
            new_creadsubcategory = None
            logger.info("CRead subcategory form is not valid")
         # End cread category

         # Update original topic category according to cread category
        if category_form.is_valid():
            new_category = TopicCategory.objects.get(
                id=category_form.cleaned_data['category_choice_field'])
        elif new_creadsubcategory:
            logger.debug("Assigning default ISO category from CREAD category")
            new_category = TopicCategory.objects.get(
                            id=new_creadsubcategory.relatedtopic.id)

        if new_poc is not None and new_author is not None:
            the_map = map_form.save()
            the_map.poc = new_poc
            the_map.metadata_author = new_author
            the_map.title = new_title
            the_map.abstract = new_abstract
            the_map.save()
            the_map.keywords.clear()
            the_map.keywords.add(*new_keywords)
            the_map.category = new_category
            the_map.save()

            if getattr(settings, 'SLACK_ENABLED', False):
                try:
                    from geonode.contrib.slack.utils import build_slack_message_map, send_slack_messages
                    send_slack_messages(build_slack_message_map("map_edit", the_map))
                except:
                    print "Could not send slack message for modified map."

            return HttpResponseRedirect(
                reverse(
                    'map_detail',
                    args=(
                        map_obj.id,
                    )))

    if poc is None:
        poc_form = ProfileForm(request.POST, prefix="poc")
    else:
        if poc is None:
            poc_form = ProfileForm(instance=poc, prefix="poc")
        else:
            map_form.fields['poc'].initial = poc.id
            poc_form = ProfileForm(prefix="poc")
            poc_form.hidden = True

    if metadata_author is None:
        author_form = ProfileForm(request.POST, prefix="author")
    else:
        if metadata_author is None:
            author_form = ProfileForm(
                instance=metadata_author,
                prefix="author")
        else:
            map_form.fields['metadata_author'].initial = metadata_author.id
            author_form = ProfileForm(prefix="author")
            author_form.hidden = True

    # creates cat - subcat association
    categories_struct = []
    for category in CReadCategory.objects.all():
        subcats = []
        for subcat in CReadSubCategory.objects.filter(category=category):
            subcats.append(subcat.id)
        categories_struct.append((category.id, category.description, subcats))

    return render_to_response(template, RequestContext(request, {
        "map": map_obj,
        "map_form": map_form,
        "poc_form": poc_form,
        "author_form": author_form,
        "category_form": category_form,

        "baseinfo_form": baseinfo_form,
        "cread_sub_form": cread_subcategory_form,
        "cread_categories": categories_struct
    }))


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

