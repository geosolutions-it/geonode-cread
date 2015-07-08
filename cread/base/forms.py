# -*- coding: utf-8 -*-

from django import forms
from mptt.forms import TreeNodeMultipleChoiceField, TreeNodeChoiceField

from django.utils.translation import ugettext as _

from cread.base.models import CReadCategory, CReadSubCategory


class CReadCategoryChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return '<span class="has-popover" data-container="body" data-toggle="popover" data-placement="top" ' \
               'data-content="' + obj.description + '" trigger="hover">' + obj.description + '</span>'


class CReadCategoryForm(forms.Form):
    cread_category_choice_field = CReadCategoryChoiceField(required=False,
                                                label='*' + _('CReadCategory'),
                                                empty_label=None,
                                                queryset=CReadCategory.objects.extra(order_by=['identifier']))

    def clean(self):
        cleaned_data = self.data
        ccf_data = cleaned_data.get("cread_category_choice_field")

        if not ccf_data:
            msg = _("CRead Category is required.")
            self._errors = self.error_class([msg])

        # Always return the full collection of cleaned data.
        return cleaned_data


class CReadSubCategoryChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return '<span class="has-popover" data-container="body" data-toggle="popover" data-placement="top" ' \
               'data-content="' + obj.description + '" trigger="hover">' + obj.description + '</span>'


class CReadSubCategoryForm(forms.Form):
    cread_subcategory_choice_field = CReadSubCategoryChoiceField(required=False,
                                                label='*' + _('CReadSubCategory'),
                                                empty_label=None,
                                                queryset=CReadSubCategory.objects.extra(order_by=['identifier']))

    def clean(self):
        cleaned_data = self.data
        ccf_data = cleaned_data.get("cread_subcategory_choice_field")

        if not ccf_data:
            msg = _("CRead SubCategory is required.")
            self._errors = self.error_class([msg])

        # Always return the full collection of cleaned data.
        return cleaned_data


