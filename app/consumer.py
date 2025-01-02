from quixstreams import Application
import json
SEG_KEY_1 = "Chandler Hwy to Hoddle St"

def main():
    app = Application(
        broker_address="localhost:9092",
        loglevel="DEBUG",
        auto_offset_reset="earliest",
    )

    with app.get_consumer() as consumer:
        consumer.subscribe(["MELBOURNE_TRAFFIC"])

        while True:
            msg = consumer.poll(1)

            if msg is None:
                print("Waiting...")
            elif msg.error() is not None:
                raise Exception(msg.error())
            else:
                key = msg.key().decode("utf8")
                value = json.loads(msg.value())
                offset = msg.offset()

                print(f"{offset} {key} {value}")
                consumer.store_offsets(msg)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass