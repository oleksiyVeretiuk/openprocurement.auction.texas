# -*- coding: utf-8 -*-
from gevent import monkey
monkey.patch_all()

import argparse
import logging.config
import os
import sys

import yaml
from gevent.lock import BoundedSemaphore
from zope.component.globalregistry import getGlobalSiteManager

from openprocurement.auction.utils import check
from openprocurement.auction.worker_core import constants as C

from openprocurement.auction.texas.auction import Auction, SCHEDULER
from openprocurement.auction.texas.constants import DEADLINE_HOUR
from openprocurement.auction.texas.context import prepare_context, IContext
from openprocurement.auction.texas.database import prepare_database, IDatabase
from openprocurement.auction.texas.datasource import prepare_datasource, IDataSource
from openprocurement.auction.texas.scheduler import prepare_job_service, IJobService


logging.addLevelName(25, 'CHECK')
logging.Logger.check = check

LOGGER = logging.getLogger('Auction Worker Texas')


def register_utilities(worker_config, args):
    auction_id = args.auction_doc_id
    gsm = getGlobalSiteManager()
    exceptions = []
    init_functions = []

    database = prepare_database(worker_config.get('database', {}))
    doc = database.get_auction_document(auction_id)

    # Initializing datasource
    if args.standalone or doc.get('standalone'):
        datasource_config = {'type': 'test'}
        worker_config['deadline'] = {'enabled': False}
    else:
        datasource_config = worker_config.get('datasource', {})
    datasource_config.update(auction_id=auction_id)
    init_functions.append(
        (prepare_datasource, (datasource_config,), 'datasource', IDataSource)
    )

    # Initializing database
    database_config = worker_config.get('database', {})
    init_functions.append(
        (prepare_database, (database_config,), 'database', IDatabase)
    )

    # Initializing context
    context_config = worker_config.get('context', {})
    init_functions.append(
        (prepare_context, (context_config,), 'context', IContext)
    )

    # Initializing JobService
    init_functions.append(
        (prepare_job_service, (), 'job_service', IJobService)
    )

    # Checking and registering utilities
    for init_function, args, utility_name, interface in init_functions:
        result = ('ok', None)
        try:
            utility = init_function(*args)
        except Exception as e:
            exceptions.append(e)
            result = ('failed', e)
        else:
            gsm.registerUtility(utility, interface)
        finally:
            LOGGER.check('{} - {}'.format(utility_name, result[0]), result[1])
    if exceptions:
        raise exceptions[0]

    # Updating context
    context = gsm.queryUtility(IContext)
    context['auction_doc_id'] = auction_id

    deadline_defaults = {
            'enabled': True,
            'deadline_hour': DEADLINE_HOUR
    }
    deadline_defaults.update(worker_config.get('deadline', {}))
    if not deadline_defaults['enabled']:
        deadline_defaults['deadline_hour'] = None
    worker_config['deadline'] = deadline_defaults
    context['worker_defaults'] = worker_config

    # Initializing semaphore which is used for locking WSGI server actions
    # during applying bids or updating auction document
    context['server_actions'] = BoundedSemaphore()


def main():
    parser = argparse.ArgumentParser(description='---- Auction ----')
    parser.add_argument('cmd', type=str, help='')
    parser.add_argument('auction_doc_id', type=str, help='auction_doc_id')
    parser.add_argument('auction_worker_config', type=str,
                        help='Auction Worker Configuration File')
    parser.add_argument('--with_api_version', type=str, help='Tender Api Version')
    parser.add_argument('--planning_procerude', type=str, help='Override planning procerude',
                        default=None, choices=[None, C.PLANNING_FULL, C.PLANNING_PARTIAL_DB, C.PLANNING_PARTIAL_CRON])
    parser.add_argument('-debug', dest='debug', action='store_const',
                        const=True, default=False,
                        help='Debug mode for auction')
    parser.add_argument('--standalone', dest='standalone', action='store_const',
                        const=True, default=False,
                        help='Use TestingFileDataSource for auction')
    parser.add_argument('--doc_id', dest='doc_id', type=str, default=False,
                        help='id of existing auction protocol document')

    args = parser.parse_args()

    if os.path.isfile(args.auction_worker_config):
        worker_defaults = yaml.load(open(args.auction_worker_config))
        if args.with_api_version:
            worker_defaults['resource_api_version'] = args.with_api_version
        if args.cmd != 'cleanup':
            worker_defaults['handlers']['journal']['TENDER_ID'] = args.auction_doc_id

        worker_defaults['handlers']['journal']['TENDERS_API_VERSION'] = worker_defaults['resource_api_version']
        worker_defaults['handlers']['journal']['TENDERS_API_URL'] = worker_defaults['resource_api_server']

        logging.config.dictConfig(worker_defaults)
    else:
        print "Auction worker defaults config not exists!!!"
        sys.exit(1)

    register_utilities(worker_defaults, args)
    auction = Auction(args.auction_doc_id, worker_defaults=worker_defaults, debug=args.debug)
    if args.cmd == 'check':
        exit()
    if args.cmd == 'run':
        SCHEDULER.start()
        auction.schedule_auction()
        auction.wait_to_end()
        SCHEDULER.shutdown()
    elif args.cmd == 'planning':
        auction.prepare_auction_document()
    elif args.cmd == 'announce':
        auction.post_announce()
    elif args.cmd == 'post_results':
        auction.post_auction_results()
    elif args.cmd == 'cancel':
        auction.cancel_auction()
    elif args.cmd == 'reschedule':
        auction.reschedule_auction()
    elif args.cmd == 'post_auction_protocol':
        print auction.post_auction_protocol(args.doc_id)


if __name__ == "__main__":
    main()
