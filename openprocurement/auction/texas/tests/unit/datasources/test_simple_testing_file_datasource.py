# -*- coding: utf-8 -*-
import mock
import unittest

from datetime import timedelta

from openprocurement.auction.texas.datasource import SimpleTestingFileDataSource


class TestSimpleTestingFileDataSource(unittest.TestCase):
    datasource_class = SimpleTestingFileDataSource

    def setUp(self):
        self.auction_data = {
            'data': {
                'title': 'test_title',
                'title_en': 'test_title_en',
                'title_ru': 'test_title_ru',
                'auctionPeriod': {},
                'bids': [
                    {'id': 'bid_1'},
                    {'id': 'bid_2'},
                ]
            }
        }

        self.patch_open = mock.patch(
            '__builtin__.open', mock.mock_open(read_data='')
        )
        self.mocked_open = self.patch_open.start()

        self.patch_json_load = mock.patch('openprocurement.auction.texas.datasource.json.load')
        self.mocked_json_load = self.patch_json_load.start()
        self.mocked_json_load.return_value = self.auction_data

        self.patch_datetime = mock.patch('openprocurement.auction.texas.datasource.datetime')
        self.mocked_datetime = self.patch_datetime.start()
        self.mocked_datetime.return_value = 'datetime'
        self.mocked_datetime.now().__add__().isoformat.return_value = 'test_datetime'

        self.patch_open_bidders_name = mock.patch('openprocurement.auction.texas.datasource.open_bidders_name')
        self.mocked_open_bidders_name = self.patch_open_bidders_name.start()
        self.mocked_open_bidders_name.return_value = 'new_db_doc'

    def tearDown(self):
        self.patch_open.stop()
        self.patch_json_load.stop()
        self.patch_datetime.stop()
        self.patch_open_bidders_name.stop()

    def test_init(self):
        datasource = self.datasource_class()

        self.assertIn(
            '/tests/functional/data/tender_texas.json', datasource.path
        )

    def test_get_date(self):
        datasource = self.datasource_class()

        expected = {
            'data': {
                'auctionPeriod': {'startDate': 'test_datetime'},
                'standalone': True,
                'title': '[TEST]test_title',
                'title_en': '[TEST]test_title_en',
                'title_ru': '[TEST]test_title_ru',
                'bids': [
                    {'id': 'bid_1'},
                    {'id': 'bid_2'},
                ]
            }
        }

        auction_data = datasource.get_data()

        self.assertEqual(auction_data, expected)
        self.assertEqual(self.mocked_open.call_count, 1)
        self.assertEqual(self.mocked_json_load.call_count, 1)
        self.assertEqual(self.mocked_datetime.now().__add__().isoformat.call_count, 1)
        self.assertEqual(self.mocked_datetime.now().__add__._mock_call_args_list[1][0], (timedelta(seconds=120), ))

    def test_update_source_object(self):
        db_document = 'db_doc'
        datasource = self.datasource_class()

        result = datasource.update_source_object('external_data', db_document, 'history_data')

        self.assertEqual(self.mocked_open.call_count, 1)
        self.assertEqual(self.mocked_json_load.call_count, 1)
        self.mocked_open_bidders_name.assert_called_once_with(
            db_document,
            {'bid_1': {'bidNumber': '1', 'tenderers': [{'name': 'Opened name of bidder # 1'}]},
             'bid_2': {'bidNumber': '2', 'tenderers': [{'name': 'Opened name of bidder # 2'}]}}
        )
        self.assertEqual(result, 'new_db_doc')


def suite():
    tests = unittest.TestSuite()
    tests.addTest(unittest.makeSuite(TestSimpleTestingFileDataSource))
    return tests
