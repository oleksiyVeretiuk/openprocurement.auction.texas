import unittest
import munch
import mock

from copy import deepcopy

from openprocurement.auction.texas.cli import main, register_utilities
from openprocurement.auction.texas.context import IContext
from openprocurement.auction.texas.constants import DEADLINE_HOUR


class RegisterUtilitiesTest(unittest.TestCase):

    def setUp(self):
        self.patch_prepare_datasource = mock.patch(
            'openprocurement.auction.texas.cli.prepare_datasource'
        )
        self.mocked_prepare_datasource = self.patch_prepare_datasource.start()

        self.patch_prepare_database = mock.patch(
            'openprocurement.auction.texas.cli.prepare_database'
        )
        self.mocked_prepare_database = self.patch_prepare_database.start()
        self.mocked_db = mock.MagicMock()
        self.mocked_prepare_database.return_value = self.mocked_db
        self.mocked_db.get_auction_document.return_value = {}

        self.patch_prepare_context = mock.patch(
            'openprocurement.auction.texas.cli.prepare_context'
        )
        self.mocked_prepare_context = self.patch_prepare_context.start()
        self.context = {}
        self.mocked_prepare_context.return_value = self.context

        self.patch_prepare_job_service = mock.patch(
            'openprocurement.auction.texas.cli.prepare_job_service'
        )
        self.mocked_prepare_job_service = self.patch_prepare_job_service.start()
        self.mocked_job_service = mock.MagicMock()
        self.mocked_prepare_job_service.return_value = self.mocked_job_service

        self.patch_get_global_site_manager = mock.patch(
            'openprocurement.auction.texas.cli.getGlobalSiteManager'
        )
        self.mocked_get_global_site_manager = self.patch_get_global_site_manager.start()
        self.mocked_gsm = mock.MagicMock()
        self.mocked_get_global_site_manager.return_value = self.mocked_gsm
        self.mocked_gsm.queryUtility.return_value = self.context

        self.patch_bounded_semaphore = mock.patch(
            'openprocurement.auction.texas.cli.BoundedSemaphore'
        )
        self.mocked_bounded_semaphore = self.patch_bounded_semaphore.start()
        self.bounded_semaphore = 'bounded semaphore'
        self.mocked_bounded_semaphore.return_value = self.bounded_semaphore

    def tearDown(self):
        self.patch_prepare_datasource.stop()
        self.patch_prepare_database.stop()
        self.patch_prepare_context.stop()
        self.patch_prepare_job_service.stop()
        self.patch_get_global_site_manager.stop()
        self.patch_bounded_semaphore.stop()

    def test_register_utilities(self):
        worker_config = {
            'context': {'context': 'config'},
            'datasource': {'datasource': 'config'},
            'database': {'database': 'config'},
        }
        args = munch.Munch({})
        args.auction_doc_id = '1' * 32
        args.standalone = False

        register_utilities(worker_config, args)

        self.assertEqual(self.mocked_db.get_auction_document.call_count, 1)
        self.mocked_db.get_auction_document.assert_called_with(args.auction_doc_id)

        self.assertEqual(self.mocked_prepare_database.call_count, 2)
        self.mocked_prepare_database.assert_called_with(worker_config['database'])

        self.assertEqual(self.mocked_prepare_context.call_count, 1)
        self.mocked_prepare_context.assert_called_with(worker_config['context'])

        self.assertEqual(self.mocked_prepare_datasource.call_count, 1)
        resulted_datasource_config = deepcopy(worker_config['datasource'])
        resulted_datasource_config['auction_id'] = args.auction_doc_id
        self.mocked_prepare_datasource.assert_called_with(resulted_datasource_config)

        self.assertEqual(self.mocked_prepare_job_service.call_count, 1)
        self.mocked_prepare_job_service.assert_called_with()

        self.assertEqual(self.mocked_gsm.registerUtility.call_count, 4)

        self.assertEqual(self.mocked_gsm.queryUtility.call_count, 1)
        self.mocked_gsm.queryUtility.assert_called_with(IContext)

        resulted_worker_config = deepcopy(worker_config)
        resulted_worker_config['datasource']['auction_id'] = args.auction_doc_id
        resulted_worker_config['deadline'] = {
            'enabled': True,
            'deadline_time': {'hour': DEADLINE_HOUR}
        }
        self.assertEqual(self.context['worker_defaults'], resulted_worker_config)
        self.assertEqual(self.context['server_actions'], self.bounded_semaphore)

    def test_register_utilities_standalone(self):
        worker_config = {
            'context': {'context': 'config'},
            'datasource': {'datasource': 'config'},
            'database': {'database': 'config'},
        }
        args = munch.Munch({})
        args.auction_doc_id = '1' * 32
        args.standalone = True

        register_utilities(worker_config, args)

        self.assertEqual(self.mocked_db.get_auction_document.call_count, 1)
        self.mocked_db.get_auction_document.assert_called_with(args.auction_doc_id)

        self.assertEqual(self.mocked_prepare_database.call_count, 2)
        self.mocked_prepare_database.assert_called_with(worker_config['database'])

        self.assertEqual(self.mocked_prepare_context.call_count, 1)
        self.mocked_prepare_context.assert_called_with(worker_config['context'])

        self.assertEqual(self.mocked_prepare_datasource.call_count, 1)
        resulted_datasource_config = {
            'auction_id': args.auction_doc_id,
            'type': 'test'
        }
        self.mocked_prepare_datasource.assert_called_with(resulted_datasource_config)

        self.assertEqual(self.mocked_prepare_job_service.call_count, 1)
        self.mocked_prepare_job_service.assert_called_with()

        self.assertEqual(self.mocked_gsm.registerUtility.call_count, 4)

        self.assertEqual(self.mocked_gsm.queryUtility.call_count, 1)
        self.mocked_gsm.queryUtility.assert_called_with(IContext)

        resulted_worker_config = deepcopy(worker_config)
        resulted_worker_config['datasource'] = resulted_datasource_config
        resulted_worker_config['deadline'] = {
            'enabled': False,
            'deadline_time': {}
        }
        self.assertEqual(self.context['worker_defaults'], resulted_worker_config)
        self.assertEqual(self.context['server_actions'], self.bounded_semaphore)

    def test_register_utilities_disabled_deadline(self):
        worker_config = {
            'context': {'context': 'config'},
            'datasource': {'datasource': 'config'},
            'database': {'database': 'config'},
            'deadline': {'enabled': False, 'deadline_time': {'hour': 20}}
        }
        args = munch.Munch({})
        args.auction_doc_id = '1' * 32
        args.standalone = False

        register_utilities(worker_config, args)

        self.assertEqual(self.mocked_db.get_auction_document.call_count, 1)
        self.mocked_db.get_auction_document.assert_called_with(args.auction_doc_id)

        self.assertEqual(self.mocked_prepare_database.call_count, 2)
        self.mocked_prepare_database.assert_called_with(worker_config['database'])

        self.assertEqual(self.mocked_prepare_context.call_count, 1)
        self.mocked_prepare_context.assert_called_with(worker_config['context'])

        self.assertEqual(self.mocked_prepare_datasource.call_count, 1)
        resulted_datasource_config = deepcopy(worker_config['datasource'])
        resulted_datasource_config['auction_id'] = args.auction_doc_id
        self.mocked_prepare_datasource.assert_called_with(resulted_datasource_config)

        self.assertEqual(self.mocked_prepare_job_service.call_count, 1)
        self.mocked_prepare_job_service.assert_called_with()

        self.assertEqual(self.mocked_gsm.registerUtility.call_count, 4)

        self.assertEqual(self.mocked_gsm.queryUtility.call_count, 1)
        self.mocked_gsm.queryUtility.assert_called_with(IContext)

        resulted_worker_config = deepcopy(worker_config)
        resulted_worker_config['datasource'] = resulted_datasource_config
        resulted_worker_config['deadline'] = {
            'enabled': False,
            'deadline_time': {}
        }
        self.assertEqual(self.context['worker_defaults'], resulted_worker_config)
        self.assertEqual(self.context['server_actions'], self.bounded_semaphore)

    def test_deadline_configuring(self):
        worker_config = {
            'context': {'context': 'config'},
            'datasource': {'datasource': 'config'},
            'database': {'database': 'config'},
            'deadline': {'enabled': True, 'deadline_time': {'hour': 20}}
        }
        args = munch.Munch({})
        args.auction_doc_id = '1' * 32
        args.standalone = False

        register_utilities(worker_config, args)

        self.assertEqual(self.mocked_db.get_auction_document.call_count, 1)
        self.mocked_db.get_auction_document.assert_called_with(args.auction_doc_id)

        self.assertEqual(self.mocked_prepare_database.call_count, 2)
        self.mocked_prepare_database.assert_called_with(worker_config['database'])

        self.assertEqual(self.mocked_prepare_context.call_count, 1)
        self.mocked_prepare_context.assert_called_with(worker_config['context'])

        self.assertEqual(self.mocked_prepare_datasource.call_count, 1)
        resulted_datasource_config = deepcopy(worker_config['datasource'])
        resulted_datasource_config['auction_id'] = args.auction_doc_id
        self.mocked_prepare_datasource.assert_called_with(resulted_datasource_config)

        self.assertEqual(self.mocked_prepare_job_service.call_count, 1)
        self.mocked_prepare_job_service.assert_called_with()

        self.assertEqual(self.mocked_gsm.registerUtility.call_count, 4)

        self.assertEqual(self.mocked_gsm.queryUtility.call_count, 1)
        self.mocked_gsm.queryUtility.assert_called_with(IContext)

        resulted_worker_config = deepcopy(worker_config)
        resulted_worker_config['datasource'] = resulted_datasource_config
        resulted_worker_config['deadline'] = {'enabled': True, 'deadline_time': {'hour': 20}}
        self.assertEqual(self.context['worker_defaults'], resulted_worker_config)
        self.assertEqual(self.context['server_actions'], self.bounded_semaphore)


class MainTest(unittest.TestCase):

    def setUp(self):
        self.patch_gevent_scheduler = mock.patch(
            'openprocurement.auction.texas.cli.SCHEDULER'
        )
        self.mocked_SCHEDULER = self.patch_gevent_scheduler.start()

        self.patch_arg_parser = mock.patch(
            'openprocurement.auction.texas.cli.argparse.ArgumentParser'
        )
        self.mocked_arg_parser = self.patch_arg_parser.start()
        self.mocked_parser_obj = mock.MagicMock()
        self.mocked_arg_parser.return_value = self.mocked_parser_obj

        self.patch_auction = mock.patch(
            'openprocurement.auction.texas.cli.Auction'
        )
        self.mocked_auction_class = self.patch_auction.start()
        self.auction_instance = mock.MagicMock()
        self.mocked_auction_class.return_value = self.auction_instance

        self.patch_open = mock.patch(
            'openprocurement.auction.texas.cli.open',
            create=True
        )
        self.mocked_open = self.patch_open.start()
        self.open_result = 'open result'
        self.mocked_open.return_value = self.open_result

        self.patch_yaml = mock.patch(
            'openprocurement.auction.texas.cli.yaml'
        )
        self.mocked_yaml = self.patch_yaml.start()
        self.yaml_output = {
            'handlers': {
                'journal': {}
            },
            'resource_api_version': 'version',
            'resource_api_server': 'server'
        }
        self.mocked_yaml.load.return_value = self.yaml_output

        self.patch_register_utilities = mock.patch(
            'openprocurement.auction.texas.cli.register_utilities'
        )
        self.mocked_register_utilities = self.patch_register_utilities.start()

        self.patch_os = mock.patch(
            'openprocurement.auction.texas.cli.os'
        )
        self.mocked_os = self.patch_os.start()
        self.mocked_os.path.isfile.return_value = True

        self.patch_logging = mock.patch(
            'openprocurement.auction.texas.cli.logging'
        )
        self.mocked_logging = self.patch_logging.start()

    def tearDown(self):
        self.patch_yaml.stop()
        self.patch_gevent_scheduler.stop()
        self.patch_arg_parser.stop()
        self.patch_os.stop()
        self.patch_logging.stop()
        self.patch_open.stop()
        self.patch_register_utilities.stop()
        self.patch_auction.stop()

    def test_main_with_worker_config(self):
        resulted_yaml = deepcopy(self.yaml_output)

        args = munch.Munch({
            'cmd': '',
            'auction_worker_config': 'path/to/config',
            'with_api_version': None,
            'auction_doc_id': '1' * 32,
            'debug': False
        })
        self.mocked_parser_obj.parse_args.return_value = args

        main()

        self.assertEqual(self.mocked_os.path.isfile.call_count, 1)
        self.mocked_os.path.isfile.assert_called_with(args.auction_worker_config)

        self.assertEqual(self.mocked_yaml.load.call_count, 1)
        self.mocked_yaml.load.assert_called_with(self.open_result)

        self.assertEqual(self.mocked_open.call_count, 1)
        self.mocked_open.assert_called_with(args.auction_worker_config)

        self.assertEqual(self.mocked_logging.config.dictConfig.call_count, 1)
        resulted_yaml['handlers']['journal']['TENDERS_API_VERSION'] = resulted_yaml['resource_api_version']
        resulted_yaml['handlers']['journal']['TENDERS_API_URL'] = resulted_yaml['resource_api_server']
        resulted_yaml['handlers']['journal']['TENDER_ID'] = args.auction_doc_id
        self.mocked_logging.config.dictConfig.assert_called_with(resulted_yaml)

        self.assertEqual(self.mocked_register_utilities.call_count, 1)
        self.mocked_register_utilities.assert_called_with(resulted_yaml, args)

        self.assertEqual(self.mocked_auction_class.call_count, 1)
        self.mocked_auction_class.assert_called_with(
            args.auction_doc_id,
            worker_defaults=resulted_yaml,
            debug=args.debug
        )

    def test_main_without_worker_config(self):
        args = munch.Munch({
            'cmd': '',
            'auction_worker_config': 'path/to/config',
            'with_api_version': None,
            'auction_doc_id': '1' * 32,
            'debug': False
        })
        self.mocked_os.path.isfile.return_value = False
        self.mocked_parser_obj.parse_args.return_value = args

        with self.assertRaises(SystemExit):
            main()

        self.assertEqual(self.mocked_os.path.isfile.call_count, 1)

        self.assertEqual(self.mocked_yaml.load.call_count, 0)

        self.assertEqual(self.mocked_open.call_count, 0)

        self.assertEqual(self.mocked_logging.config.dictConfig.call_count, 0)

        self.assertEqual(self.mocked_register_utilities.call_count, 0)

        self.assertEqual(self.mocked_auction_class.call_count, 0)

    def test_with_api_version(self):
        resulted_yaml = deepcopy(self.yaml_output)

        args = munch.Munch({
            'cmd': '',
            'auction_worker_config': 'path/to/config',
            'with_api_version': 'another api version',
            'auction_doc_id': '1' * 32,
            'debug': False
        })
        self.mocked_parser_obj.parse_args.return_value = args

        main()

        self.assertEqual(self.mocked_os.path.isfile.call_count, 1)
        self.mocked_os.path.isfile.assert_called_with(args.auction_worker_config)

        self.assertEqual(self.mocked_yaml.load.call_count, 1)
        self.mocked_yaml.load.assert_called_with(self.open_result)

        self.assertEqual(self.mocked_open.call_count, 1)
        self.mocked_open.assert_called_with(args.auction_worker_config)

        self.assertEqual(self.mocked_logging.config.dictConfig.call_count, 1)
        resulted_yaml['resource_api_version'] = args.with_api_version
        resulted_yaml['handlers']['journal']['TENDERS_API_VERSION'] = resulted_yaml['resource_api_version']
        resulted_yaml['handlers']['journal']['TENDERS_API_URL'] = resulted_yaml['resource_api_server']
        resulted_yaml['handlers']['journal']['TENDER_ID'] = args.auction_doc_id
        self.mocked_logging.config.dictConfig.assert_called_with(resulted_yaml)

        self.assertEqual(self.mocked_register_utilities.call_count, 1)
        self.mocked_register_utilities.assert_called_with(resulted_yaml, args)

        self.assertEqual(self.mocked_auction_class.call_count, 1)
        self.mocked_auction_class.assert_called_with(
            args.auction_doc_id,
            worker_defaults=resulted_yaml,
            debug=args.debug
        )

    def test_without_api_version(self):
        resulted_yaml = deepcopy(self.yaml_output)

        args = munch.Munch({
            'cmd': '',
            'auction_worker_config': 'path/to/config',
            'with_api_version': None,
            'auction_doc_id': '1' * 32,
            'debug': False
        })
        self.mocked_parser_obj.parse_args.return_value = args

        main()

        self.assertEqual(self.mocked_os.path.isfile.call_count, 1)
        self.mocked_os.path.isfile.assert_called_with(args.auction_worker_config)

        self.assertEqual(self.mocked_yaml.load.call_count, 1)
        self.mocked_yaml.load.assert_called_with(self.open_result)

        self.assertEqual(self.mocked_open.call_count, 1)
        self.mocked_open.assert_called_with(args.auction_worker_config)

        self.assertEqual(self.mocked_logging.config.dictConfig.call_count, 1)
        resulted_yaml['handlers']['journal']['TENDERS_API_VERSION'] = resulted_yaml['resource_api_version']
        resulted_yaml['handlers']['journal']['TENDERS_API_URL'] = resulted_yaml['resource_api_server']
        resulted_yaml['handlers']['journal']['TENDER_ID'] = args.auction_doc_id
        self.mocked_logging.config.dictConfig.assert_called_with(resulted_yaml)

        self.assertEqual(self.mocked_register_utilities.call_count, 1)
        self.mocked_register_utilities.assert_called_with(resulted_yaml, args)

        self.assertEqual(self.mocked_auction_class.call_count, 1)
        self.mocked_auction_class.assert_called_with(
            args.auction_doc_id,
            worker_defaults=resulted_yaml,
            debug=args.debug
        )

    def test_with_cleanup(self):
        resulted_yaml = deepcopy(self.yaml_output)

        args = munch.Munch({
            'cmd': 'cleanup',
            'auction_worker_config': 'path/to/config',
            'with_api_version': 'another api version',
            'auction_doc_id': '1' * 32,
            'debug': False
        })
        self.mocked_parser_obj.parse_args.return_value = args

        main()

        self.assertEqual(self.mocked_os.path.isfile.call_count, 1)
        self.mocked_os.path.isfile.assert_called_with(args.auction_worker_config)

        self.assertEqual(self.mocked_yaml.load.call_count, 1)
        self.mocked_yaml.load.assert_called_with(self.open_result)

        self.assertEqual(self.mocked_open.call_count, 1)
        self.mocked_open.assert_called_with(args.auction_worker_config)

        self.assertEqual(self.mocked_logging.config.dictConfig.call_count, 1)
        resulted_yaml['resource_api_version'] = args.with_api_version
        resulted_yaml['handlers']['journal']['TENDERS_API_VERSION'] = resulted_yaml['resource_api_version']
        resulted_yaml['handlers']['journal']['TENDERS_API_URL'] = resulted_yaml['resource_api_server']
        self.mocked_logging.config.dictConfig.assert_called_with(resulted_yaml)

        self.assertEqual(self.mocked_register_utilities.call_count, 1)
        self.mocked_register_utilities.assert_called_with(resulted_yaml, args)

        self.assertEqual(self.mocked_auction_class.call_count, 1)
        self.mocked_auction_class.assert_called_with(
            args.auction_doc_id,
            worker_defaults=resulted_yaml,
            debug=args.debug
        )

    def test_without_cleanup(self):
        resulted_yaml = deepcopy(self.yaml_output)

        args = munch.Munch({
            'cmd': '',
            'auction_worker_config': 'path/to/config',
            'with_api_version': 'another api version',
            'auction_doc_id': '1' * 32,
            'debug': False
        })
        self.mocked_parser_obj.parse_args.return_value = args

        main()

        self.assertEqual(self.mocked_os.path.isfile.call_count, 1)
        self.mocked_os.path.isfile.assert_called_with(args.auction_worker_config)

        self.assertEqual(self.mocked_yaml.load.call_count, 1)
        self.mocked_yaml.load.assert_called_with(self.open_result)

        self.assertEqual(self.mocked_open.call_count, 1)
        self.mocked_open.assert_called_with(args.auction_worker_config)

        self.assertEqual(self.mocked_logging.config.dictConfig.call_count, 1)
        resulted_yaml['resource_api_version'] = args.with_api_version
        resulted_yaml['handlers']['journal']['TENDERS_API_VERSION'] = resulted_yaml['resource_api_version']
        resulted_yaml['handlers']['journal']['TENDERS_API_URL'] = resulted_yaml['resource_api_server']
        resulted_yaml['handlers']['journal']['TENDER_ID'] = args.auction_doc_id
        self.mocked_logging.config.dictConfig.assert_called_with(resulted_yaml)

        self.assertEqual(self.mocked_register_utilities.call_count, 1)
        self.mocked_register_utilities.assert_called_with(resulted_yaml, args)

        self.assertEqual(self.mocked_auction_class.call_count, 1)
        self.mocked_auction_class.assert_called_with(
            args.auction_doc_id,
            worker_defaults=resulted_yaml,
            debug=args.debug
        )

    def test_cmd_check(self):
        args = munch.Munch({
            'cmd': 'check',
            'auction_worker_config': 'path/to/config',
            'with_api_version': 'another api version',
            'auction_doc_id': '1' * 32,
            'debug': False
        })
        self.mocked_parser_obj.parse_args.return_value = args

        with self.assertRaises(SystemExit):
            main()

    def test_cmd_run(self):
        args = munch.Munch({
            'cmd': 'run',
            'auction_worker_config': 'path/to/config',
            'with_api_version': 'another api version',
            'auction_doc_id': '1' * 32,
            'debug': False
        })
        self.mocked_parser_obj.parse_args.return_value = args

        main()
        self.assertEqual(self.mocked_SCHEDULER.start.call_count, 1)
        self.mocked_SCHEDULER.start.assert_called_with()

        self.assertEqual(self.mocked_SCHEDULER.shutdown.call_count, 1)
        self.mocked_SCHEDULER.shutdown.assert_called_with()

        self.assertEqual(self.auction_instance.schedule_auction.call_count, 1)
        self.auction_instance.schedule_auction.assert_called_with()

        self.assertEqual(self.auction_instance.wait_to_end.call_count, 1)
        self.auction_instance.wait_to_end.assert_called_with()


    def test_cmd_planning(self):
        args = munch.Munch({
            'cmd': 'planning',
            'auction_worker_config': 'path/to/config',
            'with_api_version': 'another api version',
            'auction_doc_id': '1' * 32,
            'debug': False
        })
        self.mocked_parser_obj.parse_args.return_value = args

        main()

        self.assertEqual(self.auction_instance.prepare_auction_document.call_count, 1)
        self.auction_instance.prepare_auction_document.assert_called_with()

    def test_cmd_announce(self):
        args = munch.Munch({
            'cmd': 'announce',
            'auction_worker_config': 'path/to/config',
            'with_api_version': 'another api version',
            'auction_doc_id': '1' * 32,
            'debug': False
        })
        self.mocked_parser_obj.parse_args.return_value = args

        main()

        self.assertEqual(self.auction_instance.post_announce.call_count, 1)
        self.auction_instance.post_announce.assert_called_with()

    def test_cmd_post_results(self):
        args = munch.Munch({
            'cmd': 'post_results',
            'auction_worker_config': 'path/to/config',
            'with_api_version': 'another api version',
            'auction_doc_id': '1' * 32,
            'debug': False
        })
        self.mocked_parser_obj.parse_args.return_value = args

        main()

        self.assertEqual(self.auction_instance.post_auction_results.call_count, 1)
        self.auction_instance.post_auction_results.assert_called_with()

    def test_cmd_cancel(self):
        args = munch.Munch({
            'cmd': 'cancel',
            'auction_worker_config': 'path/to/config',
            'with_api_version': 'another api version',
            'auction_doc_id': '1' * 32,
            'debug': False
        })
        self.mocked_parser_obj.parse_args.return_value = args

        main()

        self.assertEqual(self.auction_instance.cancel_auction.call_count, 1)
        self.auction_instance.cancel_auction.assert_called_with()

    def test_cmd_reschedule(self):
        args = munch.Munch({
            'cmd': 'reschedule',
            'auction_worker_config': 'path/to/config',
            'with_api_version': 'another api version',
            'auction_doc_id': '1' * 32,
            'debug': False
        })
        self.mocked_parser_obj.parse_args.return_value = args

        main()

        self.assertEqual(self.auction_instance.reschedule_auction.call_count, 1)
        self.auction_instance.reschedule_auction.assert_called_with()

    def test_cmd_post_auction_protocol(self):
        args = munch.Munch({
            'cmd': 'post_auction_protocol',
            'auction_worker_config': 'path/to/config',
            'with_api_version': 'another api version',
            'auction_doc_id': '1' * 32,
            'debug': False,
            'doc_id': 'some document id'
        })
        self.mocked_parser_obj.parse_args.return_value = args

        main()

        self.assertEqual(self.auction_instance.post_auction_protocol.call_count, 1)
        self.auction_instance.post_auction_protocol.assert_called_with(args.doc_id)
