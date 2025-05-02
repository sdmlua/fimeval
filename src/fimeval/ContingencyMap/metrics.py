import numpy as np


# Get all the evaluation metrics
def evaluationmetrics(out_image1, out_image2):
    merged = out_image1 + out_image2
    unique_values, counts = np.unique(merged, return_counts=True)
    class_pixel_counts = dict(zip(unique_values, counts))
    class_pixel_counts
    TN = class_pixel_counts[1]
    FP = class_pixel_counts[2]
    FN = class_pixel_counts[3]
    TP = class_pixel_counts[4]
    TPR = TP / (TP + FN)
    FNR = FN / (TP + FN)
    Acc = (TP + TN) / (TP + TN + FP + FN)
    Prec = TP / (TP + FP)
    sen = TP / (TP + FN)
    F1_score = 2 * (Prec * sen) / (Prec + sen)
    CSI = TP / (TP + FN + FP)
    POD = TP / (TP + FN)
    FPR = FP / (FP + TN)
    FAR = FP / (TP + FP)
    Dice = 2 * TP / (2 * TP + FP + FN)

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
        Dice,
    )
