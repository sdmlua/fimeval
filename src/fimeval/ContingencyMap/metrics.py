import numpy as np
import math
import math


# Get all the evaluation metrics
def evaluationmetrics(merged):
    # merged = out_image1 + out_image2
    unique_values, counts = np.unique(merged, return_counts=True)
    class_pixel_counts = dict(zip(unique_values, counts))
    class_pixel_counts
    TN = class_pixel_counts.get(1, 0)
    FP = class_pixel_counts.get(2, 0)
    FN = class_pixel_counts.get(3, 0)
    TP = class_pixel_counts.get(4, 0)
    epsilon = 1e-8
    TPR = TP / (TP + FN + epsilon)
    FNR = FN / (TP + FN + epsilon)
    Acc = (TP + TN) / (TP + TN + FP + FN + epsilon)
    Prec = TP / (TP + FP + epsilon)
    sen = TP / (TP + FN + epsilon)
    F1_score = 2 * (Prec * sen) / (Prec + sen + epsilon)
    CSI = TP / (TP + FN + FP + epsilon)
    POD = TP / (TP + FN + epsilon)
    FPR = FP / (FP + TN + epsilon)
    FAR = FP / (TP + FP + epsilon)
    N = TP + FP + FN + TN
    a = float(TP + FP)
    b = float(TP + FN)
    c = float(TN + FP)
    d = float(TN + FN)

    den_term = a * b * c * d
    den = math.sqrt(den_term) if den_term > 0 else 0.0
    mcc = ((TP * TN) - (FP * FN)) / den if den > 0 else 0.0
    po = Acc
    pe = (
        ((((TP + FP) * (TP + FN)) + ((FN + TN) * (FP + TN))) / (N**2)) if N > 0 else 0.0
    )
    kappa = (po - pe) / (1 - pe) if (1 - pe) != 0 else 0.0

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
        mcc,
        kappa,
        mcc,
        kappa,
        merged,
        FAR,
    )
