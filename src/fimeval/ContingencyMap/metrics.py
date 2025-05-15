import numpy as np


# Get all the evaluation metrics
def evaluationmetrics(out_image1, out_image2):
    merged = out_image1 + out_image2
    unique_values, counts = np.unique(merged, return_counts=True)
    class_pixel_counts = dict(zip(unique_values, counts))
    class_pixel_counts
    TN = class_pixel_counts.get(1,0)
    FP = class_pixel_counts.get(2,0)
    FN = class_pixel_counts.get(3,0)
    TP = class_pixel_counts.get(4,0)
    epsilon = 1e-8
    TPR = TP / (TP + FN+epsilon)
    FNR = FN / (TP + FN+epsilon)
    Acc = (TP + TN) / (TP + TN + FP + FN+epsilon)
    Prec = TP / (TP + FP+epsilon)
    sen = TP / (TP + FN+epsilon)
    F1_score = 2 * (Prec * sen) / (Prec + sen+epsilon)
    CSI = TP / (TP + FN + FP+epsilon)
    POD = TP / (TP + FN+epsilon)
    FPR = FP / (FP + TN+epsilon)
    FAR = FP / (TP + FP+epsilon)

    return (
        unique_values,
        TN,
        FP,
        FN,
        TP,
        TPR,
        FNR,
        Acc,
        Prec,
        sen,
        CSI,
        F1_score,
        POD,
        FPR,
        merged,
        FAR,
    )
