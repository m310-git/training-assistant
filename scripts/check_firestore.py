"""
Firestore データ確認スクリプト
手動確認用
"""

import json
from google.cloud import firestore
from google.oauth2 import service_account
import sys

# 認証情報の読み込み（streamlit/secrets.toml から）
# ローカル開発用なので環境変数から読み取る
import os
from dotenv import load_dotenv

load_dotenv()

# secrets.toml の代わりに環境変数または JSON ファイルを使用
# 実際のサービスアカウントキーは .streamlit/secrets.toml にあるため、
# ここでは Streamlit の secrets を模倣した辞書を作成
# 実際には .streamlit/secrets.toml の内容をコピーして使用してください

# 簡易版: 環境変数 GOOGLE_APPLICATION_CREDENTIALS が設定されていればそれを使用
# 設定されていない場合は、手動でキーファイルパスを指定

if __name__ == "__main__":
    # プロジェクトID
    project_id = "training-assistant-prod"
    
    # Firestore クライアント初期化
    # ADC (Application Default Credentials) を使用
    try:
        db = firestore.Client(project=project_id)
    except Exception as e:
        print(f"Firestore クライアント初期化エラー: {e}")
        print("環境変数 GOOGLE_APPLICATION_CREDENTIALS を設定してください")
        sys.exit(1)
    
    # ドキュメント一覧を取得
    collection_ref = db.collection("training_logs")
    docs = collection_ref.get()
    
    print("=== Firestore ドキュメント一覧 ===")
    doc_ids = []
    for doc in docs:
        data = doc.to_dict()
        doc_id = doc.id
        doc_ids.append(doc_id)
        print(f"\nドキュメントID: {doc_id}")
        print(f"  user_id: {data.get('user_id')}")
        print(f"  training_date: {data.get('training_date')}")
        print(f"  exercise_id: {data.get('exercise_id')}")
        print(f"  exercise_name: {data.get('exercise_name')}")
        print(f"  set_count: {data.get('set_count')}")
        print(f"  total_volume: {data.get('total_volume')}")
        print(f"  is_deleted: {data.get('is_deleted')}")
        print(f"  status: {data.get('status')}")
        print(f"  created_at (ドキュメント): {data.get('created_at')}")
        print(f"  updated_at (ドキュメント): {data.get('updated_at')}")
        
        # セット情報を表示
        sets = data.get('sets', [])
        print(f"  セット数: {len(sets)}")
        for i, s in enumerate(sets):  # 全セット表示
            print(f"    セット{i+1}: set_number={s.get('set_number')}, weight={s.get('weight_kg')}, reps={s.get('reps')}, is_deleted={s.get('is_deleted')}, created_at={s.get('created_at')}, updated_at={s.get('updated_at')}")
    
    if not doc_ids:
        print("\nドキュメントが見つかりません")
    else:
        print(f"\n=== 確認したいドキュメントID ===")
        for doc_id in doc_ids:
            print(f"  {doc_id}")
        
        # 全削除オプション
        if len(sys.argv) > 1 and sys.argv[1] == "--delete-all":
            print("\n=== 全削除実行 ===")
            for doc_id in doc_ids:
                doc_ref = db.collection("training_logs").document(doc_id)
                doc_ref.delete()
                print(f"削除: {doc_id}")
            print("全削除完了")
