import datetime
import os
import argparse
import time

import pika

import config
import handlers
import logger
import messaging
import random

from mascoord.utils import time_since

random.seed(0)

log = logger.get_logger('Factory')

start_time = time.time()


def on_message(ch, method, properties, body):
    msg = eval(body.decode('utf-8'))
    func = handlers.directory.get(msg['type'], None)

    if func:
        func(msg)
    else:
        log.warning(f'Message type {msg["type"]} has no handler')

    sim_time = time_since(start_time)
    log.info(f'Up time: {sim_time}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Dynamic DCOP Algorithms')
    parser.add_argument(
        '-a',
        '--algorithm',
        dest='alg',
        type=str,
        choices=['c-cocoa', 'sdpop'],
        required=True,
        help='The DCOP algorithm to be used with the Dynamic Graph algorithm',
    )
    parser.add_argument(
        '-d',
        '--domain_size',
        type=int,
        required=True,
        help='The number of discrete points in the domain of the agent',
    )

    args = parser.parse_args()
    handlers.set_dcop_algorithm(args.alg)
    handlers.set_domain_size(args.domain_size)

    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(
            host=config.BROKER_URL,
            port=config.BROKER_PORT,
            heartbeat=0,  # only for experiment purposes - not recommended (https://www.rabbitmq.com/heartbeats.html)
            credentials=pika.credentials.PlainCredentials(config.PIKA_USERNAME, config.PIKA_PASSWORD))
        )
        channel = connection.channel()
        log.info(f'Connected to broker, domain_size = {handlers.domain_size}')
        channel.exchange_declare(exchange=messaging.COMM_EXCHANGE, exchange_type='topic')

        # factory queue
        queue_name = 'factory-queue'
        channel.queue_declare(queue=queue_name, exclusive=True)

        # register topics (aka routing keys) associated to the factory queue
        channel.queue_bind(exchange=messaging.COMM_EXCHANGE,
                           queue=queue_name,
                           routing_key=f'{messaging.DASHBOARD_COMMAND_CHANNEL}.#')
        channel.queue_bind(exchange=messaging.COMM_EXCHANGE,
                           queue=queue_name,
                           routing_key=f'{messaging.FACTORY_COMMAND_CHANNEL}.#')

        # subscribe to dashboard commands
        channel.basic_consume(queue=queue_name, on_message_callback=on_message, auto_ack=True)

        # send available simulations to dashboard
        simulations = os.listdir('simulations')
        if simulations:
            parsed_sim = [{
                'date': str(datetime.datetime.fromtimestamp(eval(sim.removesuffix('.sim')))),
                'filename': sim,
            } for sim in simulations if '.sim' in sim]
            channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                                  routing_key=f'{messaging.MONITORING_CHANNEL}',
                                  body=messaging.create_saved_simulations_report({
                                      'simulations': parsed_sim,
                                  }))

        # report algorithm in use
        channel.basic_publish(exchange=messaging.COMM_EXCHANGE,
                              routing_key=f'{messaging.MONITORING_CHANNEL}',
                              body=messaging.create_dcop_algorithm_report({
                                  'dcop': args.alg,
                              }))

        channel.start_consuming()
    except ConnectionError as e:
        log.error(str(e))
