# -*- coding: utf-8 -*-

import os
import sys
import logging
import shutil
import traceback
import math

from guardian.shortcuts import get_perms

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.db.models import F
from django.forms.models import inlineformset_factory
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.translation import ugettext as _
from django.utils import simplejson as json
from django.http import Http404
from django.template import loader
from django import forms
from django.core.exceptions import ObjectDoesNotExist

from geonode.layers.models import Layer
from geonode.maps.models import Map, MapLayer

from geonode.utils import forward_mercator, llbbox_to_mercator, default_map_config, layer_from_viewer_config

from cread.maptemplates.models import MapTemplate
from cread.maptemplates.forms import ThematicMapLayerForm

logger = logging.getLogger("geonode.maptemplates.views")


def choose_template(request, template='maptemplates/choose_template.html'):

    maptemplates = MapTemplate.objects.all()

    maptemplates = []
    for mp in MapTemplate.objects.all():
        maptemplates.append({'id': mp.id, 'name': mp.name, 'description': mp.description})

    return render_to_response(template, RequestContext(request, {
        "maptemplates": maptemplates,
    }))


@login_required
def choose_layers(request, template_id, template='maptemplates/choose_layers.html'):

    maptemplate = MapTemplate.objects.prefetch_related('subcategories').get(pk=template_id)

    if maptemplate is None:
        return HttpResponse(loader.render_to_string(
            '404.html',
            RequestContext(request, {})),
            status=404)

    subcategories = maptemplate.subcategories.all()

    forms_list = []

    if request.method == "POST":

        is_valid = True
        layer_ids = []

        for subcat in subcategories:
            form = ThematicMapLayerForm(
                request.POST,
                prefix="layer_choice_%s" % subcat.identifier,
                subcategory=subcat
                )

            is_valid = is_valid and form.is_valid()
            forms_list.append((subcat, form))
            if is_valid:
                layer = form.cleaned_data['layer']
                logger.debug("Collecting layer " + layer.title)
                layer_ids.append(layer.id)

        if is_valid:
            # all set: we can forward the request to next step

            newmap = map_create(request, maptemplate.id, layer_ids)
            return HttpResponseRedirect(
                reverse('map_detail',
                    kwargs={'mapid': newmap.id}))

                #reverse(
                    #'maptemplate_metadata_create',
                    #kwargs={
                        #'template_id': maptemplate.id,
                        #'layer_ids': layer_ids,
                    #}))

    else:  # GET request

        for subcat in subcategories:

            form = ThematicMapLayerForm(
                prefix="layer_choice_%s" % subcat.identifier,
                subcategory=subcat)

            forms_list.append((subcat, form))

    return render_to_response(template, RequestContext(request, {
        "maptemplate": maptemplate,
        "subcategories": subcategories,
        "forms": forms_list
    }))


@login_required
def map_create(request, template_id, layer_ids, template='maptemplates/choose_layers.html'):

    maptemplate = MapTemplate.objects.prefetch_related('subcategories').get(pk=template_id)

    if maptemplate is None:
        return HttpResponse(loader.render_to_string(
            '404.html',
            RequestContext(request, {})),
            status=404)

    layers = []

    for layer_id in layer_ids:
        layer = Layer.objects.get(pk=layer_id)  # TODO: check permissions
        if layer is None:
            logger.warning("Layer not found for id %s", layer_id)
        else:
            logger.info("adding layer %r", layer)
            logger.info(" ows_url %s", layer.ows_url)
            logger.info(" get ows url %s", layer.get_ows_url())
            layers.append(layer)

    newmap = _create_map(request.user, maptemplate, layers)

    return newmap

    #if newmap:
        #return HttpResponseRedirect(
            #reverse(
                #'maptemplate_map_metadata_create',
                #kwargs={
                    #'map_id': newmap.id,
                #}))
    #else:


def _create_map(user, maptemplate, layers):
    '''
    Creates a new map.

    If the query argument 'copy' is given, the initial map is
    a copy of the map with the id specified, otherwise the
    default map configuration is used.  If copy is specified
    and the map specified does not exist a 404 is returned.
    '''

    logger.debug("Create new map from template [%s] for user [%r]", maptemplate.name, user)

    #newmap = Map()
    newmap = create_from_layer_list(user, layers,
        "Map from template [%s]" % maptemplate.name,
        "This map has been created using the template [%s].\n\n%s" % (
            maptemplate.name, maptemplate.description)
        )
    return newmap


def create_from_layer_list(user, layers, title, abstract):

    newmap = Map()

    """Copied from maps.models and fixed
    """
    newmap.owner = user
    newmap.title = title
    newmap.abstract = abstract
    newmap.projection = "EPSG:900913"
    newmap.zoom = 0
    newmap.center_x = 0
    newmap.center_y = 0
    #bbox = None
    index = 0
    incr_bbox = None

    DEFAULT_BASE_LAYERS = settings.MAP_BASELAYERS

    is_published = True
    if settings.RESOURCE_PUBLISHING:
        is_published = False
    newmap.is_published = is_published

    # Save the map in order to create an id in the database
    # used below for the maplayers.
    newmap.save()

    # Add background layers

    for layer in DEFAULT_BASE_LAYERS:
        logger.info("Adding baselayer %r", layer)
        maplayer = layer_from_viewer_config(MapLayer,
            layer,
            layer['source'],  # source
            index)
        if not maplayer.group == 'background':
            logger.info("Skipping not base layer %r", layer)
            continue
        if 'name' not in layer or not layer['name']:
            logger.info("Unnamed base layer %r", layer)
            maplayer.name = 'UNNAMED BACKGROUND LAYER'

        maplayer.map = newmap
        maplayer.save()
        index += 1

    # Add local layers

    for layer in layers:
        if not isinstance(layer, Layer):
            try:
                layer = Layer.objects.get(typename=layer)
            except ObjectDoesNotExist:
                raise Exception(
                    'Could not find layer with name %s' %
                    layer)

        if not user.has_perm(
                'base.view_resourcebase',
                obj=layer.resourcebase_ptr):
            # invisible layer, skip inclusion or raise Exception?
            raise Exception(
                'User %s tried to create a map with layer %s without having premissions' %
                (user, layer))

        ### Add required parameters for GXP lazy-loading

        # compute (incremental) bbox
        layer_bbox = layer.bbox
        if incr_bbox is None:
            incr_bbox = list(layer_bbox[0:4])
        else:
            incr_bbox[0] = min(incr_bbox[0], layer_bbox[0])
            incr_bbox[1] = max(incr_bbox[1], layer_bbox[1])
            incr_bbox[2] = min(incr_bbox[2], layer_bbox[2])
            incr_bbox[3] = max(incr_bbox[3], layer_bbox[3])

        config = layer.attribute_config()

        config["title"] = layer.title
        config["queryable"] = True
        config["srs"] = layer.srid if layer.srid != "EPSG:4326" else "EPSG:900913"
        config["bbox"] = llbbox_to_mercator([float(coord) for coord in incr_bbox])

        #if layer.storeType == "remoteStore":
            #service = layer.service
            #maplayer = MapLayer(map=map_obj,
                                #name=layer.typename,
                                #ows_url=layer.ows_url,
                                #layer_params=json.dumps(config),
                                #visibility=True,
                                #source_params=json.dumps({
                                    #"ptype": service.ptype,
                                    #"remote": True,
                                    #"url": service.base_url,
                                    #"name": service.name}))
        #else:
            #maplayer = MapLayer(
                #map=map_obj,
                #name=layer.typename,
                #ows_url=layer.ows_url,
                #layer_params=json.dumps(config),
                #visibility=True
            #)

        MapLayer.objects.create(
            map=newmap,
            name=layer.typename,
            ows_url=layer.ows_url,
            stack_order=index,
            visibility=True,
            layer_params=json.dumps(config)
        )

        index += 1

    # Set bounding box based on all layers extents.
    bbox = newmap.get_bbox_from_layers(newmap.local_layers)

    newmap.set_bounds_from_bbox(bbox)

    newmap.set_missing_info()

    # Save again to persist the zoom and bbox changes and
    # to generate the thumbnail.
    newmap.save()

    return newmap


    #DEFAULT_BASE_LAYERS = default_map_config()

    #bbox = None
    #map_obj = Map(projection="EPSG:900913")

    #map_obj.title = "Map from template [%s]" % maptemplate.name
    #map_obj.abstract = "This map has been created using the template [%s].\n\n%s" % (
        #maptemplate.name, maptemplate.description)

    #maplayers = []
    #cnt = 0
    #for layer in layers_list:

        #if not user.has_perm(
                #'view_resourcebase',
                #obj=layer.get_self_resource()):
            ## invisible layer, skip inclusion
            #logger.warning("Layer %s not accessible to user %s", layer.id, user)
            #continue

        #layer_bbox = layer.bbox
        ## assert False, str(layer_bbox)
        #if bbox is None:
            #bbox = list(layer_bbox[0:4])
        #else:
            #bbox[0] = min(bbox[0], layer_bbox[0])
            #bbox[1] = max(bbox[1], layer_bbox[1])
            #bbox[2] = min(bbox[2], layer_bbox[2])
            #bbox[3] = max(bbox[3], layer_bbox[3])

        #config = layer.attribute_config()

        ## Add required parameters for GXP lazy-loading
        #config["title"] = layer.title
        #config["queryable"] = True
        #config["srs"] = layer.srid if layer.srid != "EPSG:4326" else "EPSG:900913"
        #config["bbox"] = llbbox_to_mercator([float(coord) for coord in bbox])

        #if layer.storeType == "remoteStore":
            #service = layer.service
            #maplayer = MapLayer(map=map_obj,
                                #name=layer.typename,
                                #ows_url=layer.ows_url,
                                #layer_params=json.dumps(config),
                                #visibility=True,
                                #source_params=json.dumps({
                                    #"ptype": service.ptype,
                                    #"remote": True,
                                    #"url": service.base_url,
                                    #"name": service.name}))
        #else:
            #maplayer = MapLayer(
                #map=map_obj,
                #name=layer.typename,
                #ows_url=layer.ows_url,
                #layer_params=json.dumps(config),
                #visibility=True
            #)

        #maplayers.append(maplayer)

    #if bbox is not None:
        #minx, miny, maxx, maxy = [float(c) for c in bbox]
        #x = (minx + maxx) / 2
        #y = (miny + maxy) / 2

        #center = list(forward_mercator((x, y)))
        #if center[1] == float('-inf'):
            #center[1] = 0

        #BBOX_DIFFERENCE_THRESHOLD = 1e-5

        ## Check if the bbox is invalid
        #valid_x = (maxx - minx) ** 2 > BBOX_DIFFERENCE_THRESHOLD
        #valid_y = (maxy - miny) ** 2 > BBOX_DIFFERENCE_THRESHOLD

        #if valid_x:
            #width_zoom = math.log(360 / abs(maxx - minx), 2)
        #else:
            #width_zoom = 15

        #if valid_y:
            #height_zoom = math.log(360 / abs(maxy - miny), 2)
        #else:
            #height_zoom = 15

        #map_obj.center_x = center[0]
        #map_obj.center_y = center[1]
        #map_obj.zoom = math.ceil(min(width_zoom, height_zoom))

        #try:
            #map_obj.owner = user
            #map_obj.save()
            #map_obj.set_default_permissions()

            #logger.debug("Saved new map with id %s", maptemplate.id)

            #for maplayer in maplayers:
                #maplayer.map = map_obj
                #maplayer.save()

            ##
            ##map_obj.update_from_viewer(body)

            ##MapSnapshot.objects.create(
                ##config=clean_config(body),
                ##map=map_obj,
                ##user=request.user)
            #return map_obj

        #except Exception:
            #logger.warning("Error saving map")
            #print(traceback.format_exc())
            #return None

    ##config = map_obj.viewer_json(
        ##user, *(DEFAULT_BASE_LAYERS + maplayers))
    ##config['fromLayer'] = True

    ##return json.dumps(config)
#


