# -*- coding: utf-8 -*-
import logging

from openprocurement.auction.auctions_server import auctions_proxy
from openprocurement.auction.core import RunDispatcher
from openprocurement.auction.interfaces import (
    IFeedItem, IAuctionDatabridge, IAuctionsChronograph, IAuctionsServer
)

from openprocurement.auction.texas.interfaces import ITexasAuction
from openprocurement.auction.texas.planning import TexasPlanning

LOGGER = logging.getLogger(__name__)


def texasProcedure(components, procurement_method_types):
    for procurementMethodType in procurement_method_types:
        includeme(components, procurementMethodType)


def texas_routes(components):
    server = components.queryUtility(IAuctionsServer)
    server.add_url_rule('/texas-auctions/<auction_doc_id>/<path:path>', 'auctions',
                        auctions_proxy,
                        methods=['GET', 'POST'])


def includeme(components, procurement_method_type):
    components.add_auction(ITexasAuction,
                           procurementMethodType=procurement_method_type)
    components.registerAdapter(TexasPlanning, (IAuctionDatabridge, IFeedItem),
                               ITexasAuction)
    components.registerAdapter(RunDispatcher,
                               (IAuctionsChronograph, IFeedItem),
                               ITexasAuction)
    LOGGER.info("Included %s plugin" % procurement_method_type,
                extra={'MESSAGE_ID': 'included_plugin'})
