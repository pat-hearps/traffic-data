import gcsfs

from core.config import GCS_PROJECT

print("trying to acquire gc filesystem")
fs = gcsfs.GCSFileSystem(token="google_default",
                         project=GCS_PROJECT,
                         access="read_write")
print("GCSFS acquired")

def write_df_pqt(df, destination: str):
    print(f"attempting to open fs destination: {destination}")
    # Write the DataFrame to a Parquet file directly in GCS
    with fs.open(destination, mode='wb') as f:
        print("destination open, writing parquet")
        df.write_parquet(f)
    
    print(f"df written to {destination}")
