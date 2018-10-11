import munch
import os
import yaml

from zope.component import getGlobalSiteManager
from flask import redirect
from pytz import timezone as tz
from datetime import datetime, timedelta
from dateutil.tz import tzlocal
from mock import MagicMock, patch

from openprocurement.auction.texas.forms import BidsForm
from openprocurement.auction.texas.server import initialize_application, add_url_rules
from openprocurement.auction.texas.auction import Auction
from openprocurement.auction.texas.context import IContext
from openprocurement.auction.texas.cli import register_utilities

from openprocurement.auction.texas.tests.data.data import tender_data, test_auction_document


PWD = os.path.dirname(os.path.realpath(__file__))

worker_defaults_file_path = os.path.join(PWD, "../data/auction_worker_defaults.yaml")
with open(worker_defaults_file_path) as stream:
    worker_defaults = yaml.load(stream)


def update_auctionPeriod(data):
    new_start_time = (datetime.now(tzlocal()) + timedelta(seconds=1)).isoformat()
    if 'lots' in data['data']:
        for lot in data['data']['lots']:
            lot['auctionPeriod']['startDate'] = new_start_time
    data['data']['auctionPeriod']['startDate'] = new_start_time


def create_test_app():
    worker_app = initialize_application()
    update_auctionPeriod(tender_data)
    logger = MagicMock()
    logger.name = 'some-logger'
    yaml_config = yaml.load(open(worker_defaults_file_path))

    args = munch.Munch(
        {
            'standalone': False,
            'auction_doc_id': str(tender_data['data']['auctionID'])
         }
    )
    db = MagicMock()
    db.get.return_value = test_auction_document
    with patch('openprocurement.auction.texas.cli.prepare_database', db):
        register_utilities(yaml_config, args)

    app_auction = Auction(
        tender_id=tender_data['data']['auctionID'],
        worker_defaults=yaml.load(open(worker_defaults_file_path)),
    )
    worker_app.config.update(app_auction.worker_defaults)
    worker_app.logger_name = logger.name
    worker_app._logger = logger
    worker_app.config['auction'] = app_auction
    worker_app.config['timezone'] = tz('Europe/Kiev')
    worker_app.config['SESSION_COOKIE_PATH'] = '/{}/{}'.format(
        'auctions', tender_data['data']['auctionID'])
    worker_app.config['SESSION_COOKIE_NAME'] = 'auction_session'
    worker_app.oauth = MagicMock()
    worker_app.bids_form = BidsForm
    worker_app.form_handler = MagicMock()
    worker_app.form_handler.return_value = {'data': 'ok'}
    worker_app.remote_oauth = MagicMock()
    # Add context to app
    worker_app.gsm = getGlobalSiteManager()
    worker_app.context = worker_app.gsm.queryUtility(IContext)
    worker_app.context['bidders_data'] = tender_data['data']['bids']
    worker_app.context['auction_document'] = {}

    worker_app.remote_oauth.authorized_response.side_effect = [None, {
        u'access_token': u'aMALGpjnB1iyBwXJM6betfgT4usHqw',
        u'token_type': u'Bearer',
        u'expires_in': 86400,
        u'refresh_token': u'uoRKeSJl9UFjuMwOw6PikXuUVp7MjX',
        u'scope': u'email'
    }]
    worker_app.remote_oauth.authorize.return_value = \
        redirect('https://my.test.url')
    worker_app.logins_cache[(u'aMALGpjnB1iyBwXJM6betfgT4usHqw', '')] = {
        u'bidder_id': u'f7c8cd1d56624477af8dc3aa9c4b3ea3',
        u'expires':
            (datetime.now(tzlocal()) + timedelta(0, 600)).isoformat()
    }
    worker_app.auction_bidders = {
        u'f7c8cd1d56624477af8dc3aa9c4b3ea3': {
            'clients': {},
            'channels': {}
        }}

    # Register views
    add_url_rules(worker_app)
    return worker_app.test_client()
