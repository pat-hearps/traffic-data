from decouple import config

API_KEY = config("API_KEY", cast=str)
