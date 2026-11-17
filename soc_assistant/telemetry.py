"""Separate authentication/endpoint normalization. Not joined to KDD records."""
def normalize_auth(record):
    required={'timestamp','user','source_ip','success'}
    if not required<=record.keys(): raise ValueError('Missing authentication fields')
    if not isinstance(record['success'],bool): raise ValueError('success must be boolean')
    return {'type':'authentication',**record}

def normalize_endpoint(record):
    required={'timestamp','host','process_name','parent_process'}
    if not required<=record.keys(): raise ValueError('Missing endpoint fields')
    return {'type':'endpoint',**record}

def spark_auth_features(frame):
    """Requires timestamp (timestamp), user, source_ip, success (boolean)."""
    from pyspark.sql import functions as F
    return frame.groupBy(F.window('timestamp','5 minutes'),'user','source_ip').agg(F.count('*').alias('attempts'),F.sum(F.when(~F.col('success'),1).otherwise(0)).alias('failed_attempts'))
