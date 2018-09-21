import json
import munch
import unittest
import os
import yaml

from zope.component import getGlobalSiteManager
from flask import session, redirect
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


class TestFlaskApp(unittest.TestCase):

    def setUp(self):
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

        self.app = worker_app.test_client()

    def test_server_login(self):
        app = self.app
        headers = {
            'X-Forwarded-Path':
                'http://localhost:8090/auctions/11111111111111111111111111111111'
                '/authorized?code=HVRviZDxswGzM8AYN3rz0qMLrh6rhY'
        }
        res = app.post('/login', headers=headers)
        self.assertEqual(res.status, '405 METHOD NOT ALLOWED')
        self.assertEqual(res.status_code, 405)

        res = app.get('/login')
        self.assertEqual(res.status, '401 UNAUTHORIZED')
        self.assertEqual(res.status_code, 401)

        res = app.get('/login?bidder_id=5675acc9232942e8940a034994ad883e&'
                      'hash=bd4a790aac32b73e853c26424b032e5a29143d1f')
        self.assertEqual(res.status, '302 FOUND')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.location, 'https://my.test.url')
        with app.application.test_request_context():
            session['login_bidder_id'] = u'5675acc9232942e8940a034994ad883e'
            session['login_hash'] = u'bd4a790aac32b73e853c26424b032e5a29143d1f'
            session['login_callback'] = 'http://localhost/authorized'
            log_message = 'Session: {}'.format(repr(session))
            app.application.logger.debug.assert_called_with(log_message)

        res = app.get('/login?bidder_id=5675acc9232942e8940a034994ad883e&'
                      'hash=bd4a790aac32b73e853c26424b032e5a29143d1f',
                      headers=headers)
        self.assertEqual(res.status, '302 FOUND')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.location, 'https://my.test.url')
        with app.application.test_request_context():
            session[u'login_bidder_id'] = u'5675acc9232942e8940a034994ad883e'
            session[u'login_hash'] = u'bd4a790aac32b73e853c26424b032e5a29143d1f'
            session[u'login_callback'] = u'http://localhost:8090/auctions/' \
                '11111111111111111111111111111111/authorized'
            log_message = 'Session: {}'.format(repr(session))
            app.application.logger.debug.assert_called_with(log_message)

        res = app.get('/login?bidder_id=5675acc9232942e8940a034994ad883e&'
                      'hash=bd4a790aac32b73e853c26424b032e5a29143d1f&'
                      'return_url=https://my.secret.url/')
        self.assertEqual(res.status, '302 FOUND')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.location, 'https://my.test.url')
        with app.application.test_request_context():
            session['return_url'] = u'https://my.secret.url/'
            session['login_bidder_id'] = u'5675acc9232942e8940a034994ad883e'
            session['login_hash'] = u'bd4a790aac32b73e853c26424b032e5a29143d1f'
            session['login_callback'] = 'http://localhost/authorized'

    def test_server_authorized(self):
        app = self.app
        headers = {
            'X-Forwarded-Path':
                'http://localhost:8090/auctions/11111111111111111111111111111111'
                '/authorized?code=HVRviZDxswGzM8AYN3rz0qMLrh6rhY'
        }

        res = app.post('/authorized', headers=headers)
        self.assertEqual(res.status, '405 METHOD NOT ALLOWED')
        self.assertEqual(res.status_code, 405)

        res = app.get('/authorized', headers=headers)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.status, '403 FORBIDDEN')

        res = app.get('/authorized?error=access_denied')
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.status, '403 FORBIDDEN')

        res = app.get('/authorized', headers=headers)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.status, '302 FOUND')
        self.assertEqual(
            res.location,
            'http://localhost:8090/auctions/11111111111111111111111111111111'
        )
        auctions_loggedin = False
        auction_session = False
        path = False
        for h in res.headers:
            if h[1].startswith('auctions_loggedin=1'):
                auctions_loggedin = True
                if h[1].index('Path=/auctions/UA-11111'):
                    path = True
            if h[1].startswith('auction_session='):
                auction_session = True
        self.assertTrue(auction_session)
        self.assertTrue(auctions_loggedin)
        self.assertTrue(path)

    def test_server_relogin(self):
        app = self.app
        headers = {
            'X-Forwarded-Path':
                'http://localhost:8090/auctions/11111111111111111111111111111111'
                '/authorized?code=HVRviZDxswGzM8AYN3rz0qMLrh6rhY'
        }

        res = app.post('/relogin', headers=headers)
        self.assertEqual(res.status, '405 METHOD NOT ALLOWED')
        self.assertEqual(res.status_code, 405)

        res = app.get('/relogin', headers=headers)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.status, '302 FOUND')
        self.assertEqual(
            res.location,
            'http://localhost:8090/auctions/11111111111111111111111111111111'
        )
        s = {
            'login_callback': 'https://some.url/',
            'login_bidder_id': 'some_id',
            'login_hash': 'some_cache',
            'amount': 100
        }
        with patch('openprocurement.auction.texas.views.session', s):
            res = app.get('/relogin?amount=100', headers=headers)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.status, '302 FOUND')
        self.assertEqual(res.location, 'https://my.test.url')

    def test_server_check_authorization(self):
        app = self.app

        res = app.get('/check_authorization')
        self.assertEqual(res.status, '405 METHOD NOT ALLOWED')
        self.assertEqual(res.status_code, 405)

        s = {
            'remote_oauth': (u'aMALGpjnB1iyBwXJM6betfgT4usHqw', ''),
            'client_id': 'b3a000cdd006b4176cc9fafb46be0273'
        }

        res = app.post('/check_authorization')
        self.assertEqual(res.status, '401 UNAUTHORIZED')
        self.assertEqual(res.status_code, 401)

        with patch('openprocurement.auction.texas.views.session', s):
            res = app.post('/check_authorization')
        self.assertEqual(res.status, '200 OK')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json.loads(res.data)['status'], 'ok')

        with patch('openprocurement.auction.texas.views.session', s):
            app.application.logins_cache[
                (u'aMALGpjnB1iyBwXJM6betfgT4usHqw', '')
            ]['expires'] = (
                (datetime.now(tzlocal()) - timedelta(0, 600)).isoformat()
            )
            res = app.post('/check_authorization')
        self.assertEqual(res.status, '401 UNAUTHORIZED')
        self.assertEqual(res.status_code, 401)
        app.application.logger.info.assert_called_with(
            'Grant will end in a short time. Activate re-login functionality',
            extra={}
        )
        s['remote_oauth'] = 'invalid'

        with patch('openprocurement.auction.texas.views.session', s):
            res = app.post('/check_authorization')
        self.assertEqual(res.status, '401 UNAUTHORIZED')
        self.assertEqual(res.status_code, 401)
        app.application.logger.warning.assert_called_with(
            "Client_id {} didn't passed check_authorization".format(
                s['client_id']), extra={})

    def test_server_logout(self):
        app = self.app
        s = {
            'remote_oauth': (u'aMALGpjnB1iyBwXJM6betfgT4usHqw', ''),
            'client_id': 'b3a000cdd006b4176cc9fafb46be0273'
        }
        headers = {
            'X-Forwarded-Path':
                'http://localhost:8090/auctions/11111111111111111111111111111111'
                '/authorized?code=HVRviZDxswGzM8AYN3rz0qMLrh6rhY'
        }
        with patch('openprocurement.auction.texas.views.session', s):
            res = app.get('/logout', headers=headers)
        self.assertEqual(res.status_code, 302)
        self.assertEqual(res.status, '302 FOUND')
        self.assertEqual(
            res.location,
            'http://localhost:8090/auctions/11111111111111111111111111111111'
        )

    def test_server_postbid(self):
        app = self.app

        res = app.get('/postbid')
        self.assertEqual(res.status, '405 METHOD NOT ALLOWED')
        self.assertEqual(res.status_code, 405)

        s = {
            'remote_oauth': (u'aMALGpjnB1iyBwXJM6betfgT4usHqw', ''),
            'client_id': 'b3a000cdd006b4176cc9fafb46be0273'
        }
        with patch('openprocurement.auction.texas.views.session', s):
            res = app.post(
                '/postbid',
                data=json.dumps(
                    {'bidder_id': u'f7c8cd1d56624477af8dc3aa9c4b3ea3'}
                ),
                headers={'Content-Type': 'application/json'}
            )
        self.assertEqual(res.status, '200 OK')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json.loads(res.data)['data'], 'ok')

        with patch('openprocurement.auction.texas.views.session', s):
            res = app.post(
                '/postbid',
                data=json.dumps(
                    {'bidder_id': u'5675acc9232942e8940a034994666666'}
                ),
                headers={'Content-Type': 'application/json'}
            )
        mess_str = \
            'Client with client id: b3a000cdd006b4176cc9fafb46be0273 and ' \
            'bidder_id 5675acc9232942e8940a034994666666 wants post bid but ' \
            'response status from Oauth'
        app.application.logger.warning.assert_called_with(mess_str)
        self.assertEqual(res.status, '401 UNAUTHORIZED')
        self.assertEqual(res.status_code, 401)

    def test_server_kickclient(self):
        app = self.app
        s = {
            'remote_oauth': (u'aMALGpjnB1iyBwXJM6betfgT4usHqw', ''),
            'client_id': 'b3a000cdd006b4176cc9fafb46be0273'
        }
        data = {
            'client_id': s['client_id'],
            'bidder_id': u'f7c8cd1d56624477af8dc3aa9c4b3ea3'
        }
        headers = {'Content-Type': 'application/json'}

        res = app.get('/kickclient')
        self.assertEqual(res.status, '405 METHOD NOT ALLOWED')
        self.assertEqual(res.status_code, 405)

        res = app.post('/kickclient', data=json.dumps(data), headers=headers)
        self.assertEqual(res.status, '401 UNAUTHORIZED')
        self.assertEqual(res.status_code, 401)

        with patch('openprocurement.auction.texas.views.session', s):
            res = app.post('/kickclient', data=json.dumps(data), headers=headers)
        self.assertEqual(res.status, '200 OK')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(json.loads(res.data)['status'], 'ok')


def suite():
    tests = unittest.TestSuite()
    tests.addTest(unittest.makeSuite(TestFlaskApp))
    return tests
