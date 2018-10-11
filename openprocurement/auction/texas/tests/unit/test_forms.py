# -*- coding: utf-8 -*-
import unittest
from uuid import uuid4

import mock
from munch import munchify
from openprocurement.auction.texas.bids import BidsHandler

from openprocurement.auction.texas.constants import MAIN_ROUND, PAUSE
from openprocurement.auction.texas.forms import BidsForm, form_handler
from openprocurement.auction.texas.tests.unit.utils import create_test_app


class TestFormValidation(unittest.TestCase):

    def setUp(self):
        self.bids_form = BidsForm()
        self.auction_document = {}
        self.bids_form.document = self.auction_document

        self.auction_data = {
            'amount': 100,
            'minimalStep': 50,
            'bidder_id': uuid4().hex
        }

    def tearDown(self):
        self.auction_document = {}

    def test_default_data_required_validators(self):
        valid = self.bids_form.validate()

        self.assertEqual(valid, False)
        self.assertEqual(len(self.bids_form.errors), 2)
        self.assertIn(('bid', [u'Bid amount is required']), self.bids_form.errors.items())
        self.assertIn(('bidder_id', [u'No bidder id']), self.bids_form.errors.items())

    def test_bid_value_stage_error(self):
        self.auction_document.update({
            'current_stage': 0,
            'stages': [{'type': PAUSE, 'amount': self.auction_data['amount']}],
            'minimalStep': {'amount': self.auction_data['minimalStep']}
        })
        self.bids_form.bidder_id.data = self.auction_data['bidder_id']
        self.bids_form.bid.data = 150

        valid = self.bids_form.validate()

        self.assertEqual(valid, False)
        self.assertEqual(len(self.bids_form.errors), 1)
        self.assertEqual({'bid': [u'Current stage does not allow bidding']}, self.bids_form.errors)

    def test_bid_value_too_low(self):
        self.auction_document.update({
            'current_stage': 0,
            'stages': [{'type': MAIN_ROUND, 'amount': self.auction_data['amount']}],
            'minimalStep': {'amount': self.auction_data['minimalStep']}
        })
        self.bids_form.bidder_id.data = self.auction_data['bidder_id']
        self.bids_form.bid.data = 50

        valid = self.bids_form.validate()

        self.assertEqual(valid, False)
        self.assertEqual(len(self.bids_form.errors), 1)
        self.assertEqual({'bid': [u'Too low value']}, self.bids_form.errors)

    def test_bid_value_not_a_multiplier(self):
        self.auction_document.update({
            'current_stage': 0,
            'stages': [{'type': MAIN_ROUND, 'amount': self.auction_data['amount']}],
            'minimalStep': {'amount': self.auction_data['minimalStep']}
        })
        self.bids_form.bidder_id.data = self.auction_data['bidder_id']
        self.bids_form.bid.data = 142

        valid = self.bids_form.validate()

        self.assertEqual(valid, False)
        self.assertEqual(len(self.bids_form.errors), 1)
        self.assertEqual(
            {'bid': [u'Value should be a multiplier of ' 
                     u'a minimalStep amount ({})'.format(self.auction_data['minimalStep'])]},
            self.bids_form.errors
        )

    def test_bid_value_success(self):
        self.auction_document.update({
            'current_stage': 0,
            'stages': [{'type': MAIN_ROUND, 'amount': self.auction_data['amount']}],
            'minimalStep': {'amount': self.auction_data['minimalStep']}
        })
        self.bids_form.bidder_id.data = self.auction_data['bidder_id']
        self.bids_form.bid.data = 150

        valid = self.bids_form.validate()

        self.assertEqual(valid, True)


class TestFormHandler(unittest.TestCase):

    def setUp(self):
        self.app = create_test_app()
        self.app.application.form_handler = form_handler
        self.app.application.bids_handler = BidsHandler()

        self.auction_document = {'current_stage': 0}
        self.app.application.context['auction_document'] = self.auction_document

        self.patch_request = mock.patch(
            'openprocurement.auction.texas.forms.request', munchify({'json': {}, 'headers': {}})
        )
        self.patch_request.start()

        self.patch_session = mock.patch(
            'openprocurement.auction.texas.forms.session', munchify({'client_id': None})
        )
        self.patch_session.start()

    def tearDown(self):
        self.patch_request.stop()
        self.patch_session.stop()

    def test_form_handler_success(self):

        self.app.application.bids_handler.add_bid = mock.MagicMock(
            return_value=True
        )

        magic_form = mock.MagicMock()
        magic_form.validate.return_value = True

        self.app.application.bids_form = mock.MagicMock()
        self.app.application.bids_form.from_json.return_value = magic_form

        with self.app.application.test_request_context():
            res = self.app.application.form_handler()

        self.assertEqual(res, {'status': 'ok', 'data': magic_form.data})

    def test_form_handler_error(self):

        self.app.application.bids_handler.add_bid = mock.MagicMock(
            return_value=Exception('Something went wrong :(')
        )

        magic_form = mock.MagicMock()
        magic_form.validate.return_value = True

        self.app.application.bids_form = mock.MagicMock()
        self.app.application.bids_form.from_json.return_value = magic_form

        with self.app.application.test_request_context():
            res = self.app.application.form_handler()

        self.assertEqual(res, {'status': 'failed', 'errors': [["Exception('Something went wrong :(',)"]]})

    def test_form_handler_invalid(self):
        with self.app.application.test_request_context():
            res = self.app.application.form_handler()

        self.assertEqual(
            res, {'status': 'failed', 'errors': {'bid': [u'Bid amount is required'], 'bidder_id': [u'No bidder id']}}
        )


def suite():
    tests = unittest.TestSuite()
    tests.addTest(unittest.makeSuite(TestFormValidation))
    tests.addTest(unittest.makeSuite(TestFormHandler))
    return tests
