import json

from quixstreams import Application
import requests

from core.config import API_KEY_TRAFFIC, URL_TRAFFIC, KAFKA_ADDR

from core.log_config import get_logger

log = get_logger(__name__)

headers = {
    "Cache-Control": "no-cache",
    "Ocp-Apim-Subscription-Key": API_KEY_TRAFFIC
}
SEG_KEY_1 = "Chandler Hwy to Hoddle St"

def main():
    log.info("Hitting traffic API")
    resp = requests.get(url=URL_TRAFFIC, headers=headers)

    if resp.status_code != 200:
        raise Exception(resp.text)

    log.info("Connecting to kafka application")
    app = Application(
        broker_address=KAFKA_ADDR,
        loglevel="DEBUG",
        auto_create_topics=True
    )


    rdict = resp.json()

    segment_properties = features_as_topic_dict(rdict['features'])

    if (segment := segment_properties.get(SEG_KEY_1)):

        log.info(f"logging segment {SEG_KEY_1}")
        
        with app.get_producer() as producer:

            producer.produce(
                topic="MELBOURNE_TRAFFIC",
                key=SEG_KEY_1,
                value=json.dumps(segment),
            )

        log.info("segment logged")
    log.info("Finished")



def features_as_topic_dict(features: list[dict]) -> dict:
    """Turn list of individual road segment (feature) dictionaries into
    a dictionary with keys = each unique segment name.
    """
    properties_by_segment = {}
    for feat in features:
        properties = feat.get('properties')       
        if seg_name := properties.get('segmentName'):
            properties_by_segment[seg_name] = properties
    log.info(f"Found {len(properties_by_segment)} features with properties")
    return properties_by_segment


if __name__ == '__main__':
    main()
