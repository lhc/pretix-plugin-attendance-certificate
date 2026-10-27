from django.urls import reverse
from django.template.loader import get_template
from django.contrib.humanize.templatetags.humanize import intcomma
from django.utils.translation import gettext_lazy as _, ngettext
from django import forms

from pretix.plugins.sendmail.views import BaseSenderView
from pretix.plugins.sendmail.forms import BaseMailForm
from pretix.base.models import OrderPosition, Order

from pretix_attendance_certificate.tasks import send_certificate_of_attendance_mails
from django_scopes.forms import SafeModelMultipleChoiceField
from pretix.base.models import CheckinList
from django.utils.translation import pgettext_lazy
from pretix.control.forms.widgets import Select2Multiple


class CertificateEmailForm(BaseMailForm):
    checked_in = forms.BooleanField(
        label=pgettext_lazy(
            "sendmail_form",
            "Send out certificates only to recipients with check-in on any list",
        ),
        required=False,
        initial=True,
    )
    checkin_lists = SafeModelMultipleChoiceField(
        queryset=CheckinList.objects.none(), required=False
    )  # overridden later

    def __init__(self, *args, **kwargs) -> None:
        event = self.event = kwargs["event"]
        super().__init__(*args, **kwargs)

        self.fields["checkin_lists"].queryset = event.checkin_lists.all()
        self.fields["checkin_lists"].widget = Select2Multiple(
            attrs={
                "data-model-select2": "generic",
                "data-select2-url": reverse(
                    "control:event.orders.checkinlists.select2",
                    kwargs={
                        "event": event.slug,
                        "organizer": event.organizer.slug,
                    },
                ),
                "data-placeholder": pgettext_lazy(
                    "sendmail_form", "Restrict to recipients with check-in on list"
                ),
            }
        )
        self.fields["checkin_lists"].widget.choices = self.fields[
            "checkin_lists"
        ].choices
        self.fields["checkin_lists"].label = pgettext_lazy(
            "sendmail_form", "Restrict to recipients with check-in on list"
        )


class SendCertificateEmailView(BaseSenderView):
    form_class = CertificateEmailForm
    form_fragment_name = (
        "pretix_attendance_certificate/send_form_fragment_attendance_certificate.html"
    )
    context_parameters = ["event", "order", "position_or_address"]
    task = send_certificate_of_attendance_mails

    ACTION_TYPE = "pretix_attendance_certificate.sendmail.sent"
    TITLE = _("Attendance Certificate")
    DESCRIPTION = _("Send out the attendance certificates to attendees.")

    @classmethod
    def get_url(cls, event):
        return reverse(
            "plugins:pretix_attendance_certificate:send",
            kwargs={
                "event": event.slug,
                "organizer": event.organizer.slug,
            },
        )

    def get_object_queryset(self, form):
        event = self.request.event

        order_positions = OrderPosition.objects.filter(
            canceled=False,
            item__admission=True,
            order__event=event,
            order__status__in=[Order.STATUS_PAID],
        )

        checked_in = form.cleaned_data["checked_in"]
        if checked_in:
            order_positions = order_positions.filter(
                all_checkins__successful=checked_in
            )

        checkin_lists = form.cleaned_data["checkin_lists"]
        if checkin_lists:
            order_positions = order_positions.filter(
                all_checkins__list__in=checkin_lists
            )

        return order_positions.distinct()

    def describe_match_size(self, cnt):
        return ngettext(
            "%(number)s matching ticket",
            "%(number)s matching tickets",
            cnt or 0,
        ) % {
            "number": intcomma(cnt or 0),
        }

    def get_task_kwargs(self, form, objects):
        kwargs = super().get_task_kwargs(form, objects)
        return kwargs

    @classmethod
    def show_history_meta_data(cls, logentry, _cache_store):
        tpl = get_template(
            "pretix_attendance_certificate/history_fragment_attendance_certificate.html"
        )
        return tpl.render(
            {
                "log": logentry,
            }
        )
