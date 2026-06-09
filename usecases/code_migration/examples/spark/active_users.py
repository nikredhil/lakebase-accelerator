# Monthly active customers (distinct customers with a completed order per month).
# Already in the transform(spark) shape — exercises the "easy" near-identity path.
from pyspark.sql import functions as F


def transform(spark):
    orders = spark.table("orders")
    return (
        orders.filter(F.col("status") == "completed")
        .withColumn("order_month", F.date_format(F.col("order_date"), "yyyy-MM"))
        .groupBy("order_month")
        .agg(F.countDistinct("customer_id").alias("active_customers"))
        .orderBy("order_month")
    )
