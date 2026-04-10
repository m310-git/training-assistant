

SELECT * FROM UNNEST([
    STRUCT('chest'    AS body_part_id, '胸'    AS body_part_name, 'Monday'    AS training_day, 1 AS sort_order),
    STRUCT('back'     AS body_part_id, '背中'   AS body_part_name, 'Tuesday'   AS training_day, 2 AS sort_order),
    STRUCT('shoulder' AS body_part_id, '肩'    AS body_part_name, 'Wednesday' AS training_day, 3 AS sort_order),
    STRUCT('leg'      AS body_part_id, '脚'    AS body_part_name, 'Thursday'  AS training_day, 4 AS sort_order),
    STRUCT('arm'      AS body_part_id, '腕'    AS body_part_name, 'Friday'    AS training_day, 5 AS sort_order),
    STRUCT('other'    AS body_part_id, 'その他' AS body_part_name, CAST(NULL AS STRING) AS training_day, 6 AS sort_order)
])