from datetime import datetime
import json
import time

import polars as pl
from quixstreams import Application

from core.config import FWY_TOPIC, MELB_TZ_NAME, GCS_BUCKET, TZ_MELB
from core.log_config import get_logger
from core.utils import JEncoder

log = get_logger(__name__)


def main(freeway_topic: str = FWY_TOPIC):
    app = Application(
        broker_address="localhost:9092",
        loglevel="DEBUG",
        auto_offset_reset="earliest",
    )


    with app.get_consumer() as consumer:
        print(f"TOPICS=\n{consumer.list_topics()}")
        consumer.subscribe([freeway_topic])
        
        messages = []
        while True:
            
            msg = consumer.poll(1)

            if msg is None:
                if messages:
                    
                    now = datetime.now(tz=TZ_MELB)
                    df = pl.DataFrame(messages)
                    df = dateparse_df(df)
                    log.info(f"Message queue empty, writing current data (len={len(df)}) to storage at {now.isoformat()}")
                    log.info(f"dataframe=\n{df}")
                    filepath = f"{now.strftime("%Y/%m/%d")}/data_{now.strftime("%H%M%S")}.pqt"
                    destination = f"gs://{GCS_BUCKET}/raw1/{filepath}"

                    from app.cloud import write_df_pqt
                    write_df_pqt(df, destination)

                    # clear data from memory
                    del df
                    messages = []

                log.info("Waiting...")
                time.sleep(10)

            elif msg.error() is not None:
                raise Exception(msg.error())
            else:
                key = msg.key().decode("utf8")
                data = parse_data(json.loads(msg.value()))
                messages.append(data)
                offset = msg.offset()

                log.debug(f"{offset = }\n{key = }\n{json.dumps(data, indent=4, cls=JEncoder)}")
                consumer.store_offsets(msg)
            

def dateparse_df(df: pl.DataFrame, dt_col: str = 'publishedTime') -> pl.DataFrame:
    df = df.with_columns(publishedTime=pl.col(dt_col).str.to_datetime().cast(pl.Datetime).dt.replace_time_zone(MELB_TZ_NAME))
    return df

def parse_data(data: dict) -> dict:
    """A few basic data type transformations"""
    data["id"] = int(data["source"]["sourceId"])
    data["parentPathId"] = int(data["parentPathId"])
    del data["freewayName"]  # it's only ended up here because we've filtered to this freeway name
    del data["source"]  # don't need, we have id, and extra dict nesting will be more confusing
    return data


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
