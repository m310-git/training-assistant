def validate_weight(weight):
    if weight is None:
        return False, "重量を入力してください"
    if weight < 0 or weight > 500:
        return False, "重量は0〜500kgの範囲で入力してください"
    return True, ""

def validate_reps(reps):
    if reps is None:
        return False, "回数を入力してください"
    if reps < 1 or reps > 100:
        return False, "回数は1〜100の範囲で入力してください"
    return True, ""

def validate_rpe(rpe):
    if rpe is None:
        return True, ""  # 任意項目
    if rpe < 6.0 or rpe > 10.0:
        return False, "RPEは6.0〜10.0の範囲で入力してください"
    return True, ""