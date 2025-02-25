from decouple import config
import pytz

API_KEY_TRAFFIC = config("API_KEY_TRAFFIC", cast=str)

GCS_PROJECT = config("GCS_PROJECT", cast=str)
GCS_BUCKET = config("GCS_BUCKET", cast=str)

ENVIRONMENT = config("ENVIRONMENT", cast=str, default="local")

if ENVIRONMENT == "local":
    KAFKA_ADDR = "localhost:9092"
else:
    KAFKA_ADDR = config("KAFKA_ADDR", cast=str)

URL_TRAFFIC = "https://data-exchange-api.vicroads.vic.gov.au/opendata/variable/freewaytraveltime/v1/traffic"

FWY_FILTER = "Eastern Fwy"
FWY_TOPIC = FWY_FILTER.replace(" ", "_")

MELB_TZ_NAME = "Australia/Melbourne"
TZ_MELB = pytz.timezone(MELB_TZ_NAME)


