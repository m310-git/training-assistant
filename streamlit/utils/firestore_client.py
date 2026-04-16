"""
Firestore クライアントユーティリティ

Input画面のトレーニングログ保存・復元・削除を担当する。
Firestore SDK へのアクセスはこのファイルに閉じ込める。
"""

import uuid
from datetime import datetime, timedelta, timezone
from google.cloud import firestore
from google.oauth2 import service_account
import streamlit as st

# --- コレクション名 ---
COLLECTION_NAME = "training_logs"


@st.cache_resource
def get_firestore_client():
    """Firestore クライアントを初期化して返す（キャッシュ付き）"""
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"]
    )
    return firestore.Client(
        credentials=credentials,
        project="training-assistant-prod"
    )


def build_training_doc_id(user_id: str, training_date: str, exercise_id: str) -> str:
    """
    ドキュメントIDを生成する
    形式: {user_id}_{training_date}_{exercise_id}
    """
    return f"{user_id}_{training_date}_{exercise_id}"


def get_training_log(user_id: str, training_date: str, exercise_id: str) -> dict | None:
    """
    指定ユーザー・日付・種目のトレーニングログを取得する
    論理削除されていないドキュメントのみ返す
    """
    try:
        db = get_firestore_client()
        doc_id = build_training_doc_id(user_id, training_date, exercise_id)
        doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
        doc = doc_ref.get()

        if doc.exists:
            data = doc.to_dict()
            # 論理削除済みなら None を返す
            if data.get("is_deleted", False):
                return None
            return data
        return None
    except Exception as e:
        st.error(f"Firestore 取得エラー: {e}")
        return None


def save_training_log(
    user_id: str,
    user_name: str,
    training_date: str,
    body_part_id: str,
    body_part_name: str,
    exercise_id: str,
    exercise_name: str,
    sets: list[dict],
) -> bool:
    """
    トレーニングログを保存する（新規 or 更新）

    sets の各要素は以下を含む:
    - set_id: str (UUIDv4)
    - set_number: int
    - weight_kg: float
    - reps: int
    - rpe: float | None
    - memo: str
    - is_deleted: bool
    - created_at: str (ISO8601)
    - updated_at: str (ISO8601)
    """
    try:
        db = get_firestore_client()
        doc_id = build_training_doc_id(user_id, training_date, exercise_id)
        doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
        now = datetime.now(timezone.utc).isoformat()

        # 有効セットのみで集計
        active_sets = [s for s in sets if not s.get("is_deleted", False)]
        set_count = len(active_sets)
        total_volume = sum(
            s.get("weight_kg", 0) * s.get("reps", 0) for s in active_sets
        )

        # 既存ドキュメントを確認
        existing_doc = doc_ref.get()

        if existing_doc.exists:
            existing_data = existing_doc.to_dict()
            # 更新時: created_at, editable_until は変更しない
            # 既存セットは set_id をキーに created_at を維持
            existing_sets_map = {
                s.get("set_id"): s.get("created_at")
                for s in existing_data.get("sets", [])
                if s.get("set_id")
            }
            # sets 配列を更新: 既存セットは created_at を維持、新規セットは now
            updated_sets = []
            for s in sets:
                set_id = s.get("set_id")
                if set_id and set_id in existing_sets_map:
                    # 既存セット: created_at を維持
                    s["created_at"] = existing_sets_map[set_id]
                elif not s.get("created_at"):
                    # 新規セットまたは created_at がない場合
                    s["created_at"] = now
                s["updated_at"] = now
                updated_sets.append(s)

            doc_ref.update({
                "sets": updated_sets,
                "set_count": set_count,
                "total_volume": round(total_volume, 1),
                "updated_at": now,
                "last_edited_at": now,
                "sync_status": "pending",
                "synced_at": None,
                "sync_version": existing_data.get("sync_version", 0) + 1,
            })
        else:
            # 新規作成: created_at 固定、editable_until = created_at + 3時間
            editable_until = (
                datetime.now(timezone.utc) + timedelta(hours=3)
            ).isoformat()
            
            # 新規作成時は sets[].created_at を設定
            updated_sets = []
            for s in sets:
                s_copy = s.copy()
                if not s_copy.get("created_at"):
                    s_copy["created_at"] = now
                if not s_copy.get("updated_at"):
                    s_copy["updated_at"] = now
                updated_sets.append(s_copy)

            doc_data = {
                "doc_id": doc_id,
                "user_id": user_id,
                "user_name": user_name,
                "training_date": training_date,
                "body_part_id": body_part_id,
                "body_part_name": body_part_name,
                "exercise_id": exercise_id,
                "exercise_name": exercise_name,
                "input_source": "streamlit",
                "status": "active",
                "is_deleted": False,
                "sets": updated_sets,
                "set_count": set_count,
                "total_volume": round(total_volume, 1),
                "created_at": now,
                "updated_at": now,
                "last_edited_at": now,
                "editable_until": editable_until,
                "sync_status": "pending",
                "synced_at": None,
                "sync_version": 1,
                "schema_version": 1,
            }
            doc_ref.set(doc_data)

        return True
    except Exception as e:
        st.error(f"Firestore 保存エラー: {e}")
        return False


def soft_delete_set(
    user_id: str,
    training_date: str,
    exercise_id: str,
    set_id: str,
) -> bool:
    """
    指定セットを論理削除する
    sets 配列内の該当 set_id の is_deleted を True にする
    """
    try:
        db = get_firestore_client()
        doc_id = build_training_doc_id(user_id, training_date, exercise_id)
        doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
        doc = doc_ref.get()

        if not doc.exists:
            return False

        data = doc.to_dict()
        sets = data.get("sets", [])
        now = datetime.now(timezone.utc).isoformat()

        updated = False
        for s in sets:
            if s.get("set_id") == set_id:
                s["is_deleted"] = True
                s["updated_at"] = now
                updated = True
                break

        if not updated:
            return False

        # 有効セットで再集計
        active_sets = [s for s in sets if not s.get("is_deleted", False)]
        set_count = len(active_sets)
        total_volume = sum(
            s.get("weight_kg", 0) * s.get("reps", 0) for s in active_sets
        )

        doc_ref.update({
            "sets": sets,
            "set_count": set_count,
            "total_volume": round(total_volume, 1),
            "updated_at": now,
            "last_edited_at": now,
            "sync_status": "pending",
            "synced_at": None,
            "sync_version": data.get("sync_version", 0) + 1,
        })
        return True
    except Exception as e:
        st.error(f"Firestore セット削除エラー: {e}")
        return False


def soft_delete_training_log(
    user_id: str,
    training_date: str,
    exercise_id: str,
) -> bool:
    """
    ドキュメント全体を論理削除する
    """
    try:
        db = get_firestore_client()
        doc_id = build_training_doc_id(user_id, training_date, exercise_id)
        doc_ref = db.collection(COLLECTION_NAME).document(doc_id)
        doc = doc_ref.get()

        if not doc.exists:
            return False

        data = doc.to_dict()
        now = datetime.now(timezone.utc).isoformat()

        doc_ref.update({
            "status": "deleted",
            "is_deleted": True,
            "updated_at": now,
            "last_edited_at": now,
            "sync_status": "pending",
            "synced_at": None,
            "sync_version": data.get("sync_version", 0) + 1,
        })
        return True
    except Exception as e:
        st.error(f"Firestore 全削除エラー: {e}")
        return False
