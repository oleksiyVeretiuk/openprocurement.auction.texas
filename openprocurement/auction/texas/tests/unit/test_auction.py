import unittest
import mock

from copy import deepcopy
from datetime import datetime, timedelta

from openprocurement.auction.texas.auction import Auction
from openprocurement.auction.worker_core.constants import TIMEZONE
from openprocurement.auction.texas.constants import (
    MULTILINGUAL_FIELDS,
    ADDITIONAL_LANGUAGES,
    DEADLINE_HOUR,
    ROUND_DURATION,
    DEFAULT_AUCTION_TYPE,
    SANDBOX_AUCTION_DURATION
)


class MutableMagicMock(mock.MagicMock):
    def _mock_call(_mock_self, *args, **kwargs):
        return super(MutableMagicMock, _mock_self)._mock_call(*deepcopy(args), **deepcopy(kwargs))


class AuctionInitSetup(unittest.TestCase):

    def setUp(self):
        self.tender_id = '1' * 32

        patch_get_gsm = mock.patch(
            'openprocurement.auction.texas.auction.getGlobalSiteManager'
        )

        mock_get_gsm = patch_get_gsm.start()
        mock_gsm = mock.MagicMock()
        mock_get_gsm.return_value = mock_gsm

        self.auction = Auction(self.tender_id)
        patch_get_gsm.stop()

        self.mock_db = mock.MagicMock()
        self.mock_datasource = mock.MagicMock()
        self.mock_job_service = mock.MagicMock()
        self.mock_end_auction_event = mock.MagicMock()
        self.mock_context = {
            '_end_auction_event': self.mock_end_auction_event,
            'auction_doc_id': self.tender_id,
            'deadline': 'deadline',
            'worker_defaults': {
                'deadline': {
                    'deadline_time': {'hour': DEADLINE_HOUR}
                }
            }
        }

        self.auction.database = self.mock_db
        self.auction.datasource = self.mock_datasource
        self.auction.context = self.mock_context
        self.auction.job_service = self.mock_job_service
        self.auction._end_auction_event = self.mock_end_auction_event

        self.patch_utils = mock.patch(
            'openprocurement.auction.texas.auction.utils',
        )
        self.mocked_utils = self.patch_utils.start()

        self.patch_logger = mock.patch(
            'openprocurement.auction.texas.auction.LOGGER'
        )
        self.mocked_logger = self.patch_logger.start()

    def tearDown(self):
        self.patch_utils.stop()
        self.patch_logger.stop()


class TestScheduleAuction(AuctionInitSetup):

    def setUp(self):
        super(TestScheduleAuction, self).setUp()
        self.auction.start_auction = mock.MagicMock()
        self.auction.startDate = 'startDate'

        self.patch_scheduler = mock.patch(
            'openprocurement.auction.texas.auction.SCHEDULER'
        )
        self.mocked_scheduler = self.patch_scheduler.start()

        self.patch_run_server = mock.patch(
            'openprocurement.auction.texas.auction.run_server'
        )
        self.mocked_run_server = self.patch_run_server.start()
        self.mocked_run_server.return_value = 'server'

        self.patch_synchronize_auction_info = mock.patch.object(
            self.auction, 'synchronize_auction_info'
        )
        self.mocked_synchronize_auction_info = self.patch_synchronize_auction_info.start()

        self.auction.bids_mapping = {'bids': 'mapping'}
        self.auction._auction_data = {'auction': 'data'}
        self.auction.bidders_data = {'bidders': 'data'}

    def tearDown(self):
        super(TestScheduleAuction, self).tearDown()
        self.patch_scheduler.stop()
        self.patch_run_server.stop()
        self.patch_synchronize_auction_info.stop()

    def test_auction_schedule(self):
        auction_document = {
            'stages': [
                {
                    'start': datetime.now().isoformat()
                },
                {
                    'start': datetime.now().isoformat()
                }
            ],
        }
        self.mock_db.get_auction_document.return_value = auction_document
        self.mocked_utils.update_auction_document.return_value.__enter__.return_value = auction_document

        convert_datetime_results = [
            datetime.now(),
            datetime.now(),
            datetime.now(),
        ]
        self.mocked_utils.convert_datetime.side_effect = iter(convert_datetime_results)
        auction_protocol = {'auction': 'protocol'}
        self.mocked_utils.prepare_auction_protocol.return_value = auction_protocol

        self.auction.schedule_auction()

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.auction.context['auction_doc_id'])

        self.assertEqual(self.mocked_utils.update_auction_document.call_count, 1)
        self.mocked_utils.update_auction_document.assert_called_with(self.auction.context, self.auction.database)

        self.assertEqual(self.auction.context['auction_document'], auction_document)
        self.assertEqual(self.auction.context['auction_data'], self.auction._auction_data)
        self.assertEqual(self.auction.context['bidders_data'], self.auction.bidders_data)
        self.assertEqual(self.auction.context['bids_mapping'], self.auction.bids_mapping)
        self.assertEqual(self.auction.context['auction_protocol'], auction_protocol)

        self.assertEqual(self.mocked_scheduler.add_job.call_count, 1)
        self.mocked_scheduler.add_job.assert_called_with(
            self.auction.start_auction,
            'date',
            run_date=convert_datetime_results[0],
            name='Start of Auction',
            id='auction:start'
        )

        self.assertEqual(self.auction.job_service.add_pause_job.call_count, 1)
        self.auction.job_service.add_pause_job.assert_called_with(convert_datetime_results[1])

        self.assertEqual(self.auction.job_service.add_ending_main_round_job.call_count, 1)
        self.auction.job_service.add_ending_main_round_job.assert_called_with(
            convert_datetime_results[2] + timedelta(seconds=ROUND_DURATION)
        )
        self.mocked_utils.convert_datetime.assert_called_with(
            auction_document['stages'][1]['start']
        )

        self.assertEqual(self.mocked_run_server.call_count, 1)
        self.mocked_run_server.assert_called_with(self.auction, None, self.mocked_logger)

        self.assertEqual(self.auction.context['server'], 'server')


class TestCancelAuction(AuctionInitSetup):

    def setUp(self):
        super(TestCancelAuction, self).setUp()
        self.patch_datetime = mock.patch('openprocurement.auction.texas.auction.datetime')

        self.mock_datetime = self.patch_datetime.start()
        self.mock_now = mock.MagicMock()

        self.isoformat_mock = mock.MagicMock()
        self.isormat_date = 'isoformat_date'
        self.isoformat_mock.isoformat.return_value = self.isormat_date
        self.mock_now.return_value = self.isoformat_mock

        self.mock_datetime.now = self.mock_now

    def tearDown(self):
        super(TestCancelAuction, self).tearDown()
        self.patch_datetime.stop()

    def test_cancellation_if_auction_doc_exist(self):
        auction_document = {
            'current_stage': 1
        }
        self.mock_db.get_auction_document.return_value = auction_document
        self.mocked_utils.update_auction_document.return_value.__enter__.return_value = auction_document

        self.auction.cancel_auction()

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.auction.context['auction_doc_id'])

        self.assertEqual(self.mocked_utils.update_auction_document.call_count, 1)
        self.mocked_utils.update_auction_document.assert_called_with(self.auction.context, self.auction.database)

        self.assertEqual(self.mock_datetime.now.call_count, 1)
        self.mock_datetime.now.assert_called_with(TIMEZONE)

        self.assertEqual(auction_document['current_stage'], -100)
        self.assertEqual(auction_document['endDate'], self.isormat_date)

    def test_cancellation_if_auction_doc_not_exist(self):
        self.mock_db.get_auction_document.return_value = None

        self.auction.cancel_auction()

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.auction.context['auction_doc_id'])

        self.assertEqual(self.mocked_utils.update_auction_document.call_count, 0)

        self.assertEqual(self.mock_datetime.now.call_count, 0)


class TestRescheduleAuction(AuctionInitSetup):

    def test_reschedule_if_auction_doc_exist(self):
        auction_document = {
            'current_stage': 1
        }
        self.mock_db.get_auction_document.return_value = auction_document
        self.mocked_utils.update_auction_document.return_value.__enter__.return_value = auction_document

        self.auction.reschedule_auction()

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.auction.context['auction_doc_id'])

        self.assertEqual(self.mocked_utils.update_auction_document.call_count, 1)
        self.mocked_utils.update_auction_document.assert_called_with(self.auction.context, self.auction.database)

        self.assertEqual(auction_document['current_stage'], -101)

    def test_reschedule_if_auction_doc_not_exist(self):
        self.mock_db.get_auction_document.return_value = None

        self.auction.reschedule_auction()

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.auction.context['auction_doc_id'])

        self.assertEqual(self.mocked_utils.update_auction_document.call_count, 0)


class TestStartAuction(AuctionInitSetup):

    def setUp(self):
        super(TestStartAuction, self).setUp()

        self.patch_synchronize_auction_info = mock.patch.object(
            self.auction, 'synchronize_auction_info'
        )
        self.mocked_synchronize_auction_info = self.patch_synchronize_auction_info.start()

        self.patch_prepare_initial_bids = mock.patch.object(
            self.auction, '_prepare_initial_bids'
        )
        self.mocked_prepare_initial_bids = self.patch_prepare_initial_bids.start()

        self.auction.auction_protocol = {
            'timeline': {
                'auction_start': {
                    'time': ''
                }
            }
        }

        self.patch_datetime = mock.patch('openprocurement.auction.texas.auction.datetime')

        self.mock_datetime = self.patch_datetime.start()

        self.mock_now = mock.MagicMock()
        self.isoformat_mock = mock.MagicMock()
        self.isormat_date = 'isoformat_date'
        self.isoformat_mock.isoformat.return_value = self.isormat_date
        self.mock_now.return_value = self.isoformat_mock

        self.mock_datetime.now = self.mock_now

        self.auction.context['server_actions'] = 'server_actions'

    def tearDown(self):
        super(TestStartAuction, self).tearDown()
        self.patch_prepare_initial_bids.stop()
        self.patch_synchronize_auction_info.stop()

    def test_start_auction(self):
        auction_document = {
            'current_stage': -1
        }
        self.mock_db.get_auction_document.return_value = auction_document
        self.mocked_utils.update_auction_document.return_value.__enter__.return_value = auction_document

        self.auction.start_auction()

        self.assertEqual(auction_document['current_stage'], 0)

        self.assertEqual(self.mocked_utils.lock_server.call_count, 1)
        self.mocked_utils.lock_server.assert_called_with(self.auction.context['server_actions'])

        self.assertEqual(self.mocked_utils.update_auction_document.call_count, 1)
        self.mocked_utils.update_auction_document.assert_called_with(self.auction.context, self.auction.database)


class TestPostAnnounce(AuctionInitSetup):

    def test_post_announce(self):
        auction_document = {
            'current_stage': 1
        }
        self.mock_db.get_auction_document.return_value = auction_document

        auction_from_ds = {'auction': 'from_datasource'}
        self.mock_datasource.get_data.return_value = auction_from_ds

        self.mocked_utils.update_auction_document.return_value.__enter__.return_value = auction_document

        bids_info = 'bids info'
        self.mocked_utils.get_bids.return_value = bids_info

        self.auction.post_announce()

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.auction.context['auction_doc_id'])

        self.assertEqual(self.mocked_utils.get_bids.call_count, 1)
        self.mocked_utils.get_bids.assert_called_with(auction_from_ds)

        self.assertEqual(self.mock_datasource.get_data.call_count, 1)
        self.mock_datasource.get_data.assert_called_with(with_credentials=True)

        self.assertEqual(self.mocked_utils.update_auction_document.call_count, 1)
        self.mocked_utils.update_auction_document.assert_called_with(self.auction.context, self.auction.database)

        self.assertEqual(self.mocked_utils.open_bidders_name.call_count, 1)
        self.mocked_utils.open_bidders_name.assert_called_with(auction_document, bids_info)


class TestPrepareAuctionDocument(AuctionInitSetup):

    def setUp(self):
        super(TestPrepareAuctionDocument, self).setUp()

        self.start_date = 'startDate'
        self.auction.startDate = self.start_date
        self.auction.worker_defaults['sandbox_mode'] = False
        self.auction.debug = False

        self.auction_data = {'auction': 'data'}
        self.auction._auction_data = self.auction_data

        self.patch_synchronize_auction_info = mock.patch.object(
            self.auction, 'synchronize_auction_info'
        )
        self.mocked_synchronize_auction_info = self.patch_synchronize_auction_info.start()

        self.mocked_prepare_auction_document_data = MutableMagicMock()
        self.auction._prepare_auction_document_data = self.mocked_prepare_auction_document_data

        self.patch_reschedule = mock.patch.object(
            self.auction, 'reschedule_auction'
        )
        self.mocked_reschedule = self.patch_reschedule.start()

        self.prepared_stages = ['pause', 'main']
        self.mocked_utils.prepare_auction_stages.return_value = self.prepared_stages

    def tearDown(self):
        super(TestPrepareAuctionDocument, self).tearDown()
        self.patch_synchronize_auction_info.stop()
        self.patch_reschedule.stop()

    def test_if_public_document(self):
        public_document = {
            '_rev': '111'
        }
        self.mock_db.get_auction_document.return_value = public_document

        auction_document = deepcopy(public_document)
        self.auction.prepare_auction_document()

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.mock_context['auction_doc_id'])

        self.assertEqual(self.mocked_synchronize_auction_info.call_count, 1)
        self.mocked_synchronize_auction_info.assert_called_with(prepare=True)

        self.assertEqual(self.mocked_prepare_auction_document_data.call_count, 1)
        self.mocked_prepare_auction_document_data.assert_called_with(auction_document)

        self.assertEqual(self.mocked_utils.prepare_auction_stages.call_count, 1)
        self.mocked_utils.prepare_auction_stages.assert_called_with(self.start_date, auction_document, self.mock_context['deadline'])

        self.assertEqual(self.mocked_utils.set_absolute_deadline.call_count, 1)
        self.mocked_utils.set_absolute_deadline.assert_called_with(self.mock_context, self.start_date)

        self.assertEqual(self.mocked_utils.set_relative_deadline.call_count, 0)

        auction_document['stages'] = self.prepared_stages
        self.assertEqual(self.mock_db.save_auction_document.call_count, 1)
        self.mock_db.save_auction_document.assert_called_with(
            auction_document,
            self.mock_context['auction_doc_id']
        )

        self.assertEqual(self.mock_datasource.set_participation_urls.call_count, 1)
        self.mock_datasource.set_participation_urls.assert_called_with(
            self.auction_data
        )

        self.assertEqual(self.mocked_reschedule.call_count, 0)

    def test_if_no_public_document(self):
        public_document = {}
        self.mock_db.get_auction_document.return_value = public_document

        auction_document = {}

        self.auction.prepare_auction_document()

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.mock_context['auction_doc_id'])

        self.assertEqual(self.mocked_synchronize_auction_info.call_count, 1)
        self.mocked_synchronize_auction_info.assert_called_with(prepare=True)

        self.assertEqual(self.mocked_prepare_auction_document_data.call_count, 1)
        self.mocked_prepare_auction_document_data.assert_called_with(auction_document)

        self.assertEqual(self.mocked_utils.prepare_auction_stages.call_count, 1)
        self.mocked_utils.prepare_auction_stages.assert_called_with(self.start_date, auction_document, self.mock_context['deadline'])

        self.assertEqual(self.mocked_utils.set_absolute_deadline.call_count, 1)
        self.mocked_utils.set_absolute_deadline.assert_called_with(self.mock_context, self.start_date)

        self.assertEqual(self.mocked_utils.set_relative_deadline.call_count, 0)

        auction_document['stages'] = self.prepared_stages
        self.assertEqual(self.mock_db.save_auction_document.call_count, 1)
        self.mock_db.save_auction_document.assert_called_with(
            auction_document,
            self.mock_context['auction_doc_id']
        )

        self.assertEqual(self.mock_datasource.set_participation_urls.call_count, 1)
        self.mock_datasource.set_participation_urls.assert_called_with(
            self.auction_data
        )

        self.assertEqual(self.mocked_reschedule.call_count, 0)

    def test_if_debug(self):
        self.auction.debug = True

        public_document = {
            '_rev': '111'
        }
        self.mock_db.get_auction_document.return_value = public_document

        auction_document = deepcopy(public_document)
        auction_document['mode'] = 'test'
        auction_document['test_auction_data'] = self.auction_data

        self.auction.prepare_auction_document()

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.mock_context['auction_doc_id'])

        self.assertEqual(self.mocked_synchronize_auction_info.call_count, 1)
        self.mocked_synchronize_auction_info.assert_called_with(prepare=True)

        self.assertEqual(self.mocked_prepare_auction_document_data.call_count, 1)
        self.mocked_prepare_auction_document_data.assert_called_with(auction_document)

        self.assertEqual(self.mocked_utils.prepare_auction_stages.call_count, 1)
        self.mocked_utils.prepare_auction_stages.assert_called_with(self.start_date, auction_document, self.mock_context['deadline'])

        self.assertEqual(self.mocked_utils.set_absolute_deadline.call_count, 1)
        self.mocked_utils.set_absolute_deadline.assert_called_with(self.mock_context, self.start_date)

        self.assertEqual(self.mocked_utils.set_relative_deadline.call_count, 0)

        auction_document['stages'] = self.prepared_stages
        self.assertEqual(self.mock_db.save_auction_document.call_count, 1)
        self.mock_db.save_auction_document.assert_called_with(
            auction_document,
            self.mock_context['auction_doc_id']
        )

        self.assertEqual(self.mock_datasource.set_participation_urls.call_count, 1)
        self.mock_datasource.set_participation_urls.assert_called_with(
            self.auction_data
        )

        self.assertEqual(self.mocked_reschedule.call_count, 0)

    def test_if_no_debug(self):
        self.auction.debug = False

        public_document = {
            '_rev': '111'
        }
        self.mock_db.get_auction_document.return_value = public_document

        auction_document = deepcopy(public_document)

        self.auction.prepare_auction_document()

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.mock_context['auction_doc_id'])

        self.assertEqual(self.mocked_synchronize_auction_info.call_count, 1)
        self.mocked_synchronize_auction_info.assert_called_with(prepare=True)

        self.assertEqual(self.mocked_prepare_auction_document_data.call_count, 1)
        self.mocked_prepare_auction_document_data.assert_called_with(auction_document)

        self.assertEqual(self.mocked_utils.prepare_auction_stages.call_count, 1)
        self.mocked_utils.prepare_auction_stages.assert_called_with(self.start_date, auction_document, self.mock_context['deadline'])

        self.assertEqual(self.mocked_utils.set_absolute_deadline.call_count, 1)
        self.mocked_utils.set_absolute_deadline.assert_called_with(self.mock_context, self.start_date)

        self.assertEqual(self.mocked_utils.set_relative_deadline.call_count, 0)

        auction_document['stages'] = self.prepared_stages
        self.assertEqual(self.mock_db.save_auction_document.call_count, 1)
        self.mock_db.save_auction_document.assert_called_with(
            auction_document,
            self.mock_context['auction_doc_id']
        )

        self.assertEqual(self.mock_datasource.set_participation_urls.call_count, 1)
        self.mock_datasource.set_participation_urls.assert_called_with(
            self.auction_data
        )

        self.assertEqual(self.mocked_reschedule.call_count, 0)

    def test_if_sandbox(self):
        self.auction.worker_defaults['sandbox_mode'] = True

        public_document = {
            '_rev': '111'
        }
        self.mock_db.get_auction_document.return_value = public_document

        auction_document = deepcopy(public_document)

        self.auction.prepare_auction_document()

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.mock_context['auction_doc_id'])

        self.assertEqual(self.mocked_synchronize_auction_info.call_count, 1)
        self.mocked_synchronize_auction_info.assert_called_with(prepare=True)

        self.assertEqual(self.mocked_prepare_auction_document_data.call_count, 1)
        self.mocked_prepare_auction_document_data.assert_called_with(auction_document)

        self.assertEqual(self.mocked_utils.prepare_auction_stages.call_count, 1)
        self.mocked_utils.prepare_auction_stages.assert_called_with(
            self.start_date,
            auction_document,
            self.mock_context['deadline'],
            fast_forward=True
        )

        self.assertEqual(self.mocked_utils.set_absolute_deadline.call_count, 1)
        self.mocked_utils.set_absolute_deadline.assert_called_with(self.mock_context, self.start_date)

        self.assertEqual(self.mocked_utils.set_relative_deadline.call_count, 0)

        auction_document['stages'] = self.prepared_stages
        self.assertEqual(self.mock_db.save_auction_document.call_count, 1)
        self.mock_db.save_auction_document.assert_called_with(
            auction_document,
            self.mock_context['auction_doc_id']
        )

        self.assertEqual(self.mock_datasource.set_participation_urls.call_count, 1)
        self.mock_datasource.set_participation_urls.assert_called_with(
            self.auction_data
        )

        self.assertEqual(self.mocked_reschedule.call_count, 0)

    def test_if_no_sandbox(self):
        self.auction.worker_defaults['sandbox_mode'] = False

        public_document = {
            '_rev': '111'
        }
        self.mock_db.get_auction_document.return_value = public_document

        auction_document = deepcopy(public_document)

        self.auction.prepare_auction_document()

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.mock_context['auction_doc_id'])

        self.assertEqual(self.mocked_synchronize_auction_info.call_count, 1)
        self.mocked_synchronize_auction_info.assert_called_with(prepare=True)

        self.assertEqual(self.mocked_prepare_auction_document_data.call_count, 1)
        self.mocked_prepare_auction_document_data.assert_called_with(auction_document)

        self.assertEqual(self.mocked_utils.prepare_auction_stages.call_count, 1)
        self.mocked_utils.prepare_auction_stages.assert_called_with(self.start_date, auction_document, self.mock_context['deadline'])

        self.assertEqual(self.mocked_utils.set_absolute_deadline.call_count, 1)
        self.mocked_utils.set_absolute_deadline.assert_called_with(self.mock_context, self.start_date)

        self.assertEqual(self.mocked_utils.set_relative_deadline.call_count, 0)

        auction_document['stages'] = self.prepared_stages
        self.assertEqual(self.mock_db.save_auction_document.call_count, 1)
        self.mock_db.save_auction_document.assert_called_with(
            auction_document,
            self.mock_context['auction_doc_id']
        )

        self.assertEqual(self.mock_datasource.set_participation_urls.call_count, 1)
        self.mock_datasource.set_participation_urls.assert_called_with(
            self.auction_data
        )

        self.assertEqual(self.mocked_reschedule.call_count, 0)

    def test_if_main_round(self):
        self.mocked_utils.prepare_auction_stages.return_value = self.prepared_stages

        public_document = {
            '_rev': '111'
        }
        self.mock_db.get_auction_document.return_value = public_document

        auction_document = deepcopy(public_document)

        self.auction.prepare_auction_document()

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.mock_context['auction_doc_id'])

        self.assertEqual(self.mocked_synchronize_auction_info.call_count, 1)
        self.mocked_synchronize_auction_info.assert_called_with(prepare=True)

        self.assertEqual(self.mocked_prepare_auction_document_data.call_count, 1)
        self.mocked_prepare_auction_document_data.assert_called_with(auction_document)

        self.assertEqual(self.mocked_utils.prepare_auction_stages.call_count, 1)
        self.mocked_utils.prepare_auction_stages.assert_called_with(self.start_date, auction_document, self.mock_context['deadline'])

        self.assertEqual(self.mocked_utils.set_absolute_deadline.call_count, 1)
        self.mocked_utils.set_absolute_deadline.assert_called_with(self.mock_context, self.start_date)

        self.assertEqual(self.mocked_utils.set_relative_deadline.call_count, 0)

        auction_document['stages'] = self.prepared_stages
        self.assertEqual(self.mock_db.save_auction_document.call_count, 1)
        self.mock_db.save_auction_document.assert_called_with(
            auction_document,
            self.mock_context['auction_doc_id']
        )

        self.assertEqual(self.mock_datasource.set_participation_urls.call_count, 1)
        self.mock_datasource.set_participation_urls.assert_called_with(
            self.auction_data
        )

        self.assertEqual(self.mocked_reschedule.call_count, 0)

    def test_if_no_main_round(self):
        prepared_stages = [self.prepared_stages[0], {}]
        self.mocked_utils.prepare_auction_stages.return_value = prepared_stages

        public_document = {
            '_rev': '111'
        }
        self.mock_db.get_auction_document.return_value = public_document

        auction_document = deepcopy(public_document)

        self.auction.prepare_auction_document()

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.mock_context['auction_doc_id'])

        self.assertEqual(self.mocked_synchronize_auction_info.call_count, 1)
        self.mocked_synchronize_auction_info.assert_called_with(prepare=True)

        self.assertEqual(self.mocked_prepare_auction_document_data.call_count, 1)
        self.mocked_prepare_auction_document_data.assert_called_with(auction_document)

        self.assertEqual(self.mocked_utils.prepare_auction_stages.call_count, 1)
        self.mocked_utils.prepare_auction_stages.assert_called_with(self.start_date, auction_document, self.mock_context['deadline'])

        self.assertEqual(self.mocked_utils.set_absolute_deadline.call_count, 1)
        self.mocked_utils.set_absolute_deadline.assert_called_with(self.mock_context, self.start_date)

        self.assertEqual(self.mocked_utils.set_relative_deadline.call_count, 0)

        auction_document['stages'] = prepared_stages
        self.assertEqual(self.mock_db.save_auction_document.call_count, 1)
        self.mock_db.save_auction_document.assert_called_with(
            auction_document,
            self.mock_context['auction_doc_id']
        )

        self.assertEqual(self.mock_datasource.set_participation_urls.call_count, 0)

        self.assertEqual(self.mocked_reschedule.call_count, 1)

    def test_if_mod_test_and_smd(self):
        self.auction.worker_defaults['sandbox_mode'] = True

        public_document = {
            '_rev': '111'
        }
        self.auction._auction_data = {
            'data': {
                'mode': 'test',
                'submissionMethodDetails': 'quick',
            }
        }
        self.mock_db.get_auction_document.return_value = public_document

        auction_document = deepcopy(public_document)
        auction_document.update({'submissionMethodDetails': 'quick'})

        self.auction.prepare_auction_document()

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.mock_context['auction_doc_id'])

        self.assertEqual(self.mocked_synchronize_auction_info.call_count, 1)
        self.mocked_synchronize_auction_info.assert_called_with(prepare=True)

        self.assertEqual(self.mocked_prepare_auction_document_data.call_count, 1)
        self.mocked_prepare_auction_document_data.assert_called_with(auction_document)

        self.assertEqual(self.mocked_utils.prepare_auction_stages.call_count, 1)
        self.mocked_utils.prepare_auction_stages.assert_called_with(
            self.start_date,
            auction_document,
            self.mock_context['deadline'],
            fast_forward=True
        )

        self.assertEqual(self.mocked_utils.set_absolute_deadline.call_count, 0)

        self.assertEqual(self.mocked_utils.set_relative_deadline.call_count, 1)
        self.mocked_utils.set_relative_deadline.assert_called_with(
            self.mock_context, self.start_date, SANDBOX_AUCTION_DURATION
        )

        auction_document['stages'] = self.prepared_stages
        self.assertEqual(self.mock_db.save_auction_document.call_count, 1)
        self.mock_db.save_auction_document.assert_called_with(
            auction_document,
            self.mock_context['auction_doc_id']
        )

        self.assertEqual(self.mock_datasource.set_participation_urls.call_count, 1)
        self.mock_datasource.set_participation_urls.assert_called_with(
            self.auction._auction_data
        )

        self.assertEqual(self.mocked_reschedule.call_count, 0)


class TestPrepareInitialBids(AuctionInitSetup):

    def setUp(self):
        super(TestPrepareInitialBids, self).setUp()

        self.start_date = 'startDate'
        self.auction.startDate = self.start_date
        self.bids_mapping = {
            'id_1': 'bid_1',
            'id_2': 'bid_2'
        }
        self.auction.bids_mapping = deepcopy(self.bids_mapping)

        self.auction.auction_protocol = {
            'timeline': {
                'auction_start': {
                    'initial_bids': []
                }
            }
        }

        self.patch_sorting_start_bids_by_amount = mock.patch(
            'openprocurement.auction.texas.auction.sorting_start_bids_by_amount'
        )
        self.resulted_stages = ['1_stage', '2_stage']
        self.mocked_utils.prepare_results_stage.side_effect = self.resulted_stages

    def tearDown(self):
        super(TestPrepareInitialBids, self).tearDown()
        self.patch_sorting_start_bids_by_amount.stop()

    def test_prepare_initial_bids(self):
        auction_document = {
            'value': {'amount': 10000},
            'initial_bids': []
        }

        bidders_data = [
            {
                'id': 'id_1',
                'date': 'date_1',
                'value': {'amount': 1000},
                'owner': 'owner_1',
                'bidNumber': 1,
            },
            {
                'id': 'id_2',
                'date': 'date_2',
                'value': {'amount': 2000},
                'owner': 'owner_2',
                'bidNumber': 2
            }
        ]
        self.auction.bidders_data = deepcopy(bidders_data)

        self.mocked_sorting_start_bids_by_amount = self.patch_sorting_start_bids_by_amount.start()
        self.mocked_sorting_start_bids_by_amount.return_value = deepcopy(bidders_data)

        auction_protocol = {
            'timeline': {
                'auction_start': {
                    'initial_bids': [
                        {
                            'bidder': bidders_data[0]['id'],
                            'date': bidders_data[0]['date'],
                            'amount': auction_document['value']['amount'],
                            'bid_number': self.bids_mapping[bidders_data[0]['id']]
                        },
                        {
                            'bidder': bidders_data[1]['id'],
                            'date': bidders_data[1]['date'],
                            'amount': auction_document['value']['amount'],
                            'bid_number': self.bids_mapping[bidders_data[1]['id']]
                        }
                    ]
                }
            }
        }

        self.auction._prepare_initial_bids(auction_document)

        self.assertEqual(self.mocked_sorting_start_bids_by_amount.call_count, 1)
        self.mocked_sorting_start_bids_by_amount.assert_called_with(bidders_data)

        self.assertEqual(self.mocked_utils.prepare_results_stage.call_count, 2)
        self.mocked_utils.prepare_results_stage.assert_called_with(
            bidder_id=bidders_data[1]['id'],
            time=bidders_data[1]['date'],
            bidder_name=self.bids_mapping[bidders_data[1]['id']],
            amount=auction_document['value']['amount']
        )

        self.assertEqual(auction_document['initial_bids'], self.resulted_stages)
        self.assertEqual(self.mock_context['auction_protocol'], auction_protocol)

    # def test_prepare_initial_bids_without_date(self):
    #     auction_document = {
    #         'value': {'amount': 10000},
    #         'initial_bids': []
    #     }
    #
    #     bidders_data = [
    #         {
    #             'id': 'id_1',
    #             'value': {'amount': 1000},
    #             'owner': 'owner_1'
    #         },
    #         {
    #             'id': 'id_2',
    #             'value': {'amount': 2000},
    #             'owner': 'owner_2'
    #         }
    #     ]
    #     self.auction.bidders_data = deepcopy(bidders_data)
    #
    #     self.mocked_sorting_start_bids_by_amount = self.patch_sorting_start_bids_by_amount.start()
    #     self.mocked_sorting_start_bids_by_amount.return_value = deepcopy(bidders_data)
    #
    #     auction_protocol = {
    #         'timeline': {
    #             'auction_start': {
    #                 'initial_bids': [
    #                     {
    #                         'bidder': bidders_data[0]['id'],
    #                         'date': self.start_date,
    #                         'amount': auction_document['value']['amount'],
    #                         'bid_number': self.bids_mapping[bidders_data[0]['id']]
    #                     },
    #                     {
    #                         'bidder': bidders_data[1]['id'],
    #                         'date': self.start_date,
    #                         'amount': auction_document['value']['amount'],
    #                         'bid_number': self.bids_mapping[bidders_data[1]['id']]
    #                     }
    #                 ]
    #             }
    #         }
    #     }
    #
    #     self.auction._prepare_initial_bids(auction_document)
    #
    #     self.assertEqual(self.mocked_sorting_start_bids_by_amount.call_count, 1)
    #     self.mocked_sorting_start_bids_by_amount.assert_called_with(bidders_data)
    #
    #     self.assertEqual(self.mocked_utils.prepare_results_stage.call_count, 2)
    #     self.mocked_utils.prepare_results_stage.assert_called_with(
    #         bidder_id=bidders_data[1]['id'],
    #         time=self.start_date,
    #         bidder_name=self.bids_mapping[bidders_data[1]['id']],
    #         amount=auction_document['value']['amount']
    #     )
    #
    #     self.assertEqual(auction_document['initial_bids'], self.resulted_stages)
    #     self.assertEqual(self.mock_context['auction_protocol'], auction_protocol)


class TestPrepareAuctionDocumentData(AuctionInitSetup):

    def setUp(self):
        super(TestPrepareAuctionDocumentData, self).setUp()

        self.auction_data = {
            'data': {
                'auctionID': 'auction-id',
                'procurementMethodType': 'landlease',
                'procuringEntity': {'some': 'entity'},
                'items': ['item1', 'item2'],
                'value': {'amount': 1000},
                'minimalStep': {'amount': 100},
                'title': 'Title',
                'description': 'Description',
                'title_en': 'Translated title'
            }
        }

        self.auction.worker_defaults['resource_api_version'] = '1'
        self.auction._auction_data = deepcopy(self.auction_data)

    def test_prepare_auction_document_data(self):
        auction_document = {}

        expected_result = {
            "_id": self.mock_context['auction_doc_id'],
            "stages": [],
            "auctionID": self.auction_data["data"].get("auctionID", ""),
            "procurementMethodType": self.auction_data["data"].get(
                "procurementMethodType", "texas"),
            "TENDERS_API_VERSION": self.auction.worker_defaults['resource_api_version'],
            "current_stage": -1,
            "results": [],
            "initial_bids": [],
            "procuringEntity": self.auction_data["data"]['procuringEntity'],
            "items": self.auction_data["data"]["items"],
            "value": self.auction_data["data"]["value"],
            "minimalStep": self.auction_data["data"]["minimalStep"],
            "initial_value": self.auction_data["data"]["value"]["amount"],
            "auction_type": DEFAULT_AUCTION_TYPE,
            "title": self.auction_data["data"]["title"],
            "title_en": self.auction_data["data"]["title_en"],
            "description": self.auction_data["data"]["description"]
        }

        self.auction._prepare_auction_document_data(auction_document)
        self.assertEqual(auction_document, expected_result)


class TestSynchronizeAuctionInfo(AuctionInitSetup):

    def setUp(self):
        super(TestSynchronizeAuctionInfo, self).setUp()

        self.patch_set_auction_data = mock.patch.object(
            self.auction, '_set_auction_data'
        )
        self.mocked_set_auction_data = self.patch_set_auction_data.start()

        self.patch_set_start_date = mock.patch.object(
            self.auction, '_set_start_date'
        )
        self.mocked_set_start_date = self.patch_set_start_date.start()

        self.patch_set_bidders_data = mock.patch.object(
            self.auction, '_set_bidders_data'
        )
        self.mocked_set_bidders_data = self.patch_set_bidders_data.start()

        self.patch_set_mapping = mock.patch.object(
            self.auction, '_set_mapping'
        )
        self.mocked_set_mapping = self.patch_set_mapping.start()

    def test_synchronize_auction_info(self):
        self.auction.synchronize_auction_info()

        self.assertEqual(self.mocked_set_auction_data.call_count, 1)
        self.mocked_set_auction_data.assert_called_with(False)

        self.assertEqual(self.mocked_set_start_date.call_count, 1)
        self.assertEqual(self.mocked_set_bidders_data.call_count, 1)
        self.assertEqual(self.mocked_set_mapping.call_count, 1)


class TestSetAuctionData(AuctionInitSetup):

    def setUp(self):
        super(TestSetAuctionData, self).setUp()

        self.patch_generate_request_id = mock.patch(
            'openprocurement.auction.texas.auction.generate_request_id'
        )
        self.mocked_generate_request_id = self.patch_generate_request_id.start()
        self.mocked_generate_request_id.return_value = 'generated_request_id'

        self.start_date = 'converted_datetime'
        self.mocked_utils.convert_datetime.return_value = self.start_date

        self.patch_sys = mock.patch(
            'openprocurement.auction.texas.auction.sys'
        )
        self.mock_sys = self.patch_sys.start()

    def tearDown(self):
        super(TestSetAuctionData, self).tearDown()
        self.patch_generate_request_id.stop()
        self.patch_sys.stop()

    def test_with_prepare(self):

        get_data = [
            {'data': {'auctionPeriod': {'startDate': 'startDate'}}},
            {'data': {'second': 'data'}}
        ]

        self.mock_datasource.get_data.side_effect = iter(get_data)
        self.mock_db.get_auction_document.return_value = {'some': 'data'}

        expected_auction_data = {}
        expected_auction_data.update(get_data[0])
        expected_auction_data['data'].update(get_data[1]['data'])

        self.auction._set_auction_data(True)

        self.assertEqual(self.mock_datasource.get_data.call_count, 2)
        self.mock_datasource.get_data.assert_called_with(public=False)

        self.assertEqual(self.auction._auction_data, expected_auction_data)
        self.assertEqual(self.auction.startDate, self.start_date)

        self.assertEqual(self.mock_end_auction_event.set.call_count, 0)

        self.assertEqual(self.mocked_utils.convert_datetime.call_count, 1)
        self.mocked_utils.convert_datetime.assert_called_with(expected_auction_data['data']['auctionPeriod']['startDate'])

        self.assertEqual(self.mock_db.get_auction_document.call_count, 0)
        self.assertEqual(self.mock_db.save_auction_document.call_count, 0)

        self.assertEqual(self.mock_sys.exit.call_count, 0)

    def test_without_prepare(self):

        get_data = [
            {'data': {'auctionPeriod': {'startDate': 'startDate'}}},
        ]

        self.mock_datasource.get_data.side_effect = iter(get_data)
        self.mock_db.get_auction_document.return_value = {'some': 'data'}

        expected_auction_data = get_data[0]

        self.auction._set_auction_data(False)

        self.assertEqual(self.mock_datasource.get_data.call_count, 1)
        self.mock_datasource.get_data.assert_called_with(public=False)

        self.assertEqual(self.auction._auction_data, expected_auction_data)
        self.assertEqual(self.auction.startDate, self.start_date)
        self.assertEqual(self.mock_end_auction_event.set.call_count, 0)

        self.assertEqual(self.mocked_utils.convert_datetime.call_count, 1)
        self.mocked_utils.convert_datetime.assert_called_with(expected_auction_data['data']['auctionPeriod']['startDate'])

        self.assertEqual(self.mock_db.get_auction_document.call_count, 0)
        self.assertEqual(self.mock_db.save_auction_document.call_count, 0)

        self.assertEqual(self.mock_sys.exit.call_count, 0)

    def test_with_auction_data(self):
        get_data = [
            {'data': {'auctionPeriod': {'startDate': 'startDate'}}},
        ]

        self.mock_datasource.get_data.side_effect = iter(get_data)
        self.mock_db.get_auction_document.return_value = {'some': 'data'}

        expected_auction_data = get_data[0]

        self.auction._set_auction_data(False)

        self.assertEqual(self.mock_datasource.get_data.call_count, 1)
        self.mock_datasource.get_data.assert_called_with(public=False)

        self.assertEqual(self.auction._auction_data, expected_auction_data)
        self.assertEqual(self.auction.startDate, self.start_date)
        self.assertEqual(self.mock_end_auction_event.set.call_count, 0)

        self.assertEqual(self.mocked_utils.convert_datetime.call_count, 1)
        self.mocked_utils.convert_datetime.assert_called_with(expected_auction_data['data']['auctionPeriod']['startDate'])

        self.assertEqual(self.mock_db.get_auction_document.call_count, 0)
        self.assertEqual(self.mock_db.save_auction_document.call_count, 0)

        self.assertEqual(self.mock_sys.exit.call_count, 0)

    def test_without_auction_data(self):
        self.mock_datasource.get_data.return_value = {}

        auction_document = {'some': 'data'}
        self.mock_db.get_auction_document.return_value = auction_document
        self.auction.startDate = None

        expected_auction_data = {'data': {}}

        self.auction._set_auction_data(False)

        self.assertEqual(self.mock_datasource.get_data.call_count, 1)
        self.mock_datasource.get_data.assert_called_with(public=False)

        self.assertEqual(self.auction._auction_data, expected_auction_data)
        self.assertEqual(self.auction.startDate, None)
        self.assertEqual(self.mock_end_auction_event.set.call_count, 0)

        self.assertEqual(self.mocked_utils.convert_datetime.call_count, 0)

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.tender_id)

        expected_call = deepcopy(auction_document)
        expected_call['current_stage'] = -100

        self.assertEqual(self.mock_db.save_auction_document.call_count, 1)
        self.mock_db.save_auction_document.assert_called_with(expected_call, self.tender_id)

        self.assertEqual(self.mock_sys.exit.call_count, 0)

    def test_with_auction_document(self):
        self.mock_datasource.get_data.return_value = {}

        auction_document = {'some': 'data'}
        self.mock_db.get_auction_document.return_value = auction_document
        self.auction.startDate = None

        expected_auction_data = {'data': {}}

        self.auction._set_auction_data(False)

        self.assertEqual(self.mock_datasource.get_data.call_count, 1)
        self.mock_datasource.get_data.assert_called_with(public=False)

        self.assertEqual(self.auction._auction_data, expected_auction_data)
        self.assertEqual(self.auction.startDate, None)
        self.assertEqual(self.mock_end_auction_event.set.call_count, 0)

        self.assertEqual(self.mocked_utils.convert_datetime.call_count, 0)

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.tender_id)

        expected_call = deepcopy(auction_document)
        expected_call['current_stage'] = -100

        self.assertEqual(self.mock_db.save_auction_document.call_count, 1)
        self.mock_db.save_auction_document.assert_called_with(expected_call, self.tender_id)

        self.assertEqual(self.mock_sys.exit.call_count, 0)

    def test_without_auction_document(self):
        self.mock_datasource.get_data.return_value = {}

        self.mock_db.get_auction_document.return_value = {}
        self.auction.startDate = None

        expected_auction_data = {'data': {}}

        self.auction._set_auction_data(False)

        self.assertEqual(self.mock_datasource.get_data.call_count, 1)
        self.mock_datasource.get_data.assert_called_with(public=False)

        self.assertEqual(self.auction._auction_data, expected_auction_data)
        self.assertEqual(self.auction.startDate, None)
        self.assertEqual(self.mock_end_auction_event.set.call_count, 1)

        self.assertEqual(self.mocked_utils.convert_datetime.call_count, 0)

        self.assertEqual(self.mock_db.get_auction_document.call_count, 1)
        self.mock_db.get_auction_document.assert_called_with(self.tender_id)

        self.assertEqual(self.mock_db.save_auction_document.call_count, 0)

        self.assertEqual(self.mock_sys.exit.call_count, 1)
        self.mock_sys.exit.assert_called_with(1)


class TestSetStartDate(AuctionInitSetup):

    def setUp(self):
        super(TestSetStartDate, self).setUp()
        self.auction.worker_defaults['sandbox_mode'] = False

        self.auction._auction_data = {
            'data': {
                'auctionPeriod': {
                    'startDate': 'startDate'
                }
            }
        }

        self.converted_time = datetime.now()
        self.mocked_utils.convert_datetime.return_value = self.converted_time

    def test_start_date(self):
        self.auction._set_start_date()

        self.assertEqual(self.auction.startDate, self.converted_time)


class TestBiddersData(AuctionInitSetup):

    def setUp(self):
        super(TestBiddersData, self).setUp()

        self.prepared_bids = [
            {
                'id': 'id_1',
                'date': 'date_1',
                'value': 'value_1',
                'owner': 'owner_1',
                'bidNumber': '1'
            },
            {
                'id': 'id_2',
                'date': 'date_2',
                'value': 'value_2',
                'owner': 'owner_2',
                'status': 'active',
            },
            {
                'id': 'id_3',
                'date': 'date_3',
                'value': 'value_3',
                'owner': 'owner_3',
                'status': 'invalid'
            }
        ]
        self.auction._auction_data = {
            'data': {'bids': self.prepared_bids}
        }

    def test_bidders_data(self):

        expected_result = deepcopy(self.prepared_bids[:2])
        del expected_result[1]['status']
        expected_result[1]['bidNumber'] = None

        self.auction._set_bidders_data()

        self.assertEqual(self.auction.bidders_data, expected_result)


class TestSetMapping(AuctionInitSetup):

    def setUp(self):
        super(TestSetMapping, self).setUp()
        self.prepared_bids = [
            {
                'id': 'id_1',
                'date': 'date_1',
                'value': 'value_1',
                'owner': 'owner_1'
            },
            {
                'id': 'id_2',
                'date': 'date_2',
                'value': 'value_2',
                'owner': 'owner_2',
            }
        ]

        self.auction.bidders_data = self.prepared_bids
        self.auction.bids_mapping = {}

    def test_set_mapping(self):
        expected_result = {
            'id_1': 1,
            'id_2': 2
        }

        self.auction._set_mapping()

        self.assertEqual(self.auction.bids_mapping, expected_result)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestScheduleAuction))

    return suite
