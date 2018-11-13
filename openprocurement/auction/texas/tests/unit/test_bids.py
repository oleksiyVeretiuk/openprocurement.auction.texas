import unittest

import mock
from copy import deepcopy
from datetime import datetime

from openprocurement.auction.texas.bids import BidsHandler
from openprocurement.auction.texas.constants import DEADLINE_HOUR


class TestBidsHandler(unittest.TestCase):
    def setUp(self):

        self.bids_handler = BidsHandler()
        self.bids_handler.context = {
            'bids_mapping': {'test_bidder_id': 'test_name'},
            'worker_defaults': {
                'deadline': {
                    'deadline_hour': DEADLINE_HOUR
                }
            }
        }
        self.bids_handler.database = mock.MagicMock()
        self.bids_handler.job_service = mock.MagicMock()
        self.test_bid = {'amount': 350, 'bidder_id': 'test_bidder_id', 'time': 'current_time'}

        self.patch_update_auction_document = mock.patch(
            'openprocurement.auction.texas.utils.update_auction_document'
        )
        self.mocked_update_auction_document = self.patch_update_auction_document.start()

        self.bid_with_name = deepcopy(self.test_bid)
        self.bid_with_name.update({'bidder_name': 'test_name'})

    def tearDown(self):
        self.patch_update_auction_document.stop()


class TestAddBid(TestBidsHandler):

    def setUp(self):
        super(TestAddBid, self).setUp()

        self.patch_sorting_by_amount = mock.patch('openprocurement.auction.texas.bids.sorting_by_amount')
        self.patch_prepare_results_stage = mock.patch('openprocurement.auction.texas.bids.utils.prepare_results_stage')
        self.patch_end_bid_stage = mock.patch.object(self.bids_handler, 'end_bid_stage')

        self.mocked_sorting_by_amount = self.patch_sorting_by_amount.start()
        self.mocked_prepare_results_stage = self.patch_prepare_results_stage.start()
        self.mocked_end_bid_stage = self.patch_end_bid_stage.start()

        self.mocked_sorting_by_amount.return_value = [{'result': 'sorted_results'}]
        self.mocked_prepare_results_stage.return_value = {'result': 'prepared_result_stage'}

    def tearDown(self):
        super(TestAddBid, self).tearDown()
        self.patch_sorting_by_amount.stop()
        self.patch_prepare_results_stage.stop()
        self.patch_end_bid_stage.stop()

    def test_add_bid_not_in_results(self):
        auction_document = {'stages': [{}], 'results': []}
        self.mocked_update_auction_document.return_value.__enter__.return_value = auction_document

        result = self.bids_handler.add_bid(0, self.test_bid)

        self.assertEqual(result, True)

        self.mocked_update_auction_document.assert_called_once_with(
            self.bids_handler.context, self.bids_handler.database
        )
        self.mocked_prepare_results_stage.assert_called_once_with(**self.bid_with_name)
        self.mocked_sorting_by_amount.assert_called_once_with([self.mocked_prepare_results_stage.return_value])
        self.mocked_end_bid_stage.assert_called_once_with(self.bid_with_name)

        self.assertEqual(auction_document['results'], self.mocked_sorting_by_amount.return_value)
        self.assertEqual(auction_document['stages'][0], self.mocked_prepare_results_stage.return_value)

    def test_add_bid_already_in_results(self):
        auction_document = {'stages': [{}], 'results': [{'bidder_id': 'test_bidder_id'}]}
        self.mocked_update_auction_document.return_value.__enter__.return_value = auction_document

        result = self.bids_handler.add_bid(0, self.test_bid)

        self.assertEqual(result, True)

        self.mocked_update_auction_document.assert_called_once_with(
            self.bids_handler.context, self.bids_handler.database
        )
        self.mocked_prepare_results_stage.assert_called_once_with(**self.bid_with_name)
        self.mocked_sorting_by_amount.assert_called_once_with([self.mocked_prepare_results_stage.return_value])
        self.mocked_end_bid_stage.assert_called_once_with(self.bid_with_name)

        self.assertEqual(auction_document['results'], self.mocked_sorting_by_amount.return_value)
        self.assertEqual(auction_document['stages'][0], self.mocked_prepare_results_stage.return_value)

    def test_add_bid_error(self):
        exc = Exception('Something went wrong :(')
        self.mocked_prepare_results_stage.side_effect = exc

        result = self.bids_handler.add_bid(0, self.test_bid)

        self.assertEqual(result, exc)
        self.mocked_update_auction_document.assert_called_once_with(
            self.bids_handler.context, self.bids_handler.database
        )
        self.mocked_prepare_results_stage.assert_called_once_with(**self.bid_with_name)
        self.assertEqual(self.mocked_sorting_by_amount.call_count, 0)
        self.assertEqual(self.mocked_end_bid_stage.call_count, 0)


class TestEndBidStage(TestBidsHandler):

    def setUp(self):
        super(TestEndBidStage, self).setUp()
        self.bids_handler.context['auction_protocol'] = {}
        self.patch_generate_request_id = mock.patch('openprocurement.auction.texas.bids.generate_request_id')
        self.mocked_generate_request_id = self.patch_generate_request_id.start()

        self.deadline = datetime.now().replace(hour=DEADLINE_HOUR)
        self.bids_handler.context['deadline'] = self.deadline

        self.patch_scheduler = mock.patch('openprocurement.auction.texas.bids.SCHEDULER')
        self.mocked_scheduler = self.patch_scheduler.start()

        self.patch_approve_auction_protocol_info_on_bids_stage = mock.patch(
            'openprocurement.auction.texas.bids.approve_auction_protocol_info_on_bids_stage'
        )
        self.mocked_approve_auction_protocol_info_on_bids_stage = \
            self.patch_approve_auction_protocol_info_on_bids_stage.start()
        self.mocked_approve_auction_protocol_info_on_bids_stage.return_value = {'auction': 'protocol'}

        self.patch_prepare_auction_stages = mock.patch(
            'openprocurement.auction.texas.bids.utils.prepare_auction_stages'
        )
        self.mocked_prepare_auction_stages = self.patch_prepare_auction_stages.start()

        self.patch_get_round_ending_time = mock.patch('openprocurement.auction.texas.bids.get_round_ending_time')
        self.mocked_get_round_ending_time = self.patch_get_round_ending_time.start()
        self.round_ending_time_result = 'round_end_date'
        self.mocked_get_round_ending_time.return_value = self.round_ending_time_result

        self.patch_round_duration = mock.patch('openprocurement.auction.texas.bids.ROUND_DURATION')
        self.mocked_round_duration = self.patch_round_duration.start()

        self.patch_convert_datetime = mock.patch('openprocurement.auction.texas.bids.utils.convert_datetime')
        self.mocked_convert_datetime = self.patch_convert_datetime.start()
        self.convert_datetime_results = ['converted_bid_time', 'converted_round_start_time']
        self.mocked_convert_datetime.side_effect = self.convert_datetime_results

    def tearDown(self):
        super(TestEndBidStage, self).tearDown()
        self.patch_generate_request_id.stop()
        self.patch_scheduler.stop()
        self.patch_prepare_auction_stages.stop()
        self.patch_convert_datetime.stop()
        self.patch_get_round_ending_time.stop()
        self.patch_round_duration.stop()
        self.patch_approve_auction_protocol_info_on_bids_stage.stop()

    def test_end_bid_stage_no_main_round(self):
        auction_document = {'stages': [], 'results': [], 'minimalStep': 30, 'current_stage': 0}
        expected_bid_document = {
            'value': {'amount': self.bid_with_name['amount']},
            'minimalStep': auction_document['minimalStep']
        }

        self.mocked_update_auction_document.return_value.__enter__.return_value = auction_document
        self.bids_handler.context['auction_document'] = auction_document
        self.mocked_prepare_auction_stages.return_value = ('pause', {})

        result = self.bids_handler.end_bid_stage(self.bid_with_name)

        self.assertEqual(result, None)
        self.assertEqual(auction_document['stages'], ['pause'])

        self.mocked_generate_request_id.assert_called_once()
        self.mocked_scheduler.remove_all_jobs.assert_called_once()
        self.mocked_approve_auction_protocol_info_on_bids_stage.assert_called_once_with(
            self.bids_handler.context['auction_document'], {}
        )
        self.assertEqual(
            self.bids_handler.context['auction_protocol'],
            self.mocked_approve_auction_protocol_info_on_bids_stage.return_value
        )
        self.mocked_update_auction_document.assert_called_once_with(
            self.bids_handler.context, self.bids_handler.database
        )

        self.mocked_convert_datetime.assert_called_once_with(self.bid_with_name['time'])
        self.mocked_prepare_auction_stages.assert_called_once_with(
            self.convert_datetime_results[0], expected_bid_document, self.deadline, fast_forward=False
        )

        self.bids_handler.job_service.add_ending_main_round_job.assert_called_once_with(self.deadline)

        self.assertEqual(self.bids_handler.job_service.add_pause_job.call_count, 0)
        self.assertEqual(self.mocked_get_round_ending_time.call_count, 0)

    def test_end_bid_stage_with_main_round(self):
        auction_document = {'stages': [], 'results': [], 'minimalStep': 30, 'current_stage': 0}
        expected_bid_document = {
            'value': {'amount': self.bid_with_name['amount']},
            'minimalStep': auction_document['minimalStep']
        }

        self.mocked_update_auction_document.return_value.__enter__.return_value = auction_document
        self.bids_handler.context['auction_document'] = auction_document
        prepare_auction_stages_result = ['pause', {'start': 'test'}]
        self.mocked_prepare_auction_stages.return_value = prepare_auction_stages_result

        result = self.bids_handler.end_bid_stage(self.bid_with_name)

        self.assertEqual(result, None)
        self.assertEqual(auction_document['stages'], prepare_auction_stages_result)

        self.mocked_generate_request_id.assert_called_once()
        self.mocked_scheduler.remove_all_jobs.assert_called_once()
        self.mocked_approve_auction_protocol_info_on_bids_stage.assert_called_once_with(
            self.bids_handler.context['auction_document'], {}
        )
        self.assertEqual(
            self.bids_handler.context['auction_protocol'],
            self.mocked_approve_auction_protocol_info_on_bids_stage.return_value
        )
        self.mocked_update_auction_document.assert_called_once_with(
            self.bids_handler.context, self.bids_handler.database
        )
        self.mocked_convert_datetime.assert_any_call(self.bid_with_name['time'])
        self.mocked_prepare_auction_stages.assert_called_once_with(
            self.convert_datetime_results[0], expected_bid_document, self.deadline, fast_forward=False
        )

        self.mocked_convert_datetime.assert_any_call(prepare_auction_stages_result[1]['start'])

        self.bids_handler.job_service.add_ending_main_round_job.assert_called_once_with(self.round_ending_time_result)
        self.bids_handler.job_service.add_pause_job.assert_called_once_with(self.convert_datetime_results[1])

        self.mocked_get_round_ending_time.assert_called_once_with(
            self.convert_datetime_results[1], self.mocked_round_duration, self.deadline
        )


def suite():
    tests = unittest.TestSuite()
    tests.addTest(unittest.makeSuite(TestAddBid))
    tests.addTest(unittest.makeSuite(TestEndBidStage))
    return tests
