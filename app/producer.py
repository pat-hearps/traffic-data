
import requests
from core.config import API_KEY_TRAFFIC, URL_TRAFFIC

headers = {
    "Cache-Control": "no-cache",
    "Ocp-Apim-Subscription-Key": API_KEY_TRAFFIC
}
TOPIC_1 = "Chandler Hwy to Hoddle St"

def main():

    resp = requests.get(url=URL_TRAFFIC, headers=headers)

    if resp.status_code != 200:
        raise Exception(resp.text)

    rdict = resp.json()
    segment_properties = features_as_topic_dict(rdict['features'])

    if (segment := segment_properties.get(TOPIC_1)):
        pass






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
