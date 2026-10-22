import datetime
import inspect

import pytest
from django.utils import translation
from django.utils.timezone import now
from django_scopes import scopes_disabled

from pretix.base.models import (
    Event,
    Item,
    Order,
    OrderPosition,
    Organizer,
    Team,
    User,
)
from pretix.base.models import SalesChannel

from pretix_attendance_certificate.models import AttendanceCertificateLayout


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef, request):
    """Disable django-scopes for all non-yield fixtures.

    Mirrors pretix' own test suite so fixtures can create scoped models
    (Order, OrderPosition, ...) without an active scope.
    """
    if inspect.isgeneratorfunction(fixturedef.func):
        yield
    else:
        with scopes_disabled():
            yield


@pytest.fixture(autouse=True)
def reset_locale():
    translation.activate("en")


@pytest.fixture
def organizer():
    return Organizer.objects.create(name="Test Organizer", slug="test-organizer")


@pytest.fixture
def sales_channel(organizer):
    return SalesChannel.objects.create(
        organizer=organizer,
        label="Sales Channel",
        identifier="sales-channel",
        type="sales-channel-type",
    )


@pytest.fixture
def event(organizer):
    event = Event.objects.create(
        organizer=organizer,
        name="Dummy",
        slug="dummy",
        date_from=now(),
        live=True,
        plugins="pretix_attendance_certificate",
    )
    return event


@pytest.fixture
def layout(event):
    return AttendanceCertificateLayout.objects.create(event=event, name="Default")


@pytest.fixture
def item(event):
    return Item.objects.create(
        name="Test item", event=event, default_price=13, admission=True
    )


@pytest.fixture
def order(event, sales_channel):
    return Order.objects.create(
        event=event,
        status=Order.STATUS_PAID,
        expires=now() + datetime.timedelta(hours=1),
        total=13,
        code="DUMMY",
        email="order@example.com",
        datetime=now(),
        locale="en",
        sales_channel=sales_channel,
    )


@pytest.fixture
def pos(order, item):
    return OrderPosition.objects.create(
        order=order,
        item=item,
        price=13,
        attendee_name_parts={"_legacy": "Marco Acierno"},
        attendee_email="attendee@dummy.test",
    )


@pytest.fixture
def create_order_position(order, item):
    def _create_order_position(order, item, **kwargs):
        return OrderPosition.objects.create(
            order=order,
            item=item,
            price=kwargs.get("price", 13),
            attendee_name_parts={"_legacy": "Marco Acierno"},
            attendee_email=kwargs.get("attendee_email", "attendee@example.com"),
        )

    return _create_order_position


@pytest.fixture
def logged_in_client(client, event):
    user = User.objects.create_user("dummy@dummy.dummy", "dummy")
    team = Team.objects.create(organizer=event.organizer)
    team.members.add(user)
    team.limit_events.add(event)
    team.limit_event_permissions["event.orders:write"] = True
    team.save()
    client.force_login(user)
    return client
