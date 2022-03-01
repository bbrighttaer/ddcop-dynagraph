import datetime
import os

import pika

import config
import handlers
import logger
import messaging
import random

random.seed(0)

log = logger.get_logger('Factory')


def on_message(ch, method, properties, body):
    msg = eval(body.decode('utf-8'))
    func = handlers.directory.get(msg['type'], None)

    if func:
        func(msg)
    else:
        log.warning(f'Message type {msg["type"]} has no handler')


if __name__ == '__main__':
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=config.BROKER_URL, port=config.BROKER_PORT))
        channel = connection.channel()
        print('Connected to broker')
        channel.exchange_declare(exchange=messaging.COMM_EXCHANGE, exchange_type='topic')

        # factory queue
        queue_name = 'factory-queue'
        channel.queue_declare(queue=queue_name, exclusive=True)

        # register topics (aka routing keys) associated to the factory queue
        channel.queue_bind(exchange=messaging.COMM_EXCHANGE,
                           queue=queue_name,
                           routing_key=f'{messaging.DASHBOARD_COMMAND_CHANNEL}.#')

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

        channel.start_consuming()
    except ConnectionError as e:
        log.error(str(e))
