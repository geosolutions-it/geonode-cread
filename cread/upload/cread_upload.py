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
from django.utils import simplejson as json
from django.utils.html import escape
from django.template.defaultfilters import slugify
from django.forms.models import inlineformset_factory
from django.db.models import F

from geonode.tasks.deletion import delete_layer
from geonode.services.models import Service
from geonode.layers.forms import LayerForm, LayerUploadForm, NewLayerUploadForm, LayerAttributeForm
from geonode.base.forms import CategoryForm
from geonode.layers.models import Layer, Attribute, UploadSession
from geonode.base.enumerations import CHARSETS
from geonode.base.models import TopicCategory

from geonode.utils import default_map_config
from geonode.utils import GXPLayer
from geonode.utils import GXPMap
from geonode.layers.utils import file_upload, is_raster, is_vector
from geonode.utils import resolve_object, llbbox_to_mercator
from geonode.people.forms import ProfileForm, PocForm
from geonode.security.views import _perms_info_json
from geonode.documents.models import get_related_documents
from geonode.utils import build_social_links
from geonode.geoserver.helpers import cascading_delete, gs_catalog

from geonode.layers.views import _resolve_layer
from geonode.layers.views import _PERMISSION_MSG_METADATA

from cread.base.models import CReadResource, CReadCategory, CReadSubCategory
from cread.base.forms import CReadCategoryForm, CReadSubCategoryForm

from django.http import Http404
from django.template import loader
from django.core.exceptions import PermissionDenied
from django.views.generic.edit import CreateView

from geonode.base.models import ResourceBase
from geonode.documents.models import Document
from geonode.documents.forms import DocumentForm, DocumentCreateForm

ALLOWED_DOC_TYPES = settings.ALLOWED_DOCUMENT_TYPES

_PERMISSION_MSG_GENERIC = _('You do not have permissions for this document.')
_PERMISSION_MSG_METADATA = _(
    "You are not permitted to modify this document's metadata")

logger = logging.getLogger("geonode.layers.views")

CONTEXT_LOG_FILE = None

if 'geonode.geoserver' in settings.INSTALLED_APPS:
    from geonode.geoserver.helpers import _render_thumbnail
    from geonode.geoserver.helpers import ogc_server_settings
    CONTEXT_LOG_FILE = ogc_server_settings.LOG_FILE


@login_required
def cread_upload_geo(request, template='cread_upload_geo.html'):
#def layer_upload(request, template='upload/layer_upload.html'):
    logger.debug("*** ENTER cread_upload_geo")

    if request.method == 'GET':
        ctx = {
            'charsets': CHARSETS,
            'is_layer': True,
        }
        return render_to_response(template,
                                  RequestContext(request, ctx))
    elif request.method == 'POST':
        logger.debug("cread_upload_geo: POST")

        form = NewLayerUploadForm(request.POST, request.FILES)
        tempdir = None
        errormsgs = []
        out = {'success': False}

        if form.is_valid():
            logger.debug("cread_upload_geo: form is valid")

            title = form.cleaned_data["layer_title"]

            # Replace dots in filename - GeoServer REST API upload bug
            # and avoid any other invalid characters.
            # Use the title if possible, otherwise default to the filename
            if title is not None and len(title) > 0:
                name_base = title
            else:
                name_base, __ = os.path.splitext(
                    form.cleaned_data["base_file"].name)

            name = slugify(name_base.replace(".", "_"))

            try:
                # Moved this inside the try/except block because it can raise
                # exceptions when unicode characters are present.
                # This should be followed up in upstream Django.
                tempdir, base_file = form.write_files()
                saved_layer = file_upload(
                    base_file,
                    name=name,
                    user=request.user,
                    overwrite=False,
                    charset=form.cleaned_data["charset"],
                    abstract=form.cleaned_data["abstract"],
                    title=form.cleaned_data["layer_title"],
                )

            except Exception as e:
                logger.debug("cread_upload_geo: ERROR saving layer: %s" % str(e))

                exception_type, error, tb = sys.exc_info()
                logger.exception(e)
                out['success'] = False
                out['errors'] = str(error)
                # Assign the error message to the latest UploadSession from that user.
                latest_uploads = UploadSession.objects.filter(user=request.user).order_by('-date')
                if latest_uploads.count() > 0:
                    upload_session = latest_uploads[0]
                    upload_session.error = str(error)
                    upload_session.traceback = traceback.format_exc(tb)
                    upload_session.context = log_snippet(CONTEXT_LOG_FILE)
                    upload_session.save()
                    out['traceback'] = upload_session.traceback
                    out['context'] = upload_session.context
                    out['upload_session'] = upload_session.id
            else:
                out['success'] = True
                if hasattr(saved_layer, 'info'):
                    out['info'] = saved_layer.info
                out['url'] = reverse(
                    'layer_detail', args=[
                        saved_layer.service_typename])

                upload_session = saved_layer.upload_session
                upload_session.processed = True
                upload_session.save()
                permissions = form.cleaned_data["permissions"]
                if permissions is not None and len(permissions.keys()) > 0:
                    saved_layer.set_permissions(permissions)

            finally:
                if tempdir is not None:
                    shutil.rmtree(tempdir)
        else:
            logger.debug("cread_upload_geo: form is NOT valid")
            for e in form.errors.values():
                errormsgs.extend([escape(v) for v in e])

            out['errors'] = form.errors
            out['errormsgs'] = errormsgs

        if out['success']:
            status_code = 200
        else:
            status_code = 400
        return HttpResponse(
            json.dumps(out),
            mimetype='application/json',
            status=status_code)


@login_required
def layer_metadata(request, layername, template='layers/cread_layer_metadata.html'):
    logger.debug("*** ENTER CREAD:layer_metadata")

    layer = _resolve_layer(
        request,
        layername,
        'base.change_resourcebase_metadata',
        _PERMISSION_MSG_METADATA)

    clayerqs = CReadResource.objects.filter(resource=layer)

    if len(clayerqs) == 0:
        logger.info('cread_resource does not exist for layer %r', layer)
        clayer = None
    else:
        logger.debug('cread_resource found for layer %r (%d)', layer, len(clayerqs))
        clayer = clayerqs[0]

    layer_attribute_set = inlineformset_factory(
        Layer,
        Attribute,
        extra=0,
        form=LayerAttributeForm,
    )
    topic_category = layer.category
    cread_category = clayer.category if clayer else None
    cread_subcategory = clayer.subcategory if clayer else None

    poc = layer.poc
    metadata_author = layer.metadata_author

    if request.method == "POST":
        layer_form = LayerForm(request.POST, instance=layer, prefix="resource")
        attribute_form = layer_attribute_set(
            request.POST,
            instance=layer,
            prefix="layer_attribute_set",
            queryset=Attribute.objects.order_by('display_order'))
        category_form = CategoryForm(
            request.POST,
            prefix="category_choice_field",
            initial=int(
                request.POST["category_choice_field"]) if "category_choice_field" in request.POST else None)
        #cread_category_form = CReadCategoryForm(
            #request.POST,
            #prefix="cread_category_choice_field",
            #initial=int(
                #request.POST["cread_category_choice_field"]) if "cread_category_choice_field" in request.POST else None)
        cread_subcategory_form = CReadSubCategoryForm(
            request.POST,
            prefix="cread_subcategory_choice_field",
            initial=int(
                request.POST["cread_subcategory_choice_field"]) if "cread_subcategory_choice_field" in request.POST else None)
    else:
        layer_form = LayerForm(instance=layer, prefix="resource")
        _preprocess_fields(layer_form)

        attribute_form = layer_attribute_set(
            instance=layer,
            prefix="layer_attribute_set",
            queryset=Attribute.objects.order_by('display_order'))
        category_form = CategoryForm(
            prefix="category_choice_field",
            initial=topic_category.id if topic_category else None)
        #cread_category_form = CReadCategoryForm(
            #prefix="cread_category_choice_field",
            #initial=cread_category.id if cread_category else None)
        cread_subcategory_form = CReadSubCategoryForm(
            prefix="cread_subcategory_choice_field",
            initial=cread_subcategory.id if cread_subcategory else None)

    if request.method == "POST" \
        and layer_form.is_valid() \
        and attribute_form.is_valid() \
        and cread_subcategory_form.is_valid():

        new_poc = layer_form.cleaned_data['poc']
        new_author = layer_form.cleaned_data['metadata_author']
        new_keywords = layer_form.cleaned_data['keywords']

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
            #cread_cat_id = cread_category_form.cleaned_data['cread_category_choice_field']
            #cread_cat_id = cread_cat_id if cread_cat_id else 1
            #new_creadcategory = CReadCategory.objects.get(id=cread_cat_id)
            cread_subcat_id = cread_subcategory_form.cleaned_data['cread_subcategory_choice_field']
            new_creadsubcategory = CReadSubCategory.objects.get(id=cread_subcat_id)
            new_creadcategory = new_creadsubcategory.category
            logger.debug("Selected cread cat/subcat: %s : %s / %s",
                new_creadcategory.identifier,
                new_creadcategory.name,
                new_creadsubcategory.identifier)

            if clayer:
                logger.info("Update CReadResource record")
            else:
                logger.info("Create new CReadResource record")
                clayer = CReadResource()
                clayer.resource = layer

            clayer.category = new_creadcategory
            clayer.subcategory = new_creadsubcategory
            clayer.save()
            # End cread category
        else:
            logger.info("CRead subcategory form is not valid")
			
        if category_form.is_valid():
            new_category = TopicCategory.objects.get(
                id=category_form.cleaned_data['category_choice_field'])
        else:
            logger.debug("Assigning default ISO category")
            new_category = TopicCategory.objects.get(
                id=new_creadsubcategory.relatedtopic.id)

        for form in attribute_form.cleaned_data:
            la = Attribute.objects.get(id=int(form['id'].id))
            la.description = form["description"]
            la.attribute_label = form["attribute_label"]
            la.visible = form["visible"]
            la.display_order = form["display_order"]
            la.save()

        if new_poc is not None and new_author is not None:
            new_keywords = layer_form.cleaned_data['keywords']
            layer.keywords.clear()
            layer.keywords.add(*new_keywords)
            the_layer = layer_form.save()
            the_layer.poc = new_poc
            the_layer.metadata_author = new_author
            Layer.objects.filter(id=the_layer.id).update(
                category=new_category
                )

            return HttpResponseRedirect(
                reverse(
                    'layer_detail',
                    args=(
                        layer.service_typename,
                    )))

    logger.debug("layer valid %s ", layer_form.is_valid())
    logger.debug("attribute valid %s ", attribute_form.is_valid())
    logger.debug("subcat valid %s ", cread_subcategory_form.is_valid())

    if poc is None:
        poc_form = ProfileForm(instance=poc, prefix="poc")
    else:
        layer_form.fields['poc'].initial = poc.id
        poc_form = ProfileForm(prefix="poc")
        poc_form.hidden = True

    if metadata_author is None:
        author_form = ProfileForm(instance=metadata_author, prefix="author")
    else:
        layer_form.fields['metadata_author'].initial = metadata_author.id
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
        "layer": layer,
        "layer_form": layer_form,
        "poc_form": poc_form,
        "author_form": author_form,
        "attribute_form": attribute_form,
        "category_form": category_form,
        "cread_form": None,  # read_category_form,
        "cread_sub_form": cread_subcategory_form,
        "cread_categories": categories_struct
    }))


def _preprocess_fields(form):
    """
    This preprocessing field is performed automatically when passing a whole form to the bootstrep filter.
    Anyway we will present each single field on its own, so we have to pre-preprocess them.
    See
       https://github.com/pinax/django-forms-bootstrap/blob/v3.0.1/django_forms_bootstrap/templatetags/bootstrap_tags.py#L9
    """
    for field in form.fields:
        name = form.fields[field].widget.__class__.__name__.lower()
        if not name.startswith("radio") and not name.startswith("checkbox"):
            try:
                form.fields[field].widget.attrs["class"] += " form-control"
            except KeyError:
                form.fields[field].widget.attrs["class"] = " form-control"
    return form


def log_snippet(log_file):
    if not os.path.isfile(log_file):
        return "No log file at %s" % log_file

    with open(log_file, "r") as f:
        f.seek(0, 2)  # Seek @ EOF
        fsize = f.tell()  # Get Size
        f.seek(max(fsize - 10024, 0), 0)  # Set pos @ last n chars
        return f.read()


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


def _resolve_document(request, docid, permission='base.change_resourcebase',
                      msg=_PERMISSION_MSG_GENERIC, **kwargs):
    '''
    Resolve the document by the provided primary key and check the optional permission.
    '''
    return resolve_object(request, Document, {'pk': docid},
                          permission=permission, permission_msg=msg, **kwargs)

						  
@login_required
def document_metadata(
        request,
        docid,
        template='documents/cread_document_metadata.html'):
    
    logger.debug("*** ENTER CREAD:document_metadata")
    
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
    else:	
        cdocumentqs = CReadResource.objects.filter(resource=document)

	if len(cdocumentqs) == 0:
		logger.info('cread_resource does not exist for document %r', document)
		cdocument = None
	else:
		logger.debug('cread_resource found for document %r (%d)', document, len(cdocumentqs))
		cdocument = cdocumentqs[0]
			
        poc = document.poc
        metadata_author = document.metadata_author
        topic_category = document.category
	cread_subcategory = cdocument.subcategory if cdocument else None

        if request.method == "POST":
            document_form = DocumentForm(
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
            document_form = DocumentForm(instance=document, prefix="resource")
            category_form = CategoryForm(
                prefix="category_choice_field",
                initial=topic_category.id if topic_category else None)
            cread_subcategory_form = CReadSubCategoryForm(
	    	prefix="cread_subcategory_choice_field",
		initial=cread_subcategory.id if cread_subcategory else None)

        if request.method == "POST" and document_form.is_valid(
        ) and cread_subcategory_form.is_valid():
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

		if cdocument:
			logger.info("Update CReadResource record")
		else:
			logger.info("Create new CReadResource record")
			cdocument = CReadResource()
			cdocument.resource = document
		
		cdocument.category = new_creadcategory
		cdocument.subcategory = new_creadsubcategory
		cdocument.save()
		# End cread category
	    else:
		logger.info("CRead subcategory form is not valid")


            if category_form.is_valid():
            	new_category = TopicCategory.objects.get(
                	id=category_form.cleaned_data['category_choice_field'])
            else:
            	logger.debug("Assigning default ISO category")
            	new_category = TopicCategory.objects.get(
                	id=new_creadsubcategory.relatedtopic.id)
					
            if new_poc is not None and new_author is not None:
                the_document = document_form.save()
                the_document.poc = new_poc
                the_document.metadata_author = new_author
                the_document.keywords.add(*new_keywords)
                Document.objects.filter(id=the_document.id).update(category=new_category)
                return HttpResponseRedirect(
                    reverse(
                        'document_detail',
                        args=(
                            document.id,
                        )))

	logger.debug("subcat valid %s ", cread_subcategory_form.is_valid())
		
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
                document_form.fields[
                    'metadata_author'].initial = metadata_author.id
                author_form = ProfileForm(prefix="author")
                author_form.hidden = True

        categories_struct = []
	for category in CReadCategory.objects.all():
		subcats = []
		for subcat in CReadSubCategory.objects.filter(category=category):
			subcats.append(subcat.id)
		categories_struct.append((category.id, category.description, subcats))
			
        return render_to_response(template, RequestContext(request, {
            "document": document,
            "document_form": document_form,
            "poc_form": poc_form,
            "author_form": author_form,
            "category_form": category_form,
            "cread_sub_form": cread_subcategory_form,
            "cread_categories": categories_struct
        }))
