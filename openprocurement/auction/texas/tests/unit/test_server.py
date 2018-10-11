import json
import unittest
from openprocurement.auction.texas.tests.unit.utils import create_test_app

from flask import session
from datetime import datetime, timedelta
from dateutil.tz import tzlocal
from mock import patch


class TestFlaskApp(unittest.TestCase):

    def setUp(self):
        self.app = create_test_app()

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
