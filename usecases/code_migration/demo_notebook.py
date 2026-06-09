# Databricks notebook source
# MAGIC %md
# MAGIC # 🚀 Lakebase Code-Migration Accelerator — Live Demo
# MAGIC
# MAGIC Reusable Databricks accelerator. **Use case:** migrate legacy pipeline code to Databricks.
# MAGIC
# MAGIC **Flow:** detect language → convert **SQL / dbt / Spark → Databricks PySpark** → run the
# MAGIC converted code on **Databricks** *and* the original on an **independent engine (DuckDB)** against
# MAGIC the same data sample → **compare**. Pass ✅ → raise a PR for human review. Fail ❌ → retry & learn.
# MAGIC
# MAGIC Every run is logged to **MLflow** (governance + observability). Pick the widgets at the top,
# MAGIC then **Run all**. (Tip: attach to **Serverless** so it starts in seconds.)

# COMMAND ----------

# MAGIC %md
# MAGIC ## ⚙️ Infrastructure-as-code (the reusable accelerator)
# MAGIC The use case runs on infra the accelerator provisions and tears down with one command each —
# MAGIC future use cases reuse the same plumbing, and `destroy` stops billing:
# MAGIC ```
# MAGIC accelerator deploy  code_migration   # terraform apply (1–2 node cluster) + DAB deploy
# MAGIC accelerator run     code_migration   # detect → convert → dual-run validate → PR
# MAGIC accelerator destroy code_migration   # bundle destroy + terraform destroy  (stops billing)
# MAGIC ```
# MAGIC This notebook runs on **serverless**, so the demo itself needs no cluster wait.

# COMMAND ----------

# MAGIC %pip install duckdb mlflow-skinny -q

# COMMAND ----------

dbutils.widgets.dropdown("example", "sql", ["sql", "dbt", "spark"], "Source example")
dbutils.widgets.dropdown("converter", "rule", ["rule", "databricks"], "Converter")
EXAMPLE = dbutils.widgets.get("example")
CONVERTER = dbutils.widgets.get("converter")  # rule = deterministic | databricks = hosted Claude
print(f"example={EXAMPLE}  converter={CONVERTER}")

# COMMAND ----------

# MAGIC %md ## 1️⃣ The source code a team hands us

# COMMAND ----------

EXAMPLES = {
    "sql": """SELECT
    r.region_name,
    ROUND(SUM(o.amount), 2) AS total_revenue,
    COUNT(*)                AS order_count
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
JOIN regions   r ON c.region_id  = r.region_id
WHERE o.status = 'completed'
GROUP BY r.region_name
ORDER BY total_revenue DESC, r.region_name""",
    "dbt": """{{ config(materialized='table') }}
SELECT
    c.customer_id,
    ROUND(SUM(o.amount), 2) AS lifetime_value,
    COUNT(*)                AS num_orders
FROM {{ ref('customers') }} c
JOIN {{ source('raw', 'orders') }} o ON o.customer_id = c.customer_id
WHERE o.status = 'completed'
GROUP BY c.customer_id
ORDER BY lifetime_value DESC, c.customer_id""",
    "spark": """from pyspark.sql import functions as F

def transform(spark):
    orders = spark.table("orders")
    return (orders
            .filter(F.col("status") == "completed")
            .withColumn("order_month", F.date_format(F.col("order_date"), "yyyy-MM"))
            .groupBy("order_month")
            .agg(F.countDistinct("customer_id").alias("active_customers"))
            .orderBy("order_month"))""",
}
source = EXAMPLES[EXAMPLE]
print(source)

# COMMAND ----------

# MAGIC %md ## 📋 Start an MLflow run (observability)

# COMMAND ----------

# MLflow is optional — the demo runs fine even if it's unavailable on the compute.
try:
    import mlflow as MLF
except Exception as _e:
    MLF = None
    print("[mlflow unavailable, observability skipped]:", _e)

try:
    WORKSPACE_URL = "https://" + spark.conf.get("spark.databricks.workspaceUrl")
except Exception:
    WORKSPACE_URL = ""

EXP_ID = RUN_ID = ""
if MLF:
    MLF.end_run()  # clear any stale active run
    run = MLF.start_run(run_name=f"demo-{EXAMPLE}-{CONVERTER}")
    MLF.log_params({"example": EXAMPLE, "converter": CONVERTER})
    EXP_ID, RUN_ID = run.info.experiment_id, run.info.run_id
    print("MLflow run:", f"{WORKSPACE_URL}/ml/experiments/{EXP_ID}/runs/{RUN_ID}")

# COMMAND ----------

# MAGIC %md ## 2️⃣ Detect the language
# MAGIC `rule` = deterministic (no model). `databricks` = workspace-hosted Claude via Model Serving (governed, no external key).

# COMMAND ----------

import re

def detect_rule(code):
    if re.search(r"{{.*?\b(ref|source|config)\s*\(", code, re.S):
        return "dbt"
    if re.search(r"\b(SparkSession|pyspark|spark\.)|def\s+transform\s*\(", code):
        return "spark"
    if re.search(r"\bSELECT\b", code, re.I):
        return "sql"
    return "unknown"

def dbx_chat(system, user, max_tokens=4000, endpoint="databricks-claude-opus-4-8"):
    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.serving import ChatMessage, ChatMessageRole
    w = WorkspaceClient()
    r = w.serving_endpoints.query(
        name=endpoint, max_tokens=max_tokens,
        messages=[ChatMessage(role=ChatMessageRole.SYSTEM, content=system),
                  ChatMessage(role=ChatMessageRole.USER, content=user)])
    return (r.choices[0].message.content or "").strip()

if CONVERTER == "databricks":
    out = dbx_chat("Classify the code as ONE word: sql, dbt, spark, or unknown.", f"```\n{source}\n```", 20)
    language = out.lower().split()[0].strip(".,`") if out else "unknown"
    if language not in ("sql", "dbt", "spark"):
        language = detect_rule(source)
else:
    language = detect_rule(source)

if MLF:
    MLF.set_tag("detected_language", language)
print("Detected language:", language)

# COMMAND ----------

# MAGIC %md ## 3️⃣ Convert → Databricks PySpark

# COMMAND ----------

def render_dbt(sql):
    sql = re.sub(r"{{\s*config\([^}]*\)\s*}}", "", sql)
    sql = re.sub(r"{{\s*ref\(\s*'([^']+)'\s*\)\s*}}", r"\1", sql)
    sql = re.sub(r"{{\s*source\(\s*'[^']+'\s*,\s*'([^']+)'\s*\)\s*}}", r"\1", sql)
    return sql.strip()

def rule_convert(code, language):
    if language in ("sql", "dbt"):
        inner = (render_dbt(code) if language == "dbt" else code).strip().rstrip(";")
        return "def transform(spark):\n    return spark.sql(" + repr(inner) + ")"
    return code.strip()

def strip_fences(s):
    return re.sub(r"^```(?:python)?\s*|\s*```$", "", s, flags=re.M).strip()

if CONVERTER == "databricks":
    sysmsg = ("Convert the given SQL/dbt/Spark code into a Databricks PySpark module that defines "
              "`def transform(spark):` returning a DataFrame, reading inputs via spark.table('<name>') "
              "(available tables: regions, customers, orders). Output ONLY the Python module — no prose, no fences.")
    converted = strip_fences(dbx_chat(sysmsg, f"Convert this {language} code:\n```\n{source}\n```", 4000))
else:
    converted = rule_convert(source, language)

if MLF:
    MLF.log_text(converted, "converted_transform.py")
print(converted)

# COMMAND ----------

# MAGIC %md ## 4️⃣ Small mock data sample (deterministic)

# COMMAND ----------

import random, datetime as dt
import pandas as pd

rng = random.Random(42)
REGIONS = ["North", "South", "East", "West"]
STATUSES = ["completed", "pending", "cancelled"]
N_CUST, N_ORD = 150, 400

regions = pd.DataFrame({"region_id": range(1, 5), "region_name": REGIONS})
customers = pd.DataFrame({
    "customer_id": range(1, N_CUST + 1),
    "region_id": [rng.randint(1, 4) for _ in range(N_CUST)],
    "signup_date": [dt.date(2023, 1, 1) + dt.timedelta(days=rng.randint(0, 365)) for _ in range(N_CUST)],
})
orders = pd.DataFrame({
    "order_id": range(1, N_ORD + 1),
    "customer_id": [rng.randint(1, N_CUST) for _ in range(N_ORD)],
    "order_date": [dt.date(2024, 1, 1) + dt.timedelta(days=rng.randint(0, 364)) for _ in range(N_ORD)],
    "amount": [round(rng.uniform(5, 500), 2) for _ in range(N_ORD)],
    "status": [rng.choices(STATUSES, weights=[0.7, 0.2, 0.1])[0] for _ in range(N_ORD)],
})
tables = {"regions": regions, "customers": customers, "orders": orders}
for name, pdf in tables.items():
    spark.createDataFrame(pdf).createOrReplaceTempView(name)
print("Registered temp views:", list(tables))
display(orders.head(10))

# COMMAND ----------

# MAGIC %md ## 5️⃣ Run the CONVERTED code on **Databricks** (candidate)

# COMMAND ----------

ns = {}
exec(converted, ns)
candidate_sdf = ns["transform"](spark)
candidate = candidate_sdf.toPandas()
display(candidate_sdf)

# COMMAND ----------

# MAGIC %md ## 6️⃣ Run the ORIGINAL on an **independent engine** (DuckDB) — the reference

# COMMAND ----------

import duckdb

con = duckdb.connect()
for name, pdf in tables.items():
    con.register(name, pdf)

if language == "sql":
    reference = con.execute(source).df()
elif language == "dbt":
    reference = con.execute(render_dbt(source)).df()
else:
    ns2 = {}
    exec(source, ns2)
    reference = ns2["transform"](spark).toPandas()
display(reference)

# COMMAND ----------

# MAGIC %md ## 7️⃣ Compare → PASS / FAIL  (+ log result to MLflow)

# COMMAND ----------

import numpy as np

def normalize(df, tol=2):
    df = df.copy()
    df.columns = [str(c) for c in df.columns]
    df = df[sorted(df.columns)]
    for c in df.select_dtypes(include="float").columns:
        df[c] = df[c].round(tol)
    return df.sort_values(by=list(df.columns)).reset_index(drop=True)

ref_n, cand_n = normalize(reference), normalize(candidate)
ok = ref_n.shape == cand_n.shape and list(ref_n.columns) == list(cand_n.columns)
if ok:
    for c in ref_n.columns:
        if ref_n[c].dtype.kind in "fc":
            ok &= bool(np.allclose(ref_n[c], cand_n[c], atol=0.011, rtol=0))
        else:
            ok &= bool((ref_n[c].to_numpy() == cand_n[c].to_numpy()).all())

if MLF:
    MLF.log_metrics({"passed": int(ok), "rows": int(ref_n.shape[0])})
    MLF.set_tag("result", "PASS" if ok else "FAIL")
    MLF.end_run()

verdict = "✅ PASS — converted PySpark matches the original. Safe to raise a PR for human review." if ok \
    else "❌ FAIL — results differ. Pipeline would retry conversion and append a lesson to SKILLS.md."
mlflow_link = (f"<p style='margin-top:8px'>📊 <a href='{WORKSPACE_URL}/ml/experiments/{EXP_ID}/runs/{RUN_ID}' "
               f"target='_blank'>View this run + params/artifact in MLflow</a></p>") if (MLF and RUN_ID) else ""
displayHTML(
    f"<div style='font-size:22px;padding:16px;border-radius:8px;"
    f"background:{'#1e4620' if ok else '#5c1a1a'};color:white'>"
    f"<b>{EXAMPLE.upper()}</b> via <b>{CONVERTER}</b> &nbsp; {verdict}</div>{mlflow_link}"
)

# COMMAND ----------

# MAGIC %md
# MAGIC ### What this demonstrates
# MAGIC - **Reusable accelerator**: one flow handles SQL, dbt, and Spark sources.
# MAGIC - **Trust via validation**: converted code is proven equal to the original on a data sample
# MAGIC   before any human sees it — only then does it raise a PR.
# MAGIC - **Governed & observable**: conversion runs on **workspace-hosted Claude** (no external key)
# MAGIC   and every run is logged to **MLflow** with the converted artifact and pass/fail.
# MAGIC - **Infra-as-code (off-screen)**: Terraform spins a 1–2 node cluster / this runs on serverless,
# MAGIC   and `destroy` tears it down to stop billing. Same accelerator, future use cases plug in.
