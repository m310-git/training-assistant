-- ============================================================
-- ユーザーマスタ（3名分）
-- ※ line_user_id は後でLINEの実際のIDに差し替え
-- ============================================================
INSERT INTO raw.user_master VALUES
    ('user_001', 'ユーザー1', 'U_LINE_ID_001', TRUE, CURRENT_TIMESTAMP()),
    ('user_002', 'ユーザー2', 'U_LINE_ID_002', TRUE, CURRENT_TIMESTAMP()),
    ('user_003', 'ユーザー3', 'U_LINE_ID_003', TRUE, CURRENT_TIMESTAMP());

-- ============================================================
-- 種目マスタ（15種目）
-- 5部位 × 3種目ずつ
-- ============================================================
INSERT INTO raw.exercise_master VALUES
    -- 胸
    ('bench_press',       'ベンチプレス',             'chest',    TRUE,  TRUE, 1, CURRENT_TIMESTAMP()),
    ('incline_db_press',  'インクラインDBプレス',       'chest',    FALSE, TRUE, 2, CURRENT_TIMESTAMP()),
    ('cable_fly',         'ケーブルフライ',            'chest',    FALSE, TRUE, 3, CURRENT_TIMESTAMP()),
    -- 背中
    ('deadlift',          'デッドリフト',              'back',     TRUE,  TRUE, 1, CURRENT_TIMESTAMP()),
    ('lat_pulldown',      'ラットプルダウン',           'back',     FALSE, TRUE, 2, CURRENT_TIMESTAMP()),
    ('seated_row',        'シーテッドロウ',            'back',     FALSE, TRUE, 3, CURRENT_TIMESTAMP()),
    -- 肩
    ('overhead_press',    'オーバーヘッドプレス',       'shoulder', TRUE,  TRUE, 1, CURRENT_TIMESTAMP()),
    ('side_raise',        'サイドレイズ',              'shoulder', FALSE, TRUE, 2, CURRENT_TIMESTAMP()),
    ('face_pull',         'フェイスプル',              'shoulder', FALSE, TRUE, 3, CURRENT_TIMESTAMP()),
    -- 脚
    ('squat',             'スクワット',                'leg',      TRUE,  TRUE, 1, CURRENT_TIMESTAMP()),
    ('leg_press',         'レッグプレス',              'leg',      FALSE, TRUE, 2, CURRENT_TIMESTAMP()),
    ('leg_curl',          'レッグカール',              'leg',      FALSE, TRUE, 3, CURRENT_TIMESTAMP()),
    -- 腕
    ('barbell_curl',      'バーベルカール',            'arm',      FALSE, TRUE, 1, CURRENT_TIMESTAMP()),
    ('triceps_pushdown',  'トライセプスプッシュダウン',  'arm',      FALSE, TRUE, 2, CURRENT_TIMESTAMP()),
    ('hammer_curl',       'ハンマーカール',            'arm',      FALSE, TRUE, 3, CURRENT_TIMESTAMP());
