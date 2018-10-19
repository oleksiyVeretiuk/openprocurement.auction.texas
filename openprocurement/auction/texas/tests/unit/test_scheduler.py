import unittest
import mock
from copy import deepcopy


from openprocurement.auction.texas.constants import (
    DEADLINE_HOUR,
    END,
    PREANNOUNCEMENT
)
from openprocurement.auction.texas.scheduler import JobService


class MutableMagickMock(mock.MagicMock):
    def _mock_call(_mock_self, *args, **kwargs):
        return super(mock.MagicMock, _mock_self)._mock_call(*deepcopy(args), **deepcopy(kwargs))


class TestScheduler(unittest.TestCase):

    def setUp(self):
        self.server_actions = 'server actions'
        self.job_service = JobService()
        self.job_service.context = {
            'server_actions': self.server_actions,
            'worker_defaults': {
                'deadline': {
                    'deadline_hour': DEADLINE_HOUR
                }
            },
            'auction_document': {'current_stage': 0}
        }
        self.job_service.database = mock.MagicMock()
        self.job_service.datasource = mock.MagicMock()

        self.patch_update_auction_document = mock.patch(
            'openprocurement.auction.texas.scheduler.update_auction_document'
        )
        self.mocked_update_auction_document = self.patch_update_auction_document.start()

        self.patch_lock_server = mock.patch(
            'openprocurement.auction.texas.scheduler.lock_server'
        )
        self.mocked_lock_server = self.patch_lock_server.start()

        self.patch_gevent_scheduler = mock.patch(
            'openprocurement.auction.texas.scheduler.SCHEDULER'
        )
        self.mocked_SCHEDULER = self.patch_gevent_scheduler.start()

    def tearDown(self):
        self.patch_update_auction_document.stop()
        self.patch_lock_server.stop()
        self.patch_gevent_scheduler.stop()


class TestEndingMainRoundJob(TestScheduler):

    def test_add_ending_main_round_job(self):
        job_start_date = 'start_date'
        end_auction_method = mock.MagicMock()
        self.job_service.end_auction = end_auction_method

        self.job_service.add_ending_main_round_job(job_start_date)

        self.assertEqual(self.mocked_SCHEDULER.add_job.call_count, 1)
        self.mocked_SCHEDULER.add_job.assert_called_with(
            end_auction_method,
            'date',
            run_date=job_start_date,
            name='End of Auction',
            id='auction:{}'.format(END)
        )


class TestPauseJob(TestScheduler):

    def test_add_pause_job(self):
        job_start_date = 'start_date'
        switch_to_next_round = mock.MagicMock()
        self.job_service.switch_to_next_stage = switch_to_next_round

        self.job_service.add_pause_job(job_start_date)

        self.assertEqual(self.mocked_SCHEDULER.add_job.call_count, 1)
        self.mocked_SCHEDULER.add_job.assert_called_with(
            switch_to_next_round,
            'date',
            run_date=job_start_date,
            name='End of Pause',
            id='auction:pause'
        )


class TestSwitchToNextStage(TestScheduler):

    def test_switch_to_next_stage(self):
        default_current_stage = 0
        auction_document = {'current_stage': default_current_stage}
        self.mocked_update_auction_document.return_value.__enter__.return_value = auction_document

        self.job_service.switch_to_next_stage()

        self.assertEqual(self.mocked_lock_server.call_count, 1)
        self.mocked_lock_server.assert_called_with(self.server_actions)

        self.assertEqual(self.mocked_update_auction_document.call_count, 1)
        self.mocked_update_auction_document.assert_called_with(self.job_service.context, self.job_service.database)

        self.assertEqual(auction_document['current_stage'], default_current_stage + 1)


class TestEndAuction(TestScheduler):

    def setUp(self):
        super(TestEndAuction, self).setUp()

        self.auction_id = '1' * 32
        self.job_service.context['auction_doc_id'] = self.auction_id
        self.job_service.context['auction_data'] = {'auction': 'data'}

        self.server = mock.MagicMock()
        self.job_service.context['server'] = None
        self.first_protocol = {'first': 'protocol'}
        self.job_service.context['auction_protocol'] = self.first_protocol

        self.end_auction_event = mock.MagicMock()
        self.job_service.context['end_auction_event'] = self.end_auction_event

        self.patch_delete_mapping = mock.patch(
            'openprocurement.auction.texas.scheduler.delete_mapping'
        )
        self.mocked_delete_mapping = self.patch_delete_mapping.start()

        self.patch_approve_protocol = mock.patch(
            'openprocurement.auction.texas.scheduler.approve_auction_protocol_info_on_announcement',
            new_callable=MutableMagickMock
        )
        self.mocked_approve_protocol = self.patch_approve_protocol.start()
        self.final_protocol = {'auction': 'protocol'}
        self.mocked_approve_protocol.return_value = self.final_protocol

        self.patch_prepare_end_stage = mock.patch(
            'openprocurement.auction.texas.scheduler.prepare_end_stage'
        )
        self.mocked_prepare_end_stage = self.patch_prepare_end_stage.start()
        self.end_stage = {'end': 'stage'}
        self.mocked_prepare_end_stage.return_value = self.end_stage

        self.patch_yaml_dump = mock.patch(
            'openprocurement.auction.texas.scheduler.yaml_dump'
        )
        self.mocked_yaml_dump = self.patch_yaml_dump.start()
        self.mocked_yaml_dump.return_value = 'yaml dump'

        self.auction_document = {
            'stages': [],
            'current_stage': 0
        }
        self.job_service.context['auction_document'] = self.auction_document

        self.mocked_update_auction_document.return_value.__enter__.return_value = self.auction_document

        self.job_service.datasource.update_source_object = MutableMagickMock()
        self.job_service.datasource.update_source_object.return_value = None

        self.patch_datetime = mock.patch(
            'openprocurement.auction.texas.scheduler.datetime'
        )
        self.mocked_datetime = self.patch_datetime.start()
        now = mock.MagicMock()
        self.isoformat = 'isoformat_now'
        now.isoformat.return_value = self.isoformat
        self.mocked_datetime.now.return_value = now

    def test_end_auction_without_server(self):
        auction_document_before_approval = deepcopy(self.auction_document)
        auction_document_before_approval['stages'].append(
            {
                'start': self.isoformat,
                'type': PREANNOUNCEMENT,
            }
        )
        auction_document_before_approval['current_stage'] = 0

        self.job_service.context['server'] = None

        self.job_service.end_auction()

        self.assertEqual(self.server.stop.call_count, 0)

        self.assertEqual(self.mocked_delete_mapping.call_count, 1)
        self.mocked_delete_mapping.assert_called_with(
            self.job_service.context['worker_defaults'],
            self.auction_id
        )

        self.assertEqual(self.mocked_update_auction_document.call_count, 2)
        self.mocked_update_auction_document.assert_called_with(self.job_service.context, self.job_service.database)

        self.assertEqual(self.mocked_approve_protocol.call_count, 1)
        self.mocked_approve_protocol.assert_called_with(auction_document_before_approval, self.first_protocol)

        self.assertEqual(self.job_service.datasource.update_source_object.call_count, 1)
        self.job_service.datasource.update_source_object.assert_called_with(
            self.job_service.context['auction_data'],
            auction_document_before_approval,
            self.job_service.context['auction_protocol']
        )

        self.assertEqual(self.end_auction_event.set.call_count, 1)

        final_document = deepcopy(auction_document_before_approval)
        final_document['current_stage'] = 1
        final_document['stages'].append(self.end_stage)
        final_document['endDate'] = self.isoformat
        self.assertEqual(self.job_service.context['auction_document'], final_document)
        self.assertEqual(self.job_service.context['auction_protocol'], self.final_protocol)

    def test_end_auction_with_server(self):
        auction_document_before_approval = deepcopy(self.auction_document)
        auction_document_before_approval['stages'].append(
            {
                'start': self.isoformat,
                'type': PREANNOUNCEMENT,
            }
        )
        auction_document_before_approval['current_stage'] = 0

        final_document = deepcopy(auction_document_before_approval)
        final_document['current_stage'] = 1
        final_document['stages'].append(self.end_stage)
        final_document['endDate'] = self.isoformat

        self.job_service.context['server'] = self.server

        self.job_service.end_auction()

        self.assertEqual(self.server.stop.call_count, 1)

        self.assertEqual(self.mocked_delete_mapping.call_count, 1)
        self.mocked_delete_mapping.assert_called_with(
            self.job_service.context['worker_defaults'],
            self.auction_id
        )

        self.assertEqual(self.mocked_update_auction_document.call_count, 2)
        self.mocked_update_auction_document.assert_called_with(self.job_service.context, self.job_service.database)

        self.assertEqual(self.mocked_approve_protocol.call_count, 1)
        self.mocked_approve_protocol.assert_called_with(auction_document_before_approval, self.first_protocol)

        self.assertEqual(self.job_service.datasource.update_source_object.call_count, 1)
        self.job_service.datasource.update_source_object.assert_called_with(
            self.job_service.context['auction_data'],
            auction_document_before_approval,
            self.job_service.context['auction_protocol']
        )

        self.assertEqual(self.end_auction_event.set.call_count, 1)

        self.assertEqual(self.job_service.context['auction_document'], final_document)
        self.assertEqual(self.job_service.context['auction_protocol'], self.final_protocol)

    def test_end_auction_without_results(self):
        self.job_service.datasource.update_source_object.return_value = None

        auction_document_before_approval = deepcopy(self.auction_document)
        auction_document_before_approval['stages'].append(
            {
                'start': self.isoformat,
                'type': PREANNOUNCEMENT,
            }
        )

        final_document = deepcopy(auction_document_before_approval)
        final_document['current_stage'] = 1
        final_document['stages'].append(self.end_stage)
        final_document['endDate'] = self.isoformat

        auction_document_before_approval['current_stage'] = 0
        self.job_service.end_auction()

        self.assertEqual(self.server.stop.call_count, 0)

        self.assertEqual(self.mocked_delete_mapping.call_count, 1)
        self.mocked_delete_mapping.assert_called_with(
            self.job_service.context['worker_defaults'],
            self.auction_id
        )

        self.assertEqual(self.mocked_update_auction_document.call_count, 2)
        self.mocked_update_auction_document.assert_called_with(self.job_service.context, self.job_service.database)

        self.assertEqual(self.mocked_approve_protocol.call_count, 1)
        self.mocked_approve_protocol.assert_called_with(auction_document_before_approval, self.first_protocol)

        self.assertEqual(self.job_service.datasource.update_source_object.call_count, 1)
        self.job_service.datasource.update_source_object.assert_called_with(
            self.job_service.context['auction_data'],
            auction_document_before_approval,
            self.job_service.context['auction_protocol']
        )

        self.assertEqual(self.end_auction_event.set.call_count, 1)

        self.assertEqual(self.job_service.context['auction_document'], final_document)
        self.assertEqual(self.job_service.context['auction_protocol'], self.final_protocol)

    def test_end_auction_with_results(self):
        resulted_doc = {'resulted': 'document', 'stages': []}

        self.mocked_update_auction_document.return_value.__enter__.side_effect = iter([
            self.auction_document,
            resulted_doc
        ])
        self.job_service.datasource.update_source_object.return_value = resulted_doc

        auction_document_before_approval = deepcopy(self.auction_document)
        auction_document_before_approval['stages'].append(
            {
                'start': self.isoformat,
                'type': PREANNOUNCEMENT,
            }
        )
        final_document = deepcopy(resulted_doc)
        final_document['current_stage'] = 0
        final_document['stages'].append(self.end_stage)
        final_document['endDate'] = self.isoformat

        auction_document_before_approval['current_stage'] = 0
        self.job_service.end_auction()

        self.assertEqual(self.server.stop.call_count, 0)

        self.assertEqual(self.mocked_delete_mapping.call_count, 1)
        self.mocked_delete_mapping.assert_called_with(
            self.job_service.context['worker_defaults'],
            self.auction_id
        )

        self.assertEqual(self.mocked_update_auction_document.call_count, 2)
        self.mocked_update_auction_document.assert_called_with(self.job_service.context, self.job_service.database)

        self.assertEqual(self.mocked_approve_protocol.call_count, 1)
        self.mocked_approve_protocol.assert_called_with(auction_document_before_approval, self.first_protocol)

        self.assertEqual(self.job_service.datasource.update_source_object.call_count, 1)
        self.job_service.datasource.update_source_object.assert_called_with(
            self.job_service.context['auction_data'],
            auction_document_before_approval,
            self.job_service.context['auction_protocol']
        )

        self.assertEqual(self.end_auction_event.set.call_count, 1)

        self.assertEqual(self.job_service.context['auction_document'], final_document)
        self.assertEqual(self.job_service.context['auction_protocol'], self.final_protocol)
