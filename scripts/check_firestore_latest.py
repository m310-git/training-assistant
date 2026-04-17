#!/usr/bin/env python3
"""Firestore の最新トレーニングログを確認するスクリプト"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from google.cloud import firestore
import json

# Firestore クライアント初期化
fs_client = firestore.Client(project="training-assistant-prod")

# training_logs コレクションを取得
collection_ref = fs_client.collection("training_logs")

# sync_status=pending のドキュメントを確認
pending_docs = collection_ref.where("sync_status", "==", "pending").get()
print(f"=== sync_status=pending のドキュメント: {len(list(pending_docs))}件 ===")
for doc in pending_docs:
    print(f"\nドキュメントID: {doc.id}")
    data = doc.to_dict()
    print(f"  user_id: {data.get('user_id')}")
    print(f"  training_date: {data.get('training_date')}")
    print(f"  exercise_name: {data.get('exercise_name')}")
    print(f"  sync_status: {data.get('sync_status')}")
    print(f"  synced_at: {data.get('synced_at')}")
    print(f"  created_at: {data.get('created_at')}")
    print(f"  updated_at: {data.get('updated_at')}")
    print(f"  sets count: {len(data.get('sets', []))}")
    if data.get('sets'):
        print(f"  sets[0]: {data['sets'][0]}")

# 最新10件を確認
docs = collection_ref.order_by("created_at", direction=firestore.Query.DESCENDING).limit(10).get()
print("\n=== Firestore training_logs 最新10件 ===")
for doc in docs:
    print(f"\nドキュメントID: {doc.id}")
    data = doc.to_dict()
    print(f"  user_id: {data.get('user_id')}")
    print(f"  training_date: {data.get('training_date')}")
    print(f"  exercise_name: {data.get('exercise_name')}")
    print(f"  sync_status: {data.get('sync_status')}")
    print(f"  synced_at: {data.get('synced_at')}")
    print(f"  created_at: {data.get('created_at')}")
    print(f"  updated_at: {data.get('updated_at')}")
    print(f"  sets count: {len(data.get('sets', []))}")
