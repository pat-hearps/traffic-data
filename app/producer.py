import json

from quixstreams import Application
import requests

from core.config import API_KEY_TRAFFIC, URL_TRAFFIC, KAFKA_ADDR

headers = {
    "Cache-Control": "no-cache",
    "Ocp-Apim-Subscription-Key": API_KEY_TRAFFIC
}
SEG_KEY_1 = "Chandler Hwy to Hoddle St"

def main():
    app = Application(
        broker_address=KAFKA_ADDR,
        loglevel="DEBUG"
    )


    resp = requests.get(url=URL_TRAFFIC, headers=headers)

    if resp.status_code != 200:
        raise Exception(resp.text)

    rdict = resp.json()
    segment_properties = features_as_topic_dict(rdict['features'])

    if (segment := segment_properties.get(SEG_KEY_1)):
        pass

        
        with app.get_producer() as producer:

            producer.produce(
                topic="MELBOURNE_TRAFFIC",
                key=SEG_KEY_1,
                value=json.dumps(segment),
            )

            

def features_as_topic_dict(features: list[dict]) -> dict:
    segment_props = {}
    for feat in features:
        props = feat.get('properties')
        sgn = props.get('segmentName')
        if sgn:
            segment_props[sgn] = props
    print(f"Found {len(segment_props)} features with properties")
    return segment_props


if __name__ == '__main__':
    main()
