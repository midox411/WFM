import pandas as pd
from pyspark.sql import SparkSession, functions as F


def _load_as_spark_df(spark: SparkSession, input_path: str):
    """Reads the Parquet file with pandas (handles nanosecond timestamps fine)
    then hands it to Spark via Arrow. Needed because Spark 3.5's native Parquet
    reader cannot read the TIMESTAMP(NANOS) logical type that pandas/pyarrow
    write by default (fails with 'Illegal Parquet type: INT64 (TIMESTAMP(NANOS))').
    Going through pandas + Arrow avoids that code path entirely - no need to
    touch how the simulator writes its files."""
    pdf = pd.read_parquet(input_path)
    for col in pdf.columns:
        if pd.api.types.is_datetime64_any_dtype(pdf[col]):
            pdf[col] = pdf[col].astype("datetime64[us]")

    spark.conf.set("spark.sql.execution.arrow.pyspark.enabled", "true")
    return spark.createDataFrame(pdf)


def run_aggregation(spark: SparkSession, input_path: str, output_dir: str) -> None:
    df = _load_as_spark_df(spark, input_path)

    df = df.withColumn(
        "interval_15min",
        F.from_unixtime((F.unix_timestamp("timestamp") / 900).cast("long") * 900).cast("timestamp"),
    ).withColumn("date", F.to_date("timestamp")) \
     .withColumn("hour", F.hour("timestamp"))

    agg_exprs = [
        F.count("*").alias("call_volume"),
        F.sum(F.when(F.col("disposition") == "answered", 1).otherwise(0)).alias("answered_count"),
        F.sum(F.when(F.col("disposition") == "abandoned", 1).otherwise(0)).alias("abandoned_count"),
        F.sum(F.when(F.col("disposition") == "transferred", 1).otherwise(0)).alias("transferred_count"),
        F.avg("wait_time_sec").alias("avg_wait_time_sec"),
        F.avg("handle_time_sec").alias("avg_handle_time_sec"),
    ]

    volume_15min = df.groupBy("interval_15min", "skill_id").agg(*agg_exprs) \
        .orderBy("interval_15min", "skill_id")

    volume_hourly = df.groupBy("date", "hour", "skill_id").agg(*agg_exprs) \
        .orderBy("date", "hour", "skill_id")

    volume_daily = df.groupBy("date", "skill_id").agg(*agg_exprs) \
        .orderBy("date", "skill_id")

    volume_15min.coalesce(1).write.mode("overwrite").parquet(f"{output_dir}/volume_15min")
    volume_hourly.coalesce(1).write.mode("overwrite").parquet(f"{output_dir}/volume_hourly")
    volume_daily.coalesce(1).write.mode("overwrite").parquet(f"{output_dir}/volume_daily")

    print(f"volume_15min: {volume_15min.count()} rows")
    print(f"volume_hourly: {volume_hourly.count()} rows")
    print(f"volume_daily: {volume_daily.count()} rows")


if __name__ == "__main__":
    spark = SparkSession.builder.appName("wfm_call_volume_aggregation_local").getOrCreate()
    run_aggregation(spark, "/opt/wfm_data/raw/call_events.parquet", "/opt/wfm_data/processed")
    spark.stop()