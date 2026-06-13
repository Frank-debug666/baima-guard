import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from threading import Lock

import torch
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from api_model import SmsRNNClassifier


ROOT = Path(__file__).resolve().parent
CHECKPOINT_PATH = ROOT / "model" / "sms_rnn_api.pt"
FEEDBACK_PATH = ROOT / "feedback_store.json"
WEB_PATH = ROOT / "frontend" / "dist"
feedback_lock = Lock()

if not CHECKPOINT_PATH.exists():
    raise RuntimeError("缺少真实推理模型，请先运行 python train_api_model.py")

checkpoint = torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=False)
config = checkpoint["config"]
vocab = checkpoint["vocab"]
model = SmsRNNClassifier(
    vocab_size=config["vocab_size"],
    embed_dim=config["embed_dim"],
    hidden_dim=config["hidden_dim"],
    num_classes=config["num_classes"],
)
model.load_state_dict(checkpoint["model_state"])
model.eval()

app = FastAPI(title="白马卫士短信智能过滤 API")


class SmsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class FeedbackRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    predicted_class: int = Field(ge=0, le=1)
    is_correct: bool


def normalize_text(text: str):
    return re.sub(r"[\W_]+", "", text.lower(), flags=re.UNICODE)


def load_feedback():
    if not FEEDBACK_PATH.exists():
        return []
    try:
        return json.loads(FEEDBACK_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_feedback(records):
    temporary_path = FEEDBACK_PATH.with_suffix(".tmp")
    temporary_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_path.replace(FEEDBACK_PATH)


def feedback_override(text: str):
    normalized = normalize_text(text)
    best_match = None
    for record in load_feedback():
        similarity = SequenceMatcher(None, normalized, record["normalized_text"]).ratio()
        required_similarity = 1.0 if min(len(normalized), len(record["normalized_text"])) < 8 else 0.72
        if similarity >= required_similarity and (best_match is None or similarity > best_match[0]):
            best_match = (similarity, record)
    if not best_match:
        return None
    similarity, record = best_match
    corrected_class = record["corrected_class"]
    probability = 0.99 if corrected_class == 1 else 0.01
    return {
        "class_id": corrected_class,
        "risk_probability": probability,
        "similarity": similarity,
        "evidence": f"已学习用户纠错话术，相似度 {similarity:.0%}",
    }


RISK_GROUPS = {
    "要求转账或提供资金": [
        (r"转(?:给|我|账|款)", "要求转账"), (r"打(?:钱|款)", "要求打款"),
        (r"汇(?:钱|款)", "要求汇款"), (r"借我", "要求借款"),
        (r"垫付", "要求垫付"), (r"代付", "要求代付"), (r"付款", "要求付款"),
        (r"交(?:钱|费|保证金)", "要求交费"), (r"银行卡", "涉及银行卡"),
        (r"收款码", "要求收款码"), (r"安全账户", "要求转入安全账户"),
        (r"充值", "要求充值"), (r"红包", "涉及红包资金"),
    ],
    "要求保密或制造信息差": [
        (r"只告诉你", "只告诉你"), (r"不要告诉", "要求不要告诉他人"),
        (r"别告诉", "要求别告诉他人"), (r"不要声张", "要求不要声张"),
        (r"保密", "要求保密"), (r"内部消息", "声称内部消息"),
        (r"只有你知道", "声称只有你知道"), (r"私下处理", "要求私下处理"),
        (r"不要报警", "阻止报警"), (r"不能外传", "要求不能外传"),
    ],
    "催促立即行动": [
        (r"速度", "催促速度处理"), (r"马上", "要求马上处理"),
        (r"立即", "要求立即处理"), (r"赶紧", "催促赶紧处理"),
        (r"尽快", "要求尽快处理"), (r"现在就", "要求现在处理"),
        (r"错过", "制造错过焦虑"), (r"最后机会", "制造最后机会焦虑"),
        (r"限时", "制造限时压力"), (r"逾期", "制造逾期压力"),
    ],
    "异常身份或权威包装": [
        (r"我是秦始皇", "冒充秦始皇"), (r"我是皇帝", "冒充皇帝"),
        (r"重铸大秦", "异常身份话术"), (r"公检法", "冒充公检法"),
        (r"公安局", "冒充公安机关"), (r"法院", "冒充法院"),
        (r"检察院", "冒充检察院"), (r"领导换号", "冒充领导换号"),
        (r"老板换号", "冒充老板换号"), (r"熟人换号", "冒充熟人换号"),
        (r"客服专员", "冒充客服"), (r"班主任换号", "冒充老师换号"),
        (r"我是你(?:爸|妈|儿子|女儿)", "冒充亲属"),
    ],
    "中奖或高收益诱导": [
        (r"中奖", "声称中奖"), (r"大奖", "声称获得大奖"),
        (r"稳赚", "承诺稳赚"), (r"高收益", "承诺高收益"),
        (r"返利", "返利诱导"), (r"带你赚钱", "赚钱诱导"),
        (r"免费领取", "免费领取诱导"), (r"点击链接", "诱导点击链接"),
        (r"刷单", "刷单返利"), (r"内幕股", "股票内幕诱导"),
        (r"投资群", "投资群诱导"), (r"日赚", "高收益日赚诱导"),
    ],
    "账户或隐私窃取": [
        (r"验证码", "索要验证码"), (r"密码", "索要密码"),
        (r"身份证", "索要身份证信息"), (r"账户异常", "声称账户异常"),
        (r"涉嫌洗钱", "以涉嫌洗钱恐吓"), (r"关闭(?:花呗|借呗|账户)", "诱导关闭账户"),
        (r"屏幕共享", "要求屏幕共享"), (r"远程协助", "要求远程控制"),
    ],
}


def analyze_risk_policy(text: str):
    safety_phrases = [
        "不要向陌生人转账", "不要给陌生人转账", "不要提供验证码",
        "切勿提供验证码", "谨防诈骗", "防骗提醒", "反诈提醒",
        "请勿相信陌生链接", "如非本人操作请联系",
    ]
    suspicious_followups = ["安全账户", "屏幕共享", "远程协助", "点击链接", "转给我", "联系我"]
    if any(phrase in text for phrase in safety_phrases) and not any(term in text for term in suspicious_followups):
        return 0.0, [], ""

    hits = []
    for group, patterns in RISK_GROUPS.items():
        matched = next((label for pattern, label in patterns if re.search(pattern, text, re.I)), None)
        if matched:
            hits.append((group, matched))

    groups = {group for group, _ in hits}
    money = "要求转账或提供资金" in groups
    manipulation = bool(groups & {"要求保密或制造信息差", "催促立即行动", "异常身份或权威包装"})
    lure = "中奖或高收益诱导" in groups
    privacy = "账户或隐私窃取" in groups

    if money and manipulation:
        return 0.98, [f"{group}：{term}" for group, term in hits], "组合诈骗话术"
    if (lure or privacy) and manipulation:
        return 0.96, [f"{group}：{term}" for group, term in hits], "诱导诈骗话术"
    if money and (lure or privacy):
        return 0.95, [f"{group}：{term}" for group, term in hits], "资金诈骗话术"
    if len(groups) >= 3:
        return 0.92, [f"{group}：{term}" for group, term in hits], "多重风险话术"
    return 0.0, [], ""


def model_probability(text: str):
    ids = [vocab.get(char, 1) for char in text[: config["max_len"]]]
    length = max(1, len(ids))
    ids += [0] * (config["max_len"] - len(ids))
    texts = torch.tensor([ids], dtype=torch.long)
    lengths = torch.tensor([length], dtype=torch.long)
    with torch.no_grad():
        return float(torch.softmax(model(texts, lengths), dim=1)[0][1].item())


def build_explanation(text, probability, class_id, policy_evidence, policy_category, learned_evidence):
    risk_terms = ["中奖", "点击", "链接", "转账", "汇款", "账户异常", "验证码", "领取", "免费", "贷款"]
    normal_terms = ["会议", "通知", "快递", "签收", "上课", "生日", "天气", "提醒", "到账"]
    hits = [term for term in risk_terms if term in text]
    normal_hits = [term for term in normal_terms if term in text]

    if class_id == 1:
        category = "反馈学习话术" if learned_evidence else policy_category or ("诈骗诱导" if hits else "营销骚扰")
        evidence = [learned_evidence] if learned_evidence else []
        evidence.extend(f"风险策略识别：{item}" for item in policy_evidence[:3])
        evidence.extend(f"发现敏感表达：{term}" for term in hits[:2])
        if not evidence:
            evidence.append("文本组合特征与风险短信样本相似")
        action = "建议拦截并向用户提示风险"
    else:
        category = "反馈纠正正常话术" if learned_evidence else "正常通知" if normal_hits else "日常信息"
        evidence = [learned_evidence] if learned_evidence else [f"发现日常场景表达：{term}" for term in normal_hits[:2]]
        if not evidence:
            evidence.append("未发现明显诱导、转账或异常链接特征")
        action = "建议正常放行，保留用户反馈入口"

    level = "高风险" if probability >= 0.9 else "需关注" if probability >= 0.55 else "低风险"
    return level, category, evidence[:4], action


@app.get("/api/health")
def health():
    feedback = load_feedback()
    return {
        "status": "ok",
        "model": "SmsRNNClassifier + RiskPolicy + FeedbackLearning",
        "test_accuracy": checkpoint["metrics"]["test_accuracy"],
        "risk_threshold": checkpoint["metrics"]["risk_threshold"],
        "false_positive_rate": checkpoint["metrics"]["false_positive_rate"],
        "risk_recall": checkpoint["metrics"]["risk_recall"],
        "feedback_count": len(feedback),
        "learned_risk_count": sum(record["corrected_class"] == 1 for record in feedback),
        "learned_normal_count": sum(record["corrected_class"] == 0 for record in feedback),
    }


@app.post("/api/feedback")
def submit_feedback(request: FeedbackRequest):
    corrected_class = request.predicted_class if request.is_correct else 1 - request.predicted_class
    normalized = normalize_text(request.text)
    record = {
        "text": request.text.strip(),
        "normalized_text": normalized,
        "predicted_class": request.predicted_class,
        "corrected_class": corrected_class,
        "is_correct": request.is_correct,
    }
    with feedback_lock:
        records = [item for item in load_feedback() if item["normalized_text"] != normalized]
        records.append(record)
        save_feedback(records[-500:])
    return {
        "status": "saved",
        "feedback_count": len(records[-500:]),
        "corrected_class": corrected_class,
        "message": "反馈已保存，后续相同或相似话术将使用纠正结果。",
    }


@app.post("/api/predict")
def predict(request: SmsRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="短信内容不能为空")

    raw_model_probability = model_probability(text)
    policy_probability, policy_evidence, policy_category = analyze_risk_policy(text)
    learned = feedback_override(text)
    risk_threshold = checkpoint["metrics"].get("risk_threshold", 0.5)

    if learned:
        risk_probability = learned["risk_probability"]
        class_id = learned["class_id"]
        learned_evidence = learned["evidence"]
    else:
        risk_probability = max(raw_model_probability, policy_probability)
        class_id = int(risk_probability >= risk_threshold)
        learned_evidence = ""

    risk_level, category, evidence, action = build_explanation(
        text, risk_probability, class_id, policy_evidence, policy_category, learned_evidence
    )
    return {
        "class_id": class_id,
        "label": "风险短信" if class_id == 1 else "正常短信",
        "risk_probability": risk_probability,
        "model_probability": raw_model_probability,
        "policy_probability": policy_probability,
        "feedback_learned": bool(learned),
        "confidence": risk_probability if class_id == 1 else 1 - risk_probability,
        "risk_threshold": risk_threshold,
        "risk_level": risk_level,
        "category": category,
        "evidence": evidence,
        "suggested_action": action,
        "reason": "真实 RNN 模型、扩展风险策略与持久化反馈学习共同完成判断。",
    }


if WEB_PATH.exists():
    app.mount("/", StaticFiles(directory=WEB_PATH, html=True), name="web")
