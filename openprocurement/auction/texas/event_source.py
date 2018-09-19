from sse import Sse as PySse
from gevent.queue import Queue
from flask import (
    current_app, Blueprint, request,
    session, Response, jsonify, abort
)
from openprocurement.auction.event_source import (
    send_event_to_client, send_event, SseStream
)
from openprocurement.auction.utils import (
    prepare_extra_journal_fields, get_bidder_id
)


sse = Blueprint('sse', __name__)


@sse.route("/set_sse_timeout", methods=['POST'])
def set_sse_timeout():
    current_app.logger.info(
        'Handle set_sse_timeout request with session {}'.format(repr(dict(session))),
        extra=prepare_extra_journal_fields(request.headers)
    )
    if 'remote_oauth' in session and 'client_id' in session:
        bidder_data = get_bidder_id(current_app, session)
        if bidder_data:
            current_app.logger.info("Bidder {} with client_id {} set sse_timeout".format(
                                    bidder_data['bidder_id'], session['client_id'],
                                    ), extra=prepare_extra_journal_fields(request.headers))
            bidder = bidder_data['bidder_id']
            if 'timeout' in request.json:
                session["sse_timeout"] = int(request.json['timeout'])
                send_event_to_client(
                    bidder, session['client_id'], '',
                    event='StopSSE'
                )
                return jsonify({'timeout': session["sse_timeout"]})
    return abort(401)


@sse.route("/event_source")
def event_source():
    current_app.logger.debug(
        'Handle event_source request with session {}'.format(repr(dict(session))),
        extra=prepare_extra_journal_fields(request.headers)
    )
    if 'remote_oauth' in session and 'client_id' in session:
        bidder_data = get_bidder_id(current_app, session)
        if bidder_data:
            valid_bidder = False
            client_hash = session['client_id']
            bidder = bidder_data['bidder_id']
            for bidder_info in current_app.context['bidders_data']:
                if bidder_info['id'] == bidder:
                    valid_bidder = True
                    break

            if valid_bidder:
                if bidder not in current_app.auction_bidders:
                    current_app.auction_bidders[bidder] = {
                        "clients": {},
                        "channels": {}
                    }

                if client_hash not in current_app.auction_bidders[bidder]:
                    real_ip = request.environ.get('HTTP_X_REAL_IP', '')
                    if real_ip.startswith('172.'):
                        real_ip = ''
                    current_app.auction_bidders[bidder]["clients"][client_hash] = {
                        'ip': ','.join(
                            [request.headers.get('X-Forwarded-For', ''), real_ip]
                        ),
                        'User-Agent': request.headers.get('User-Agent'),
                    }
                    current_app.auction_bidders[bidder]["channels"][client_hash] = Queue()

                current_app.logger.info(
                    'Send identification for bidder: {} with client_hash {}'.format(bidder, client_hash),
                    extra=prepare_extra_journal_fields(request.headers)
                )
                identification_data = {"bidder_id": bidder,
                                       "client_id": client_hash,
                                       "return_url": session.get('return_url', '')}

                send_event_to_client(bidder, client_hash, identification_data,
                                     "Identification")

                if not session.get("sse_timeout", 0):
                    current_app.logger.debug('Send ClientsList')
                    send_event(
                        bidder,
                        current_app.auction_bidders[bidder]["clients"],
                        "ClientsList"
                    )
                response = Response(
                    SseStream(
                        current_app.auction_bidders[bidder]["channels"][client_hash],
                        bidder_id=bidder,
                        client_id=client_hash,
                        timeout=session.get("sse_timeout", 0)
                    ),
                    direct_passthrough=True,
                    mimetype='text/event-stream',
                    content_type='text/event-stream'
                )
                response.headers['Cache-Control'] = 'no-cache'
                response.headers['X-Accel-Buffering'] = 'no'
                return response
            else:
                current_app.logger.info(
                    'Not valid bidder: bidder_id {} with client_hash {}'.format(bidder, client_hash),
                    extra=prepare_extra_journal_fields(request.headers)
                )

    current_app.logger.debug(
        'Disable event_source for unauthorized user.',
        extra=prepare_extra_journal_fields(request.headers)
    )
    events_close = PySse()
    events_close.add_message("Close", "Disable")
    response = Response(
        iter([bytearray(''.join([x for x in events_close]), 'UTF-8')]),
        direct_passthrough=True,
        mimetype='text/event-stream',
        content_type='text/event-stream'
    )
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response
