"""
Prefect Flow: dbt run + dbt test
Phase 3: Cloud Scheduler + Cloud Functionsを置換
"""
import subprocess
from prefect import flow, task
from prefect_gcp import GcpCredentials


@task
def run_dbt_run():
    """dbt runを実行"""
    cmd = ["venv\\Scripts\\dbt.exe", "run", "--project-dir", "dbt"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"dbt run failed: {result.stderr}")
    return result.stdout


@task
def run_dbt_test():
    """dbt testを実行"""
    cmd = ["venv\\Scripts\\dbt.exe", "test", "--project-dir", "dbt"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"dbt test failed: {result.stderr}")
    return result.stdout


@flow(name="dbt-daily-pipeline")
def dbt_daily_pipeline():
    """日次dbtパイプライン: dbt run + dbt test"""
    # dbt run実行
    run_output = run_dbt_run()
    print(f"dbt run output: {run_output}")
    
    # dbt test実行
    test_output = run_dbt_test()
    print(f"dbt test output: {test_output}")
    
    return "Pipeline completed successfully"


if __name__ == "__main__":
    # ローカルテスト実行
    dbt_daily_pipeline()
