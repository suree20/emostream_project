from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_timestamp, window, when, lit
from pyspark.sql.types import StringType, StructType, StructField

spark = SparkSession.builder \
    .appName("EmojiStreamingApp") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0") \
    .config("spark.streaming.stopGracefullyOnShutdown", "true") \
    .config("spark.sql.shuffle.partitions", "200") \
    .config("spark.sql.legacy.timeParserPolicy", "LEGACY")\
    .getOrCreate()

schema = StructType([
    StructField("user_id", StringType(), True),
    StructField("emoji_type", StringType(), True),
    StructField("timestamp", StringType(), True)
])

emoji_df = spark \
    .readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9092") \
    .option("subscribe", "emoji_topic") \
    .option("startingOffsets", "latest") \
    .load()

emoji_values = emoji_df.selectExpr("CAST(value AS STRING)")
emoji_data = emoji_values.selectExpr(
    "json_tuple(value, 'user_id', 'emoji_type', 'timestamp') as (user_id, emoji_type, timestamp)"
)

emoji_data = emoji_data.withColumn(
    "timestamp", 
    to_timestamp(col("timestamp"), "yyyy-MM-dd'T'HH:mm:ss.SSSSSS") 
)

emoji_data_with_watermark = emoji_data \
    .withWatermark("timestamp", "1 minute")

emoji_data_aggregated = emoji_data_with_watermark \
    .groupBy("emoji_type", window("timestamp", "1 minute")) \
    .count() \
    .withColumn(
        "scaled_count",
        when(col("count") <= 1000, lit(1)).otherwise(col("count") / 1000) 
    ) \
    .select("emoji_type", "scaled_count", "window")

query = emoji_data_aggregated.writeStream \
    .format("console") \
    .outputMode("complete") \
    .trigger(processingTime="2 seconds") \
    .start()

query.awaitTermination()
