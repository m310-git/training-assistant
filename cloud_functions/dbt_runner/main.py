import functions_framework
import json
import subprocess
from datetime import datetime
from google.cloud import bigquery

bq_client = bigquery.Client()

def run_dbt(command, select=None):
    cmd = ["dbt", command, "--project-dir", "/workspace/dbt"]
    if select:
        cmd.extend(["--select", select])
    result = subprocess.run(cmd, capture_output=True, text=True)
    print(f"dbt {command} stdout: {result.stdout}")
    print(f"dbt {command} stderr: {result.stderr}")
    if result.returncode != 0:
        raise Exception(f"dbt {command} failed: {result.stderr}")
    return result.stdout

def retrain_ml_model():
    query = """
        CREATE OR REPLACE MODEL mart.training_predictor
        OPTIONS(
            model_type = 'BOOSTED_TREE_REGRESSOR',
            input_label_cols = ['next_weight_kg'],
            num_trials = 5,
            max_iterations = 50,
            early_stop = TRUE,
            data_split_method = 'AUTO_SPLIT'
        ) AS
        WITH training_pairs AS (
            SELECT
                user_id, exercise_id, set_number, training_date,
                weight_kg, reps, volume, rpe,
                LAG(weight_kg) OVER w AS prev_weight_kg,
                LAG(reps) OVER w AS prev_reps,
                LAG(rpe) OVER w AS prev_rpe,
                LAG(volume) OVER w AS prev_volume,
                DATE_DIFF(training_date, LAG(training_date) OVER w, DAY) AS days_since_last,
                weight_kg AS next_weight_kg
            FROM mart.fct_training_set
            WINDOW w AS (
                PARTITION BY user_id, exercise_id, set_number
                ORDER BY training_date
            )
        )
        SELECT
            prev_weight_kg, prev_reps, prev_rpe, prev_volume,
            set_number, days_since_last, next_weight_kg
        FROM training_pairs
        WHERE prev_weight_kg IS NOT NULL
          AND days_since_last IS NOT NULL
    """
    bq_client.query(query).result()
    print("ML model retrained successfully")

@functions_framework.http
def handle_daily_pipeline(request):
    """日次パイプライン: dbt run + test + ML再学習（月曜のみ）"""
    try:
        # 1. dbt run
        run_dbt("run")

        # 2. dbt test
        run_dbt("test")

        # 3. ML再学習（月曜のみ）
        today = datetime.now().weekday()  # 0=月曜
        if today == 0:
            retrain_ml_model()
            run_dbt("run", select="m_ml_suggestion")

        return json.dumps({"status": "completed"})

    except Exception as e:
        print(f"Pipeline error: {e}")
        return json.dumps({"status": "error", "message": str(e)}), 500