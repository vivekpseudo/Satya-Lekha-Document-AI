from app.classifier import classify_document


def evaluate_texts(rows: list[dict]) -> dict:
    total = len(rows)
    correct = 0
    per_class = {}

    for row in rows:
        predicted = classify_document(row["text"]).document_type
        expected = row["label"]
        bucket = per_class.setdefault(expected, {"total": 0, "correct": 0})
        bucket["total"] += 1
        if predicted == expected:
            correct += 1
            bucket["correct"] += 1

    accuracy = correct / total if total else 0.0
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(accuracy, 4),
        "per_class": {
            label: {
                **metrics,
                "recall": round(
                    metrics["correct"] / metrics["total"], 4
                ) if metrics["total"] else 0.0,
            }
            for label, metrics in per_class.items()
        },
    }
