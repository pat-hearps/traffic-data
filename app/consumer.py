from datetime import datetime
import json
import time

from quixstreams import Application

from core.config import FWY_TOPIC, TZ_MELB
from core.utils import JEncoder


def main(freeway_topic: str = FWY_TOPIC):
    app = Application(
        broker_address="localhost:9092",
        loglevel="DEBUG",
        auto_offset_reset="earliest",
    )


    with app.get_consumer() as consumer:
        print(f"TOPICS=\n{consumer.list_topics()}")
        consumer.subscribe([freeway_topic])
        

        while True:
            msg = consumer.poll(1)

            if msg is None:
                print("Waiting...")
            elif msg.error() is not None:
                raise Exception(msg.error())
            else:
                key = msg.key().decode("utf8")
                data = parse_data(json.loads(msg.value()))
                offset = msg.offset()

                print(f"{offset = }\n{key = }\n{json.dumps(data, indent=4, cls=JEncoder)}")
                consumer.store_offsets(msg)
            time.sleep(2)


def parse_data(data: dict) -> dict:
    """A few basic data type transformations"""
    data["publishedTime"] = TZ_MELB.localize(datetime.fromisoformat(data["publishedTime"]))
    data["source"]["sourceId"] = int(data["source"]["sourceId"])
    return data


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass