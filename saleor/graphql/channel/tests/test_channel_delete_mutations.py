from unittest import mock

import graphene
from django.utils.functional import SimpleLazyObject
from freezegun import freeze_time

from ....channel.error_codes import ChannelErrorCode
from ....channel.models import Channel
from ....checkout.models import Checkout
from ....order.models import Order
from ....webhook.event_types import WebhookEventAsyncType
from ....webhook.payloads import generate_meta, generate_requestor
from ...tests.utils import assert_no_permission, get_graphql_content

CHANNEL_DELETE_MUTATION = """
    mutation deleteChannel($id: ID!, $input: ChannelDeleteInput){
        channelDelete(id: $id, input: $input){
            channel{
                id
                name
                slug
                currencyCode
            }
            errors{
                field
                code
                message
            }
        }
    }
"""


def test_channel_delete_mutation_as_staff_user(
    order_list,
    checkout,
    permission_manage_channels,
    staff_api_client,
    channel_USD,
    other_channel_USD,
    product,
):
    # given
    order = order_list[0]
    order.channel = channel_USD
    order.save()

    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    channel_target_id = graphene.Node.to_global_id("Channel", other_channel_USD.id)
    variables = {"id": channel_id, "input": {"channelId": channel_target_id}}
    assert Checkout.objects.first() is not None
    # when
    response = staff_api_client.post_graphql(
        CHANNEL_DELETE_MUTATION,
        variables=variables,
        permissions=(permission_manage_channels,),
    )
    get_graphql_content(response)
    order.refresh_from_db()

    assert order.channel == other_channel_USD
    assert Checkout.objects.first() is None
    assert not Channel.objects.filter(slug=channel_USD.slug).exists()


def test_channel_delete_mutation_with_the_same_channel_and_target_channel_id(
    permission_manage_channels, staff_api_client, channel_USD
):
    # given
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {"id": channel_id, "input": {"channelId": channel_id}}

    # when
    response = staff_api_client.post_graphql(
        CHANNEL_DELETE_MUTATION,
        variables=variables,
        permissions=(permission_manage_channels,),
    )
    content = get_graphql_content(response)
    error = content["data"]["channelDelete"]["errors"][0]

    assert error["field"] == "channelId"
    assert error["code"] == ChannelErrorCode.INVALID.name


def test_channel_delete_mutation_without_migration_channel_with_orders(
    permission_manage_channels,
    staff_api_client,
    channel_USD,
    checkout,
    order_list,
):
    # given
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {"id": channel_id}
    checkout = Checkout.objects.first()
    assert checkout.channel == channel_USD
    assert Order.objects.filter(channel=channel_USD).exists()

    # when
    response = staff_api_client.post_graphql(
        CHANNEL_DELETE_MUTATION,
        variables=variables,
        permissions=(permission_manage_channels,),
    )
    content = get_graphql_content(response)

    # then
    error = content["data"]["channelDelete"]["errors"][0]
    assert error["field"] == "id"
    assert error["code"] == ChannelErrorCode.CHANNEL_WITH_ORDERS.name
    assert Channel.objects.filter(slug=channel_USD.slug).exists()


def test_channel_delete_mutation_without_orders_in_channel(
    permission_manage_channels,
    staff_api_client,
    channel_USD,
    checkout,
):
    # given
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    variables = {"id": channel_id}
    checkout = Checkout.objects.first()
    assert checkout.channel == channel_USD
    assert Order.objects.first() is None

    # when
    response = staff_api_client.post_graphql(
        CHANNEL_DELETE_MUTATION,
        variables=variables,
        permissions=(permission_manage_channels,),
    )
    content = get_graphql_content(response)

    # then
    assert not content["data"]["channelDelete"]["errors"]
    assert Checkout.objects.first() is None
    assert not Channel.objects.filter(slug=channel_USD.slug).exists()


def test_channel_delete_mutation_with_different_currency(
    permission_manage_channels, staff_api_client, channel_USD, channel_PLN
):
    # given
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    target_channel_id = graphene.Node.to_global_id("Channel", channel_PLN.id)
    variables = {"id": channel_id, "input": {"channelId": target_channel_id}}

    # when
    response = staff_api_client.post_graphql(
        CHANNEL_DELETE_MUTATION,
        variables=variables,
        permissions=(permission_manage_channels,),
    )
    content = get_graphql_content(response)
    error = content["data"]["channelDelete"]["errors"][0]

    assert error["field"] == "channelId"
    assert error["code"] == ChannelErrorCode.CHANNELS_CURRENCY_MUST_BE_THE_SAME.name


def test_channel_delete_mutation_as_app(
    permission_manage_channels,
    app_api_client,
    order_list,
    channel_USD,
    other_channel_USD,
    checkout,
):
    # given
    order = order_list[0]
    order.channel = channel_USD
    order.save()
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    channel_target_id = graphene.Node.to_global_id("Channel", other_channel_USD.id)
    variables = {"id": channel_id, "input": {"channelId": channel_target_id}}
    assert Checkout.objects.first() is not None

    # when
    response = app_api_client.post_graphql(
        CHANNEL_DELETE_MUTATION,
        variables=variables,
        permissions=(permission_manage_channels,),
    )

    get_graphql_content(response)
    order.refresh_from_db()

    # then
    assert order.channel == other_channel_USD
    assert Checkout.objects.first() is None
    assert not Channel.objects.filter(slug=channel_USD.slug).exists()


def test_channel_delete_mutation_as_customer(
    user_api_client, channel_USD, other_channel_USD
):
    # given
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    channel_target_id = graphene.Node.to_global_id("Channel", other_channel_USD.id)
    variables = {"id": channel_id, "input": {"channelId": channel_target_id}}

    # when
    response = user_api_client.post_graphql(
        CHANNEL_DELETE_MUTATION,
        variables=variables,
        permissions=(),
    )

    # then
    assert_no_permission(response)
    assert Channel.objects.filter(slug=channel_USD.slug).exists()


def test_channel_delete_mutation_as_anonymous(
    api_client, channel_USD, other_channel_USD
):
    # given
    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    channel_target_id = graphene.Node.to_global_id("Channel", other_channel_USD.id)
    variables = {"id": channel_id, "input": {"channelId": channel_target_id}}

    # when
    response = api_client.post_graphql(
        CHANNEL_DELETE_MUTATION,
        variables=variables,
        permissions=(),
    )

    # then
    assert_no_permission(response)
    assert Channel.objects.filter(slug=channel_USD.slug).exists()


@freeze_time("2022-05-12 12:00:00")
@mock.patch("saleor.plugins.webhook.plugin.get_webhooks_for_event")
@mock.patch("saleor.plugins.webhook.plugin.trigger_webhooks_async")
def test_channel_delete_mutation_trigger_webhook(
    mocked_webhook_trigger,
    mocked_get_webhooks_for_event,
    any_webhook,
    checkout,
    permission_manage_channels,
    staff_api_client,
    channel_USD,
    other_channel_USD,
    settings,
):
    # given
    mocked_get_webhooks_for_event.return_value = [any_webhook]
    settings.PLUGINS = ["saleor.plugins.webhook.plugin.WebhookPlugin"]

    channel_id = graphene.Node.to_global_id("Channel", channel_USD.id)
    channel_target_id = graphene.Node.to_global_id("Channel", other_channel_USD.id)
    variables = {"id": channel_id, "input": {"channelId": channel_target_id}}
    assert Checkout.objects.first() is not None

    # when
    response = staff_api_client.post_graphql(
        CHANNEL_DELETE_MUTATION,
        variables=variables,
        permissions=(permission_manage_channels,),
    )
    get_graphql_content(response)

    # then
    assert not Channel.objects.filter(slug=channel_USD.slug).exists()

    mocked_webhook_trigger.assert_called_once_with(
        {
            "id": graphene.Node.to_global_id("Channel", channel_USD.id),
            "is_active": channel_USD.is_active,
            "meta": generate_meta(
                requestor_data=generate_requestor(
                    SimpleLazyObject(lambda: staff_api_client.user)
                )
            ),
        },
        WebhookEventAsyncType.CHANNEL_DELETED,
        [any_webhook],
        channel_USD,
        SimpleLazyObject(lambda: staff_api_client.user),
    )
