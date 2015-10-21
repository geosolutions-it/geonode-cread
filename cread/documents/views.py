# -*- coding: utf-8 -*-

import os
import sys
import logging
import shutil
import traceback

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.conf import settings
from django.template import RequestContext
from django.utils.translation import ugettext as _


from geonode.base.forms import CategoryForm
from geonode.base.models import TopicCategory
from geonode.people.forms import ProfileForm, PocForm

from geonode.utils import resolve_object

from cread.base.models import CReadResource, CReadCategory, CReadSubCategory
from cread.base.forms import CReadSubCategoryForm, CReadBaseInfoForm
from cread.documents.forms import CReadDocumentForm


from django.http import Http404
from django.template import loader
from django.core.exceptions import PermissionDenied
from django.views.generic.edit import CreateView

from geonode.base.models import ResourceBase
from geonode.documents.models import Document
from geonode.documents.forms import DocumentCreateForm
from geonode.documents.views import document_detail

logger = logging.getLogger("geonode.documents.views")

ALLOWED_DOC_TYPES = settings.ALLOWED_DOCUMENT_TYPES

_PERMISSION_MSG_GENERIC = _('You do not have permissions for this document.')
_PERMISSION_MSG_METADATA = _(
    "You are not permitted to modify this document's metadata")
_PERMISSION_MSG_VIEW = _("You are not permitted to view this document")


def _resolve_document(request, docid, permission='base.change_resourcebase',
                      msg=_PERMISSION_MSG_GENERIC, **kwargs):
    '''
    Resolve the document by the provided primary key and check the optional permission.
    '''
    return resolve_object(request, Document, {'pk': docid},
                          permission=permission, permission_msg=msg, **kwargs)



CONTEXT_LOG_FILE = None

if 'geonode.geoserver' in settings.INSTALLED_APPS:
    from geonode.geoserver.helpers import ogc_server_settings
    CONTEXT_LOG_FILE = ogc_server_settings.LOG_FILE


class CreadDocumentUploadView(CreateView):
    template_name = 'cread_upload_doc.html'
    form_class = DocumentCreateForm

    def get_context_data(self, **kwargs):
        context = super(CreadDocumentUploadView, self).get_context_data(**kwargs)
        context['ALLOWED_DOC_TYPES'] = ALLOWED_DOC_TYPES
        return context

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        self.object = form.save(commit=False)
        self.object.owner = self.request.user
        resource_id = self.request.POST.get('resource', None)
        if resource_id:
            self.object.content_type = ResourceBase.objects.get(id=resource_id).polymorphic_ctype
            self.object.object_id = resource_id
        # by default, if RESOURCE_PUBLISHING=True then document.is_published
        # must be set to False
        is_published = True
        if settings.RESOURCE_PUBLISHING:
            is_published = False
        self.object.is_published = is_published
        self.object.save()
        self.object.set_permissions(form.cleaned_data['permissions'])
        return HttpResponseRedirect(
            reverse(
                'document_metadata',
                args=(
                    self.object.id,
                )))


@login_required
def document_metadata(
        request,
        docid,
        template='documents/cread_document_metadata.html'):

    document = None
    try:
        document = _resolve_document(
            request,
            docid,
            'base.change_resourcebase_metadata',
            _PERMISSION_MSG_METADATA)

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
                        'error_message': _("You are not allowed to edit this document.")})), status=403)

    if document is None:
        return HttpResponse(
            'An unknown error has occured.',
            mimetype="text/plain",
            status=401
        )

    cdocumentqs = CReadResource.objects.filter(resource=document)

    if len(cdocumentqs) == 0:
        logger.info('cread_resource does not exist for document %r', document)
        cread_resource = None
    else:
        logger.debug('cread_resource found for document %r (%d)', document, len(cdocumentqs))
        cread_resource = cdocumentqs[0]

    poc = document.poc
    metadata_author = document.metadata_author
    topic_category = document.category
    cread_subcategory = cread_resource.subcategory if cread_resource else None

    if request.method == "POST":
        baseinfo_form = CReadBaseInfoForm(request.POST, prefix="baseinfo")
        document_form = CReadDocumentForm(
            request.POST,
            instance=document,
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
            initial={'title': document.title,
                     'abstract': document.abstract})

        document_form = CReadDocumentForm(instance=document, prefix="resource")
        category_form = CategoryForm(
            prefix="category_choice_field",
            initial=topic_category.id if topic_category else None)
        cread_subcategory_form = CReadSubCategoryForm(
            prefix="cread_subcategory_choice_field",
            initial=cread_subcategory.id if cread_subcategory else None)

    if request.method == "POST" \
            and baseinfo_form.is_valid() \
            and document_form.is_valid() \
            and cread_subcategory_form.is_valid():

        new_poc = document_form.cleaned_data['poc']
        new_author = document_form.cleaned_data['metadata_author']
        new_keywords = document_form.cleaned_data['keywords']
        #new_category = TopicCategory.objects.get(
        #    id=category_form.cleaned_data['category_choice_field'])

        if new_poc is None:
            if poc.user is None:
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
                cread_resource.resource = document

            cread_resource.category = new_creadcategory
            cread_resource.subcategory = new_creadsubcategory
            cread_resource.save()
            # End cread category
        else:
            new_creadsubcategory = None
            logger.info("CRead subcategory form is not valid")

        if category_form.is_valid():
            new_category = TopicCategory.objects.get(
                id=category_form.cleaned_data['category_choice_field'])
        elif new_creadsubcategory:
            logger.debug("Assigning default ISO category")
            new_category = TopicCategory.objects.get(
                            id=new_creadsubcategory.relatedtopic.id)

        if new_poc is not None and new_author is not None:
            the_document = document_form.save()
            the_document.poc = new_poc
            the_document.metadata_author = new_author
            the_document.keywords.add(*new_keywords)
            Document.objects.filter(id=the_document.id).update(
                category=new_category,
                title=baseinfo_form.cleaned_data['title'],
                abstract=baseinfo_form.cleaned_data['abstract']
                )
            return HttpResponseRedirect(
                reverse(
                    'document_detail',
                    args=(
                        document.id,
                    )))

    logger.debug("subcat valid %s ", cread_subcategory_form.is_valid())

    # etj: CHECKME: this block seems wrong, but it's copied from the original documents/views
    if poc is None:
        poc_form = ProfileForm(request.POST, prefix="poc")
    else:
        if poc is None:
            poc_form = ProfileForm(instance=poc, prefix="poc")
        else:
            document_form.fields['poc'].initial = poc.id
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
            document_form.fields['metadata_author'].initial = metadata_author.id
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
        "document": document,
        "baseinfo_form": baseinfo_form,
        "document_form": document_form,
        "poc_form": poc_form,
        "author_form": author_form,
        "category_form": category_form,
        "cread_sub_form": cread_subcategory_form,
        "cread_categories": categories_struct
    }))


@login_required
def publish(request, docid, template=None):
    return _change_published_status(request, docid, True)


@login_required
def unpublish(request, docid, template=None):
    return _change_published_status(request, docid, False)


def _change_published_status(request, docid, published):

    # let's restrict auth to superuser only
    if not request.user.is_superuser:
        return HttpResponse("Not allowed", status=403)

    # search for the document
    document = None
    try:
        document = _resolve_document(
            request,
            docid,
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
                        'error_message': _("You are not allowed to view this document.")})), status=403)

    if document is None:
        return HttpResponse(
            'An unknown error has occured.',
            mimetype="text/plain",
            status=401
        )

    Document.objects.filter(id=docid).update(is_published=published)

    return document_detail(request, docid)


#def document_detail(request, docid):
    #"""
    #The view that show details of each document
    #"""
    #document = None
    #try:
        #document = _resolve_document(
            #request,
            #docid,
            #'base.view_resourcebase',
            #_PERMISSION_MSG_VIEW)

    #except Http404:
        #return HttpResponse(
            #loader.render_to_string(
                #'404.html', RequestContext(
                    #request, {
                        #})), status=404)

    #except PermissionDenied:
        #return HttpResponse(
            #loader.render_to_string(
                #'401.html', RequestContext(
                    #request, {
                        #'error_message': _("You are not allowed to view this document.")})), status=403)

    #if document is None:
        #return HttpResponse(
            #'An unknown error has occured.',
            #mimetype="text/plain",
            #status=401
        #)

    #else:
        #try:
            #related = document.content_type.get_object_for_this_type(
                #id=document.object_id)
        #except:
            #related = ''

        ## Update count for popularity ranking,
        ## but do not includes admins or resource owners
        #if request.user != document.owner and not request.user.is_superuser:
            #Document.objects.filter(id=document.id).update(popular_count=F('popular_count') + 1)

        #metadata = document.link_set.metadata().filter(
            #name__in=settings.DOWNLOAD_FORMATS_METADATA)

        #context_dict = {
            #'perms_list': get_perms(request.user, document.get_self_resource()),
            #'permissions_json': _perms_info_json(document),
            #'resource': document,
            #'metadata': metadata,
            #'imgtypes': IMGTYPES,
            #'related': related}

        #if settings.SOCIAL_ORIGINS:
            #context_dict["social_links"] = build_social_links(request, document)

        #if getattr(settings, 'EXIF_ENABLED', False):
            #try:
                #from geonode.contrib.exif.utils import exif_extract_dict
                #exif = exif_extract_dict(document)
                #if exif:
                    #context_dict['exif_data'] = exif
            #except:
                #print "Exif extraction failed."

        #return render_to_response(
            #"documents/document_detail.html",
            #RequestContext(request, context_dict))
