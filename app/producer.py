from collections import defaultdict
import json

from quixstreams import Application
import requests

from core.config import API_KEY_TRAFFIC, URL_TRAFFIC, KAFKA_ADDR, FWY_TOPIC, FWY_FILTER

from core.log_config import get_logger

log = get_logger(__name__)

headers = {
    "Cache-Control": "no-cache",
    "Ocp-Apim-Subscription-Key": API_KEY_TRAFFIC
}

def main():
    log.info("Hitting traffic API")
    resp = requests.get(url=URL_TRAFFIC, headers=headers)

    if resp.status_code != 200:
        raise Exception(resp.text)

    
    # initial processing into format needed to log by topic=freeway, key=segment
    resp_dict = resp.json()
    segment_properties = features_as_segment_dict(resp_dict['features'])
    freeway_segments = group_segments_by_freeway(segment_properties)
    filtered_segments = freeway_segments[FWY_FILTER]


    log.info("Connecting to kafka application")
    app = Application(
        broker_address=KAFKA_ADDR,
        loglevel="DEBUG",
        auto_create_topics=True
    )


    # need to create freeway topic
    fwy_topic = app.topic(FWY_TOPIC)

    with app.get_producer() as producer:
        log.info(f"producing {len(filtered_segments)} segments for {FWY_FILTER}")
        for seg_name, properties in filtered_segments.items():
            log.info(f"logging segment {seg_name}")

            producer.produce(
                topic=FWY_TOPIC,
                key=seg_name,
                value=json.dumps(properties),
            )
            log.info("segment logged")
    log.info("Finished")



def features_as_segment_dict(features: list[dict]) -> dict:
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


def group_segments_by_freeway(properties_by_segment: dict) -> dict:
    """Reorganise segments to nested dict by each freeway"""
    freeway_segments = defaultdict(dict)
    for segment, properties in properties_by_segment.items():
        freeway = properties["freewayName"]
        freeway_segments[freeway][segment] = properties
    return dict(freeway_segments)

if __name__ == '__main__':
    main()

