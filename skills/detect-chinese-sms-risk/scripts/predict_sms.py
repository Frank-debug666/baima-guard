import argparse
import json
import re
import sys
from pathlib import Path

import torch

from api_model import SmsRNNClassifier


ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = ROOT / "assets" / "sms_rnn_api.pt"

RISK_GROUPS = {
    "money_request": [r"转(?:给|我|账|款)", r"打(?:钱|款)", r"汇(?:钱|款)", r"垫付", r"充值", r"安全账户"],
    "secrecy": [r"只告诉你", r"不要告诉", r"别告诉", r"保密", r"不要报警", r"不能外传"],
    "urgency": [r"速度", r"马上", r"立即", r"赶紧", r"最后机会", r"限时"],
    "impersonation": [r"我是秦始皇", r"公检法", r"公安局", r"老板换号", r"领导换号", r"我是你(?:爸|妈|儿子|女儿)"],
    "lure": [r"中奖", r"大奖", r"高收益", r"返利", r"刷单", r"投资群", r"带你赚钱"],
    "privacy_theft": [r"验证码", r"密码", r"身份证", r"屏幕共享", r"远程协助"],
}


def policy_score(text):
    safety_phrases = [
        "不要向陌生人转账", "不要给陌生人转账", "不要提供验证码",
        "谨防诈骗", "防骗提醒", "反诈提醒", "如非本人操作请联系",
    ]
    suspicious_followups = ["安全账户", "屏幕共享", "远程协助", "点击链接", "转给我", "联系我"]
    if any(phrase in text for phrase in safety_phrases) and not any(term in text for term in suspicious_followups):
        return 0.0, []

    hits = [name for name, patterns in RISK_GROUPS.items() if any(re.search(pattern, text, re.I) for pattern in patterns)]
    hit_set = set(hits)
    manipulation = bool(hit_set & {"secrecy", "urgency", "impersonation"})
    if "money_request" in hit_set and manipulation:
        return 0.98, hits
    if hit_set & {"lure", "privacy_theft"} and manipulation:
        return 0.96, hits
    if "money_request" in hit_set and hit_set & {"lure", "privacy_theft"}:
        return 0.95, hits
    return 0.0, hits


def load_model():
    checkpoint = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    config = checkpoint["config"]
    model = SmsRNNClassifier(
        vocab_size=config["vocab_size"],
        embed_dim=config["embed_dim"],
        hidden_dim=config["hidden_dim"],
        num_classes=config["num_classes"],
    )
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return checkpoint, config, model


def predict(text, checkpoint, config, model):
    vocab = checkpoint["vocab"]
    ids = [vocab.get(char, 1) for char in text[: config["max_len"]]]
    length = max(1, len(ids))
    ids += [0] * (config["max_len"] - len(ids))
    with torch.no_grad():
        model_probability = float(torch.softmax(model(
            torch.tensor([ids], dtype=torch.long),
            torch.tensor([length], dtype=torch.long),
        ), dim=1)[0][1].item())
    policy_probability, evidence = policy_score(text)
    risk_probability = max(model_probability, policy_probability)
    threshold = checkpoint["metrics"].get("risk_threshold", 0.5)
    return {
        "label": "risk" if risk_probability >= threshold else "normal",
        "risk_probability": round(risk_probability, 4),
        "model_probability": round(model_probability, 4),
        "policy_probability": round(policy_probability, 4),
        "risk_threshold": threshold,
        "evidence": evidence,
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze Chinese SMS fraud risk.")
    parser.add_argument("text", nargs="?", help="Message to analyze. Reads stdin when omitted.")
    args = parser.parse_args()
    text = args.text or sys.stdin.read().strip()
    if not text:
        parser.error("message text is required")
    checkpoint, config, model = load_model()
    print(json.dumps(predict(text, checkpoint, config, model), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
