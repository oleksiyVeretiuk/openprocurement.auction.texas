# -*- coding: utf-8 -*-
import unittest
import mock

from datetime import datetime, timedelta

from openprocurement.auction.texas.constants import (
    DEADLINE_HOUR,
    PAUSE,
    MAIN_ROUND,
    PAUSE_DURATION,
    END,
    ROUND_DURATION
)
from openprocurement.auction.texas.utils import (
    prepare_results_stage,
    prepare_auction_stages,
    prepare_end_stage,
    get_round_ending_time,
    set_specific_hour,
    get_bids,
    open_bidders_name,
    prepare_auction_protocol,
    prepare_bid_result,
    approve_auction_protocol_info,
    approve_auction_protocol_info_on_announcement,
    approve_auction_protocol_info_on_bids_stage,
)


class TestPrepareResultStage(unittest.TestCase):

    def setUp(self):
        self.bidder_name = 'name_of_bidder'
        self.expected = {
            'bidder_id': 'id_of_bidder',
            'amount': 'name_of_bidder',
            'time': 'some_time',
            'label': dict(
                en='Bidder #{}'.format(self.bidder_name),
                uk='Учасник №{}'.format(self.bidder_name),
                ru='Участник №{}'.format(self.bidder_name)
            )
        }

    def test_prepare_result_stage(self):
        stage = prepare_results_stage(
            bidder_id=self.expected['bidder_id'],
            bidder_name=self.bidder_name,
            amount=self.expected['amount'],
            time=self.expected['time']
        )
        self.assertEqual(stage, self.expected)

    def test_time_as_datetime(self):
        time_as_datetime = datetime.now()
        self.expected['time'] = str(time_as_datetime)

        stage = prepare_results_stage(
            bidder_id=self.expected['bidder_id'],
            bidder_name=self.bidder_name,
            amount=self.expected['amount'],
            time=time_as_datetime
        )
        self.assertEqual(stage, self.expected)

    def test_no_amount(self):
        self.expected['amount'] = 0
        stage = prepare_results_stage(
            bidder_id=self.expected['bidder_id'],
            bidder_name=self.bidder_name,
            time=self.expected['time']
        )
        self.assertEqual(stage, self.expected)


class TestPrepareAuctionStages(unittest.TestCase):

    def setUp(self):
        self.auction_data = {
            'value': {'amount': 1000},
            'minimalStep': {'amount': 200}
        }

    def test_generating_stages_before_deadline(self):
        stage_start = datetime.now().replace(hour=DEADLINE_HOUR - 2)
        expected = [
            {
                'start': stage_start.isoformat(),
                'type': PAUSE,
            },
            {
                'start': (stage_start + timedelta(seconds=PAUSE_DURATION)).isoformat(),
                'planned_end': (stage_start + timedelta(seconds=ROUND_DURATION+PAUSE_DURATION)).isoformat(),
                'type': MAIN_ROUND,
                'amount': self.auction_data['value']['amount'] + self.auction_data['minimalStep']['amount'],
                'time': ''
            }
        ]
        stages = prepare_auction_stages(stage_start, self.auction_data)
        self.assertEqual(stages, expected)

    def test_planned_end_after_deadline(self):
        deadline = datetime.now().replace(hour=DEADLINE_HOUR, minute=0, second=0, microsecond=0)
        stage_start = deadline - timedelta(seconds=PAUSE_DURATION + ROUND_DURATION - 1)

        expected = [
            {
                'start': stage_start.isoformat(),
                'type': PAUSE,
            },
            {
                'start': (stage_start + timedelta(seconds=PAUSE_DURATION)).isoformat(),
                'planned_end': deadline.isoformat(),
                'type': MAIN_ROUND,
                'amount': self.auction_data['value']['amount'] + self.auction_data['minimalStep']['amount'],
                'time': ''
            }
        ]
        stages = prepare_auction_stages(stage_start, self.auction_data)
        self.assertEqual(stages, expected)


    def test_generating_stages_after_deadline(self):
        stage_start = datetime.now().replace(hour=DEADLINE_HOUR + 2)

        expected = [
            {
                'start': stage_start.isoformat(),
                'type': PAUSE,
            },
            {}
        ]

        stages = prepare_auction_stages(stage_start, self.auction_data)
        self.assertEqual(stages, expected)


class TestPrepareEndStage(unittest.TestCase):

    def test_prepare_end_stage(self):
        start = datetime.now().replace(hour=DEADLINE_HOUR - 2)
        expected = {
            'start': start.isoformat(),
            'type': END
        }

        stage = prepare_end_stage(start)
        self.assertEqual(stage, expected)


class TestGetRoundEndingTime(unittest.TestCase):

    def test_before_deadline(self):
        deadline = datetime.now()
        start_date = deadline - timedelta(hours=2)
        duration = 100

        expected = start_date + timedelta(seconds=duration)

        end_round_date = get_round_ending_time(start_date, duration, deadline)
        self.assertEqual(end_round_date, expected)

    def test_after_deadline(self):
        deadline = datetime.now()
        start_date = deadline - timedelta(seconds=50)
        duration = 100

        end_round_date = get_round_ending_time(start_date, duration, deadline)
        self.assertEqual(end_round_date, deadline)


class TestSetSpecificHour(unittest.TestCase):

    def test_set_specific_hour(self):
        date = datetime.now()
        hour = date.hour + 1 if date.hour < 23 else date.hour - 1

        expected = date.replace(hour=hour, second=0, microsecond=0, minute=0)

        new_date = set_specific_hour(date, hour)
        self.assertEqual(new_date, expected)


class TestGetActiveBids(unittest.TestCase):

    def test_bids_with_active_status(self):
        active_bid = {'status': 'active', 'id': 'active_bid'}
        draft_bid = {'status': 'draft', 'id': 'draft_bid'}

        auction_doc = {
            'data': {
                'bids': [
                    draft_bid,
                    active_bid
                ]
            }
        }

        expected = {
            draft_bid['id']: draft_bid,
            active_bid['id']: active_bid
        }
        only_active_bids = get_bids(auction_doc)
        self.assertEqual(expected, only_active_bids)


class TestOpenBiddersName(unittest.TestCase):

    def test_open_bidders_name(self):
        auction_document = {
            'initial_bids': [{'bidder_id': 'bidder_id_1'}, {'bidder_id': 'bidder_id_2'}],
            'results': [{'bidder_id': 'bidder_id_2'}, {'bidder_id': 'bidder_id_1'}],
            'stages': [{'without': 'bidder_id'}, {'bidder_id': 'bidder_id_1'}, {'bidder_id': 'bidder_id_2'}, {'bidder_id': 'bidder_id_1'}]
        }

        bids_information = {
            'bidder_id_1': {
                'tenderers': [{'name': 'Name of first bidder'}]
            },
            'bidder_id_2': {
                'tenderers': [{'name': 'Name of second bidder'}]
            },
            'bidder_id_3': {
                'tenderers': [{'name': 'Name of third bidder'}]
            },
            'bidder_id_4': {
                'tenderers': [{'name': 'Name of fourth bidder'}]
            },
        }

        # auction document with labels
        expected = {
            'initial_bids': [
                {
                    'bidder_id': 'bidder_id_1',
                    'label': {
                        'uk': 'Name of first bidder',
                        'en': 'Name of first bidder',
                        'ru': 'Name of first bidder',
                    }
                },
                {
                    'bidder_id': 'bidder_id_2',
                    'label': {
                        'uk': 'Name of second bidder',
                        'en': 'Name of second bidder',
                        'ru': 'Name of second bidder',
                    }
                }
            ],
            'results': [
                {
                    'bidder_id': 'bidder_id_2',
                    'label': {
                        'uk': 'Name of second bidder',
                        'en': 'Name of second bidder',
                        'ru': 'Name of second bidder',
                    }
                },
                {
                    'bidder_id': 'bidder_id_1',
                    'label': {
                        'uk': 'Name of first bidder',
                        'en': 'Name of first bidder',
                        'ru': 'Name of first bidder',
                    }
                }
            ],
            'stages': [
                {'without': 'bidder_id'},
                {
                    'bidder_id': 'bidder_id_1',
                    'label': {
                        'uk': 'Name of first bidder',
                        'en': 'Name of first bidder',
                        'ru': 'Name of first bidder',
                    }
                },
                {
                    'bidder_id': 'bidder_id_2',
                    'label': {
                        'uk': 'Name of second bidder',
                        'en': 'Name of second bidder',
                        'ru': 'Name of second bidder',
                    }
                },                {
                    'bidder_id': 'bidder_id_1',
                    'label': {
                        'uk': 'Name of first bidder',
                        'en': 'Name of first bidder',
                        'ru': 'Name of first bidder',
                    }
                }
            ]
        }

        document_with_opened_name = open_bidders_name(auction_document, bids_information)
        self.assertEqual(expected, document_with_opened_name)


class TestPrepareAuctionProtocol(unittest.TestCase):

    def test_prepare_auction_protocol_with_auctionID_and_items(self):
        context = {
            'auction_doc_id': 'id',
            'auction_data': {
                'data': {
                    'auctionID': 'id_of_auction',
                    'items': ['item1', 'item2']
                }
            }
        }

        expected = {
            'id': context['auction_doc_id'],
            'auctionId': context['auction_data']['data']['auctionID'],
            'auction_id': context['auction_doc_id'],
            'items': context['auction_data']['data']['items'],
            'timeline': {
                'auction_start': {
                    'initial_bids': []
                }
            }
        }
        
        auction_protocol = prepare_auction_protocol(context)
        self.assertEqual(auction_protocol, expected)

    def test_prepare_auction_protocol_without_auctionID_items(self):
        context = {
            'auction_doc_id': 'id',
            'auction_data': {
                'data': {}
            }
        }

        expected = {
            'id': context['auction_doc_id'],
            'auctionId': '',
            'auction_id': context['auction_doc_id'],
            'items': [],
            'timeline': {
                'auction_start': {
                    'initial_bids': []
                }
            }
        }

        auction_protocol = prepare_auction_protocol(context)
        self.assertEqual(auction_protocol, expected)


class TestPrepareBidResult(unittest.TestCase):

    def test_prepare_bid_result(self):
        bid = {
            'bidder_id': 'some_id',
            'amount': 5000,
            'time': 'some_time'
        }

        expected = {
            'bidder': bid['bidder_id'],
            'amount': bid['amount'],
            'time': bid['time']
        }

        bid_result = prepare_bid_result(bid)
        self.assertEqual(bid_result, expected)


class TestApproveAuctionProtocolInfo(unittest.TestCase):

    def test_approve_auction_protocol(self):
        auction_document = {
            'stages': [
                {
                    'type': PAUSE,
                    'start': 'pause_start'
                },
                {
                    'type': MAIN_ROUND,
                    'start': 'main_round_start',
                    'time': 'end_round_time',
                    'bidder_id': 'id_of_round_bidder',
                    'amount': 5000,
                },
                {
                    'type': MAIN_ROUND,
                    'start': '',
                }
            ]
        }
        auction_protocol = {
            'timeline': {}
        }

        expected = {
            'timeline': {
                'stage_0': {
                    'pause': {
                        'start': 'pause_start',
                        'end': 'main_round_start'
                    }
                },
                'stage_1': {
                    'bids': {
                        'time': 'end_round_time',
                        'bidder': 'id_of_round_bidder',
                        'amount': 5000
                    }
                },
                'stage_2': {'bids': {}}
            }
        }

        approved_protocol = approve_auction_protocol_info(auction_document, auction_protocol)
        self.assertEqual(approved_protocol, expected)


class TestApproveAuctionProtocolInfoBidsStage(unittest.TestCase):

    def test_approve_auction_protocol(self):
        auction_document = {
            'current_stage': 1,
            'stages': [
                {
                    'type': PAUSE
                },
                {
                    'type': MAIN_ROUND,
                    'time': 'end_round_time',
                    'bidder_id': 'id_of_round_bidder',
                    'amount': 5000
                }
            ]
        }
        auction_protocol = {
            'timeline': {}
        }

        expected = {
            'timeline': {
                'round_1': {
                    'time': 'end_round_time',
                    'bidder': 'id_of_round_bidder',
                    'amount': 5000
                }
            }
        }

        approved_protocol = approve_auction_protocol_info_on_bids_stage(auction_document, auction_protocol)
        self.assertEqual(approved_protocol, expected)


class TestApproveAuctionProtocolInfoAnnouncement(unittest.TestCase):

    def setUp(self):
        self.auction_document = {
            'results': [
                {
                    'time': 'end_1_round_time',
                    'bidder_id': 'id_of_1_round_bidder',
                    'amount': 5000,
                },
                {
                    'time': 'end_2_round_time',
                    'bidder_id': 'id_of_2_round_bidder',
                    'amount': 10000,
                }
            ],
            'initial_bids': [
                {
                    'time': '1_bid_create_date',
                    'bidder_id': 'id_of_1_round_bidder',
                    'amount': 1000,
                },
                {
                    'time': '2_bid_create_date',
                    'bidder_id': 'id_of_2_round_bidder',
                    'amount': 1000,
                }
            ]
        }

        self.auction_protocol = {
            'timeline': {
                'auction_start': {
                    'initial_bids': []
                }
            },

        }

        self.patch_datetime = mock.patch('openprocurement.auction.texas.utils.datetime')
        self.mocked_datetime = self.patch_datetime.start()

        # Mock isoformat function of object that returned by datetime.now()
        self.datetime_now = mock.MagicMock()
        self.isoformat_value = 'isoformat_value'
        self.datetime_now.isoformat.return_value = self.isoformat_value

        self.mocked_datetime.now.return_value = self.datetime_now

    def tearDown(self):
        self.patch_datetime.stop()

    def test_approve_auction(self):

        expected = {
            'timeline': {
                'auction_start': {
                    'initial_bids': []
                },
                'results': {
                    'time': self.isoformat_value,
                    'bids': [
                        {
                            'time': 'end_1_round_time',
                            'bidder': 'id_of_1_round_bidder',
                            'amount': 5000
                        },
                        {
                            'time': 'end_2_round_time',
                            'bidder': 'id_of_2_round_bidder',
                            'amount': 10000
                        }
                    ]
                }
            }
        }

        approved_protocol = approve_auction_protocol_info_on_announcement(
            self.auction_document,
            self.auction_protocol
        )
        self.assertEqual(approved_protocol, expected)

    def test_approve_auction_with_approved(self):

        approved = {
            'id_of_1_round_bidder': {
                'tenderers': ['tenderer1', 'tenderer2'],
                'owner': 'owner_of_bid',
                'bidNumber': 1
            },
            'id_of_2_round_bidder': {}
        }

        expected = {
            'timeline': {
                'auction_start': {
                    'initial_bids': [
                        {
                            'date': '1_bid_create_date',
                            'bidder': 'id_of_1_round_bidder',
                            'amount': 1000,
                            'bid_number': 1,
                            'identification': ['tenderer1', 'tenderer2'],
                            'owner': 'owner_of_bid'
                        },
                        {
                            'date': '2_bid_create_date',
                            'bidder': 'id_of_2_round_bidder',
                            'amount': 1000,
                            'bid_number': '',
                            'identification': [],
                            'owner': ''
                        }
                    ]
                },
                'results': {
                    'time': self.isoformat_value,
                    'bids': [
                        {
                            'time': 'end_1_round_time',
                            'bidder': 'id_of_1_round_bidder',
                            'amount': 5000,
                            'identification': ['tenderer1', 'tenderer2'],
                            'owner': 'owner_of_bid'
                        },
                        {
                            'time': 'end_2_round_time',
                            'bidder': 'id_of_2_round_bidder',
                            'amount': 10000,
                            'identification': [],
                            'owner': ''
                        }
                    ]
                }
            }
        }

        approved_protocol = approve_auction_protocol_info_on_announcement(
            self.auction_document,
            self.auction_protocol,
            approved
        )
        self.assertEqual(approved_protocol, expected)


def suite():
    suite = unittest.TestSuite()

    return suite
