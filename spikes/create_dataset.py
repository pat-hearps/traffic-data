from google.cloud import bigquery

from core.config import BQ_RAW_ZONE, BQ_SILVER, DATASET_LOCATION, GCS_PROJECT
from core.log_config import get_logger

log = get_logger(__name__)

def datasets_exist(datasets_req: list[str] = [BQ_RAW_ZONE, BQ_SILVER]):
    """Idempotently make sure BQ datasets exist as configured"""
    client = bigquery.Client()

    datasets_exist = [ds.dataset_id for ds in client.list_datasets()]

    log.info(f"datasets existing= {datasets_exist}")
    
    missing = [ds for ds in datasets_req if ds not in datasets_exist]

    if len(missing):
        log.info(f"Missing datasets: {missing}")

        for dataset in missing:
            create_dataset(dataset, client)
            

def create_dataset(dataset_id: str, client: bigquery.Client, location: str = DATASET_LOCATION):
    # From https://cloud.google.com/bigquery/docs/datasets
    log.info(f"Creating dataset {dataset_id}")
    dataset = bigquery.Dataset(f"{GCS_PROJECT}.{dataset_id}")
    # Specify the geographic location where the dataset should reside.
    dataset.location = location
    dataset = client.create_dataset(dataset, timeout=30)
    log.info(f"Created dataset {dataset.full_dataset_id}")


if __name__ == "__main__":
    datasets_exist()
