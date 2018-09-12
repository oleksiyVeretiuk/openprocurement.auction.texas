# -*- coding: utf-8 -*-
from openprocurement.auction.includeme import _register
from openprocurement.auction.auctions_server import auctions_proxy
from openprocurement.auction.interfaces import IAuctionsServer


def texasProcedure(components, procurement_method_types):
    for procurementMethodType in procurement_method_types:
        _register(components, procurementMethodType)


def texas_routes(components):
    server = components.queryUtility(IAuctionsServer)
    server.add_url_rule('/texas-auctions/<auction_doc_id>/<path:path>', 'auctions',
                     auctions_proxy,
                     methods=['GET', 'POST'])
