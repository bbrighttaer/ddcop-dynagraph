require('dotenv').config();
const {Server} = require("socket.io");
const messaging = require("./messaging");
const amqp = require("amqplib/callback_api");
const config = require("./config");
const moment = require("moment");


// amqp
amqp.connect(`amqp://${config.AMQP_BROKER_URL}:${config.AMQP_BROKER_PORT}`, (error0, connection) => {
    if (error0) {
        console.log('Error connecting to AMQP broker: ', error0.toString());
    } else {
        console.log('Connected to AMQP broker');
    }

    connection.createChannel((error1, channel) => {
        if (error1) {
            console.log('Error creating channel: ', error1.toString());
        }

        // socket
        const io = new Server(Number(config.SOCKET_PORT), { /* options */});
        io.on("connection", socket => {
            socket.on(messaging.EVT_DASHBOARD_COMMAND, (data) => {
                console.log(`[${moment().format()}] --> Factory`, data);

                // send to broker
                channel.publish(
                    messaging.COMM_EXCHANGE,
                    messaging.DASHBOARD_COMMAND_CHANNEL,
                    Buffer.from(JSON.stringify(data))
                );
            });
        });

        channel.assertExchange(messaging.COMM_EXCHANGE, 'topic', {
            durable: false,
        }, (error2, exchange) => {
            if (error2) {
                console.log('Error creating exchange: ', error2.toString());
            }

            channel.assertQueue(messaging.QUEUE_NAME, {
                exclusive: true,
            }, (error3, q) => {
                if (error3) {
                    console.log('Error creating queue: ', q.toString());
                }

                // bind topics to queue
                const topics = [`${messaging.MONITORING_CHANNEL}.#`];
                topics.forEach((topic) => {
                    channel.bindQueue(q.queue, messaging.COMM_EXCHANGE, topic);
                });

                // subscribe
                channel.consume(q.queue, (data) => {
                    console.log(`[${moment().format()}] <-- Dashboard: `, data.content.toString());

                    // send to dashboard
                    io.emit(messaging.EVT_BROKER_TO_DASHBOARD, JSON.parse(data.content.toString()));
                }, {
                    noAck: true,
                    exclusive: true,
                    noLocal: true,
                });
            });
        });
    });
});