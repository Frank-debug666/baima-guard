import json
import random
from copy import deepcopy
from collections import Counter
from pathlib import Path

import torch
from torch.utils.data import ConcatDataset, DataLoader, Dataset, random_split

from api_model import SmsRNNClassifier


ROOT = Path(__file__).resolve().parent
DATA_PATH = ROOT / "data" / "sms_samples.tsv"
OUTPUT_PATH = ROOT / "model" / "sms_rnn_api.pt"
MAX_LEN = 160
EPOCHS = 12
BATCH_SIZE = 128
SEED = 42
HARD_NORMAL_SAMPLES = [
    "您的验证码是123456，请勿告诉他人。",
    "登录验证码为458921，五分钟内有效。",
    "您的快递已到达学校驿站，请凭取件码领取。",
    "您的订单已发货，请注意查收。",
    "明天上午十点开会，请准时参加。",
    "会议地点改为三楼会议室。",
    "工资已到账，请注意查收。",
    "您的银行卡消费100元，如有疑问请联系银行客服。",
    "今天晚上一起吃饭吗？",
    "我已经到楼下了，你下来吧。",
    "老师通知明天下午正常上课。",
    "您的预约已成功，请按时到达。",
    "您的缴费已成功，感谢使用。",
    "生日快乐，祝你天天开心。",
    "您的外卖已送达，请及时领取。",
]


def load_samples():
    samples = []
    with DATA_PATH.open(encoding="utf-8") as file:
        for line in file:
            parts = line.rstrip("\n").split("\t", 1)
            if len(parts) == 2 and parts[0] in {"0", "1"}:
                samples.append((parts[1], int(parts[0])))
    return samples


def build_vocab(samples):
    counts = Counter(char for text, _ in samples for char in text)
    vocab = {"<PAD>": 0, "<UNK>": 1}
    for char, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        vocab[char] = len(vocab)
    return vocab


class SmsDataset(Dataset):
    def __init__(self, samples, vocab):
        self.samples = samples
        self.vocab = vocab

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        text, label = self.samples[index]
        ids = [self.vocab.get(char, 1) for char in text[:MAX_LEN]]
        length = max(1, len(ids))
        ids += [0] * (MAX_LEN - len(ids))
        return (
            torch.tensor(ids, dtype=torch.long),
            torch.tensor(length, dtype=torch.long),
            torch.tensor(label, dtype=torch.long),
        )


def evaluate(model, loader):
    model.eval()
    correct = 0
    total = 0
    with torch.no_grad():
        for texts, lengths, labels in loader:
            predictions = model(texts, lengths).argmax(dim=1)
            correct += (predictions == labels).sum().item()
            total += labels.size(0)
    return correct / total


def collect_probabilities(model, loader):
    model.eval()
    probabilities = []
    labels_list = []
    with torch.no_grad():
        for texts, lengths, labels in loader:
            probabilities.extend(torch.softmax(model(texts, lengths), dim=1)[:, 1].tolist())
            labels_list.extend(labels.tolist())
    return probabilities, labels_list


def choose_threshold(probabilities, labels):
    best = None
    for threshold_value in [value / 100 for value in range(50, 96)]:
        tn = fp = fn = tp = 0
        for probability, label in zip(probabilities, labels):
            prediction = int(probability >= threshold_value)
            if label == 0 and prediction == 0:
                tn += 1
            elif label == 0:
                fp += 1
            elif prediction == 0:
                fn += 1
            else:
                tp += 1
        false_positive_rate = fp / (tn + fp) if tn + fp else 0.0
        risk_recall = tp / (tp + fn) if tp + fn else 0.0
        accuracy = (tn + tp) / len(labels)
        candidate = (false_positive_rate <= 0.05, accuracy, risk_recall, threshold_value)
        if best is None or candidate > best[0]:
            best = (candidate, false_positive_rate, accuracy, risk_recall)
    return {
        "risk_threshold": best[0][3],
        "false_positive_rate": best[1],
        "accuracy": best[2],
        "risk_recall": best[3],
    }


def main():
    random.seed(SEED)
    torch.manual_seed(SEED)

    samples = load_samples()
    hard_normal_samples = [(text, 0) for text in HARD_NORMAL_SAMPLES]
    vocab = build_vocab(samples + hard_normal_samples)
    dataset = SmsDataset(samples, vocab)
    train_size = int(len(dataset) * 0.8)
    test_size = len(dataset) - train_size
    generator = torch.Generator().manual_seed(SEED)
    train_set, test_set = random_split(dataset, [train_size, test_size], generator=generator)
    augmented_train_set = ConcatDataset(
        [train_set, SmsDataset(hard_normal_samples * 20, vocab)]
    )
    train_loader = DataLoader(augmented_train_set, batch_size=BATCH_SIZE, shuffle=True)
    test_loader = DataLoader(test_set, batch_size=BATCH_SIZE)

    model = SmsRNNClassifier(len(vocab))
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = torch.nn.CrossEntropyLoss()
    best_accuracy = 0.0
    best_state = None

    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0.0
        for texts, lengths, labels in train_loader:
            outputs = model(texts, lengths)
            loss = loss_fn(outputs, labels)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        test_acc = evaluate(model, test_loader)
        if test_acc > best_accuracy:
            best_accuracy = test_acc
            best_state = deepcopy(model.state_dict())
        print(
            f"epoch={epoch + 1:02d} "
            f"loss={total_loss / len(train_loader):.4f} "
            f"test_acc={test_acc:.4f}"
        )

    model.load_state_dict(best_state)
    probabilities, labels = collect_probabilities(model, test_loader)
    threshold_metrics = choose_threshold(probabilities, labels)
    checkpoint = {
        "model_state": best_state,
        "vocab": vocab,
        "config": {
            "vocab_size": len(vocab),
            "embed_dim": 64,
            "hidden_dim": 64,
            "num_classes": 2,
            "max_len": MAX_LEN,
        },
        "metrics": {
            "test_accuracy": best_accuracy,
            **threshold_metrics,
        },
    }
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    torch.save(checkpoint, OUTPUT_PATH)
    print(json.dumps(checkpoint["metrics"], ensure_ascii=False))
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
